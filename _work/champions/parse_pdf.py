"""レスリング・スピリッツ「歴代記録」PDF → 優勝者の行(JSON lines)
使い方: python3 -I parse.py <pdf> <file_key>
文字の位置で列(階級)を決める。
"""
import json
import re
import sys

import pdfplumber

KG = re.compile(r"\d+k[g]?(以上|超)?級")
CLASSIC = re.compile(r"^(ライトフライ|フライ|バンタム|フェザー|ライト|ウエルター|ウェルター|ミドル|ライトヘビー|ヘビー)級$")
YEAR = re.compile(r"^(\d{4})(年|$)(（.*）?)?$")
SKIP = re.compile(r"出場なし|中止|該当者なし|調べ|歴代|選手権|不戦|棄権|欠場|なし】|なし）|^（$|^）$")


def wlabel(t):
    """語が階級名なら正規化した階級名(例: 77k級 → 77kg級)、団体なら「団体」、ちがえば None"""
    if t == "団体":
        return t
    m = KG.search(t)
    if m:
        return m.group(0).replace("k級", "kg級").replace("kkg", "kg")
    if CLASSIC.match(t):
        return t
    return None


def lines_of(words, tol=2.5):
    out = []
    for w in sorted(words, key=lambda w: (w["top"], w["x0"])):
        if out and abs(out[-1][0]["top"] - w["top"]) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    return out


STATE = {"last": 0}


def main(path, key):
    pdf = pdfplumber.open(path)
    cols = None  # [(center, label)]
    rows_out = []
    for pno, page in enumerate(pdf.pages):
        words = page.extract_words(x_tolerance=2, y_tolerance=2)
        lines = lines_of(words)
        # ヘッダー行: 「級」の語が 3 つ以上
        headers, notes = [], []
        for ln in lines:
            ws = [w for w in ln if wlabel(w["text"])]
            if len(ws) >= 3:
                headers.append((ln[0]["top"], [((w["x0"] + w["x1"]) / 2, wlabel(w["text"])) for w in ws]))
            elif ws and len(ws) == len(ln):
                # 表の途中の階級の注記(例: 1982年「100kg級 100kg以上級」、1985年「130kg級」)。
                # その位置の列を置きかえ、ここから下の見出しとして使う
                notes.extend(ws)
                base = headers[-1][1] if headers else cols
                if base:
                    cs = sorted(c for c, _ in base)
                    gap = min(b - a for a, b in zip(cs, cs[1:]))
                    nc = [((w["x0"] + w["x1"]) / 2, wlabel(w["text"])) for w in ws]
                    keep = [c for c in base if all(abs(c[0] - x) > gap * 0.5 for x, _ in nc)]
                    headers.append((ln[0]["top"], sorted(keep + nc)))
        years = []
        for w in sorted((w for w in words if YEAR.match(w["text"]) and w["x0"] < 100), key=lambda w: w["top"]):
            y = int(YEAR.match(w["text"]).group(1))
            if STATE["last"] and y <= STATE["last"]:
                print("YEARFIX", key, pno + 1, y, "->", STATE["last"] + 1, file=sys.stderr)
                y = STATE["last"] + 1
            STATE["last"] = y
            years.append((w["top"], y, w))
        seasons = [(w["top"], w["text"]) for w in words if w["text"] in ("春", "秋") and w["x0"] < 100]

        def header_for(top):
            hs = [h for h in headers if h[0] <= top + 1]
            return hs[-1][1] if hs else None

        # 語を列に割り当てる
        names, clubs = [], []
        for w in words:
            if any(abs(h[0] - w["top"]) < 2.5 for h in headers):
                continue
            hc = header_for(w["top"]) or cols
            if not hc:
                continue
            cx = (w["x0"] + w["x1"]) / 2
            first = min(c for c, _ in hc)
            colw = sorted(c for c, _ in hc)
            gap = min(b - a for a, b in zip(colw, colw[1:])) if len(colw) > 1 else 60
            if cx < first - gap * 0.6:
                continue  # 年・期日・場所
            lab = min(hc, key=lambda c: abs(c[0] - cx))[1]
            if lab == "団体":
                continue
            t = w["text"]
            if "（" in t[1:] and not t.startswith("（"):  # 「名前（所属）」が1語になっているとき
                i = t.index("（")
                clubs.append({"top": w["top"] + 0.1, "x0": w["x0"], "col": lab, "text": t[i:], "hc": id(hc)})
                t = t[:i]
            if SKIP.search(t):
                continue
            item = {"top": w["top"], "x0": w["x0"], "col": lab, "text": t, "hc": id(hc)}
            if t.startswith(("（", "(", "【")) or t.endswith(("）", ")")) or (clubs and clubs[-1]["col"] == lab and abs(clubs[-1]["top"] - w["top"]) < 2.5 and not clubs[-1]["text"].endswith(("）", ")"))):
                clubs.append(item)
            else:
                names.append(item)
        if headers:
            cols = headers[-1][1]
        # 同じ行・同じ列の語をつなぐ
        def merge(items):
            out = []
            for it in sorted(items, key=lambda i: (i["col"], round(i["top"] / 3), i["x0"])):
                if out and out[-1]["col"] == it["col"] and abs(out[-1]["top"] - it["top"]) < 2.5:
                    out[-1]["text"] += " " + it["text"]
                else:
                    out.append(dict(it))
            return out
        names, clubs = merge(names), merge(clubs)
        # 「・」で終わる名前は次の行の同じ列とつなぐ
        names.sort(key=lambda n: (n["col"], n["top"]))
        merged = []
        for n in names:
            if merged and merged[-1]["col"] == n["col"] and (merged[-1]["text"].endswith("・") or n["text"].startswith("・")) and 0 < n["top"] - merged[-1]["top"] < 16:
                merged[-1]["text"] += n["text"]
                continue
            merged.append(n)
        names = [n for n in merged if len(n["text"].replace(" ", "")) >= 2 and any(len(x) > 1 for x in n["text"].split())]
        for n in names:
            if not years:
                print("NOYEAR", key, pno, n["text"], file=sys.stderr)
                continue
            y = min(years, key=lambda y: abs(y[0] - n["top"]))
            se = ""
            if seasons:
                s = min(seasons, key=lambda s: abs(s[0] - n["top"]))
                if abs(s[0] - n["top"]) < 12:
                    se = s[1]
            # 所属: 同じ列で、この名前より下で一番近いもの(次の名前より上)
            below = [c for c in clubs if c["col"] == n["col"] and c["top"] > n["top"] - 1]
            nxt = [m["top"] for m in names if m["col"] == n["col"] and m["top"] > n["top"] + 2.5]
            lim = min(nxt) if nxt else 1e9
            cand = [c for c in below if c["top"] < lim]
            club = min(cand, key=lambda c: c["top"])["text"] if cand else ""
            rows_out.append({"file": key, "page": pno + 1, "year": y[1], "season": se, "weight": n["col"],
                             "name": n["text"], "club": club, "dy": round(abs(y[0] - n["top"]), 1)})
    for r in rows_out:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
