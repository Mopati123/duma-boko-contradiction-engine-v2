#!/usr/bin/env python3
"""
Process Priority Videos End-to-End
Extracts audio, transcribes with Whisper, analyzes for contradictions, and organizes.
Does everything in one shot for high-priority videos.
"""

import whisper
import json
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List
from dataclasses import dataclass
from difflib import SequenceMatcher


@dataclass
class Finding:
    video_id: str
    claim_type: str
    quote_text: str
    start_time: float
    end_time: float
    confidence: float


def extract_audio(video_path: Path, audio_path: Path) -> bool:
    """Extract audio using FFmpeg."""
    try:
        cmd = [
            'ffmpeg', '-i', str(video_path),
            '-vn', '-ar', '16000', '-ac', '1',
            '-b:a', '128k', '-y', str(audio_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=300)
        return result.returncode == 0 and audio_path.exists()
    except:
        return False


def transcribe_audio(model, audio_path: Path) -> Dict:
    """Transcribe audio with Whisper."""
    result = model.transcribe(str(audio_path), verbose=False, fp16=False)
    
    transcript_data = []
    for segment in result["segments"]:
        transcript_data.append({
            "text": segment["text"].strip(),
            "start": segment["start"],
            "duration": segment["end"] - segment["start"]
        })
    
    full_text = " ".join([entry["text"] for entry in transcript_data])
    
    return {
        "transcript": transcript_data,
        "full_text": full_text,
        "language": result.get("language", "en")
    }


def find_contradictions(video_id: str, transcript_data: List[Dict], full_text: str) -> List[Finding]:
    """Find contradictions in transcript."""
    findings = []
    
    # Target phrases
    claim_a_phrases = [
        ("promise to voters is not a legal contract", "NotLegalContract"),
        ("not a legal contract", "NotLegalContract"),
        ("not legally binding", "NotLegalContract"),
        ("votes aren't contracts", "NotLegalContract"),
        ("not a social contract", "NotLegalContract"),
    ]
    
    claim_b_phrases = [
        ("government will fulfil promises", "PromiseFulfil"),
        ("fulfil promises", "PromiseFulfil"),
        ("deliver promises", "PromiseFulfil"),
        ("no backing down", "PromiseFulfil"),
    ]
    
    text_lower = full_text.lower()
    
    # Check for Claim A phrases
    for phrase, quote_type in claim_a_phrases:
        if phrase.lower() in text_lower:
            # Find which segment contains this
            for seg in transcript_data:
                if phrase.lower() in seg["text"].lower():
                    findings.append(Finding(
                        video_id=video_id,
                        claim_type=f"ClaimA_{quote_type}",
                        quote_text=seg["text"],
                        start_time=seg["start"],
                        end_time=seg["start"] + seg["duration"],
                        confidence=1.0
                    ))
                    break
    
    # Check for Claim B phrases
    for phrase, quote_type in claim_b_phrases:
        if phrase.lower() in text_lower:
            for seg in transcript_data:
                if phrase.lower() in seg["text"].lower():
                    findings.append(Finding(
                        video_id=video_id,
                        claim_type=f"ClaimB_{quote_type}",
                        quote_text=seg["text"],
                        start_time=seg["start"],
                        end_time=seg["start"] + seg["duration"],
                        confidence=1.0
                    ))
                    break
    
    return findings


def organize_video(video_id: str, finding: Finding, source_dir: Path, dest_dir: Path):
    """Copy video with descriptive name."""
    source = source_dir / f"youtube_{video_id}.mp4"
    if not source.exists():
        return False
    
    # Get metadata
    info_path = source.with_suffix('.info.json')
    upload_date = "unknown"
    event_name = "Unknown"
    
    if info_path.exists():
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
                upload_date = info.get('upload_date', 'unknown')
                title = info.get('title', '')
                if 'kgotla' in title.lower():
                    if 'tonota' in title.lower():
                        event_name = "TonotaKgotla"
                    elif 'tlokweng' in title.lower():
                        event_name = "TlokwengKgotla"
                    elif 'ramotswa' in title.lower():
                        event_name = "RamotswaKgotla"
                    else:
                        event_name = "Kgotla"
                elif 'sona' in title.lower():
                    event_name = "SONA"
        except:
            pass
    
    # Build name
    claim_type = finding.claim_type.replace("_", "")
    new_name = f"CASE1_{claim_type}_{event_name}_{upload_date}_{video_id}.mp4"
    dest = dest_dir / new_name
    
    try:
        shutil.copy2(source, dest)
        print(f"  [OK] {new_name}")
        return True
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def process_single_video(model, video_path: Path, source_dir: Path, dest_dir: Path) -> List[Finding]:
    """Process one video end-to-end."""
    video_id = video_path.stem.replace("youtube_", "")
    
    print(f"\nProcessing {video_id}...")
    print(f"  Size: {video_path.stat().st_size / (1024*1024):.1f} MB")
    
    # Extract audio
    audio_path = Path(f"temp_{video_id}.mp3")
    print("  Extracting audio...")
    if not extract_audio(video_path, audio_path):
        print("  [ERROR] Audio extraction failed")
        return []
    
    # Transcribe
    print("  Transcribing...")
    transcript = transcribe_audio(model, audio_path)
    
    # Cleanup audio
    audio_path.unlink(missing_ok=True)
    
    # Find contradictions
    print("  Analyzing for contradictions...")
    findings = find_contradictions(video_id, transcript["transcript"], transcript["full_text"])
    
    if findings:
        print(f"  [FOUND] {len(findings)} contradictions")
        for f in findings:
            print(f"    - {f.claim_type}: {f.quote_text[:60]}...")
        
        # Organize video
        print("  Organizing...")
        for finding in findings:
            organize_video(video_id, finding, source_dir, dest_dir)
    else:
        print("  [No contradictions found]")
    
    return findings


def main():
    """Process top videos."""
    print("=" * 70)
    print("PRIORITY VIDEO PROCESSOR (End-to-End)")
    print("=" * 70)
    print()
    
    # Load Whisper model
    print("Loading Whisper model (base)...")
    model = whisper.load_model("base")
    print("Ready!")
    print()
    
    # Setup
    source_dir = Path("downloads/AUTO/Unknown")
    dest_dir = Path("downloads/PROCESSED")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Get top 5 largest videos (likely most content)
    videos = sorted(source_dir.glob("*.mp4"), key=lambda x: x.stat().st_size, reverse=True)[:5]
    
    print(f"Processing top {len(videos)} videos by size...")
    print()
    
    all_findings = []
    
    for i, video in enumerate(videos, 1):
        print(f"\n{'='*70}")
        print(f"VIDEO {i}/{len(videos)}")
        print(f"{'='*70}")
        
        findings = process_single_video(model, video, source_dir, dest_dir)
        all_findings.extend(findings)
    
    # Summary
    print()
    print("=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)
    print(f"Total videos processed: {len(videos)}")
    print(f"Total contradictions found: {len(all_findings)}")
    
    if all_findings:
        claim_a = sum(1 for f in all_findings if "ClaimA" in f.claim_type)
        claim_b = sum(1 for f in all_findings if "ClaimB" in f.claim_type)
        print(f"  Claim A (Not Legal Contract): {claim_a}")
        print(f"  Claim B (Promise Fulfil): {claim_b}")
    
    print(f"\nOrganized videos: {dest_dir}/")
    print("\nNext: Check PROCESSED folder for renamed videos with contradictions")


if __name__ == '__main__':
    main()
