"""文字の対応表(ToUnicode)もフォントの cmap も無い PDF(明治杯 2025 の入賞者一覧など)に、同じフォントを使った
ほかの PDF(対応表あり)の字形と形を照らし合わせて、対応表を作る。
同じフォントファイル(MS Pゴシックなど)の同じ字は、PDF ごとに字の一部だけ入れた形(サブセット)でも、輪郭の座標が同じことを使う。
参照の PDF どうしで同じ形に別の字が付いているもの(「一」と「ー」など)は使わない。分からない字は「〓」にする(build_candidates.py がその行を使わない)。
使い方: python3 fix_glyphs.py 直すPDF 出力PDF 参照PDF...(すでに対応表があるフォントだけの PDF は何もしない)
pypdf と fontTools が要る(pip install pypdf fonttools)"""
import io, os, re, sys, hashlib
import pypdf
from pypdf.generic import NameObject, DecodedStreamObject
from fontTools.ttLib import TTFont

def glyph_key(tt, gname):
    g = tt["glyf"][gname]
    if g.isComposite():
        return None
    if not hasattr(g, "coordinates") or g.numberOfContours <= 0:
        return None
    coords = tuple(tuple(c) for c in g.coordinates)
    return hashlib.sha1(repr((coords, tuple(g.endPtsOfContours), tuple(g.flags))).encode()).hexdigest()

def parse_tounicode(data):
    m = {}
    txt = data.decode("latin1")
    for block in re.findall(r"beginbfchar(.*?)endbfchar", txt, re.S):
        for a, b in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            m[int(a, 16)] = "".join(chr(int(b[i:i + 4], 16)) for i in range(0, len(b), 4))
    for block in re.findall(r"beginbfrange(.*?)endbfrange", txt, re.S):
        for a, b, c in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
            for k in range(int(a, 16), int(b, 16) + 1):
                m[k] = chr(int(c, 16) + k - int(a, 16))
    return m

def fonts(reader):
    seen = set()
    for page in reader.pages:
        res = page.get("/Resources") or {}
        for name, ref in (res.get("/Font") or {}).items():
            f = ref.get_object()
            if f.get("/Subtype") != "/Type0" or id(f) in seen:
                continue
            seen.add(id(f))
            d = f["/DescendantFonts"][0].get_object()
            ff = d["/FontDescriptor"].get_object().get("/FontFile2")
            if ff is None:
                continue
            yield f, d, TTFont(io.BytesIO(ff.get_object().get_data()))

def cid2gid(d, tt):
    m = d.get("/CIDToGIDMap")
    if m is None or m == "/Identity":
        return lambda c: c
    data = m.get_object().get_data()
    return lambda c: int.from_bytes(data[2 * c:2 * c + 2], "big")

target = pypdf.PdfReader(sys.argv[1])
if all("/ToUnicode" in f for f, d, tt in fonts(target)):
    print("対応表あり(直さない)", sys.argv[1], file=sys.stderr); sys.exit(0)

ref = {}
conflict = set()
def ref_fonts(path):
    try:
        yield from fonts(pypdf.PdfReader(path))
    except Exception as ex:  # 読めない参照の PDF は使わない
        print("参照に使えない", path, ex, file=sys.stderr)

for p in sys.argv[3:]:
    for f, d, tt in ref_fonts(p):
        if "/ToUnicode" not in f:
            continue
        tu = parse_tounicode(f["/ToUnicode"].get_object().get_data())
        order = tt.getGlyphOrder(); c2g = cid2gid(d, tt)
        for cid, u in tu.items():
            g = c2g(cid)
            if g >= len(order):
                continue
            k = glyph_key(tt, order[g])
            if not k or not u.strip():
                continue
            if k in ref and ref[k] != u:
                conflict.add(k)
            ref.setdefault(k, u)
print("参照の字形", len(ref), "食い違い", len(conflict), file=sys.stderr)

w = pypdf.PdfWriter(clone_from=target)
miss = 0; hit = 0
for f, d, tt in fonts(w):
    order = tt.getGlyphOrder()
    m = {}
    for gid, gname in enumerate(order):
        k = glyph_key(tt, gname)
        if k and k in ref and k not in conflict:
            m[gid] = ref[k]; hit += 1
        elif k:
            m[gid] = "〓"; miss += 1  # 分からない字は「〓」にする(読み取った名前に〓があれば使わない)
    lines = ["/CIDInit /ProcSet findresource begin 12 dict begin begincmap",
             "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
             "/CMapName /Adobe-Identity-UCS def /CMapType 2 def", "1 begincodespacerange <0000> <FFFF> endcodespacerange"]
    items = sorted(m.items())
    for i in range(0, len(items), 100):
        ch = items[i:i + 100]
        lines.append(f"{len(ch)} beginbfchar")
        lines += [f"<{g:04X}> <{''.join(f'{ord(c):04X}' for c in u)}>" for g, u in ch]
        lines.append("endbfchar")
    lines.append("endcmap CMapName currentdict /CMap defineresource pop end end")
    s = DecodedStreamObject(); s.set_data("\n".join(lines).encode())
    f[NameObject("/ToUnicode")] = w._add_object(s)
w.write(sys.argv[2] + ".tmp")
os.replace(sys.argv[2] + ".tmp", sys.argv[2])  # 元と同じファイルに書くときも、読み終えてから置きかえる
print("一致", hit, "見つからない字形", miss, file=sys.stderr)
