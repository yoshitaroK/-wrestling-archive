"""日本レスリング協会の「入賞者一覧」PDF から、階級・順位・氏名・所属を取り出す(位置で対応づける)"""
import re, subprocess, sys, html, unicodedata
from xml.etree import ElementTree as ET

WEIGHT = re.compile(r"^(?:(FS|GR|WW|F|G|W|FA|FB|女子)\s*)?(\d{2,3})\s*(?:kg|㎏|ｋｇ)?(?:級)?$", re.I)
PLACE = re.compile(r"^(?:第)?([1-8１-８])位$|^([1-8１-８])$")
ORG_HINT = re.compile(r"大学|高校|高等学校|学校|株式会社|㈱|\(株\)|（株）|自衛隊|警視庁|府警|県警|協会|クラブ|教室|少年団|役所|市役所|県庁|庁|ALSOK|ＡＬＳＯＫ|SPORTS|Club|CLUB|職員|コーチ|グループ|運輸|海運|産業|工業|ハウス|MTX|CWC|銀行|病院|会$|団$|部$|社$|塾", re.I)

def words(pdf):
    xml = subprocess.run(["pdftotext", "-bbox", pdf, "-"], capture_output=True, text=True).stdout
    pages = []
    for pg in xml.split("<page ")[1:]:
        ws = []
        for x0, y0, x1, y1, t in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', pg):
            t = unicodedata.normalize("NFKC", html.unescape(t).strip())
            if t:
                ws.append(dict(t=t, x0=float(x0), x1=float(x1), y0=float(y0), y1=float(y1)))
        pages.append(ws)
    return pages


def rows(ws, tol=3.5):
    out = []
    for w in sorted(ws, key=lambda w: (w["y0"], w["x0"])):
        cy = (w["y0"] + w["y1"]) / 2
        for r in out:
            if abs(r["cy"] - cy) <= tol:
                r["w"].append(w); break
        else:
            out.append(dict(cy=cy, w=[w]))
    for r in out:
        r["w"].sort(key=lambda w: w["x0"])
    out.sort(key=lambda r: r["cy"])
    return out

def groups(ws, gap):
    """近い単語をまとめる(1つの名前・1つの所属)"""
    g = []
    for w in ws:
        if g and w["x0"] - g[-1]["x1"] <= gap:
            g[-1]["t"] += (" " if not re.match(r"[ァ-ヶー]", w["t"]) or True else "") + w["t"]; g[-1]["x1"] = w["x1"]; g[-1]["parts"] += 1
        else:
            g.append(dict(t=w["t"], x0=w["x0"], x1=w["x1"], parts=1))
    return g

STYLE_PRE = {"FS": "フリースタイル", "F": "フリースタイル", "FA": "フリースタイル", "FB": "フリースタイル", "GR": "グレコローマン",
             "G": "グレコローマン", "WW": "女子", "W": "女子", "女子": "女子"}


def place_list(headers, n):
    labels = [h[1] for h in sorted(headers)]
    if len(labels) == n:
        return labels
    if n == 8:
        return list("12335578") if "7" in labels else list("12335555")
    return list("12335555")[:n]


def parse(pdf):
    res = []
    style = ""
    div = ""
    for ws in words(pdf):
        rs = rows(ws)
        places, weights, body = [], [], []
        for r in rs:
            line = " ".join(w["t"] for w in r["w"])
            if re.search(r"新人戦", line): div = "新人戦"
            elif re.search(r"選手権(フリー|グレコ|女子)", line): div = ""
            if re.search(r"フリースタイル|Freestyle", line): style = "フリースタイル"
            elif re.search(r"グレコ", line): style = "グレコローマン"
            elif re.search(r"女子", line) and len(r["w"]) <= 3: style = "女子"
            ph = []
            for j, w in enumerate(r["w"]):
                m = re.match(r"^(?:第)?([1-8])位", w["t"])
                if m:
                    ph.append(((w["x0"] + w["x1"]) / 2, m.group(1)))
                elif re.fullmatch(r"[1-8]", w["t"]) and j + 1 < len(r["w"]) and r["w"][j + 1]["t"].startswith("位"):
                    ph.append((w["x1"], w["t"]))
            if len(ph) >= 3:
                places = ph; body.append(("H", r, ph)); continue
            rest = []
            for w in r["w"]:
                m = WEIGHT.match(w["t"].replace(" ", ""))
                if m and w["x0"] < 130:
                    weights.append((r["cy"], STYLE_PRE.get((m.group(1) or "").upper(), style), m.group(2) + "kg"))
                elif not re.match(r"^\d+名$", w["t"]) and not (w["x0"] < 200 and w["t"] in ("氏", "名", "所", "属", "氏名", "所属", "氏名・所属")):
                    rest.append(w)
            if rest:
                body.append(("R", dict(cy=r["cy"], w=rest), places))
        for i in range(len(body) - 1):
            k1, r, hdr = body[i]; k2, nxt, _ = body[i + 1]
            if k1 != "R" or k2 != "R" or not hdr:
                continue
            cand, orgs = r["w"], nxt["w"]
            og = groups(orgs, 6)
            if sum(1 for o in og if ORG_HINT.search(o["t"])) < max(1, len(og) // 2):
                continue
            if sum(1 for w in cand if ORG_HINT.search(w["t"])) > len(cand) // 3:
                continue
            mid = [w for w in weights if r["cy"] - 2 <= w[0] <= nxt["cy"] + 2]
            above = [w for w in weights if r["cy"] - 45 <= w[0] < r["cy"] - 2]
            if mid:
                wt = min(mid, key=lambda w: abs(w[0] - (r["cy"] + nxt["cy"]) / 2))
            elif above:
                wt = max(above, key=lambda w: w[0])
            else:
                continue
            if len(og) <= len(hdr):
                # 見出しが列ごとにある表:名前と所属を、いちばん近い見出しの列に入れる
                hs = sorted(hdr)
                cols = [dict(names=[], orgs=[], pl=h[1]) for h in hs]
                for w in cand:
                    cx = (w["x0"] + w["x1"]) / 2
                    cols[min(range(len(hs)), key=lambda k: abs(hs[k][0] - cx))]["names"].append(w["t"])
                for w in orgs:
                    cx = (w["x0"] + w["x1"]) / 2
                    cols[min(range(len(hs)), key=lambda k: abs(hs[k][0] - cx))]["orgs"].append(w["t"])
                for c in cols:
                    if c["names"]:
                        res.append(dict(div=div, style=wt[1], weight=wt[2], place=c["pl"], name=" ".join(c["names"]), org=re.sub(r"(?<=[A-Za-z]) (?=[A-Za-z])", " ", " ".join(c["orgs"])).replace(" ", "") if not re.search(r"[A-Za-z] [A-Za-z]", " ".join(c["orgs"])) else " ".join(c["orgs"])))
                continue
            cols = sorted([dict(o, names=[]) for o in og], key=lambda o: o["x0"])
            for w in cand:
                cx = (w["x0"] + w["x1"]) / 2
                min(cols, key=lambda o: abs((o["x0"] + o["x1"]) / 2 - cx))["names"].append(w["t"])
            cols = [c for c in cols if c["names"]]
            pls = place_list(hdr, len(cols))
            for c, pl in zip(cols, pls):
                res.append(dict(div=div, style=wt[1], weight=wt[2], place=pl, name=" ".join(c["names"]), org=c["t"].replace(" ", "")))
    return res


if __name__ == "__main__":
    for x in parse(sys.argv[1]):
        print(x)


def parse_rotated(pdf, pages, six=()):
    """RESULT BOOK の「スタイル別入賞者一覧」(横向きのページ。階級が列・順位が行)から取り出す。
    pages は 1 から数えたページ番号。six は「5位(6位)」が6位を意味する (スタイル, 階級)"""
    res = []
    allp = words(pdf)
    for no in pages:
        ws = allp[no - 1]
        text = "".join(w["t"] for w in ws)
        style = "フリースタイル" if "フリースタイル" in text else "グレコローマン" if "グレコ" in text else "女子"
        labels = [w for w in ws if re.fullmatch(r"\d位(\(\d位\))?", w["t"]) and w["x0"] < 211]
        weights = [w for w in ws if re.fullmatch(r"\d{2,3}kg", w["t"]) and w["y0"] > 700]
        for wt in weights:
            cells = {}
            for w in ws:
                if w["y0"] > 700 or w["x0"] < wt["x0"] - 1 or w["x0"] > wt["x0"] + 31 or w in labels:
                    continue
                cy = (w["y0"] + w["y1"]) / 2
                lab = min(labels, key=lambda l: abs((l["y0"] + l["y1"]) / 2 - cy))
                kind = "name" if w["x0"] <= wt["x0"] + 15 else "org"
                cells.setdefault(id(lab), {"lab": lab, "name": [], "org": []})[kind].append(w)
            for c in cells.values():
                if not c["name"]:
                    continue
                pl = c["lab"]["t"]
                place = "6" if "(6位)" in pl and (style, wt["t"]) in six else pl[0]
                name = " ".join(w["t"] for w in sorted(c["name"], key=lambda w: -w["y0"]))
                org = "".join(w["t"] for w in sorted(c["org"], key=lambda w: -w["y0"]))
                res.append(dict(div="", style=style, weight=wt["t"], place=place, name=name, org=org))
    return res
