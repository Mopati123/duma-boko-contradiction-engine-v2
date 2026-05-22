import csv
import json
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ============= CONFIG =============
API_KEY = "AIzaSyDGQCRZoTg08EjfOPT1Ir3VC5ddLcCgJPg"

PHRASES = [
    "A promise to voters is not a legal contract",
    "election promises are not legal or social contracts",
    "election promises are not legally binding contracts",
    "Votes aren't contracts",
    "government will fulfil promises",
    "no backing down from our promises",
    "President Duma Boko",
    "Duma Boko kgotla",
    "Duma Boko 2024 election promises"
]

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
MAX_RESULTS_PER_QUERY = 20

OUTPUT_FILE = "boko_youtube_results.csv"
# ===================================


def search_youtube_videos(youtube, query, max_results=20):
    try:
        search_response = youtube.search().list(
            q=query,
            part="id,snippet",
            type="video",
            maxResults=max_results,
            order="date"  # most recent first
        ).execute()

        videos = []
        for item in search_response.get("items", []):
            video_id = item["id"]["videoId"]
            title = item["snippet"]["title"]
            description = item["snippet"]["description"]
            published_at = item["snippet"]["publishedAt"]

            videos.append({
                "search_phrase": query,
                "title": title,
                "video_id": video_id,
                "url": f"https://youtube.com/watch?v={video_id}",
                "published_at": published_at,
                "description": description[:200]  # first 200 chars
            })
        return videos

    except HttpError as e:
        print(f"HttpError for query '{query}': {e}")
        return []


def main():
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)

    # Collect all results
    all_rows = []

    for phrase in PHRASES:
        print(f"Searching: '{phrase}'")
        videos = search_youtube_videos(youtube, phrase, MAX_RESULTS_PER_QUERY)
        all_rows.extend(videos)

    # Export to CSV
    fieldnames = [
        "search_phrase", "title", "video_id", "url", "published_at", "description"
    ]

    with open(OUTPUT_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Saved {len(all_rows)} results to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
