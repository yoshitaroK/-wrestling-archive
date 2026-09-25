"""
技術動画チャンネル(tech_channels.json)の動画を「大会/技術/その他」に振り分ける共通ルール。
update_site.py(大会側に混ぜる動画を選ぶ)と build_pages.py(技術動画ページ)の両方で使う。

優先順位:
1. tech_overrides.json の指定(use: "tournament" / "technique" / "hide"、または category / hide)
2. タイトルの言葉による自動判定
   - お知らせ・記念・スパーリングなど → その他(載せない)
   - 大会名や「〇回戦」「決勝」など → 大会(大会ページへ)
   - 技術の言葉(tech_categories.json のキーワード) → 技術(技術動画ページへ)
   - どれでもない → その他(載せない。build_report.json に一覧が出る)
"""
import json
import os
import re
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))

TOURNAMENT_WORDS = ["大会", "選手権", "杯", "オープン", "OPEN", "予選", "選考会", "回戦", "決勝", "準決勝", "3位",
                    "初戦", "プレーオフ", "王座", "新人戦", "団体戦", "Aマット", "Bマット", "マッチ", "ベテランズ", "マスターズ"]
OTHER_WORDS = ["周年", "よろしく", "お世話", "記念", "ライブ配信", "スパーリング", "対決", "保護者"]


def norm(t):
    t = unicodedata.normalize("NFKC", str(t or "")).lower()
    t = "".join(chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c for c in t)
    return re.sub(r"\s+", "", t)


def load_json(name, default, root=HERE):
    try:
        with open(os.path.join(root, name), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


class Sorter:
    def __init__(self, root=HERE):
        cfg = load_json("tech_categories.json", {"categories": []}, root)
        self.cats = cfg.get("categories", [])
        self.display_order = cfg.get("display_order", [])
        self.rules = [(c["slug"], [norm(k) for k in c.get("keywords", []) if k]) for c in self.cats]
        self.valid = {c["slug"] for c in self.cats}
        ov = load_json("tech_overrides.json", {"video_overrides": []}, root)
        self.ov = {o["video_id"]: o for o in ov.get("video_overrides", []) if o.get("video_id")}
        self.t_words = [norm(w) for w in TOURNAMENT_WORDS]
        self.o_words = [norm(w) for w in OTHER_WORDS]

    def tech_category(self, title):
        k = norm(title)
        for slug, kws in self.rules:
            if any(x in k for x in kws):
                return slug
        return None

    def judge(self, vid, title):
        """戻り値: (use, category, basis)  use = tournament / technique / other / hide"""
        o = self.ov.get(vid)
        if o:
            if o.get("hide") or o.get("use") == "hide":
                return "hide", None, "manual"
            if o.get("use") == "tournament" or o.get("tournament"):
                return "tournament", None, "manual"
            if o.get("category") in self.valid:
                return "technique", o["category"], "manual"
            if o.get("use") == "other":
                return "other", None, "manual"
        k = norm(title)
        if any(x in k for x in self.o_words):
            return "other", None, "auto"
        if any(x in k for x in self.t_words):
            return "tournament", None, "auto"
        cat = self.tech_category(title)
        if cat:
            return "technique", cat, "auto"
        return "other", None, "auto"
