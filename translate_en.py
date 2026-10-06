"""
英語版のための機械翻訳(DeepL API)。

動画タイトル・大会のメモ・照合の根拠を日本語→英語に訳し、translations_en.json に保存する。
一度訳した文は保存してあるので、毎日の自動更新では新しく増えた文だけを訳す。

    DEEPL_API_KEY=xxxx python translate_en.py   (update_site.py から自動で呼ばれる)

- キー(GitHub の Secrets の DEEPL_API_KEY)が無いときは何もしない。サイトの更新は止めない
- 無料プランの上限(月50万文字)を超えないよう、1回に訳す文字数に上限を設ける(残りは翌日に回す)
- 元の日本語は書き換えない。英語版のページで、元の日本語の下に「auto-translated」として添える
- 新しく訳した文は、選手の名前の読み間違いを name_check.py で直す(players.csv の読みが確かな選手だけ)。
  直せなかった誤訳の疑いは、レポートの name_suspects(件数)と name_suspect_examples(例)に出す
"""
import json
import os
import re
import sys
import time

CACHE = "translations_en.json"
MAX_CHARS_PER_RUN = 200_000      # 1回の実行で訳す文字数の上限(無料枠は月50万文字)
BATCH = 40                       # 1回の送信でまとめて訳す文の数


def needed_texts(data):
    """訳す必要がある日本語の文の一覧"""
    jp = re.compile(r"[぀-ヿ一-鿿]")
    out = []
    for v in data.get("videos", []):
        out.append(v.get("t"))
        out.append(v.get("b"))
    for ch in data.get("tech", {}).get("channels", []):
        for v in ch.get("videos", []):
            out.append(v.get("t"))
    for ev in data.get("events", []):
        out.extend(ev.get("notes") or [])
        out.extend(x.get("source_text") for x in ev.get("schedule_history") or [])
    seen, uniq = set(), []
    for t in out:
        t = (t or "").strip()
        if t and jp.search(t) and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq


def load_cache(root):
    try:
        with open(os.path.join(root, CACHE), encoding="utf-8") as f:
            return json.load(f).get("texts", {})
    except (OSError, ValueError):
        return {}


def save_cache(root, texts):
    with open(os.path.join(root, CACHE), "w", encoding="utf-8") as f:
        json.dump({"about": "英語版の機械翻訳(DeepL)。自動生成。キーは元の日本語、値は英訳。英訳を手で直した場合、元の日本語が変わらない限りそのまま使われる",
                   "texts": dict(sorted(texts.items()))}, f, ensure_ascii=False, indent=0)


def deepl(texts, key, post=None):
    """DeepL で訳す。post はテスト用に差し替えられる"""
    import requests
    post = post or requests.post
    url = "https://api-free.deepl.com/v2/translate" if key.endswith(":fx") else "https://api.deepl.com/v2/translate"
    for attempt in range(3):
        r = post(url, headers={"Authorization": f"DeepL-Auth-Key {key}"},
                 data={"text": texts, "source_lang": "JA", "target_lang": "EN-US"}, timeout=60)
        if r.status_code == 200:
            return [t["text"] for t in r.json()["translations"]]
        if r.status_code in (429, 500, 502, 503, 504):
            time.sleep(5 * (attempt + 1))
            continue
        raise RuntimeError(f"DeepL エラー {r.status_code}: " + {
            403: "キーが正しくありません(GitHub の Secrets の DEEPL_API_KEY を確認してください)",
            456: "今月の無料枠(50万文字)を使い切りました。来月まで新しい翻訳は止まります",
        }.get(r.status_code, r.text[:200]))
    raise RuntimeError("DeepL に接続できませんでした(時間をおいて自動で再試行されます)")


def check_names(root, cache, report):
    """誤訳の疑い(選手の氏名があるのに、訳に正しい英語名が無いもの)を数えてレポートに入れる"""
    try:
        import name_check
        sus = name_check.suspects(cache, name_check.load_names(root))
        report["name_suspects"] = len(sus)
        report["name_suspect_examples"] = [{"ja": ja, "en": en, "expected": right} for ja, en, right in sus[:20]]
        if sus:
            print(f"[翻訳] 選手名の誤訳の疑い {len(sus)} 件(build_report.json の translation.name_suspect_examples)")
    except Exception as ex:  # 名前の確認に失敗しても、翻訳とサイトの更新は止めない
        report["name_check_error"] = str(ex)


def run(root=".", key=None, post=None):
    key = key if key is not None else os.environ.get("DEEPL_API_KEY", "").strip()
    with open(os.path.join(root, "data.json"), encoding="utf-8") as f:
        data = json.load(f)
    need = needed_texts(data)
    cache = load_cache(root)
    # 今は使われていない文は消す(ファイルを小さく保つ)
    cache = {k: v for k, v in cache.items() if k in set(need)}
    todo = [t for t in need if t not in cache]
    report = {"total": len(need), "translated": len(need) - len(todo), "new": 0, "pending": len(todo), "chars_used": 0, "error": "", "name_fixed": 0}
    if not todo:
        save_cache(root, cache)
        check_names(root, cache, report)
        return report
    if not key:
        print(f"[翻訳] DEEPL_API_KEY が無いため、未翻訳の {len(todo)} 件はそのまま(英語版では日本語のみ表示)")
        save_cache(root, cache)
        check_names(root, cache, report)
        return report
    try:
        import name_check
        names = name_check.load_names(root)
    except Exception:
        name_check, names = None, []
    used = 0
    try:
        for i in range(0, len(todo), BATCH):
            chunk = todo[i:i + BATCH]
            size = sum(len(t) for t in chunk)
            if used + size > MAX_CHARS_PER_RUN:
                print(f"[翻訳] 1回の上限({MAX_CHARS_PER_RUN:,}文字)に達したため、残りは次回に訳します")
                break
            for ja, en in zip(chunk, deepl(chunk, key, post)):
                if names:  # 選手の名前の読み間違いを直す
                    en, fixes = name_check.fix_text(ja, en, names)
                    report["name_fixed"] += len(fixes)
                cache[ja] = en
            used += size
            report["new"] += len(chunk)
    except RuntimeError as ex:
        report["error"] = str(ex)
        print(f"[翻訳] {ex}")
    save_cache(root, cache)
    report["translated"] = len(need) - len([t for t in need if t not in cache])
    report["pending"] = report["total"] - report["translated"]
    report["chars_used"] = used
    print(f"[翻訳] 新しく {report['new']} 件を訳しました({used:,}文字)。選手名を {report['name_fixed']} か所直しました。未翻訳 {report['pending']} 件")
    check_names(root, cache, report)
    return report


if __name__ == "__main__":
    r = run(".")
    sys.exit(0)
