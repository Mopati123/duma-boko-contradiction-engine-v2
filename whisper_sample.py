#!/usr/bin/env python3
"""
Whisper Sample Transcription
Transcribes 2-3 sample videos to demonstrate the analysis workflow.
"""

import whisper
import json
from pathlib import Path
from typing import Dict, List


def transcribe_video(video_path: Path, model_size: str = "base") -> Dict:
    """Transcribe a single video using Whisper."""
    print(f"Loading Whisper model: {model_size}")
    model = whisper.load_model(model_size)
    
    print(f"Transcribing: {video_path.name}")
    result = model.transcribe(str(video_path), verbose=False)
    
    # Format to match YouTube transcript structure
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


def save_transcript(data: Dict, output_path: Path):
    """Save transcript to JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def main():
    """Transcribe 2-3 sample videos."""
    print("=" * 70)
    print("WHISPER SAMPLE TRANSCRIPTION")
    print("=" * 70)
    print()
    
    # Find downloaded videos
    downloads_dir = Path("downloads/AUTO/Unknown")
    if not downloads_dir.exists():
        print(f"Error: {downloads_dir} not found")
        return
    
    videos = list(downloads_dir.glob("*.mp4"))
    if not videos:
        print("No videos found to transcribe")
        return
    
    # Sort by size and take first 3
    videos = sorted(videos, key=lambda x: x.stat().st_size, reverse=True)[:3]
    
    print(f"Found {len(videos)} videos to transcribe")
    print()
    
    # Setup output directory
    output_dir = Path("transcripts_whisper")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Transcribe each
    for i, video in enumerate(videos, 1):
        print(f"\n{'='*70}")
        print(f"VIDEO {i}/{len(videos)}: {video.name}")
        print(f"{'='*70}")
        
        try:
            result = transcribe_video(video, model_size="base")
            
            # Save transcript
            video_id = result["video_id"]
            output_path = output_dir / f"{video_id}_whisper.json"
            save_transcript(result, output_path)
            
            print(f"[OK] Transcript saved: {output_path}")
            print(f"     Language: {result['language']}")
            print(f"     Duration: ~{len(result['transcript'])} segments")
            print(f"     Text preview: {result['full_text'][:150]}...")
            
        except Exception as e:
            print(f"[ERROR] Failed to transcribe: {e}")
    
    print()
    print("=" * 70)
    print("SAMPLE TRANSCRIPTION COMPLETE")
    print("=" * 70)
    print(f"Transcripts saved to: {output_dir}/")
    print()
    print("Next: Run analyze_transcripts.py to find contradictions")


if __name__ == '__main__':
    main()
