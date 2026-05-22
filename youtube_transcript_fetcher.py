#!/usr/bin/env python3
"""
YouTube Transcript Fetcher
Fetches auto-generated transcripts from YouTube videos for high-accuracy analysis.
Uses youtube-transcript-api which is more accurate than Whisper for political speeches.
"""

import csv
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable


@dataclass
class TranscriptResult:
    """Result of transcript fetching."""
    video_id: str
    success: bool
    transcript: List[Dict]
    full_text: str
    language: str
    is_generated: bool
    error: Optional[str] = None


def extract_video_id(url: str) -> str:
    """Extract video ID from YouTube URL."""
    if 'youtu.be/' in url:
        return url.split('/')[-1].split('?')[0]
    elif 'v=' in url:
        return url.split('v=')[-1].split('&')[0]
    return url


def load_video_list(csv_path: str) -> List[Dict]:
    """Load video list from boko_youtube_results.csv."""
    videos = []
    csv_file = Path(csv_path)
    
    if not csv_file.exists():
        print(f"Error: {csv_path} not found")
        return videos
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            video_id = extract_video_id(row.get('url', ''))
            if video_id and video_id != 'video_id':
                videos.append({
                    'video_id': video_id,
                    'url': row.get('url', ''),
                    'title': row.get('title', ''),
                    'search_phrase': row.get('search_phrase', ''),
                    'published_at': row.get('published_at', ''),
                    'description': row.get('description', '')
                })
    
    return videos


def fetch_transcript(video_id: str) -> TranscriptResult:
    """Fetch transcript for a single video."""
    try:
        # Use the simpler get_transcript method directly
        # This returns a list of dictionaries with 'text', 'start', 'duration'
        transcript_data = YouTubeTranscriptApi.get_transcript(video_id)
        
        if transcript_data and len(transcript_data) > 0:
            # Build full text
            full_text = " ".join([entry['text'] for entry in transcript_data])
            
            return TranscriptResult(
                video_id=video_id,
                success=True,
                transcript=transcript_data,
                full_text=full_text,
                language="en",  # Default to English
                is_generated=True  # Assume auto-generated
            )
        else:
            return TranscriptResult(
                video_id=video_id,
                success=False,
                transcript=[],
                full_text="",
                language="",
                is_generated=False,
                error="Empty transcript"
            )
            
    except TranscriptsDisabled:
        return TranscriptResult(
            video_id=video_id,
            success=False,
            transcript=[],
            full_text="",
            language="",
            is_generated=False,
            error="Transcripts disabled for this video"
        )
    except NoTranscriptFound:
        return TranscriptResult(
            video_id=video_id,
            success=False,
            transcript=[],
            full_text="",
            language="",
            is_generated=False,
            error="No transcript found"
        )
    except VideoUnavailable:
        return TranscriptResult(
            video_id=video_id,
            success=False,
            transcript=[],
            full_text="",
            language="",
            is_generated=False,
            error="Video unavailable"
        )
    except Exception as e:
        return TranscriptResult(
            video_id=video_id,
            success=False,
            transcript=[],
            full_text="",
            language="",
            is_generated=False,
            error=f"Error: {str(e)}"
        )


def save_transcript(result: TranscriptResult, output_dir: Path):
    """Save transcript to JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"{result.video_id}_youtube.json"
    
    data = {
        'video_id': result.video_id,
        'success': result.success,
        'language': result.language,
        'is_generated': result.is_generated,
        'full_text': result.full_text,
        'transcript': result.transcript,
        'error': result.error
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return output_file


def process_all_videos(csv_path: str = "boko_youtube_results.csv",
                      output_dir: str = "transcripts_youtube"):
    """Process all videos and fetch transcripts."""
    
    print("=" * 70)
    print("YOUTUBE TRANSCRIPT FETCHER")
    print("=" * 70)
    print()
    
    # Load videos
    print("Loading video list...")
    videos = load_video_list(csv_path)
    print(f"Found {len(videos)} videos to process")
    print()
    
    # Setup output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Statistics
    stats = {
        'total': len(videos),
        'success': 0,
        'failed': 0,
        'disabled': 0,
        'not_found': 0,
        'unavailable': 0
    }
    
    failed_videos = []
    
    # Process each video
    for i, video in enumerate(videos, 1):
        video_id = video['video_id']
        
        print(f"[{i}/{len(videos)}] Fetching transcript for {video_id}...", end=" ")
        
        # Check if already fetched
        output_file = output_path / f"{video_id}_youtube.json"
        if output_file.exists():
            print("[CACHED]")
            stats['success'] += 1
            continue
        
        # Fetch transcript
        result = fetch_transcript(video_id)
        
        if result.success:
            print(f"[OK] Language: {result.language}, Generated: {result.is_generated}")
            stats['success'] += 1
            save_transcript(result, output_path)
        else:
            print(f"[FAILED] {result.error}")
            stats['failed'] += 1
            
            if "disabled" in result.error.lower():
                stats['disabled'] += 1
            elif "not found" in result.error.lower():
                stats['not_found'] += 1
            elif "unavailable" in result.error.lower():
                stats['unavailable'] += 1
            
            failed_videos.append({
                'video_id': video_id,
                'title': video['title'][:60],
                'error': result.error
            })
            
            # Still save the failed attempt
            save_transcript(result, output_path)
        
        # Small delay to be nice to the API
        time.sleep(0.5)
    
    # Print summary
    print()
    print("=" * 70)
    print("FETCH COMPLETE")
    print("=" * 70)
    print(f"Total videos: {stats['total']}")
    print(f"Successful: {stats['success']} ({100*stats['success']/stats['total']:.1f}%)")
    print(f"Failed: {stats['failed']} ({100*stats['failed']/stats['total']:.1f}%)")
    print()
    print("Breakdown of failures:")
    print(f"  Transcripts disabled: {stats['disabled']}")
    print(f"  No transcript found: {stats['not_found']}")
    print(f"  Video unavailable: {stats['unavailable']}")
    print()
    
    if failed_videos:
        print("Videos needing Whisper backup:")
        for v in failed_videos:
            print(f"  - {v['video_id']}: {v['title']}... ({v['error']})")
        print()
    
    print(f"Transcripts saved to: {output_dir}/")
    print()
    
    return stats, failed_videos


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch YouTube transcripts for analysis')
    parser.add_argument('--input', default='boko_youtube_results.csv', help='Input CSV file')
    parser.add_argument('--output', default='transcripts_youtube', help='Output directory')
    
    args = parser.parse_args()
    
    process_all_videos(args.input, args.output)


if __name__ == '__main__':
    main()
