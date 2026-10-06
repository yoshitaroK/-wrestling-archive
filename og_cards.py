"""選手ページの SNS 用画像(X・LINE などに URL を貼ったときに出る横長の画像)を作る。

- 1200×630。紺の地に、名前・所属・代表の印・直近7年の大会成績・サイト名を文字だけで描く
- 日本語版は assets/og/players/<選手ID>.png、英語版は <選手ID>-en.png
- 中身が変わった選手の分だけ作り直す(manifest-ja.json / manifest-en.json に中身の指紋を残す)
- 公開をやめた選手の画像は消す
- Pillow やフォントが無い・失敗したときは空を返し、ページは今までどおり動画のサムネイルを使う(毎朝の更新は止めない)
"""
import hashlib
import json
import math
import os
import re

import i18n
from i18n import L

OUT_DIR = os.path.join("assets", "og", "players")
FONT_DIR = "fonts"
FONT_BOLD = "NotoSansJP-700.ttf"
FONT_BLACK = "NotoSansJP-900.ttf"
# 見た目を変えたらこの数字を上げる(全員分が作り直される)
VERSION = 4
YEARS = 7
W, H = 1200, 630
PAD = 64

NAVY_TOP, NAVY_BOTTOM = (7, 17, 31), (12, 29, 56)
GRAD_A, GRAD_B = (19, 41, 75), (43, 79, 138)
RED = (255, 68, 88)
WHITE = (255, 255, 255)
SUB = (195, 205, 224)
MUTED = (134, 150, 178)
PLAN = (140, 184, 238)
ROW_LINE = (35, 56, 92)

# 画像の中では大会名を短くする(大会名の欄が狭いため)。ここに無い大会はサイトの大会名のまま
SHORT = {
    "明治杯全日本選抜選手権": ("明治杯", "Meiji Cup"),
    "天皇杯全日本選手権": ("天皇杯", "Emperor's Cup"),
    "東日本学生選手権（春季大会）": ("東日本(春)", "East Japan Coll. (Spring)"),
    "東日本学生選手権（秋季大会）": ("東日本(秋)", "East Japan Coll. (Autumn)"),
    "全日本大学選手権": ("全日本大学", "All Japan Univ."),
    "全日本大学グレコローマン選手権": ("全日本大学グレコ", "All Japan Univ. Greco"),
    "全日本学生選手権（インカレ）": ("インカレ", "Intercollegiate"),
    "全日本社会人選手権": ("全日本社会人", "All Japan Working Adults"),
    "オリンピック(パリ)": ("オリンピック(パリ)", "Olympics (Paris)"),
    "オリンピック(東京 2020)": ("オリンピック(東京)", "Olympics (Tokyo)"),
    "世界選手権": ("世界選手権", "World Championships"),
    "U23世界選手権": ("U23世界選手権", "U23 World Championships"),
}
STYLE_SHORT = {"フリースタイル": ("フリー", "FS"), "グレコローマン": ("グレコ", "GR"), "女子": ("女子", "WW")}
JP = re.compile(r"[぀-ヿ一-鿿々〆]")

_fonts = {}


def font(name, size):
    key = (name, size)
    if key not in _fonts:
        from PIL import ImageFont
        _fonts[key] = ImageFont.truetype(os.path.join(_root, FONT_DIR, name), size)
    return _fonts[key]


_root = "."


def style_short(s):
    """成績のスタイルを短くする(例: フリースタイル → フリー / FS)。新人戦は大会名の側に付ける"""
    base = s.replace("新人戦", "").strip()
    ja, en = STYLE_SHORT.get(base, (base, i18n.N(base)))
    return L(ja, en)


def tier(r, ctx, players):
    """大会の格。オリンピック → 世界選手権 → U23世界選手権 → 天皇杯・明治杯 → そのほか"""
    name = r.get("大会名", "")
    if name in players.OLYMPICS:
        return 0
    if name == "世界選手権":
        return 1
    if name == "U23世界選手権":
        return 2
    ev = ctx["events_by_id"].get(r.get("開催回ID", ""))
    sname = (ctx["S"].get(ev["series"], {}).get("name", "") if ev else "") or name
    return 3 if ("天皇杯" in sname or "明治杯" in sname) else 4


def short_tournament(r, ctx, bp, players):
    """画像に載せる短い大会名(新人戦は後ろに付ける)"""
    name = r.get("大会名", "")
    ev = ctx["events_by_id"].get(r.get("開催回ID", ""))
    s = ctx["S"].get(ev["series"]) if ev and name not in players.OLYMPICS and name not in players.WORLDS else None
    key = s["name"] if s else name
    if key in SHORT:
        t = L(*SHORT[key])
    elif s:
        t = bp.series_name(s)
    else:
        t = players.tournament_name(r, ctx, bp)
    if (r.get("スタイル") or "").startswith("新人戦"):
        t += L(" 新人戦", " (Rookie)")
    return t


def rank_num(v):
    m = re.match(r"^(\d+)位$", v or "")
    return int(m.group(1)) if m else 999


def card_spec(p, ctx, bp, players, this_year):
    """画像に描く中身(文字だけ)。この中身が変わったときだけ画像を作り直す"""
    first = this_year - YEARS + 1
    rows = [r for r in p["results"] if (r.get("開催年") or "0").isdigit() and first <= int(r["開催年"]) <= this_year]
    rows.sort(key=lambda r: (rank_num(r.get("成績")), tier(r, ctx, players), -int(r["開催年"]), players.weight_key(r.get("階級"))))
    results = [[r["開催年"], short_tournament(r, ctx, bp, players),
                f"{style_short(r.get('スタイル', ''))} {r.get('階級', '')}".strip(), players.rank(r.get("成績", "")),
                rank_num(r.get("成績")) <= 3] for r in rows]
    names = {r.get("大会名", "") for r in p["results"]}
    badges = [["oly", L(ja, en)] for k, (ja, en, _) in players.OLYMPICS.items() if k in names]
    for k, (ja, en, _) in players.WORLDS.items():
        ys = sorted({r.get("開催年", "") for r in p["results"] if r.get("大会名") == k})
        if ys:
            badges.append(["wc", L(ja + "(" + "・".join(ys) + ")", en + " (" + ", ".join(ys) + ")")])
    club = i18n.N(p["club"]) if p["club"] else ""
    if i18n.en() and JP.search(club or ""):
        club = ""  # 英語版に日本語を出さない(所属の英語名が無いとき)
    spec = {"v": VERSION, "lang": "en" if i18n.en() else "ja", "site": bp.site_name(), "name": players.pname(p),
            "kana": "" if i18n.en() else p["kana"], "club": club, "badges": badges, "results": results,
            "nr": len(p["results"]), "nv": len(p["videos"]),
            "years": f"{first}–{this_year}"}
    if i18n.en():
        # 万一、英語版の画像に日本語が混ざるときは、その文字列を出さない
        spec["results"] = [x for x in spec["results"] if not any(JP.search(c) for c in x[:4])]
        spec["badges"] = [b for b in spec["badges"] if not JP.search(b[1])]
    return spec


def fit(draw, text, f, width):
    """幅に収まらない文字は末尾を … にする"""
    if draw.textlength(text, font=f) <= width:
        return text
    while text and draw.textlength(text + "…", font=f) > width:
        text = text[:-1]
    return text + "…"


def render(spec, logo):
    from PIL import Image, ImageDraw
    en = spec["lang"] == "en"
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    d.rectangle([0, 0, W, H], fill=NAVY_BOTTOM)
    d.rectangle([0, 0, W, 104], fill=NAVY_TOP)  # 上の帯(ロゴとサイト名)
    d.rectangle([0, 0, 10, H], fill=RED)  # 左の赤い帯(中継のテロップ風)

    # 上:ロゴとサイト名
    x0 = PAD
    if logo is not None:
        lh = 50
        lw = round(logo.width * lh / logo.height)
        im.paste(logo.resize((lw, lh), Image.LANCZOS), (x0, 34), logo.resize((lw, lh), Image.LANCZOS))
        tx = x0 + lw + 18
    else:
        tx = x0
    d.text((tx, 40), spec["site"], font=font(FONT_BOLD, 22), fill=WHITE)
    d.text((tx, 68), "Official · Japan Wrestling Channel" if en else "Japan Wrestling Channel 公式", font=font(FONT_BOLD, 16), fill=SUB)

    # 名前・ふりがな
    y = 120
    name_f = font(FONT_BLACK, 76)
    name = fit(d, spec["name"], name_f, W - PAD * 2)
    d.text((x0, y), name, font=name_f, fill=WHITE)
    nw = d.textlength(name, font=name_f)
    if spec["kana"] and nw + 40 < W - PAD * 2:
        kf = font(FONT_BOLD, 26)
        d.text((x0 + nw + 24, y + 46), fit(d, spec["kana"], kf, W - PAD * 2 - nw - 24), font=kf, fill=SUB)
    y += 104
    if spec["club"]:
        cf = font(FONT_BOLD, 26)
        d.text((x0, y), fit(d, spec["club"], cf, W - PAD * 2), font=cf, fill=SUB)
        y += 44

    # 代表の印(オリンピックは紺のグラデーション+赤い枠、世界選手権・U23 は白抜き)
    if spec["badges"]:
        bf = font(FONT_BOLD, 20)
        bx = x0
        by = y + 4
        for kind, text in spec["badges"]:
            tw = d.textlength(text, font=bf)
            bw, bh = round(tw) + 52, 38
            if bx + bw > W - PAD:
                break
            if kind == "oly":
                pill = Image.new("RGB", (bw, bh))
                pd = ImageDraw.Draw(pill)
                for i in range(bw):
                    t = i / max(bw - 1, 1)
                    pd.line([(i, 0), (i, bh)], fill=tuple(round(a + (b - a) * t) for a, b in zip(GRAD_A, GRAD_B)))
                mask = Image.new("L", (bw, bh), 0)
                ImageDraw.Draw(mask).rounded_rectangle([0, 0, bw - 1, bh - 1], radius=bh // 2, fill=255)
                im.paste(pill, (bx, by), mask)
                d.rounded_rectangle([bx, by, bx + bw - 1, by + bh - 1], radius=bh // 2, outline=RED, width=2)
                dot, fg = RED, WHITE
            else:
                d.rounded_rectangle([bx, by, bx + bw - 1, by + bh - 1], radius=bh // 2, outline=PLAN, width=2)
                dot, fg = PLAN, WHITE
            d.ellipse([bx + 16, by + bh // 2 - 5, bx + 26, by + bh // 2 + 5], fill=dot)
            d.text((bx + 36, by + bh // 2), text, font=bf, fill=fg, anchor="lm")
            bx += bw + 12
        y = by + bh + 22

    # 大会成績(直近7年すべて)。6件までは1列、それより多いときは2列
    foot_y = H - 64
    res = spec["results"]
    if res:
        hf = font(FONT_BOLD, 17)
        d.text((x0, y), (f"Results {spec['years']}" if en else f"大会成績({spec['years']}年)"), font=hf, fill=RED)
        y += 30
        cols = 1 if len(res) <= 6 else 2
        per_col = math.ceil(len(res) / cols)
        avail = foot_y - 18 - y
        rh = max(22, min(44, avail // per_col))
        size = max(15, min(25, rh - 12))
        rf, yf = font(FONT_BOLD, size), font(FONT_BOLD, size)
        gap = 32
        cw = (W - PAD * 2 - gap * (cols - 1)) // cols
        for i, (year, tname, cat, rk, top) in enumerate(res):
            c, r = divmod(i, per_col)
            cx = x0 + c * (cw + gap)
            cy = y + r * rh
            if cy + rh > foot_y - 10:
                break
            mid = cy + rh // 2
            d.line([(cx, cy + rh - 1), (cx + cw, cy + rh - 1)], fill=ROW_LINE, width=1)
            d.text((cx, mid), year, font=yf, fill=MUTED, anchor="lm")
            yw = d.textlength("0000", font=yf) + 14
            rkw = d.textlength(rk, font=rf)
            d.text((cx + cw, mid), rk, font=rf, fill=RED if top else WHITE, anchor="rm")
            catw = min(d.textlength(cat, font=rf), cw * 0.32)
            cat_t = fit(d, cat, rf, catw)
            d.text((cx + cw - rkw - 16, mid), cat_t, font=rf, fill=SUB, anchor="rm")
            tw = cw - yw - rkw - catw - 32
            d.text((cx + yw, mid), fit(d, tname, rf, tw), font=rf, fill=WHITE, anchor="lm")
    else:
        bigf = font(FONT_BLACK, 40)
        d.text((x0, y + 10), (f"{i18n.plural(spec['nv'], 'match video')}" if en else f"試合動画 {spec['nv']}本"), font=bigf, fill=WHITE)

    # 下:件数とURL
    d.line([(x0, foot_y), (W - PAD, foot_y)], fill=RED, width=3)
    ff = font(FONT_BOLD, 20)
    count = (f"{i18n.plural(spec['nr'], 'result')} · {i18n.plural(spec['nv'], 'match video')}" if en
             else f"大会成績{spec['nr']}件・試合動画{spec['nv']}本")
    d.text((x0, foot_y + 32), count, font=ff, fill=SUB, anchor="lm")
    d.text((W - PAD, foot_y + 32), "japanwrestlingchannel.com", font=ff, fill=RED, anchor="rm")
    return im


class Cards:
    """1つの言語の分の画像をまとめて作る(players.build から使う)"""

    def __init__(self, root, this_year):
        global _root
        _root = root
        self.root, self.year = root, this_year
        self.suffix = "-en" if i18n.en() else ""
        self.dir = os.path.join(root, OUT_DIR)
        self.mpath = os.path.join(self.dir, f"manifest-{'en' if i18n.en() else 'ja'}.json")
        self.ok = True
        self.made = self.kept = 0
        self.errors = []
        try:
            from PIL import Image
            for f in (FONT_BOLD, FONT_BLACK):
                font(f, 20)
            lp = os.path.join(root, "assets", "logo.png")
            self.logo = Image.open(lp).convert("RGBA") if os.path.exists(lp) else None
        except Exception as ex:  # Pillow かフォントが無い
            self.ok = False
            self.errors.append(f"SNS用画像を作れません: {ex}")
            return
        try:
            with open(self.mpath, encoding="utf-8") as f:
                self.manifest = json.load(f)
        except (OSError, ValueError):
            self.manifest = {}
        self.new_manifest = {}
        os.makedirs(self.dir, exist_ok=True)

    def url(self, p, ctx, bp, players):
        """この選手の画像を(必要なら作って)URL を返す。作れないときは空"""
        if not self.ok:
            return ""
        try:
            spec = card_spec(p, ctx, bp, players, self.year)
            h = hashlib.sha1(json.dumps(spec, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:10]
            fn = f"{p['id']}{self.suffix}.png"
            path = os.path.join(self.dir, fn)
            if self.manifest.get(p["id"]) != h or not os.path.exists(path):
                im = render(spec, self.logo)
                # 色数を減らした PNG にして軽くする(文字と単色の図形だけなので見た目はほぼ変わらない)
                im.quantize(colors=96, method=2, dither=0).save(path, optimize=True)
                self.made += 1
            else:
                self.kept += 1
            self.new_manifest[p["id"]] = h
            return f"{bp.SITE}/{OUT_DIR.replace(os.sep, '/')}/{fn}?v={h}"
        except Exception as ex:
            self.errors.append(f"{p['id']}: {ex}")
            return ""

    def finish(self):
        """公開をやめた選手の画像を消し、manifest を書く"""
        if not self.ok:
            return {"made": 0, "kept": 0, "removed": 0, "errors": self.errors}
        removed = 0
        for fn in os.listdir(self.dir):
            m = re.match(r"^(.+?)(-en)?\.png$", fn)
            if m and (m.group(2) or "") == self.suffix and m.group(1) not in self.new_manifest:
                os.remove(os.path.join(self.dir, fn))
                removed += 1
        with open(self.mpath, "w", encoding="utf-8") as f:
            json.dump(self.new_manifest, f, ensure_ascii=False, sort_keys=True, indent=0)
        return {"made": self.made, "kept": self.kept, "removed": removed, "errors": self.errors[:20]}
