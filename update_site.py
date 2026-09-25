"""
Japan Wrestling Channel の動画を取得し、大会マスターと照合して data.json を作る。
GitHub Actions から毎日実行される(手動実行も可)。

    YOUTUBE_API_KEY=xxxx python update_site.py

出力: data.json(サイト用) / build_report.json(件数・照合状況・前回からの差分)
"""

import json
import os
import sys
import time

import requests

from build_data import build

CHANNEL_HANDLE = "japan_wrestlingchannel"
API = "https://www.googleapis.com/youtube/v3"
TECH_CHANNELS_FILE = "tech_channels.json"


def get(path, **params):
    for attempt in range(3):
        r = requests.get(f"{API}/{path}", params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()


def uploads_playlist(key, channel_id=None, handle=None):
    kw = {"id": channel_id} if channel_id else {"forHandle": handle}
    ch = get("channels", part="contentDetails", key=key, **kw)
    items = ch.get("items") or []
    if not items:
        return None
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def fetch_channel_videos(key, channel_id=None, handle=None):
    uploads = uploads_playlist(key, channel_id=channel_id, handle=handle)
    if not uploads:
        return []
    ids, token = [], None
    while True:
        p = dict(part="contentDetails", playlistId=uploads, maxResults=50, key=key)
        if token:
            p["pageToken"] = token
        data = get("playlistItems", **p)
        ids += [it["contentDetails"]["videoId"] for it in data.get("items", [])]
        token = data.get("nextPageToken")
        if not token:
            break
        time.sleep(0.2)
    videos = []
    for i in range(0, len(ids), 50):
        data = get("videos", part="snippet,contentDetails,liveStreamingDetails",
                   id=",".join(ids[i:i + 50]), key=key)
        for it in data.get("items", []):
            sn, live = it["snippet"], it.get("liveStreamingDetails", {})
            videos.append({
                "video_id": it["id"],
                "title": sn.get("title", ""),
                "published_at": sn.get("publishedAt", ""),
                "duration": it.get("contentDetails", {}).get("duration", ""),
                "live_broadcast_content": sn.get("liveBroadcastContent"),
                "scheduled_start": live.get("scheduledStartTime"),
                "actual_start": live.get("actualStartTime"),
            })
        time.sleep(0.2)
    return videos


def fetch_videos(key):
    return fetch_channel_videos(key, handle=CHANNEL_HANDLE)


def fetch_tech_videos(key, previous_tech):
    """大会マスターと照合しない、技術・指導動画チャンネルの一覧を取得する。
    1チャンネルの取得に失敗しても、他のチャンネルの更新は続ける。"""
    cfg = load(TECH_CHANNELS_FILE, {"channels": []})
    prev_by_channel = {c["slug"]: {v["id"]: v for v in c.get("videos", [])} for c in previous_tech.get("channels", [])}
    out = []
    for ch in cfg.get("channels", []):
        slug = ch["slug"]
        prev = prev_by_channel.get(slug, {})
        try:
            raw = fetch_channel_videos(key, channel_id=ch.get("channel_id"), handle=ch.get("handle"))
        except Exception as ex:
            print(f"[技術動画] {slug} の取得に失敗したため前回のデータを引き継ぎます: {ex}")
            out.append({"slug": slug, "name": ch["name"], "note": ch.get("note", ""), "videos": list(prev.values())})
            continue
        vids = []
        got = set()
        for v in raw:
            got.add(v["video_id"])
            vids.append({"id": v["video_id"], "t": v["title"], "p": v["published_at"], "du": v["duration"]})
        for vid, pv in prev.items():
            if vid not in got:
                vids.append(dict(pv, unavailable=True))
        vids.sort(key=lambda v: v.get("p") or "", reverse=True)
        out.append({"slug": slug, "name": ch["name"], "note": ch.get("note", ""), "videos": vids})
    return {"channels": out}


def load(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def main():
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        sys.exit("YOUTUBE_API_KEY が設定されていません")

    previous = load("data.json", {})
    # Japan Wrestling Channel の動画だけで前回との比較をする(他チャンネルの動画には "ch" が付いている)
    prev_videos = {v["id"]: v for v in previous.get("videos", []) if not v.get("ch")}

    videos = fetch_videos(key)
    if not videos:
        sys.exit("動画を1件も取得できませんでした。data.json は更新しません。")
    if prev_videos and len(videos) < 0.9 * len(prev_videos):
        sys.exit(f"取得件数が前回より大きく減っています({len(prev_videos)}→{len(videos)})。"
                 "APIの一時的な不具合の可能性があるため、data.json は更新しません。")

    # 前回あった動画が今回取得できなかった場合も、URLと元タイトルを残す
    got = {v["video_id"] for v in videos}
    for vid, pv in prev_videos.items():
        if vid not in got:
            videos.append({"video_id": vid, "title": pv.get("t", ""), "published_at": pv.get("p", ""),
                           "duration": pv.get("du", ""), "unavailable": True,
                           "scheduled_start": pv.get("ss"), "actual_start": pv.get("as")})

    # 技術動画チャンネル(tech_channels.json)の動画を取得し、大会の動画は大会側の照合に混ぜる
    previous_tech = previous.get("tech", {"channels": []})
    tech = fetch_tech_videos(key, previous_tech)
    from channel_sort import Sorter
    sorter = Sorter()
    extra = []
    for ch in tech.get("channels", []):
        for tv in ch.get("videos", []):
            use, _, _ = sorter.judge(tv["id"], tv.get("t", ""))
            if use == "tournament":
                extra.append({"video_id": tv["id"], "title": tv.get("t", ""), "published_at": tv.get("p", ""),
                              "duration": tv.get("du", ""), "live_broadcast_content": "none",
                              "unavailable": bool(tv.get("unavailable")), "channel": ch["name"]})
    main_ids = {v["video_id"] for v in videos}
    extra = [x for x in extra if x["video_id"] not in main_ids]

    data, report, _ = build(
        videos + extra,
        load("master_events.json", None),
        load("series_aliases.json", None),
        load("overrides.json", {}),
        load("legacy_map.json", {}),
        previous=set(prev_videos) | {v["id"] for v in previous.get("videos", []) if v.get("ch")} if prev_videos else None,
    )
    report["unavailable_now"] = [v["video_id"] for v in videos if v.get("unavailable")]
    report["from_other_channels"] = len(extra)
    data["tech"] = tech

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    with open("build_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print(f"動画 {report['video_count']} 本 / 照合 {report['link_counts']}")
    print(f"手動修正 {report['overrides_applied']} 件 / 今回取得できなかった動画 {len(report['unavailable_now'])} 本")

    # 大会・開催回ごとのページ(events/)と sitemap.xml を作り直す
    import build_pages
    build_pages.build()


if __name__ == "__main__":
    main()
