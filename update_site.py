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


def get(path, **params):
    for attempt in range(3):
        r = requests.get(f"{API}/{path}", params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()


def fetch_videos(key):
    ch = get("channels", part="contentDetails", forHandle=CHANNEL_HANDLE, key=key)
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
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
    prev_videos = {v["id"]: v for v in previous.get("videos", [])}

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

    data, report, _ = build(
        videos,
        load("master_events.json", None),
        load("series_aliases.json", None),
        load("overrides.json", {}),
        load("legacy_map.json", {}),
        previous=set(prev_videos) if prev_videos else None,
    )
    report["unavailable_now"] = [v["video_id"] for v in videos if v.get("unavailable")]

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    with open("build_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)

    print(f"動画 {report['video_count']} 本 / 照合 {report['link_counts']}")
    print(f"手動修正 {report['overrides_applied']} 件 / 今回取得できなかった動画 {len(report['unavailable_now'])} 本")


if __name__ == "__main__":
    main()
