"""
レスリング配信アーカイブ: 動画データと大会マスターから data.json を作る。

入力
  videos_raw   : YouTube API から取得した動画リスト (update_site.py が渡す)
  master_events.json   : 大会開催マスター (開催回 = event)
  series_aliases.json  : 系列と検索別名・誤統合防止ルール
  overrides.json       : 手動修正 (再ビルドしても必ず優先される)
  legacy_map.json      : 旧URL(#series/ #occurrence/)の誘導表 (任意)

方針
  - 元タイトル・動画ID・公開日時は加工せず保持する。
  - 大会名の判定は照合用キー(NFKC等で正規化)で行い、表示用には元タイトルを使う。
  - 開催回は「タイトルの日付 → タイトルの年・年度(+回数) → 配信日が開催期間内」の順で決める。
    動画の公開日だけ・近さだけでは開催回を確定しない。
  - 根拠が足りない動画は candidate(確認待ち) か unmatched(対応未確認) に残す。
  - マスターにない大会の動画は削除せず、動画タイトルから作る「未収録の大会」として保持する。
"""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))

# ---------------------------------------------------------------------------
# 文字列の正規化
# ---------------------------------------------------------------------------
ZERO_WIDTH = re.compile(r"[\u200b-\u200f\u2060\ufeff]")
DASHES = str.maketrans({c: "-" for c in "‐‑‒–—―−ｰ"})


def norm_text(s: str) -> str:
    """表示・抽出用の正規化(元タイトルは別に保持する)。"""
    if not s:
        return ""
    s = s.replace("\u309b", "\u3099").replace("\u309c", "\u309a")  # 分離濁点・半濁点
    s = unicodedata.normalize("NFKC", s)
    s = ZERO_WIDTH.sub("", s)
    s = s.translate(DASHES)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def match_key(s: str) -> str:
    """大会名判定用のキー。空白と『レスリング』を除き、よくある誤記を直す。"""
    t = norm_text(s)
    t = t.replace("レスリンク", "レスリング").replace("リーク", "リーグ")
    t = re.sub(r"\s+", "", t)
    t = t.replace("レスリング", "")
    t = t.upper().replace("U-", "U")
    return t


def kata(s: str) -> str:
    return "".join(chr(ord(c) + 0x60) if "\u3041" <= c <= "\u3096" else c for c in s)


def search_key(s: str) -> str:
    """検索用キー(画面側 JS と同じ規則)。"""
    t = norm_text(s).lower()
    t = kata(t)
    t = re.sub(r"[\s・･/／「」『』()（）\[\]【】]", "", t)
    t = t.replace("れすりんぐ", "").replace("レスリング", "")
    return t


# ---------------------------------------------------------------------------
# タイトルから情報を抜き出す
# ---------------------------------------------------------------------------
ERA_BASE = {"令和": 2018, "平成": 1988, "昭和": 1925}


def era_year(era: str, n: str) -> int:
    return ERA_BASE[era] + (1 if n == "元" else int(n))


def fy_label(fy: int) -> str:
    if fy >= 2019:
        n = fy - 2018
        return "令和元年度" if n == 1 else f"令和{n}年度"
    return f"平成{fy - 1988}年度"


def fiscal_year(d: date) -> int:
    return d.year if d.month >= 4 else d.year - 1


def valid_date(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None


def extract_meta(title: str) -> dict:
    t = norm_text(title)
    meta = {"full_date": None, "md": None, "cal_year": None, "fy": None,
            "kai": None, "day_code": None, "mat": None, "day_label": None}
    rest = t

    # 完全な日付
    m = re.search(r"(?<!\d)(20[12]\d)(\d{2})(\d{2})(?!\d)", rest)
    if m and valid_date(*m.groups()):
        meta["full_date"] = valid_date(*m.groups())
        rest = rest.replace(m.group(0), " ")
    m = re.search(r"(20[12]\d)年(\d{1,2})月(\d{1,2})日", rest)
    if not meta["full_date"] and m and valid_date(*m.groups()):
        meta["full_date"] = valid_date(*m.groups())
        rest = rest.replace(m.group(0), " ")
    # 月日
    m = re.search(r"(?<!\d)(\d{1,2})月(\d{1,2})日", rest)
    if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
        meta["md"] = (int(m.group(1)), int(m.group(2)))
        rest = rest.replace(m.group(0), " ")
    else:
        m = re.search(r"(?<![\d.,:])(\d{1,2})/(\d{1,2})(?![\d/])", rest)
        if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
            meta["md"] = (int(m.group(1)), int(m.group(2)))
            rest = rest.replace(m.group(0), " ")

    # 和暦の年度・年
    m = re.search(r"(令和|平成|昭和)\s*(元|\d{1,2})\s*年度", rest)
    if m:
        meta["fy"] = era_year(m.group(1), m.group(2))
    else:
        m = re.search(r"(令和|平成)\s*(元|\d{1,2})\s*年(?!度)", rest)
        if m:
            meta["cal_year"] = era_year(m.group(1), m.group(2))
        else:
            m = re.search(r"(?:^|[^A-Za-z])(?:H|平)(\d{2})年度", rest)
            if m:
                meta["fy"] = 1988 + int(m.group(1))
    # 西暦の年度・年
    if meta["fy"] is None and meta["cal_year"] is None:
        m = re.search(r"(?<!\d)(20[12]\d)\s*年度", rest)
        if m:
            meta["fy"] = int(m.group(1))
        else:
            m = re.search(r"(?<!\d)(20[12]\d)(?!\d)", rest)
            if m:
                meta["cal_year"] = int(m.group(1))

    m = re.search(r"第\s*(\d{1,3})\s*回", rest)
    if m:
        meta["kai"] = int(m.group(1))

    # 日目
    m = re.search(r"([1-5一二三四五])\s*日目|第([1-5])日目?", rest)
    if m:
        v = m.group(1) or m.group(2)
        meta["day_label"] = "一二三四五".index(v) + 1 if v in "一二三四五" else int(v)

    # マット・配信番号 (確認できた形だけを分離し、名前からは消さない)
    m = re.search(r"([A-E])\s*マット|([1-4])\s*マット", t)
    if m:
        meta["mat"] = m.group(1) or m.group(2)
    else:
        m = re.match(r"^\s*(\d{1,2})\s*-\s*([A-E]|\d)(?![0-9A-Za-z])", t) or \
            re.match(r"^\s*(\d{1,2})([A-E])(?![A-Za-z])", t)
        if m:
            meta["day_code"] = int(m.group(1))
            meta["mat"] = m.group(2)
        else:
            m = re.match(r"^\s*([A-E])-?(\d{1,2})(?!\d)", t) or \
                re.search(r"20[12]\d年([A-E])-(\d{1,2})", t)
            if m:
                meta["mat"] = m.group(1)
                meta["day_code"] = int(m.group(2))
            else:
                m = re.match(r"^\s*([A-E])(?=[\s\u3040-\u9fff])", t)
                if m:
                    meta["mat"] = m.group(1)
    if meta["day_code"] and not 1 <= meta["day_code"] <= 31:
        meta["day_code"] = None
    return meta


def extract_style(title: str):
    t = norm_text(title)
    styles = set()
    if re.search(r"フリー|(?<![A-Za-z])FS\s?\d|(?<![A-Za-z])F\s?\d{2,3}(?!\d)", t):
        styles.add("フリー")
    if re.search(r"グレコ|(?<![A-Za-z])GR?\s?\d{2,3}(?!\d)", t):
        styles.add("グレコ")
    if re.search(r"女子|(?<![A-Za-z])WW?\s?\d{2}(?!\d)", t):
        styles.add("女子")
    return sorted(styles)


def extract_kind(title: str) -> str:
    t = norm_text(title)
    if re.search(r"lesson|レッスン|ルール解説|育成映像|オープニング|クロージング|コレクトホールド", t, re.I):
        return "other"
    if re.search(r"インタビュ|コメント|囲み取材|総括", t):
        return "interview"
    if re.search(r"抽選会|告知|予告|見どころ|PR動画|アピール|開会式|選手宣誓|進行表|開幕です", t):
        return "announcement"
    if re.search(r"ダイジェスト|ハイライト|DVD|胴上げ", t):
        return "highlight"
    if re.search(r"lesson|レッスン|ルール解説|育成映像|opening|endroll|クロージング|オープニング|"
                 r"コレクトホールド|ターゲットエイジ", t, re.I):
        return "other"
    return "match"


# ---------------------------------------------------------------------------
# 系列の判定(照合キーに対するルール。must_remain_distinct を守る順序)
# ---------------------------------------------------------------------------
def detect_series(k: str):
    """戻り値: (series_id, candidates, rule)。
    series_id が決まらない曖昧なものは candidates に候補を入れる。"""
    has = lambda *ws: all(w in k for w in ws)
    anyof = lambda *ws: any(w in k for w in ws)

    if "日韓" in k:
        return ("japan-korea-highschool", None, "日韓") if "高校" in k else (None, ["japan-korea-highschool"], "日韓(区分不明)")
    if "ビーチ" in k:
        if "沖縄" in k:
            return "beach-okinawa", None, "ビーチ沖縄"
        if "全日本" in k:
            return "beach-national", None, "全日本ビーチ"
        if has("代表", "選考"):
            return "other-5bcfed6f", None, "ビーチ代表選考会"
        if "オープントーナメント" in k:
            return "other-bf538b5b", None, "ビーチオープン"
        return None, None, None
    if "マスターズ" in k:
        return ("masters-kanazawa" if "金沢" in k else "masters"), None, "マスターズ"
    if "U13" in k:
        return "u13", None, "U13"
    if "世界学生" in k:
        return "university-selection", None, "世界学生代表"
    if "アジア競技大会" in k:
        return "other-d6636195", None, "アジア競技大会"
    if "予選会" in k and anyof("全日本選抜", "明治杯"):
        return "meiji-qualifier", None, "全日本選抜予選会"
    if "クイーンズ" in k:
        return "queens-cup", None, "ジュニアクイーンズカップ"

    if "関東" in k:
        if "少年少女" in k:
            return None, None, None
        if "関東中学校選手権" in k:
            return "local-55908", None, "関東中学校選手権"
        if re.search(r"(斎|齋)藤つよし杯", k):
            return "local-262723", None, "齋藤つよし杯"
        if anyof("高校", "高等学校"):
            if "選抜" in k:
                return "regional-関東-qualifier", None, "関東高校選抜"
            if "リーグ" in k:
                return None, None, None
            return "regional-関東-summer", None, "関東高校大会"
        return None, None, None

    if "東日本" in k:
        if "少年少女" in k:
            return None, None, None
        if "リーグ" in k:
            return ("east-women-league" if "女子" in k else "east-league"), None, "東日本リーグ戦"
        if "春" in k:
            return "east-spring", None, "東日本学生・春季"
        if "秋" in k:
            return "east-autumn", None, "東日本学生・秋季"
        if "女子" in k:
            return None, ["east-spring", "east-autumn", "east-women-league"], "東日本学生女子(春秋・リーグ不明)"
        if anyof("学生", "新人"):
            return None, ["east-spring", "east-autumn"], "東日本学生(春季・秋季不明)"
        return None, None, None
    if "西日本" in k:
        if anyof("少年少女", "中学"):
            return None, None, None
        if "リーグ" in k:
            if "春" in k:
                return "west-spring-league", None, "西日本春季リーグ"
            if "秋" in k:
                return "west-autumn-league", None, "西日本秋季リーグ"
            return None, ["west-spring-league", "west-autumn-league"], "西日本リーグ(春秋不明)"
        if "新人" in k:
            return "west-rookie", None, "西日本新人"
        if anyof("選手権", "学生"):
            return "west-championship", None, "西日本学生選手権"

    # 大学・学生 (大学選手権 / インカレ / 大学グレコ は別系列)
    if "全日本大学学生" in k:
        return None, ["intercollegiate", "university-championship", "university-greco"], "全日本大学学生(誤記の可能性)"
    if "全日本大学" in k and "グレコ" in k:
        return "university-greco", None, "全日本大学グレコ"
    if "全日本大学選手権" in k or has("内閣総理大臣杯", "全日本大学"):
        return "university-championship", None, "全日本大学選手権"
    if "全日本学生" in k and "内閣総理大臣杯" in k:
        return None, ["university-championship", "intercollegiate"], "内閣総理大臣杯+全日本学生(矛盾)"
    if re.search(r"全日本学生グレコ[^/]*選手権", k):
        return None, ["intercollegiate", "university-greco"], "全日本学生グレコ(インカレか大学グレコか不明)"
    if "全日本学生選手権" in k or "インカレ" in k:
        return "intercollegiate", None, "全日本学生選手権"

    if "天皇杯" in k:
        return "tenno-cup", None, "天皇杯"
    if anyof("明治杯", "全日本選抜"):
        return "meiji-cup", None, "明治杯全日本選抜"

    # 中学・年代別
    if anyof("中学選抜", "中学生選抜"):
        return "juniorhigh-senbatsu", None, "全国中学選抜"
    u15, u23 = bool(re.search(r"U15", k)), bool(re.search(r"U23", k))
    u1720 = bool(re.search(r"U1[78]|U20", k))
    if u15 and u23:
        return None, ["u15-selection", "u23-selection"], "U15・U23共通案内"
    if u23:
        return "u23-selection", None, "U23"
    if u15:
        return "u15-selection", None, "U15"
    if u1720 or "全日本ジュニア" in k or (anyof("JOC", "ジュニアオリンピック") and anyof("ジュニア", "カデット")):
        return "joc-junior", None, "JOCジュニア"
    if anyof("JOC", "ジュニアオリンピック"):
        return None, ["joc-junior", "u15-selection", "u23-selection", "queens-cup"], "JOC(年代不明)"

    if "全日本選手権" in k:
        return "tenno-cup", None, "全日本選手権"

    # 高校
    if "グレコ" in k and anyof("高校", "高等学校"):
        return "highschool-greco", None, "全国高校生グレコ"
    if anyof("全国高校選抜", "全国高等学校選抜", "風間杯", "高校選抜"):
        return "highschool-senbatsu", None, "全国高校選抜"
    if anyof("インターハイ", "高校総体", "高校総合体育大会", "高等学校総合体育大会"):
        return "interhigh", None, "インターハイ"
    if anyof("全国中学生選手権", "沼尻"):
        return "juniorhigh", None, "全国中学生選手権"

    # 少年少女
    if "全国少年少女選抜" in k:
        return "kids-senbatsu", None, "全国少年少女選抜"
    if "全国少年少女選手権" in k:
        return "kids", None, "全国少年少女選手権"
    if "全国少年少女" in k:
        return None, ["kids", "kids-senbatsu"], "全国少年少女(選抜か通常か不明)"

    if anyof("国体", "国民体育大会", "国民スポーツ大会", "国スポ") and "リハーサル" not in k:
        return "kokutai", None, "国体"
    if "社会人オープン" in k:
        return "shakaijin-open", None, "社会人オープン"
    if "段別" in k:
        return "shakaijin-dan", None, "社会人段別"
    if "社会人選手権" in k:
        return "shakaijin", None, "全日本社会人選手権"
    if "女子オープン" in k:
        return "women-open", None, "全日本女子オープン"
    if "プレーオフ" in k:
        return "national-team-playoff", None, "代表プレーオフ"

    # 地方大会(マスターの local 系列。回数・日付が合う場合だけ採用する)
    if "全自衛隊" in k:
        return "local-122691", None, "全自衛隊大会"
    if "ライオンズ杯" in k:
        return None, ["local-262724", "local-281689"], "ライオンズ杯"
    if "新宿キッズ" in k:
        return None, ["local-263337", "local-282815"], "新宿キッズ"
    if "高槻" in k:
        return None, ["local-264275", "local-283739"], "高槻市長杯"
    if "日野町" in k:
        return "local-264485", None, "日野町少年少女"
    if "日野" in k and "選手権" in k:
        return "local-283989", None, "日野選手権"
    if "堺市" in k:
        return None, ["local-263382", "local-282985"], "堺市少年少女"
    if "茨木" in k:
        return "local-265888", None, "茨木市フェスティバル"
    if "吹田" in k:
        return None, ["local-268771", "local-288834"], "吹田市民"
    if "押立杯" in k and "関西" in k:
        return None, ["local-59069", "local-80844"], "押立杯関西"
    if "栄和人杯" in k:
        return "local-275021", None, "栄和人杯"
    if anyof("土性沙羅", "大府市長杯"):
        return "local-278772", None, "大府市長杯"
    if "本庄市民" in k:
        return "local-280562", None, "本庄市民大会"
    if anyof("兵庫県ジュニア", "兵庫ジュニア", "兵庫オープン") and "近畿" not in k:
        return "local-280653", None, "兵庫県ジュニアオープン"
    if "宮津" in k:
        return "local-283422", None, "宮津市長杯"
    if "濃尾" in k:
        return "local-288221", None, "濃尾少年少女"
    if "東北地区大学" in k:
        return "local-80167", None, "東北地区大学"
    if "神奈川県少年少女" in k:
        return None, ["local-107220", "local-116514", "local-59479", "local-80733", "local-98937"], "神奈川県少年少女"
    return None, None, None


# 冠名・名称が似ていて取り違えやすい系列(確認待ちの候補を示すときに使う)
CONFUSABLE = {
    "university-greco": ["intercollegiate", "university-championship"],
    "university-championship": ["intercollegiate", "university-greco"],
    "intercollegiate": ["university-championship", "university-greco"],
    "east-spring": ["east-autumn"], "east-autumn": ["east-spring"],
    "kids": ["kids-senbatsu"], "kids-senbatsu": ["kids"],
    "juniorhigh": ["juniorhigh-senbatsu"], "juniorhigh-senbatsu": ["juniorhigh"],
}

# マスター未収録の大会(動画を削除せず保持するためのグループ)。国内/海外と区分はサイト側の判断。
DERIVED_RULES = [
    ("x-fujinami-cup", "藤波朱理杯 三重県少年少女レスリング大会", ["少年少女"], "国内", lambda k: "藤波朱理杯" in k),
    ("x-takatani-cup", "高谷惣亮杯(ゴールドキッズ年末合宿)", ["少年少女"], "国内", lambda k: "高谷惣亮杯" in k or "TAKATANI" in k or "年末合宿マッチ" in k),
    # 技術動画チャンネル(GOLDKIDS・巻っず)の大会動画で見つかった、マスター未収録の大会
    ("x-chiyoda-kids", "群馬県千代田町少年少女レスリング大会", ["少年少女"], "国内", lambda k: "千代田町" in k),
    ("x-noda-open", "野田オープン大会", ["少年少女"], "国内", lambda k: "野田オープン" in k),
    ("x-shinjuku-lions", "新宿ライオンズ杯", ["少年少女"], "国内", lambda k: "新宿ライオンズ杯" in k),
    ("x-ibaraki-open", "茨城オープン", ["少年少女"], "国内", lambda k: "茨城オープン" in k),
    ("x-tokyo-team", "東京都団体戦予選", ["少年少女"], "国内", lambda k: "東京都団体戦予選" in k),
    ("x-kanto-jh-tokyo", "関東中学生選手権 東京代表選考会", ["中学"], "国内", lambda k: "関東中学生東京代表選考会" in k),
    ("x-maki-kids", "巻キッズレスリング大会", ["少年少女"], "国内", lambda k: "巻キッズ" in k),
    ("x-veterans-world", "世界ベテランズ選手権(海外)", ["マスターズ"], "海外", lambda k: "ベテランズ" in k),
    ("x-asian-championships", "アジア選手権(海外)", ["一般"], "海外", lambda k: "アジア選手権" in k and "代表" not in k),
    ("x-suginami", "杉並区区民体育祭・杉並区レスリング大会", ["少年少女"], "国内", lambda k: "杉並区" in k),
    ("x-ibaraki-junior", "茨城ジュニア大会", ["少年少女"], "国内", lambda k: "茨城ジュニア" in k),
    ("x-kanto-kids-yokosuka", "関東少年少女レスリング横須賀大会", ["少年少女"], "国内", lambda k: "関東少年少女" in k),
    ("x-east-kids", "東日本少年少女レスリング選手権大会", ["少年少女"], "国内", lambda k: "東日本少年少女" in k),
    ("x-kinki-kids", "近畿少年少女選手権・兵庫県ジュニアオープン", ["少年少女"], "国内", lambda k: "近畿少年少女" in k),
    ("x-hyogo-junior", "兵庫県ジュニアオープン(マスター未収録の回)", ["少年少女"], "国内", lambda k: "兵庫" in k and "ジュニア" in k),
    ("x-hino-junior", "日野町少年少女レスリング大会(マスター未収録の回)", ["少年少女"], "国内", lambda k: "日野町" in k or "HINOCUP" in k),
    ("x-sakai-junior", "堺市少年少女レスリング大会(マスター未収録の回)", ["少年少女"], "国内", lambda k: "堺" in k),
    ("x-kanto-hs-league", "関東高校リーグ戦(齋藤つよし杯)", ["高校"], "国内", lambda k: "関東高校リーグ" in k),
    ("x-world-championships", "世界選手権(海外)", ["一般"], "海外", lambda k: "世界選手権" in k and "代表" not in k and "U23" not in k),
    ("x-olympics", "オリンピック(海外)", ["一般"], "海外",
     lambda k: bool(re.search(r"(パリ|東京)オリンピック|オリンピック20\d\d", k)) and not re.search(r"プレーオフ|代表決定|出場枠|出場内定", k)),
    ("x-beach-world-series", "ビーチレスリング・ワールドシリーズ(海外)", ["ビーチ"], "海外", lambda k: "ワールドシリーズ" in k),
    ("x-combat-asia", "COMBAT WRESTLING ASIA", ["一般"], "国内", lambda k: "COMBATWRESTLING" in k),
    ("x-bunsugi", "BUNSUGI International Wrestling Friendly Match", ["一般"], "未確認", lambda k: "BUNSUGI" in k),
    ("x-para", "障がい者レスリング エキシビションマッチ", ["一般"], "国内", lambda k: "障害者" in k or "障がい者" in k),
    ("x-kansai-camp", "関西オープン合宿", ["未確認"], "国内", lambda k: "関西オープン合宿" in k),
    ("x-oshitate", "押立杯(大会名の確認が必要)", ["少年少女"], "国内", lambda k: k.startswith("押立杯")),
]
DERIVED_META = {sid: {"name": name, "groups": groups, "scope": scope} for sid, name, groups, scope, _ in DERIVED_RULES}

# 区分の対応(マスターの category → 絞り込み用の区分)
CATEGORY_GROUPS = {
    "一般": ["一般"], "一般・高校生": ["一般", "高校"], "代表選考": ["一般"], "国際大会・日本開催": ["一般"],
    "大学生": ["大学"], "大学生・地域大会": ["大学"],
    "高校生": ["高校"], "高校生・地域大会": ["高校"], "高校生・国際親善（国内）": ["高校"],
    "中学生": ["中学"], "中学生・地域大会": ["中学"],
    "小学生": ["少年少女"], "少年少女・地域大会": ["少年少女"], "小中学生・U13": ["少年少女", "中学"],
    "年代別・U20・U17": ["年代別"], "年代別・U23": ["年代別"], "年代別・U15": ["年代別", "中学"],
    "女子・年代別": ["女子", "年代別"], "女子・複数年代": ["女子"],
    "社会人": ["社会人"], "社会人・職域大会": ["社会人"],
    "マスターズ": ["マスターズ"], "ビーチ": ["ビーチ"],
}
SCOPE_OF = {"全国・学生連盟大会": "国内", "地域・予選・職域大会": "国内", "日本開催の国際大会": "国内"}

EVIDENCE_LABEL = {
    "current_jwf_page": "日本協会の現行ページ",
    "jwf_business_report": "日本協会の事業報告書",
    "former_jwf_archive": "旧協会サイト由来の記録",
    "former_jwf_annual_index": "旧協会サイト由来の年別一覧",
    "wrestling_spirits_report": "専門媒体の報道",
}


def display_note(n: str) -> str:
    """資料の注記を画面向けの言葉にする(内容は変えない)。"""
    n = n.replace("開始日～終了日を連続した開催期間として表示せずsessionsを表示する。", "日程は部門ごとに表示しています(間の期間は開催していません)。")
    n = n.replace("schedule_historyを参照。", "下の日程の経緯を参照してください。")
    return n


def source_type(url: str, evidence_level: str) -> str:
    if "japan-wrestling.jp/competition" in url:
        return "日本協会の大会ページ"
    if "japan-wrestling.jp" in url and ("事業報告" in url or "%E4%BA%8B%E6%A5%AD" in url):
        return "日本協会の事業報告書"
    if "japan-wrestling.jp" in url:
        return "日本協会の掲載資料"
    if re.search(r"wrestling-spirits\.jp/results?20\d\d", url):
        return "年別一覧(旧協会サイト由来)"
    if "wrestling-spirits.jp" in url:
        return "旧協会サイト由来の記事" if evidence_level.startswith("former") else "専門媒体の記事"
    return "参照資料"


# ---------------------------------------------------------------------------
# 開催回の判定
# ---------------------------------------------------------------------------
def d(s):
    return date.fromisoformat(s) if s else None


def event_ranges(e):
    if not e.get("start_date"):
        return []  # 日付未確認の記録は日付照合に使わない(日付を補わない)
    if e.get("sessions"):
        return [(d(s["start_date"]), d(s["end_date"])) for s in e["sessions"]]
    return [(d(e["start_date"]), d(e["end_date"]))]


def in_event(day: date, e, before=0, after=0):
    for s, t in event_ranges(e):
        if s - timedelta(days=before) <= day <= t + timedelta(days=after):
            return True
    return False


def event_kai(e):
    m = re.search(r"第\s*(\d{1,3})\s*回", norm_text(e.get("official_name") or "") + norm_text(e["name"]))
    return int(m.group(1)) if m else None


def resolve_event(events, meta, live_day):
    """(event, status, basis, candidates) を返す。
    status: matched(タイトルで確認) / livedate(配信日が開催期間内) / candidate / None"""
    evs = sorted(events, key=lambda e: e["start_date"] or f"{e['year']}-99")
    if meta["kai"] is not None:
        kai_ok = [e for e in evs if event_kai(e) in (None, meta["kai"])]
        # 回数が明記された開催回と食い違う場合は除外する
        if any(event_kai(e) is not None for e in evs):
            evs = kai_ok
    if not evs:
        return None, None, "回数が一致する開催回なし", []

    # 1) タイトルの完全な日付
    if meta["full_date"]:
        hit = [e for e in evs if in_event(meta["full_date"], e, 1, 1)]
        if len(hit) == 1:
            return hit[0], "matched", f"タイトルの日付 {meta['full_date'].isoformat()} が開催期間内", []

    # 2) タイトルの月日 (年はタイトルの年・年度、なければ配信日の前後1年で探す)
    if meta["md"]:
        mo, dy = meta["md"]
        if meta["cal_year"]:
            years = [meta["cal_year"]]
        elif meta["fy"]:
            years = [meta["fy"] if mo >= 4 else meta["fy"] + 1]
        else:
            years = [live_day.year - 1, live_day.year, live_day.year + 1] if live_day else []
        hits = []
        for y in years:
            day = valid_date(y, mo, dy)
            if day:
                hits += [(e, day) for e in evs if in_event(day, e, 1, 1)]
        if hits:
            if live_day:
                hits.sort(key=lambda h: abs((h[1] - live_day).days))
            e, day = hits[0]
            src = "タイトルの年・年度" if (meta["cal_year"] or meta["fy"]) else "配信日の年"
            return e, "matched", f"タイトルの月日 {mo}/{dy}({src}で{day.year}年)が開催期間内", []

    # 3) タイトルの年・年度
    by_year = None
    if meta["fy"]:
        by_year = [e for e in evs if e["start_date"] and fiscal_year(d(e["start_date"])) == meta["fy"]]
        label = f"タイトルの年度表記({fy_label(meta['fy'])})"
    elif meta["cal_year"]:
        by_year = [e for e in evs if e["year"] == meta["cal_year"]]
        label = f"タイトルの年({meta['cal_year']}年)"
        # 『平成26年』等が年度の意味で書かれている可能性(1〜3月開催の大会で解釈が分かれる)
        by_fy = [e for e in evs if e["start_date"] and fiscal_year(d(e["start_date"])) == meta["cal_year"]]
        if len(by_year) == 1 and len(by_fy) == 1 and by_year[0]["id"] != by_fy[0]["id"]:
            a, b = by_year[0], by_fy[0]
            if live_day and in_event(live_day, a, 0, 1):
                return a, "matched", f"{label}・配信日も開催期間内", []
            if live_day and in_event(live_day, b, 0, 1):
                return b, "matched", f"{label}を年度として読むと一致・配信日も開催期間内", []
            return None, "candidate", f"{label}が暦年か年度か不明(開催回が2つに分かれる)", [a["id"], b["id"]]
    if by_year is not None:
        if len(by_year) == 1:
            kai = f"・第{meta['kai']}回" if meta["kai"] else ""
            return by_year[0], "matched", f"{label}{kai}でこの系列の開催回が1件に決まる", []
        if len(by_year) > 1 and live_day:
            hit = [e for e in by_year if in_event(live_day, e, 0, 1)]
            if len(hit) == 1:
                return hit[0], "matched", f"{label}の候補のうち配信日が開催期間内", []
        if len(by_year) > 1:
            return None, "candidate", f"{label}に該当する開催回が複数", [e["id"] for e in by_year]
        if len(by_year) == 0:
            return None, None, f"{label}に該当する開催回がマスターにない", []

    # 4) 配信日(ライブ配信の開始日、なければ公開日)が開催期間内
    if live_day:
        hit = [e for e in evs if in_event(live_day, e, 0, 1)]
        if meta["day_code"]:
            hit2 = [e for e in hit if in_event(valid_date(live_day.year, live_day.month, meta["day_code"]) or live_day, e)]
            hit = hit2 or hit
        if len(hit) == 1:
            return hit[0], "livedate", "配信日が開催期間内(タイトルに年・日付なし)", []
        # 公開が開催の後: 候補として残すだけ
        after = [e for e in evs if e["start_date"] and d(e["start_date"]) <= live_day <= d(e["end_date"]) + timedelta(days=45)]
        if after:
            e = after[-1]
            gap = (live_day - d(e["end_date"])).days
            return None, "candidate", f"公開日が開催終了の{gap}日後(公開日だけでは確定しない)", [e["id"]]
    return None, None, "年・日付の手がかりなし", []


# ---------------------------------------------------------------------------
# メイン
# ---------------------------------------------------------------------------
def to_jst_date(iso):
    if not iso:
        return None
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return dt.astimezone(JST).date()


def build(videos_raw, master, aliases, overrides, legacy_map=None, as_of=None, previous=None):
    as_of = as_of or datetime.now(JST).date()
    events = master["events"]
    ev_by_id = {e["id"]: e for e in events}
    ev_by_series = defaultdict(list)
    for e in events:
        ev_by_series[e["series_id"]].append(e)
    series_info = {s["series_id"]: s for s in aliases["series"]}

    ov_by_video = {o["video_id"]: o for o in overrides.get("video_overrides", [])}

    videos = []
    seen = set()
    for raw in videos_raw:
        vid = raw["video_id"]
        if vid in seen:  # 同一YouTube IDのみ重複として整理する
            continue
        seen.add(vid)
        title = raw.get("title", "")
        meta = extract_meta(title)
        k = match_key(title)
        live_iso = raw.get("actual_start") or raw.get("scheduled_start")
        live_day = to_jst_date(live_iso) if live_iso else to_jst_date(raw.get("published_at"))
        v = {
            "id": vid,
            "title": title,
            "published_at": raw.get("published_at"),
            "scheduled_start": raw.get("scheduled_start"),
            "actual_start": raw.get("actual_start"),
            "duration": raw.get("duration", ""),
            "kind": extract_kind(title),
            "styles": extract_style(title),
            "mat": meta["mat"],
            "day_label": meta["day_label"],
            "date_hint": None,
            "series": None, "event": None, "link": "unmatched", "basis": "", "cand": [],
            "channel": raw.get("channel"),
        }
        if raw.get("unavailable"):
            v["state"] = "unavailable"  # 前回まで取得できていたが今回のAPI応答になかった(非公開・削除の可能性)
        elif raw.get("live_broadcast_content") == "upcoming":
            v["state"] = "upcoming"
        elif raw.get("live_broadcast_content") == "live":
            v["state"] = "live"
        elif raw.get("actual_start") or raw.get("live_broadcast_content") == "none":
            v["state"] = "available"
        else:
            v["state"] = "unknown"

        sid, cands, rule = detect_series(k)
        if sid and sid not in series_info:
            sid = None
        if sid:
            e, st, basis, cev = resolve_event(ev_by_series[sid], meta, live_day)
            v["series"] = sid
            if e:
                v["event"], v["link"], v["basis"] = e["id"], st, f"大会名『{rule}』+{basis}"
            elif st == "candidate":
                v["link"], v["basis"], v["cand"] = "candidate", f"大会名『{rule}』+{basis}", cev
            else:
                # 地方大会は回数・日付が合わなければ別グループ(未収録)へ回す
                if sid.startswith("local-"):
                    v["series"] = None
                else:
                    v["link"], v["basis"] = "series_only", f"大会名『{rule}』で系列は判明・{basis}"
                    # 年の記載がない抽選会・告知: 直後(60日以内)に始まる開催回を候補として示す
                    if v["kind"] == "announcement" and live_day and not (meta["fy"] or meta["cal_year"]):
                        nxt = [e for e in sorted(ev_by_series[sid], key=lambda e: e["start_date"] or "9999")
                               if e["start_date"] and 0 <= (d(e["start_date"]) - live_day).days <= 60]
                        if nxt:
                            v["link"], v["cand"] = "candidate", [nxt[0]["id"]]
                            v["basis"] = f"大会名『{rule}』の告知・抽選会動画。公開の{(d(nxt[0]['start_date']) - live_day).days}日後に始まる開催回を候補として表示(年の記載なし)"
        elif cands and all(c.startswith("local-") for c in cands):
            # 同じ地方大会の別の回: 回数・日付が合えばその回に確定、合わなければ未収録グループへ
            pool = [e for c in cands for e in ev_by_series.get(c, [])]
            e, st, basis, cev = resolve_event(pool, meta, live_day)
            if e and st in ("matched", "livedate"):
                v["series"], v["event"], v["link"] = e["series_id"], e["id"], st
                v["basis"] = f"大会名『{rule}』+{basis}"
        elif cands:
            # 曖昧な名称: 候補系列の中で日付が合う開催回を候補として提示するだけ
            pool = [e for c in cands for e in ev_by_series.get(c, [])]
            e, st, basis, cev = resolve_event(pool, meta, live_day)
            v["link"] = "candidate"
            v["basis"] = f"名称『{rule}』は複数の大会に当てはまる" + (f"・{basis}" if basis else "")
            v["cand"] = ([e["id"]] if e else []) + [c for c in cev if not e or c != e["id"]]
            v["cand_series"] = cands
            if len(set(ev_by_id[c]["series_id"] for c in v["cand"])) == 1 and v["cand"]:
                v["series"] = ev_by_id[v["cand"][0]]["series_id"]
        if v["series"] is None and v["link"] in ("unmatched",):
            for xsid, _, _, _, pred in DERIVED_RULES:
                if pred(k):
                    v["series"], v["link"], v["basis"] = xsid, "derived", "マスター未収録の大会(動画タイトルから分類)"
                    break

        # 公開(配信)日が開催より前なのに試合・インタビュー動画として照合された場合は確定しない
        if v["event"] and v["link"] in ("matched", "livedate") and live_day and v["kind"] not in ("announcement",) \
                and not (meta["md"] or meta["full_date"]):
            ev0 = ev_by_id[v["event"]]
            if ev0["start_date"] and live_day < d(ev0["start_date"]) - timedelta(days=1):
                alt = [e for c in CONFUSABLE.get(ev0["series_id"], []) for e in ev_by_series.get(c, [])
                       if e["start_date"] and d(e["end_date"]) <= live_day <= d(e["end_date"]) + timedelta(days=60)]
                v["cand"] = [ev0["id"]] + [e["id"] for e in alt]
                v["event"], v["link"] = None, "candidate"
                v["basis"] = (f"{v['basis']}。ただし公開日{live_day.isoformat()}が開催({ev0['start_date']})より前のため確定しない"
                              + ("・名称の似た大会の直後に公開" if alt else ""))

        # 表示用の日付(競技日の手がかり)
        hint = meta["full_date"]
        if not hint and meta["md"] and v["event"]:
            ev = ev_by_id[v["event"]]
            for y in {d(ev["start_date"]).year, d(ev["end_date"]).year}:
                cand_day = valid_date(y, *meta["md"])
                if cand_day and in_event(cand_day, ev, 1, 1):
                    hint = cand_day
        if not hint and v["event"] and meta["day_label"]:
            ev = ev_by_id[v["event"]]
            if ev.get("start_date") and not ev.get("sessions"):
                cand_day = d(ev["start_date"]) + timedelta(days=meta["day_label"] - 1)
                if cand_day <= d(ev["end_date"]):
                    hint = cand_day  # 「N日目」と開催初日から計算
        if not hint and v["event"] and live_day and in_event(live_day, ev_by_id[v["event"]], 0, 0):
            hint = live_day
        v["date_hint"] = hint.isoformat() if hint else None
        v["_live_day"] = live_day
        v["_meta"] = meta
        videos.append(v)

    # 手動修正(常に最優先・再ビルドでも保持)
    applied_overrides = 0
    for v in videos:
        o = ov_by_video.get(v["id"])
        if not o:
            continue
        if o.get("event_id") and o["event_id"] in ev_by_id:
            v["event"] = o["event_id"]
            v["series"] = ev_by_id[o["event_id"]]["series_id"]
        elif o.get("series_id"):
            v["series"], v["event"] = o["series_id"], None
        if o.get("kind"):
            v["kind"] = o["kind"]
        v["link"] = "manual"
        v["basis"] = f"手動確認: {o.get('basis', '')}(確認日 {o.get('checked_on', '')})"
        v["cand"] = []
        applied_overrides += 1

    # 系列不明の動画: 同じ日に公開された照合済み動画が1つの開催回だけなら候補として示す(確定はしない)
    by_day = defaultdict(list)
    for v in videos:
        by_day[v["_live_day"]].append(v)
    for v in videos:
        if v["series"] or v["link"] not in ("unmatched",):
            continue
        evs = {w["event"] for w in by_day[v["_live_day"]] if w["event"] and w["link"] in ("matched", "livedate", "manual")}
        # 後日まとめて公開された過去動画を巻き込まないよう、開催期間中〜終了4日後の配信に限る
        evs = {e for e in evs if e in ev_by_id and in_event(v["_live_day"], ev_by_id[e], 0, 4)}
        if len(evs) == 1:
            eid = evs.pop()
            v["link"], v["cand"] = "candidate", [eid]
            v["basis"] = "大会名がタイトルにない・開催期間中〜直後に同じ日に公開された動画がこの開催回に照合されている"

    # マスター未収録グループの開催回(動画の年・公開日から推定。公式の開催日ではない)
    derived_events = []
    groups = defaultdict(list)
    for v in videos:
        if v["link"] == "derived":
            groups[v["series"]].append(v)
    used_ids = set()

    def eff_year(v):
        m_ = v["_meta"]
        return m_["cal_year"] or m_["fy"] or (m_["full_date"].year if m_["full_date"] else None) or v["_live_day"].year

    for xsid, vs in groups.items():
        runs = []
        by_y = defaultdict(list)
        for v in vs:
            by_y[eff_year(v)].append(v)
        for y in sorted(by_y):
            ys = sorted(by_y[y], key=lambda v: v["_live_day"])
            run = [ys[0]]
            for a, b in zip(ys, ys[1:]):
                if (b["_live_day"] - a["_live_day"]).days <= 30:
                    run.append(b)
                else:
                    runs.append(run)
                    run = [b]
            runs.append(run)
        for run in runs:
            first, last = run[0]["_live_day"], run[-1]["_live_day"]
            kai = next((v["_meta"]["kai"] for v in run if v["_meta"]["kai"]), None)
            eid = f"x-{xsid[2:]}-{first.isoformat()}"
            while eid in used_ids:
                eid += "b"
            used_ids.add(eid)
            derived_events.append({
                "id": eid, "series_id": xsid, "year": eff_year(run[0]),
                "name": DERIVED_META[xsid]["name"] + (f"(第{kai}回)" if kai else ""),
                "status": "unverified", "start_date": first.isoformat(), "end_date": last.isoformat(),
                "venue": None, "date_quality": "video_published_date", "derived": True,
                "source_urls": [], "notes": ["マスター未収録。日付は動画の公開日から推定したもので、公式の開催日ではありません。"],
            })
            for v in run:
                v["event"] = eid

    # ------------------------------------------------------------------
    # 出力データの組み立て
    # ------------------------------------------------------------------
    counts_by_event = Counter(v["event"] for v in videos if v["event"])
    out_events = []
    for e in events:
        sd = d(e["start_date"])
        oe = {
            "id": e["id"], "series": e["series_id"], "year": e["year"],
            "fy_label": fy_label(fiscal_year(sd)) if sd else None,
            "name": e["name"], "official_name": e.get("official_name"),
            "status": e["status"], "start": e["start_date"], "end": e["end_date"],
            "venue": e.get("venue"), "date_quality": e.get("date_quality"),
            "evidence": EVIDENCE_LABEL.get(e.get("evidence_level"), e.get("evidence_level")),
            "jwf_relationship": e.get("jwf_relationship"),
            "sources": [{"url": u, "type": source_type(u, e.get("evidence_level", ""))} for u in e.get("source_urls", [])],
            "sessions": e.get("sessions"), "notes": [display_note(n) for n in e.get("notes", [])] or None,
            "group": e.get("event_group_id"),
            "schedule_history": e.get("schedule_history"),
            "n": counts_by_event.get(e["id"], 0),
        }
        out_events.append({k: v for k, v in oe.items() if v not in (None, [], "")})
    for e in derived_events:
        sd = d(e["start_date"])
        out_events.append({
            "id": e["id"], "series": e["series_id"], "year": e["year"], "fy_label": fy_label(fiscal_year(sd)),
            "name": e["name"], "status": "unverified", "start": e["start_date"], "end": e["end_date"],
            "date_quality": "video_published_date", "derived": True, "notes": e["notes"],
            "n": counts_by_event.get(e["id"], 0),
        })

    out_series = []
    series_counts = Counter(v["series"] for v in videos if v["series"])
    for s in aliases["series"]:
        evs = ev_by_series.get(s["series_id"], [])
        cats = sorted({e["category"] for e in evs})
        grp = sorted({g for c in cats for g in CATEGORY_GROUPS.get(c, ["未確認"])})
        scope = sorted({SCOPE_OF.get(e["scope"], "未確認") for e in evs}) or ["未確認"]
        out_series.append({
            "id": s["series_id"], "name": s["display_name"], "aliases": s.get("search_aliases", []),
            "groups": grp, "scope": scope[0] if len(scope) == 1 else "未確認", "categories": cats,
            "n": series_counts.get(s["series_id"], 0), "master": True,
        })
    for xsid, meta_ in DERIVED_META.items():
        if series_counts.get(xsid):
            out_series.append({
                "id": xsid, "name": meta_["name"], "aliases": [], "groups": meta_["groups"],
                "scope": meta_["scope"], "n": series_counts[xsid], "master": False,
            })
    # 系列ごとのスタイル(絞り込み用)
    styles_by_series = defaultdict(set)
    for v in videos:
        if v["series"]:
            styles_by_series[v["series"]].update(v["styles"] or ["未確認"])
    for s in out_series:
        s["styles"] = sorted(styles_by_series.get(s["id"], {"未確認"}))

    out_videos = []
    for v in videos:
        ov = {
            "id": v["id"], "t": v["title"], "p": v["published_at"], "du": v["duration"],
            "k": v["kind"], "st": v["styles"], "m": v["mat"], "dl": v["day_label"], "dh": v["date_hint"],
            "s": v["series"], "e": v["event"], "l": v["link"], "b": v["basis"], "c": v["cand"],
            "vs": v["state"], "ss": v["scheduled_start"], "as": v["actual_start"],
            "ch": v.get("channel"),
        }
        out_videos.append({k: val for k, val in ov.items() if val not in (None, [], "")})

    link_counts = Counter(v["link"] for v in videos)
    ids_now = {v["id"] for v in videos}
    report = {
        "built_at": datetime.now(JST).isoformat(timespec="seconds"),
        "as_of": as_of.isoformat(),
        "video_count": len(videos),
        "raw_count": len(videos_raw),
        "duplicate_ids_removed": len(videos_raw) - len(videos),
        "link_counts": dict(link_counts),
        "overrides_applied": applied_overrides,
        "master_events": len(events),
        "derived_events": len(derived_events),
        "events_with_videos": sum(1 for e in out_events if e.get("n")),
    }
    if previous is not None:
        missing = sorted(previous - ids_now)
        report["previous_video_count"] = len(previous)
        report["missing_from_previous"] = missing
        report["new_since_previous"] = len(ids_now - previous)

    data = {
        "as_of": as_of.isoformat(),
        "master_as_of": master["metadata"].get("as_of"),
        "series": out_series,
        "events": out_events,
        "videos": out_videos,
        "ambiguous_terms": aliases.get("ambiguous_terms", []),
        "legacy": legacy_map or {},
        "report": {k: v for k, v in report.items() if k != "missing_from_previous"},
    }
    return data, report, videos
