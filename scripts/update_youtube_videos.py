#!/usr/bin/env python3
"""Fetch new videos from a YouTube channel and merge them into videos.json."""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

CHANNEL_ID = "UCX6dKYm5Hms9AS3zFi5FSMQ"
CHANNEL_HANDLE = "@Piggreen34654"
CHANNEL_URL = f"https://www.youtube.com/{CHANNEL_HANDLE}/videos"
VIDEOS_FILE = Path(__file__).resolve().parent.parent / "videos.json"
USER_AGENT = "Mozilla/5.0 (compatible; PiggreenSiteBot/1.0)"


def fetch_channel_videos() -> list[dict[str, str]]:
    request = urllib.request.Request(CHANNEL_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8", "replace")

    match = re.search(r"var ytInitialData = ({.*?});</script>", html)
    if not match:
        raise RuntimeError("Could not parse YouTube channel page")

    data = json.loads(match.group(1))
    tabs = data["contents"]["twoColumnBrowseResultsRenderer"]["tabs"]
    videos_tab = next(
        tab
        for tab in tabs
        if tab.get("tabRenderer", {}).get("selected")
        or tab.get("tabRenderer", {}).get("title") in {"Videos", "Vidéos"}
    )
    contents = videos_tab["tabRenderer"]["content"]["richGridRenderer"]["contents"]

    videos: list[dict[str, str]] = []
    for item in contents:
        lockup = (
            item.get("richItemRenderer", {})
            .get("content", {})
            .get("lockupViewModel", {})
        )
        video_id = lockup.get("contentId")
        if not video_id:
            continue

        metadata = lockup.get("metadata", {}).get("lockupMetadataViewModel", {})
        title = metadata.get("title", {}).get("content", "")
        if not title:
            title = metadata.get("title", {}).get("runs", [{}])[0].get("text", "")

        videos.append(
            {
                "id": video_id,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )

    return videos


def load_existing_videos() -> dict:
    if not VIDEOS_FILE.exists():
        return {
            "channelId": CHANNEL_ID,
            "channelHandle": CHANNEL_HANDLE,
            "updatedAt": None,
            "videos": [],
        }

    with VIDEOS_FILE.open(encoding="utf-8") as file:
        return json.load(file)


def merge_videos(existing: dict, fetched: list[dict[str, str]]) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    by_id = {video["id"]: video for video in existing.get("videos", [])}
    fetched_ids = {video["id"] for video in fetched}

    for video in by_id.values():
        if video["id"] not in fetched_ids:
            video.pop("channelOrder", None)

    for index, video in enumerate(fetched):
        current = by_id.get(video["id"])
        if current:
            current["title"] = video["title"]
            current["url"] = video["url"]
            current.setdefault("addedAt", now)
            current["channelOrder"] = index
        else:
            by_id[video["id"]] = {
                **video,
                "addedAt": now,
                "channelOrder": index,
            }

    on_channel = [video for video in by_id.values() if "channelOrder" in video]
    archived = [video for video in by_id.values() if "channelOrder" not in video]

    on_channel.sort(key=lambda video: video["channelOrder"])
    archived.sort(key=lambda video: video.get("addedAt", ""), reverse=True)
    merged = on_channel + archived

    return {
        "channelId": CHANNEL_ID,
        "channelHandle": CHANNEL_HANDLE,
        "updatedAt": now,
        "videos": merged,
    }


def main() -> None:
    fetched = fetch_channel_videos()
    existing = load_existing_videos()
    merged = merge_videos(existing, fetched)

    with VIDEOS_FILE.open("w", encoding="utf-8") as file:
        json.dump(merged, file, ensure_ascii=False, indent=2)
        file.write("\n")

    print(f"Updated {VIDEOS_FILE.name} with {len(merged['videos'])} videos")


if __name__ == "__main__":
    main()
