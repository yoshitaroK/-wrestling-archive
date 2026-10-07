"""
UWW(世界レスリング連合)の YouTube から、日本人選手が出ている動画の一覧を作る(Issue #93)。

    YOUTUBE_API_KEY=... python3 _work/uww/uww_videos.py [--channel @ハンドル または UC…]
    python3 _work/uww/uww_videos.py --sample sample.json   (YouTube につながない確認用)

- 一覧を作るだけ。サイトのページ・data.json には何もしない
- チャンネルの動画を「アップロードの一覧」と「全部の再生リスト」の両方から取る
  (YouTube API はアップロードの一覧を新しい順に 20,000本までしか返さないため。古い動画は再生リストから拾う。
   再生リストの名前は、タイトルに大会名が無い動画の大会・年代を決めるのにも使う)
- 取った動画を、タイトル・説明の JPN / Japan と、players.csv のローマ字の名前で見分ける
  (名前が合っても、すぐ後ろに JPN 以外の国名があれば、同じローマ字の外国人選手として外す)
- 大会を丸ごと流す長時間の配信(45分以上)は外す
- 「日本人選手」の列は、players.csv で 公開=はい、かつ 未成年=いいえ の人だけ書く(サイトの決まりと同じ)
- 結果: _work/uww/uww_japan_videos.csv と _work/uww/summary.md
- UWW のチャンネルは動画が7万本以上あり、1日に使える API の量では1回で読みきれないことがある。
  そのため、どこまで読んだかを _work/uww/state.json に保存し、次に動かしたときは続きから読む
  (ワークフローが uww-list ブランチから state.json を取ってくる)。全部読み終えると summary.md に「完了」と出る
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
API = "https://www.googleapis.com/youtube/v3/"
# UWW の本体のチャンネル。見つけたチャンネル名がこれでなければ止める(違うチャンネルを読まないように)
CHANNEL_TITLE = "United World Wrestling"
CHANNEL_HANDLES = ["@UnitedWorldWrestling", "@wrestling", "@uww"]
LONG_MIN = 45
# YouTube API の1日の上限は 10,000回分。毎朝の更新(同じキーを使う。1日100回ほど)のぶんを残すため、
# 1回に使うのはこの回数まで。残りは次に動かしたときに続きから読む
CALL_LIMIT = 6000
calls = 0
STATE = os.path.join(HERE, "state.json")


class OutOfQuota(Exception):
    pass

COLS = ["動画ID", "タイトル", "公開日", "長さ", "種類", "年代", "大会", "年", "見分けた理由", "確かさ", "日本人選手", "再生リスト", "URL"]


def api(path, **params):
    """つながらないときや YouTube 側のエラー(5xx)は、待ってからやり直す。1日の上限に達したら OutOfQuota"""
    global calls
    if calls >= CALL_LIMIT:
        raise OutOfQuota()
    calls += 1
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    url = API + path + "?" + urllib.parse.urlencode(params)
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            if e.code == 403 and "quota" in body.lower():
                raise OutOfQuota()
            if e.code == 404:
                return {}  # 消された再生リストなど
            if e.code < 500 or attempt == 5:
                raise
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
            if attempt == 5:
                raise
        wait = 2 ** attempt
        print(f"つながらなかったので {wait}秒待ってやり直します({path})")
        time.sleep(wait)


def find_channel(want):
    tries = [want] if want else CHANNEL_HANDLES
    for h in tries:
        q = {"id": h} if h.startswith("UC") else {"forHandle": h}
        items = api("channels", part="snippet,contentDetails,statistics", **q).get("items") or []
        for c in items:
            print(f"チャンネル候補: {c['snippet']['title']}({c['id']}・動画 {c['statistics'].get('videoCount')}本)")
            if want or c["snippet"]["title"].strip().lower() == CHANNEL_TITLE.lower():
                return c
    sys.exit(f"{CHANNEL_TITLE} のチャンネルが見つかりませんでした。--channel に UC で始まるIDを入れて動かしてください")


def pages(path, **params):
    token = None
    while True:
        r = api(path, maxResults=50, **params, **({"pageToken": token} if token else {}))
        yield from r.get("items", [])
        token = r.get("nextPageToken")
        if not token:
            return


def load_state():
    try:
        with open(STATE, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_state(st):
    with open(STATE, "w", encoding="utf-8") as f:
        json.dump(st, f, ensure_ascii=False, separators=(",", ":"))


def is_candidate(title, description, players):
    """日本人選手が出ているかもしれない動画か(詳しい分け方は classify でする)"""
    return bool(JP_TITLE.search(title) or JP_DESC.search(description) or names_in(title, players))


def fetch(channel, players):
    """前回の続きから読む。読んだところまでを state に入れて返す(上限に達したら途中で止める)"""
    ch = find_channel(channel)
    print(f"読むチャンネル: {ch['snippet']['title']}({ch['id']})")
    st = load_state()
    if st.get("channel") != ch["id"]:
        st = {"channel": ch["id"]}
    st.setdefault("checked", [])           # videos で詳しい情報を取った動画ID
    st.setdefault("queue", [])             # 見つけたが、まだ詳しい情報を取っていない動画ID
    st.setdefault("done_playlists", [])    # 読み終えた再生リスト
    st.setdefault("candidates", {})        # 日本人選手が出ているかもしれない動画
    st.setdefault("vid_lists", {})         # 動画ID → 入っている再生リストのID(候補とまだ調べていない動画のぶんだけ)
    st.setdefault("oldest_upload", "")
    checked, queued = set(st["checked"]), set(st["queue"])

    def add(vid):
        if vid not in checked and vid not in queued:
            queued.add(vid)
            st["queue"].append(vid)

    try:
        if not st.get("uploads_done"):
            uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
            for i in pages("playlistItems", part="contentDetails", playlistId=uploads):
                add(i["contentDetails"]["videoId"])
                d = i["contentDetails"].get("videoPublishedAt", "")[:10]
                if d and (not st["oldest_upload"] or d < st["oldest_upload"]):
                    st["oldest_upload"] = d
            st["uploads_done"] = True
            print(f"アップロードの一覧: {len(st['queue'])}本(YouTube API は新しい順に 20,000本まで)")
        if "playlists" not in st:
            st["playlists"] = {pl["id"]: pl["snippet"]["title"] for pl in pages("playlists", part="snippet", channelId=ch["id"])}
            print(f"再生リスト: {len(st['playlists'])}個")
        done = set(st["done_playlists"])
        for pid in st["playlists"]:
            if pid in done:
                continue
            for i in pages("playlistItems", part="contentDetails", playlistId=pid):
                vid = i["contentDetails"]["videoId"]
                if vid not in checked or vid in st["candidates"]:
                    st["vid_lists"].setdefault(vid, [])
                    if pid not in st["vid_lists"][vid]:
                        st["vid_lists"][vid].append(pid)
                add(vid)
            st["done_playlists"].append(pid)
            done.add(pid)
        while st["queue"]:
            batch = st["queue"][:50]
            r = api("videos", part="snippet,contentDetails", id=",".join(batch))
            for v in r.get("items", []):
                if v["snippet"].get("channelId") != ch["id"]:
                    continue  # 再生リストに入っているほかのチャンネルの動画は外す
                t, d = v["snippet"]["title"], v["snippet"].get("description", "")
                if is_candidate(t, d, players):
                    st["candidates"][v["id"]] = {"title": t, "description": "JPN" if JP_DESC.search(d) else "",
                                                 "published": v["snippet"]["publishedAt"], "duration": v["contentDetails"].get("duration", "")}
            for vid in batch:
                checked.add(vid)
                st["checked"].append(vid)
                if vid not in st["candidates"]:
                    st["vid_lists"].pop(vid, None)
            del st["queue"][:len(batch)]
            queued.difference_update(batch)
        st["complete"] = True
    except OutOfQuota:
        st["complete"] = False
        print(f"API の1回分の上限({CALL_LIMIT}回)または1日の上限に達したので、ここまでを保存して止めます。続きは次に動かしたときに読みます")
    except (urllib.error.URLError, OSError) as e:
        # 何度やり直してもつながらなかったとき。ここまで読んだ分は保存して、次に続きから読む
        st["complete"] = False
        print(f"YouTube につながらなかったので、ここまでを保存して止めます({e})。続きは次に動かしたときに読みます")
    save_state(st)
    titles = st.get("playlists", {})
    videos = [{"id": vid, **c, "playlists": [titles.get(p, "") for p in st["vid_lists"].get(vid, [])]}
              for vid, c in st["candidates"].items()]
    stats = {"checked": len(st["checked"]), "queue": len(st["queue"]), "playlists": len(titles),
             "done_playlists": len(st["done_playlists"]), "oldest_upload": st["oldest_upload"], "calls": calls,
             "complete": st["complete"], "total": ch["statistics"].get("videoCount", "")}
    print(f"API の呼び出し: {calls}回")
    return ch, videos, stats


def seconds(iso):
    m = re.fullmatch(r"P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def hms(sec):
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def norm(w):
    """伸ばす音の書き方の違いをそろえる(_work/players/uww_results.py の key() と同じ考え方)"""
    w = re.sub(r"[^A-Z]", "", w.upper())
    return re.sub(r"([AEIOU])\1", r"\1", re.sub(r"OH(?=[^AEIOU]|$)", "O", w))


def load_players():
    with open(os.path.join(ROOT, "players.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    pairs, fams = {}, {}
    for p in rows:
        parts = p["ローマ字"].split()
        if len(parts) < 2:
            continue
        fam = [w for w in parts if w.isupper() and len(w) > 1] or parts[-1:]
        giv = [w for w in parts if w not in fam]
        if not giv:
            fam, giv = parts[-1:], parts[:-1]
        f, g = norm(" ".join(fam)), norm(" ".join(giv))
        pairs.setdefault((f, g), []).append(p)
        pairs.setdefault((g, f), []).append(p)
        fams.setdefault(f, []).append((g, p))
    return pairs, fams


def shown(p):
    """サイトと同じ決まり:公開=はい、かつ 未成年=いいえ の人だけ名前を書く"""
    return p.get("公開") == "はい" and p.get("未成年") == "いいえ"


TOKEN = re.compile(r"\(([A-Z]{3})\)|[A-Za-z][A-Za-z'\-]*")


def names_in(title, players):
    """タイトルの中の players.csv の名前(姓名・名姓のどちらの順でも)。後ろに JPN 以外の国名があるものは外す。
    「R. MIYAJI (JPN)」のような頭文字の名前は、すぐ後ろが (JPN) のときだけ、姓と名前の頭文字で探す"""
    pairs, fams = players
    toks = [(m.group(1), m.group(0)) for m in TOKEN.finditer(title)]
    found = []
    for i in range(len(toks) - 1):
        a, b = toks[i], toks[i + 1]
        if a[0] or b[0]:
            continue
        nxt = toks[i + 2][0] if i + 2 < len(toks) else None
        if len(a[1]) == 1 and b[1].isupper():
            if nxt == "JPN":
                hit = [p for g, p in fams.get(norm(b[1]), []) if g.startswith(a[1].upper())]
                if hit:
                    found.append((hit, True))
            continue
        hit = pairs.get((norm(a[1]), norm(b[1])))
        if not hit or (nxt and nxt != "JPN"):
            continue
        found.append((hit, bool(nxt)))
    return found


JP_TITLE = re.compile(r"\bJPN\b|\bJapan(?:ese)?\b|日本|🇯🇵")
JP_DESC = re.compile(r"\bJPN\b|\bJapan(?:ese)?\b")


def age_group(t):
    t = t.lower()
    for pat, g in [(r"\bu-?15\b", "U15"), (r"\bu-?17\b|\bcadets?\b", "U17"), (r"\bu-?20\b|\bjuniors?\b", "U20"), (r"\bu-?23\b", "U23")]:
        if re.search(pat, t):
            return g
    return "シニア(または不明)"


def kind(t, sec):
    tl = t.lower()
    if re.search(r"medal ceremony|podium|victory ceremony", tl):
        return "表彰式"
    if re.search(r"interview|reacts?\b|speaks|talks|press conference|q&a|mixed zone", tl):
        return "インタビュー"
    if re.search(r"every match|all matches|road to", tl):
        return "試合まとめ"
    if re.search(r"highlight|recap|best of|top \d+|moments|preview|documentary|story|feature|profile", tl):
        return "ハイライト・特集"
    if re.search(r"\bvs\.?\b|\bv\.? |\bdf\.?\b|\bdec\.?\b|final|semifinal|bronze|gold medal match|repechage", tl):
        return "試合"
    if sec and sec <= 60:
        return "ショート"
    return "その他"


# 上から順に見て、最初に合ったものにする(「Olympic Qualifier」を「オリンピック」にしないよう、細かいものを先に)
EVENTS = [(r"olympic qualif", "オリンピック予選"), (r"asian games", "アジア大会"), (r"olympic", "オリンピック"),
          (r"world cup", "ワールドカップ"), (r"world championships?|\bworlds\b", "世界選手権"),
          (r"asian championships?", "アジア選手権"),
          (r"ranking series|grand prix|zagreb open|yasar dogu|ibrahim moustafa|kolov|poland open|muhamet malo|matteo pellicone|takhti",
           "ランキングシリーズ等")]


def event_of(t):
    tl = t.lower()
    return next((name for pat, name in EVENTS if re.search(pat, tl)), "")


def classify(videos, players):
    rows, skipped_long = [], 0
    for v in videos:
        sec = seconds(v["duration"])
        t, d = v["title"], v["description"]
        lists = " / ".join(v.get("playlists", []))
        found = names_in(t, players)
        reasons = []
        if JP_TITLE.search(t):
            reasons.append("タイトルにJPN/Japan")
        if found:
            reasons.append("選手名の一致" + ("" if all(c for _, c in found) else "(国名なし)"))
        if not reasons and JP_DESC.search(d):
            reasons.append("説明にJPN/Japan")
        if not reasons:
            continue
        if sec >= LONG_MIN * 60:
            skipped_long += 1
            continue
        sure = "高" if reasons[0] == "タイトルにJPN/Japan" else ("中" if "選手名" in reasons[0] else "低(要確認)")
        names, note = [], ""
        for hit, _ in found:
            if len(hit) > 1:
                note = "照合なし(同じローマ字が2人以上)"
                if sure != "高":
                    sure = "低(同じローマ字が2人以上)"
                continue
            if shown(hit[0]):
                names.append(f"{hit[0]['氏名']}({hit[0]['ローマ字']})")
            else:
                note = "照合なし"
        player_col = "・".join(dict.fromkeys(names))
        if note or not names:
            player_col = (player_col + "・" if player_col else "") + (note or "照合なし")
        # 大会・年代・年は、タイトルに無ければ再生リストの名前から
        y = re.search(r"\b(19[89]\d|20[0-4]\d)\b", t) or re.search(r"\b(19[89]\d|20[0-4]\d)\b", lists)
        age = age_group(t)
        if age.startswith("シニア"):
            age = age_group(lists)
        rows.append({"動画ID": v["id"], "タイトル": t, "公開日": v["published"][:10], "長さ": hms(sec), "種類": kind(t, sec),
                     "年代": age, "大会": event_of(t) or event_of(lists), "年": y.group(1) if y else v["published"][:4],
                     "見分けた理由": "・".join(reasons), "確かさ": sure, "日本人選手": player_col,
                     "再生リスト": lists, "URL": f"https://www.youtube.com/watch?v={v['id']}"})
    rows.sort(key=lambda r: r["公開日"], reverse=True)
    return rows, skipped_long


def summary(ch, videos, rows, skipped_long, stats):
    c = lambda k: Counter(r[k] for r in rows).most_common()
    done = stats.get("complete", True)
    lines = [f"## UWW の日本人選手の動画の一覧(チャンネル: {ch['snippet']['title']}・{ch['id']})", "",
             ("- **完了**:読める動画は全部読みました" if done else
              f"- **途中**:続きがあります。もう一度「Run workflow」を押してください(1日1回、夕方4時より後に)"),
             f"- 調べた動画: {stats.get('checked', len(videos))}本(チャンネルの動画は {stats.get('total', '?')}本)"
             f"・まだ調べていない動画: {stats.get('queue', 0)}本・読んだ再生リスト: {stats.get('done_playlists', 0)}/{stats.get('playlists', 0)}個",
             f"- **日本人選手が出ている動画: {len(rows)}本**(長時間の配信 {skipped_long}本は外した)",
             f"- 一覧: `_work/uww/uww_japan_videos.csv`",
             f"- YouTube API はアップロードの一覧を新しい順に 20,000本までしか返さない(いちばん古いもの {stats.get('oldest_upload', '')})。"
             f"それより前で、どの再生リストにも入っていない動画は取れない",
             f"- 今回の API の呼び出し: {stats.get('calls', 0)}回", ""]
    for k in ("種類", "年代", "大会", "確かさ", "年"):
        lines.append(f"### {k}ごと")
        lines += [f"- {name or '(分からない)'}: {n}本" for name, n in sorted(c(k), key=lambda x: (-x[1], x[0]))[:25]]
        lines.append("")
    low = [r for r in rows if r["確かさ"].startswith("低")]
    lines.append(f"### 見分けに自信がない動画({len(low)}本。最初の30本)")
    lines += [f"- [{r['タイトル']}]({r['URL']}) … {r['見分けた理由']}・{r['確かさ']}" for r in low[:30]]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="")
    ap.add_argument("--sample", default="")
    a = ap.parse_args()
    players = load_players()
    if a.sample:
        with open(a.sample, encoding="utf-8") as f:
            videos = json.load(f)
        ch, stats = {"id": "sample", "snippet": {"title": "sample"}}, {}
    else:
        ch, videos, stats = fetch(a.channel, players)
    rows, skipped = classify(videos, players)
    with open(os.path.join(HERE, "uww_japan_videos.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, COLS)
        w.writeheader()
        w.writerows(rows)
    text = summary(ch, videos, rows, skipped, stats)
    with open(os.path.join(HERE, "summary.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
