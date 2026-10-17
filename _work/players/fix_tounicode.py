"""文字の対応表(ToUnicode)が空の PDF(2019年明治杯の入賞者一覧など)に、PDF に埋め込まれたフォント自身の対応表(cmap)から作った対応表を入れて、文字を読めるようにする。
使い方: python3 fix_tounicode.py 元のPDF 直したPDF(同じでもよい)。pypdf と fontTools が要る(pip install pypdf fonttools)"""
import io, os, sys
import pypdf
from pypdf.generic import NameObject, DecodedStreamObject
from fontTools.ttLib import TTFont

def cmap_text(m):
    items = sorted(m.items())
    out = ["/CIDInit /ProcSet findresource begin 12 dict begin begincmap",
           "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
           "/CMapName /Adobe-Identity-UCS def /CMapType 2 def",
           "1 begincodespacerange <0000> <FFFF> endcodespacerange"]
    for i in range(0, len(items), 100):
        chunk = items[i:i + 100]
        out.append(f"{len(chunk)} beginbfchar")
        for gid, u in chunk:
            out.append(f"<{gid:04X}> <{''.join(f'{ord(c):04X}' if ord(c) < 0x10000 else '' for c in u)}>")
        out.append("endbfchar")
    out += ["endcmap CMapName currentdict /CMap defineresource pop end end"]
    return "\n".join(out).encode()

src, dst = sys.argv[1], sys.argv[2]
r = pypdf.PdfReader(src); w = pypdf.PdfWriter(clone_from=r)
done = set()
for page in w.pages:
    for name, ref in page["/Resources"]["/Font"].items():
        f = ref.get_object()
        if f.get("/Subtype") != "/Type0" or id(f) in done:
            continue
        d = f["/DescendantFonts"][0].get_object()
        if d.get("/CIDToGIDMap") != "/Identity":
            sys.exit("CIDToGIDMap が Identity ではない")
        tt = TTFont(io.BytesIO(d["/FontDescriptor"].get_object()["/FontFile2"].get_object().get_data()), fontNumber=0)
        order = tt.getGlyphOrder()
        gid_of = {g: i for i, g in enumerate(order)}
        # 同じ字形が複数の文字に使われるとき(「人」と部首の「⼈」など)は、ふつうの漢字・かな・英数字を選ぶ
        def rank(code):
            if 0x4E00 <= code <= 0x9FFF: return 0
            if 0x3040 <= code <= 0x30FF or 0xFF00 <= code <= 0xFFEF or 0x20 <= code <= 0x7E: return 1
            if 0x3000 <= code <= 0x303F: return 2
            return 3
        m = {}
        for code, gname in tt.getBestCmap().items():
            g = gid_of[gname]
            if g not in m or (rank(code), code) < (rank(ord(m[g])), ord(m[g])):
                m[g] = chr(code)
        s = DecodedStreamObject(); s.set_data(cmap_text(m))
        f[NameObject("/ToUnicode")] = w._add_object(s)
        done.add(id(f))
w.write(dst + ".tmp")
os.replace(dst + ".tmp", dst)  # 元と同じファイルに書くときも、読み終えてから置きかえる
print("ok", src, len(done))
