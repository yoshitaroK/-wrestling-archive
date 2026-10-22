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


def marks(pdf):
    """「斜字体は4位」「網掛けは4位」のように、字の形や欄の色で順位を分けている一覧の、印の付いた場所をページごとに返す。
    斜字体は字の位置 ("pt", x, y)、網掛けは塗った四角 ("rect", x0, y0, x1, y1)。座標は pdftotext と同じ(左上が原点)。印の注記が無い一覧は空"""
    text = subprocess.run(["pdftotext", pdf, "-"], capture_output=True, text=True).stdout
    italic, shade = "斜字体は" in text, "網掛けは" in text
    if not (italic or shade):
        return []
    import pypdf  # 印のある一覧だけで使う(pip install pypdf)
    from pypdf.generic import ContentStream

    def mul(m, n):
        a, b, c, d, e, f = m; A, B, C, D, E, F = n
        return [a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F]
    rd, out = pypdf.PdfReader(pdf), []
    for pg in rd.pages:
        H, ms = float(pg.mediabox.top), []
        if italic:
            def vis(t, cm, tm, fd, fs):
                m = mul(tm, cm)
                if t.strip() and m[3] and abs(m[2] / m[3]) > 0.1:  # 字を斜めに傾けて書いている
                    ms.append(("pt", m[4], H - m[5]))
            pg.extract_text(visitor_text=vis)
        if shade:
            ctm, st, col, rects = [1, 0, 0, 1, 0, 0], [], None, []
            for ops, op in ContentStream(pg.get_contents(), rd).operations:
                op = op.decode() if isinstance(op, bytes) else op
                if op == "q": st.append(ctm[:])
                elif op == "Q": ctm = st.pop() if st else ctm
                elif op == "cm": ctm = mul([float(x) for x in ops], ctm)
                elif op in ("g", "rg", "k", "sc", "scn"):
                    try: col = [float(x) for x in ops]
                    except (TypeError, ValueError): col = None
                elif op == "re":
                    x, y, w, h = [float(v) for v in ops]
                    rects.append([(x, y), (x + w, y + h)])
                elif op == "m": rects.append([tuple(float(v) for v in ops)])
                elif op == "l" and rects: rects[-1].append(tuple(float(v) for v in ops))
                elif op in ("f", "f*", "F", "B", "B*"):
                    # 薄い灰色(白でも黒でもなく、色味の無いもの)で塗った四角(re でも、m・l で囲んだ形でもよい)
                    if col and (len(col) == 1 or (len(col) == 3 and max(col) - min(col) < 0.02)) and 0.5 < col[0] < 0.97:
                        for pts in rects:
                            xs = [ctm[0] * px + ctm[2] * py + ctm[4] for px, py in pts]
                            ys = [H - (ctm[1] * px + ctm[3] * py + ctm[5]) for px, py in pts]
                            ms.append(("rect", min(xs), min(ys), max(xs), max(ys)))
                    rects = []
                elif op in ("n", "S", "s"): rects = []
        out.append(ms)
    return out


def marked(ms, cx, cy, half):
    """欄の真ん中 cx・行の高さ cy の名前に、印が付いているか"""
    for m in ms:
        if m[0] == "pt" and cx - half <= m[1] < cx + half and abs(m[2] - cy) < 8:
            return True
        if m[0] == "rect" and m[1] <= cx <= m[3] and m[2] <= cy <= m[4]:
            return True
    return False


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


def spaced_names(cand):
    """2014〜2019年(と2021年明治杯の1〜8位)の一覧は、名前が「高 橋 侑 希」のように1文字ずつ空けて書かれている。
    1人分の欄は4文字分の幅で、左の2文字分が姓、右の2文字分が名(3文字の姓・名は2文字分に詰めてある)。
    そういう行なら、欄ごとの (欄の中心, "姓 名" か 入賞者なしの None) を返す。この形の行でなければ None、
    この形だが読み取りに自信が無ければ False を返す(その行は使わない)"""
    cand = [w for w in cand if not re.fullmatch(r"\d+", w["t"])]  # 名前の前の「参加人数」の欄(2019年明治杯)
    one = [w for w in cand if len(w["t"]) == 1]
    if len(cand) < 4 or len(one) < 0.6 * len(cand):
        return None
    gw = sorted(w["x1"] - w["x0"] for w in one)[len(one) // 2]
    ds = sorted(b["x0"] - a["x0"] for a, b in zip(cand, cand[1:])
                if len(a["t"]) == 1 and len(b["t"]) == 1 and 0.2 * gw < b["x0"] - a["x1"] < 1.2 * gw)
    if len(ds) < 3:
        return False
    step = ds[len(ds) // 2]
    # 詰めて書いた姓・名(「長谷川」「ケイワン」「吉田」)は、ひとかたまりで扱う。
    # pdftotext は隣の人の文字とつなげて1語にすることもある(「き伊」)ので、姓か名の始まる位置に無い語は1文字ずつに分ける
    cells = []
    def put(x, t, unit):
        if not cells or cells[-1]["empty"] or (x - cells[-1]["x"]) / step > 3.5:  # 姓は欄の左端から始まる
            cells.append(dict(x=x, toks=[], empty=False))
        if (x - cells[-1]["x"]) / step > 3.4:
            return False
        cells[-1]["toks"].append((x, t, unit))
        return True
    for w in sorted(cand, key=lambda w: w["x0"]):
        if w["t"] == "#N/A":  # 入賞者のいない欄
            cells.append(dict(x=(w["x0"] + w["x1"]) / 2 - 1.5 * step - gw / 2, toks=[], empty=True)); continue
        n = len(w["t"]); cw = (w["x1"] - w["x0"]) / n
        if n >= 2 and cw <= 1.15 * gw and w["x1"] - w["x0"] <= 2.3 * step:
            new = not cells or cells[-1]["empty"] or (w["x0"] - cells[-1]["x"]) / step > 3.5
            rel = 0 if new else (w["x0"] - cells[-1]["x"]) / step
            if rel < 0.5 or 1.5 < rel < 2.6:
                if not put(w["x0"], w["t"], True):
                    return False
                continue
        for i, ch in enumerate(w["t"]):
            if not put(w["x0"] + i * cw, ch, False):
                return False
    out = []
    for c in cells:
        cx = c["x"] + 1.5 * step + gw / 2
        if c["empty"]:
            out.append((cx, None)); continue
        ts = c["toks"]
        # 姓は左詰め・名は右詰めなので、すき間のいちばん大きいところが姓と名の境目
        if len(ts) == 2:
            cut = 1
        elif len(ts) == 3 and (ts[0][2] or ts[2][2]):
            cut = 1 if ts[0][2] else 2  # 詰めて書いた語の側が、姓か名の全部
        elif len(ts) == 3:
            g1, g2 = ts[1][0] - ts[0][0], ts[2][0] - ts[1][0]
            if max(g1, g2) < 1.3 * min(g1, g2):
                return False  # 3文字が等しい間隔で並んでいて、姓と名の境目が分からない
            cut = 1 if g1 > g2 else 2
        elif len(ts) == 4 and not any(u for _, _, u in ts):
            cut = 2
        else:
            return False
        out.append((cx, "".join(t for _, t, _ in ts[:cut]) + " " + "".join(t for _, t, _ in ts[cut:])))
    return out


def places_by_header(hdr, centers, filled=None):
    """順位の見出しは、受け持つ欄(「3位」なら2人分、「5位」なら2人分や4人分)の真ん中にある。
    見出しの位置から、欄ごとの順位を決める。合わなければ None(後ろの欄に入賞者がいないのはよい)
    filled(欄ごとに入賞者がいるか)を渡したときは、表全体の欄で見出しを合わせ、数字の並びはその行の入賞者で確かめる"""
    hs = sorted(hdr)
    if len(centers) < 2:
        return None
    pitch = sorted(b - a for a, b in zip(centers, centers[1:]))[(len(centers) - 1) // 2]
    out, j = [], 0
    for hx, lab in hs:
        if j >= len(centers):
            if hx < centers[-1]:
                return None
            continue
        best = min(range(j + 1, len(centers) + 1), key=lambda k: abs(sum(centers[j:k]) / (k - j) - hx))
        if abs(sum(centers[j:best]) / (best - j) - hx) > 0.3 * pitch:
            return None
        out += [lab] * (best - j); j = best
    if j != len(centers):
        return None
    # 順位の数字の並びが合うか(3位が2人なら次は5位、のように)
    labs = []  # 同じ順位の見出しが並んでいる(「5位」「5位」)ときは1つにまとめる
    for _, lab in hs:
        if not labs or labs[-1] != lab:
            labs.append(lab)
    for a, b in zip(labs, labs[1:]):
        if filled is not None:
            # 表の欄が「1位・2位・3位・3位・4位」のとき(2018年天皇杯の女子):トーナメントの階級は3位が2人、
            # 総当たりの階級は3位が1人と4位。入賞者がいる見出しは、その行の前の順位の人数か欄の数の続きの数字
            nf = sum(1 for o, f in zip(out, filled) if f and o == a)
            if nf and any(f and o == b for o, f in zip(out, filled)) and int(b) not in (int(a) + nf, int(a) + out.count(a)):
                return None
            continue
        n = out.count(a)
        # 入賞者がいる見出しは、ちょうど続きの数字(3位が2人なら5位)。後ろの入賞者がいない見出しも、それより小さくはならない
        if n and (int(b) < int(a) + n or (out.count(b) and int(b) != int(a) + n)):
            return None
    return out

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
    grid, pending = {}, []  # 1文字ずつ空けた名前の表の、見出しごとの欄の位置/見出しと合わなかった行

    def emit(sp, pls, orgs, wt, div, ms=(), cy=0):
        # 印(斜字体・網掛け)の付いた欄は、順位が1人ずつ:前の欄の順位の次の数字(「網掛けは各順位1名 4位/5位/6位/7位」。2018年天皇杯・2019年)
        if ms and len(sp) > 1:
            half = min(b[0] - a[0] for a, b in zip(sp, sp[1:])) / 2
            pls, prev = list(pls), 0
            for i, (cx, nm) in enumerate(sp):
                if nm and prev and marked(ms, cx, cy, half):
                    pls[i] = str(prev + 1)
                if nm:
                    prev = int(pls[i])
        # 所属は、近い所属どうしがくっつかないよう、1語ずつ いちばん近い欄に入れる
        ow = {i: [] for i in range(len(sp))}
        left = sp[0][0] - (sp[1][0] - sp[0][0]) / 2 if len(sp) > 1 else -1
        for w in orgs:
            ox = (w["x0"] + w["x1"]) / 2
            if ox < left:
                continue  # 1人目の欄より左(「参加人数」の欄の「棄権1」など。2019年明治杯)
            ow[min(range(len(sp)), key=lambda i: abs(sp[i][0] - ox))].append(w["t"])
        for i, ((cx, nm), pl) in enumerate(zip(sp, pls)):
            if not nm:
                continue
            org = " ".join(ow[i]) if re.search(r"[A-Za-z] [A-Za-z]", " ".join(ow[i])) else "".join(ow[i])
            res.append(dict(div=div, style=wt[1], weight=wt[2], place=pl, name=nm, org=org))

    style = ""
    div = ""
    mk = marks(pdf)
    for pno, ws in enumerate(words(pdf)):
        ms = mk[pno] if pno < len(mk) else []
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
                elif w["t"] == "優勝" or (w["t"] == "優" and j + 1 < len(r["w"]) and r["w"][j + 1]["t"] == "勝"):
                    # 「優 勝」と1文字ずつ空けた見出し(2016年明治杯など)は1位
                    ph.append(((w["x0"] + w["x1"]) / 2 if w["t"] == "優勝" else w["x1"], "1"))
            if len(ph) >= 3:
                places = ph; body.append(("H", r, ph)); continue
            rest = []
            # 行の左に「氏 名」「所 属」と書いた表(2024年からの協会の一覧):どちらの行かが分かる
            lab = {"氏": "name", "名": "name", "氏名": "name", "所": "org", "属": "org", "所属": "org"}
            labs = {lab[w["t"]] for w in r["w"] if w["x0"] < 200 and w["t"] in lab}
            for w in r["w"]:
                m = WEIGHT.match(w["t"].replace(" ", ""))
                if m and w["x0"] < 130:
                    weights.append((r["cy"], STYLE_PRE.get((m.group(1) or "").upper(), style), m.group(2) + "kg"))
                elif not re.match(r"^\d+名$", w["t"]) and not (w["x0"] < 200 and w["t"] in ("氏", "名", "所", "属", "氏名", "所属", "氏名・所属")):
                    rest.append(w)
            if rest:
                body.append(("R", dict(cy=r["cy"], w=rest, lab=labs.pop() if len(labs) == 1 else ""), places))
        for i in range(len(body) - 1):
            k1, r, hdr = body[i]; k2, nxt, _ = body[i + 1]
            if k1 != "R" or k2 != "R" or not hdr:
                continue
            cand, orgs = r["w"], nxt["w"]
            og = groups(orgs, 6)
            labeled = r["lab"] == "name" and nxt["lab"] == "org"  # 「氏 名」「所 属」の行の組。所属らしい言葉が無くても所属の行
            if not labeled and sum(1 for o in og if ORG_HINT.search(o["t"])) < max(1, len(og) // 2):
                continue
            if not labeled and sum(1 for w in cand if ORG_HINT.search(w["t"])) > len(cand) // 3:
                continue
            mid = [w for w in weights if r["cy"] - 2 <= w[0] <= nxt["cy"] + 2]
            above = [w for w in weights if r["cy"] - 45 <= w[0] < r["cy"] - 2]
            if mid:
                wt = min(mid, key=lambda w: abs(w[0] - (r["cy"] + nxt["cy"]) / 2))
            elif above:
                wt = max(above, key=lambda w: w[0])
            else:
                continue
            sp = spaced_names(cand)
            if sp is False:
                continue  # 1文字ずつ空けた名前の行だが、読み取りに自信が無いので使わない
            if sp:
                # 1文字ずつ空けた名前:欄ごとに名前を作り、順位は見出しの位置から、所属はいちばん近いものと組にする
                pls = places_by_header(hdr, [cx for cx, _ in sp])
                grid.setdefault(id(hdr), []).extend(cx for cx, _ in sp)
                if pls is None:
                    pending.append((hdr, sp, orgs, wt, div, ms, r["cy"]))  # あとで表全体の欄で合わせ直す
                    continue
                emit(sp, pls, orgs, wt, div, ms, r["cy"])
                continue
            if len(og) <= len(hdr) or labeled:  # 「氏 名」「所 属」の表は、英語の所属(「Sports Design Lab」)が離れて書かれていても列で分ける
                # 見出しが列ごとにある表:名前と所属を、いちばん近い見出しの列に入れる
                hs = sorted(hdr)
                cols = [dict(names=[], orgs=[], pl=h[1]) for h in hs]
                ext = [[] for _ in hs]  # 列ごとの名前の左右の端
                for w in cand:
                    cx = (w["x0"] + w["x1"]) / 2
                    k = min(range(len(hs)), key=lambda k: abs(hs[k][0] - cx))
                    cols[k]["names"].append(w["t"]); ext[k] += [w["x0"], w["x1"]]
                # 「氏 名」「所 属」の表は、所属を名前の真ん中にいちばん近い列に入れる(見出しの「1 位」の位置は列の真ん中からずれている)
                cen = [(min(e) + max(e)) / 2 if labeled and e else h[0] for e, h in zip(ext, hs)]
                for w in orgs:
                    cx = (w["x0"] + w["x1"]) / 2
                    cols[min(range(len(hs)), key=lambda k: abs(cen[k] - cx))]["orgs"].append(w["t"])
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
    # 見出しと欄が合わなかった行は、同じ表のほかの行も合わせた欄の位置で、もう一度見出しと合わせる。
    # 入賞者のいない欄があると、その行だけでは欄の位置が分からないため(2018年天皇杯の女子)。合わなければ使わない
    for hdr, sp, orgs, wt, dv, ms, cy in pending:
        cs = sorted(grid[id(hdr)])
        cols = []
        for cx in cs:
            if cols and cx - cols[-1][-1] < 15:
                cols[-1].append(cx)
            else:
                cols.append([cx])
        cols = [sum(c) / len(c) for c in cols]
        at = [min(range(len(cols)), key=lambda k: abs(cols[k] - cx)) for cx, _ in sp]
        if len(set(at)) != len(at) or any(abs(cols[k] - cx) > 15 for k, (cx, _) in zip(at, sp)):
            continue
        pls = places_by_header(hdr, cols, [k in at for k in range(len(cols))])
        if pls is None:
            continue
        emit(sp, [pls[k] for k in at], orgs, wt, dv, ms, cy)
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


def parse_table(pdf):
    """1行に1人ずつ「階級 順位 姓 名 所属」と並んだ表(2020年全日本大学グレコローマン選手権の個人成績表など)から取り出す。
    スタイルは書かれていないので空にする(大会の決まったスタイルを使う)"""
    text = subprocess.run(["pdftotext", "-layout", pdf, "-"], capture_output=True, text=True).stdout
    res = []
    for line in text.split("\n"):
        m = re.match(r"^\s*(\d{2,3})\s+(優勝|第([1-8])位)\s+(.+?)\s{2,}(\S+)\s*$", unicodedata.normalize("NFKC", line))
        if not m:
            continue
        name = " ".join(m.group(4).split())
        res.append(dict(div="", style="", weight=m.group(1) + "kg", place=m.group(3) or "1", name=name, org=m.group(5)))
    return res
