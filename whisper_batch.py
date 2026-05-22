#!/usr/bin/env python3
"""
Batch Whisper Transcription
Transcribes top 10 videos by priority (metadata matches first, then by size)
"""

import whisper
import json
from pathlib import Path
from typing import Dict, List

def get_priority_videos():
    """Get videos prioritized by metadata analysis, then by size."""
    downloads_dir = Path("downloads/AUTO/Unknown")
    videos = list(downloads_dir.glob("*.mp4"))
    
    # Try to read metadata analysis
    priority_ids = []
    csv_file = Path("metadata_analysis.csv")
    if csv_file.exists():
        import csv
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            # Sort by confidence descending
            rows = sorted(reader, key=lambda x: float(x.get('confidence', 0)), reverse=True)
            for row in rows[:10]:
                priority_ids.append(row['video_id'])
    
    # Match videos to priority IDs
    priority_videos = []
    other_videos = []
    
    for video in videos:
        vid_id = video.stem.replace('youtube_', '')
        if vid_id in priority_ids:
            priority_videos.append((priority_ids.index(vid_id), video))
        else:
            other_videos.append(video)
    
    # Sort priority videos by their rank
    priority_videos.sort(key=lambda x: x[0])
    
    # Add remaining videos sorted by size (largest first = likely longer/more content)
    other_videos.sort(key=lambda x: x.stat().st_size, reverse=True)
    
    # Combine: priority first, then top by size
    final_list = [v[1] for v in priority_videos] + other_videos
    
    return final_list[:10]


def transcribe_video(model, video_path: Path) -> Dict:
    """Transcribe a single video."""
    print(f"\nTranscribing: {video_path.name}")
    print(f"Size: {video_path.stat().st_size / (1024*1024):.1f} MB")
    
    try:
        result = model.transcribe(str(video_path), verbose=False, fp16=False)
        
        transcript_data = []
        for segment in result["segments"]:
            transcript_data.append({
                "text": segment["text"].strip(),
                "start": segment["start"],
                "duration": segment["end"] - segment["start"]
            })
        
        full_text = " ".join([entry["text"] for entry in transcript_data])
        
        return {
            "video_id": video_path.stem.replace("youtube_", ""),
            "success": True,
            "language": result.get("language", "en"),
            "is_generated": True,
            "full_text": full_text,
            "transcript": transcript_data
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            "video_id": video_path.stem.replace("youtube_", ""),
            "success": False,
            "error": str(e)
        }


def save_transcript(data: Dict, output_dir: Path):
    """Save transcript to JSON."""
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{data['video_id']}_whisper.json"
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    return output_path


def main():
    """Batch transcribe top 10 videos."""
    print("=" * 70)
    print("BATCH WHISPER TRANSCRIPTION (Top 10 Videos)")
    print("=" * 70)
    print()
    
    # Get priority videos
    videos = get_priority_videos()
    print(f"Selected {len(videos)} videos for transcription")
    print()
    
    # Load model once
    print("Loading Whisper model (base)...")
    model = whisper.load_model("base")
    print("Model loaded!")
    print()
    
    # Transcribe each
    output_dir = Path("transcripts_whisper")
    success_count = 0
    
    for i, video in enumerate(videos, 1):
        print(f"\n{'='*70}")
        print(f"VIDEO {i}/{len(videos)}")
        print(f"{'='*70}")
        
        result = transcribe_video(model, video)
        
        if result['success']:
            output_path = save_transcript(result, output_dir)
            print(f"[OK] Saved: {output_path}")
            print(f"     Segments: {len(result['transcript'])}")
            print(f"     Preview: {result['full_text'][:100]}...")
            success_count += 1
        else:
            print(f"[FAILED] {result.get('error', 'Unknown error')}")
    
    print()
    print("=" * 70)
    print("BATCH TRANSCRIPTION COMPLETE")
    print("=" * 70)
    print(f"Successful: {success_count}/{len(videos)}")
    print(f"Transcripts saved to: {output_dir}/")


if __name__ == '__main__':
    main()
