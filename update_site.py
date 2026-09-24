"""
Japan Wrestling Channel の動画を取得し、大会ごとに分類して data.json を生成するスクリプト。
GitHub Actions から定期実行される想定(手動実行も可能)。

環境変数 YOUTUBE_API_KEY にAPIキーをセットして実行してください。
    YOUTUBE_API_KEY=xxxx python update_site.py
"""

import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date

import requests

CHANNEL_HANDLE = "japan_wrestlingchannel"
API_BASE = "https://www.googleapis.com/youtube/v3"
GAP_DAYS = 5  # 同じ大会の「開催回」とみなす、配信日同士の最大間隔


# ---------------------------------------------------------------------------
# 1. YouTube Data API から全動画メタデータを取得
# ---------------------------------------------------------------------------
def get_uploads_playlist_id(api_key: str) -> str:
    resp = requests.get(
        f"{API_BASE}/channels",
        params={"part": "contentDetails", "forHandle": CHANNEL_HANDLE, "key": api_key},
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("items"):
        print("エラー: チャンネルが見つかりませんでした。", data)
        sys.exit(1)
    return data["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_all_video_ids(api_key: str, playlist_id: str) -> list:
    video_ids = []
    page_token = None
    while True:
        params = {"part": "contentDetails", "playlistId": playlist_id, "maxResults": 50, "key": api_key}
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(f"{API_BASE}/playlistItems", params=params)
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            video_ids.append(item["contentDetails"]["videoId"])
        page_token = data.get("nextPageToken")
        if not page_token:
            break
        time.sleep(0.2)
    return video_ids


def fetch_video_details(api_key: str, video_ids: list) -> list:
    videos = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        resp = requests.get(
            f"{API_BASE}/videos",
            params={"part": "snippet,contentDetails,statistics", "id": ",".join(batch), "key": api_key},
        )
        resp.raise_for_status()
        data = resp.json()
        for item in data.get("items", []):
            snippet = item["snippet"]
            stats = item.get("statistics", {})
            videos.append(
                {
                    "video_id": item["id"],
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "thumbnail_url": snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
                    "duration": item.get("contentDetails", {}).get("duration", ""),
                    "view_count": int(stats.get("viewCount", 0)),
                }
            )
        print(f"  詳細情報 {len(videos)}/{len(video_ids)} 件取得済み...")
        time.sleep(0.2)
    return videos


# ---------------------------------------------------------------------------
# 2. タイトルから大会名を抽出・正規化(過去の対話で検証したロジック)
# ---------------------------------------------------------------------------
bracket_pat = re.compile(r"【.*?】")
date_tokens = re.compile(
    r"\d{8}|\d{1,2}[/／]\d{1,2}|\d{1,2}月\d{1,2}日(\([月火水木金土日]\))?|"
    r"(19|20)\d{2}年度?|[令平昭][和成](元|\d{1,2})年度?|[ABCD1-9１-９４]?\s*マット|\d日目|"
    r"\d{1,2}[-‐−][A-Z]"
)


def clean_candidate(title):
    t = bracket_pat.sub(" ", title)
    t = date_tokens.sub(" ", t)
    t = re.sub(r"[\u3000\u200b\s]+", " ", t).strip()
    return t


def extract_name(title):
    cleaned = clean_candidate(title)
    matches = re.findall(r".+?(?:杯|選手権大会|選手権|大会|カップ|リーグ戦|オープン|CUP|フェスティバル)", cleaned)
    if not matches:
        return None
    return max(matches, key=len).strip()


def strip_junk(name):
    name = re.sub(r"^[」・：:\(\)（）\s0-9A-Za-z\-\.０-９ＡーＺｅ]+", "", name)
    name = re.sub(r"^[（(][月火水木金土日][）)][：:\s]*", "", name)
    return name.strip()


QUALIFIERS = [
    "学生", "大学", "社会人", "選抜", "中学", "高校", "高等学校", "女子", "ジュニア",
    "少年少女", "マスターズ", "世界", "ジュニアクイーン", "JOC", "天皇杯", "国民体育",
    "関東", "関西", "西日本", "東日本", "近畿", "堺市", "日野", "三重県", "兵庫",
]
NOISE = ["レスリング", "スタイル", "グレコローマン", "グレコ", "　", " "]
STRIP_SUFFIXES = ["選手権大会", "選手権", "大会", "カップ", "杯"]


def normalize_core(name):
    n = strip_junk(name)
    for w in NOISE:
        n = n.replace(w, "")
    for _ in range(2):
        for suf in STRIP_SUFFIXES:
            if n.endswith(suf):
                n = n[: -len(suf)]
                break
    return n.strip()


def qualifier_signature(name):
    return frozenset(q for q in QUALIFIERS if q in name)


def to_ordinal(dstr):
    y, m, d = map(int, dstr.split("-"))
    return date(y, m, d).toordinal()


def parse_duration_minutes(dur):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", dur)
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 60 + mi + (1 if s else 0)


# ---------------------------------------------------------------------------
# 3. サイト用データ構造の構築
# ---------------------------------------------------------------------------
def build_site_data(raw_videos):
    for d in raw_videos:
        d["date"] = d["published_at"][:10]

    by_date = defaultdict(list)
    for d in raw_videos:
        by_date[d["date"]].append(d)

    date_to_name = {}
    for dt, vids in by_date.items():
        cands = [extract_name(v["title"]) for v in vids]
        cands = [c for c in cands if c]
        if cands:
            cnt = Counter(cands)
            date_to_name[dt] = sorted(cnt.items(), key=lambda kv: (kv[1], len(kv[0])), reverse=True)[0][0]
        else:
            date_to_name[dt] = None

    key_to_variants = defaultdict(lambda: defaultdict(int))
    key_to_dates = defaultdict(list)
    for dt, vids in by_date.items():
        name = date_to_name[dt]
        if name is None:
            continue
        core = normalize_core(name)
        sig = qualifier_signature(strip_junk(name))
        key = (core, sig)
        key_to_variants[key][name] += len(vids)
        key_to_dates[key].append(dt)

    key_to_canonical = {}
    for key, vc in key_to_variants.items():
        key_to_canonical[key] = sorted(vc.items(), key=lambda kv: -kv[1])[0][0]

    for d in raw_videos:
        name = date_to_name[d["date"]]
        if name is None:
            d["tournament"] = None
        else:
            core = normalize_core(name)
            sig = qualifier_signature(strip_junk(name))
            d["tournament"] = key_to_canonical[(core, sig)]

    # --- series: 大会名でまとめる(年度をまたいで統合) ---
    tournaments = defaultdict(list)
    unclassified = []
    for d in raw_videos:
        entry = {
            "id": d["video_id"],
            "title": d["title"].replace("\u3000", " ").replace("\u200b", ""),
            "date": d["date"],
            "duration": d["duration"],
            "views": d.get("view_count", 0),
            "thumb": d.get("thumbnail_url", ""),
        }
        if d["tournament"]:
            tournaments[d["tournament"]].append(entry)
        else:
            unclassified.append(entry)

    site_tournaments = []
    for name, vids in tournaments.items():
        vids_sorted = sorted(vids, key=lambda v: v["date"])
        site_tournaments.append(
            {
                "name": name,
                "count": len(vids),
                "date_from": vids_sorted[0]["date"],
                "date_to": vids_sorted[-1]["date"],
                "videos": sorted(vids, key=lambda v: v["date"], reverse=True),
            }
        )
    site_tournaments.sort(key=lambda t: t["date_to"], reverse=True)

    # --- occurrence: 日程(開催回)でまとめる ---
    occurrences_raw = []
    for key, dates_list in key_to_dates.items():
        dates_sorted = sorted(dates_list, key=to_ordinal)
        canonical = key_to_canonical[key]
        run = [dates_sorted[0]]
        for prev, cur in zip(dates_sorted, dates_sorted[1:]):
            if to_ordinal(cur) - to_ordinal(prev) <= GAP_DAYS:
                run.append(cur)
            else:
                occurrences_raw.append((canonical, run))
                run = [cur]
        occurrences_raw.append((canonical, run))

    occurrence_data = []
    for canonical, dates_run in occurrences_raw:
        vids = []
        for dt in dates_run:
            for v in by_date[dt]:
                vids.append(
                    {
                        "id": v["video_id"],
                        "title": v["title"].replace("\u3000", " ").replace("\u200b", ""),
                        "date": v["date"],
                        "duration": v["duration"],
                        "views": v.get("view_count", 0),
                        "thumb": v.get("thumbnail_url", ""),
                    }
                )
        vids_sorted = sorted(vids, key=lambda x: x["date"])
        date_from, date_to = vids_sorted[0]["date"], vids_sorted[-1]["date"]
        year_label = date_from[:4] if date_from[:4] == date_to[:4] else (date_from[:4] + "-" + date_to[:4])
        occurrence_data.append(
            {
                "name": canonical,
                "label": canonical + "(" + year_label + ")",
                "count": len(vids),
                "date_from": date_from,
                "date_to": date_to,
                "videos": sorted(vids, key=lambda v: v["date"], reverse=True),
            }
        )
    occurrence_data.sort(key=lambda o: o["date_to"], reverse=True)

    return {
        "generated_video_count": len(raw_videos),
        "tournament_count": len(site_tournaments),
        "occurrence_count": len(occurrence_data),
        "tournaments": site_tournaments,
        "occurrences": occurrence_data,
        "unclassified": sorted(unclassified, key=lambda v: v["date"], reverse=True),
    }


def main():
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("エラー: 環境変数 YOUTUBE_API_KEY が設定されていません。")
        sys.exit(1)

    print("チャンネル情報を取得中...")
    playlist_id = get_uploads_playlist_id(api_key)

    print("動画ID一覧を取得中...")
    video_ids = fetch_all_video_ids(api_key, playlist_id)
    print(f"合計 {len(video_ids)} 本の動画が見つかりました。")

    print("各動画の詳細情報を取得中...")
    raw_videos = fetch_video_details(api_key, video_ids)

    print("大会ごとに分類中...")
    site_data = build_site_data(raw_videos)

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(site_data, f, ensure_ascii=False, separators=(",", ":"))

    print(f"完了: 大会数 {site_data['tournament_count']} / 開催回数 {site_data['occurrence_count']} / 未分類 {len(site_data['unclassified'])}")


if __name__ == "__main__":
    main()
