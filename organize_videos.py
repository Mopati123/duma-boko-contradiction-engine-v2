#!/usr/bin/env python3
"""
Organize Videos by Contradiction
Renames and moves videos to PROCESSED folder with descriptive names.
"""

import json
import csv
import shutil
from pathlib import Path
from typing import Dict, List


def load_analysis_results(csv_path: str = "analysis_results.csv") -> List[Dict]:
    """Load analysis results CSV."""
    results = []
    csv_file = Path(csv_path)
    
    if not csv_file.exists():
        return results
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append(row)
    
    return results


def get_video_metadata(video_id: str, source_dir: Path) -> Dict:
    """Get metadata from info.json file."""
    info_path = source_dir / f"youtube_{video_id}.info.json"
    
    if not info_path.exists():
        return {}
    
    try:
        with open(info_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}


def generate_descriptive_name(video_id: str, analysis: Dict, metadata: Dict) -> str:
    """Generate descriptive filename based on analysis."""
    # Extract date
    upload_date = metadata.get('upload_date', 'unknown')
    
    # Extract event from title
    title = metadata.get('title', '')
    event_name = "Unknown"
    
    if 'kgotla' in title.lower():
        if 'tonota' in title.lower():
            event_name = "TonotaKgotla"
        elif 'tutume' in title.lower():
            event_name = "TutumeKgotla"
        elif 'tlokweng' in title.lower():
            event_name = "TlokwengKgotla"
        elif 'kanye' in title.lower():
            event_name = "KanyeKgotla"
        elif 'ramotswa' in title.lower() or 'gamalete' in title.lower():
            event_name = "RamotswaKgotla"
        elif 'kgagodi' in title.lower():
            event_name = "KgagodiKgotla"
        elif 'palapye' in title.lower():
            event_name = "PalapyeKgotla"
        else:
            event_name = "Kgotla"
    elif 'sona' in title.lower():
        event_name = "SONA"
    elif 'inaugural' in title.lower() or 'un speech' in title.lower():
        event_name = "UNSpeech"
    elif 'press' in title.lower() or 'interview' in title.lower():
        event_name = "PressInterview"
    elif 'parliament' in title.lower():
        event_name = "Parliament"
    
    # Determine claim type
    claim_type = analysis.get('claim_type', 'Unclassified')
    quote_type = analysis.get('quote_type', 'Unknown')
    
    # Format quote type
    if quote_type == 'promise_fulfil':
        quote_type_str = "PromiseFulfil"
    elif quote_type == 'not_legal_contract':
        quote_type_str = "NotLegalContract"
    else:
        quote_type_str = quote_type.replace('_', '').title()
    
    # Build filename
    return f"CASE1_{claim_type}_{quote_type_str}_{event_name}_{upload_date}_{video_id}.mp4"


def organize_video(video_id: str, analysis: Dict, source_dir: Path, dest_dir: Path):
    """Organize a single video."""
    # Get metadata
    metadata = get_video_metadata(video_id, source_dir)
    
    # Generate new name
    new_name = generate_descriptive_name(video_id, analysis, metadata)
    
    # Source and dest paths
    source_video = source_dir / f"youtube_{video_id}.mp4"
    dest_video = dest_dir / new_name
    
    if not source_video.exists():
        print(f"  [SKIP] Video not found: {source_video}")
        return False
    
    try:
        # Copy video
        shutil.copy2(source_video, dest_video)
        print(f"  [OK] {new_name}")
        
        # Copy related files
        for ext in ['.info.json', '.description', '.webp', '.mp3']:
            src = source_video.with_suffix(ext)
            if src.exists():
                dst = dest_video.with_suffix(ext)
                shutil.copy2(src, dst)
        
        # Copy transcript if exists
        transcript_sources = [
            Path(f"transcripts_whisper/{video_id}_whisper.json"),
            Path(f"transcripts_youtube/{video_id}_youtube.json")
        ]
        for src in transcript_sources:
            if src.exists():
                dst = dest_dir / f"{dest_video.stem}.transcript.json"
                shutil.copy2(src, dst)
                break
        
        return True
        
    except Exception as e:
        print(f"  [ERROR] {e}")
        return False


def generate_evidence_csv(analysis_results: List[Dict], output_path: Path):
    """Generate final evidence CSV."""
    if not analysis_results:
        print("No analysis results to export")
        return
    
    fieldnames = [
        'case_id', 'event_name', 'claim_type', 'quote_text',
        'start_time', 'end_time', 'timestamp_readable',
        'context_before', 'context_after',
        'confidence', 'video_filename', 'url',
        'verified', 'notes'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for result in analysis_results:
            # Format timestamp
            start_sec = float(result.get('start_time', 0))
            mins = int(start_sec // 60)
            secs = int(start_sec % 60)
            timestamp_str = f"{mins}:{secs:02d}"
            
            row = {
                'case_id': 'CASE1',
                'event_name': result.get('event_name', 'Unknown'),
                'claim_type': result.get('claim_type', 'Unknown'),
                'quote_text': result.get('quote_text', '')[:200],
                'start_time': result.get('start_time', ''),
                'end_time': result.get('end_time', ''),
                'timestamp_readable': timestamp_str,
                'context_before': result.get('context_before', '')[:150],
                'context_after': result.get('context_after', '')[:150],
                'confidence': result.get('confidence', 0),
                'video_filename': result.get('video_id', ''),
                'url': f"https://youtube.com/watch?v={result.get('video_id', '')}",
                'verified': 'pending',
                'notes': f"Matched: {result.get('matched_phrase', '')}"
            }
            writer.writerow(row)
    
    print(f"Exported evidence: {output_path}")


def generate_summary_report(processed_count: int, total_videos: int, 
                            claim_a_count: int, claim_b_count: int):
    """Generate summary report."""
    report_path = Path("downloads/PROCESSED/processing_report.txt")
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("=" * 70 + "\n")
        f.write("VIDEO EVIDENCE PROCESSING REPORT\n")
        f.write("=" * 70 + "\n\n")
        f.write(f"Date: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("STATISTICS:\n")
        f.write(f"  Total videos analyzed: {total_videos}\n")
        f.write(f"  Videos processed: {processed_count}\n")
        f.write(f"  Claim A (Promise Fulfil): {claim_a_count}\n")
        f.write(f"  Claim B (Not Legal Contract): {claim_b_count}\n\n")
        f.write("OUTPUT LOCATIONS:\n")
        f.write(f"  Organized videos: downloads/PROCESSED/\n")
        f.write(f"  Evidence CSV: downloads/evidence_final.csv\n")
        f.write(f"  This report: downloads/PROCESSED/processing_report.txt\n\n")
        f.write("=" * 70 + "\n")
    
    print(f"Generated report: {report_path}")


def main():
    """Main organization function."""
    print("=" * 70)
    print("ORGANIZING VIDEOS BY CONTRADICTION")
    print("=" * 70)
    print()
    
    # Setup directories
    source_dir = Path("downloads/AUTO/Unknown")
    dest_dir = Path("downloads/PROCESSED")
    dest_dir.mkdir(parents=True, exist_ok=True)
    
    # Load analysis results
    print("Loading analysis results...")
    analysis_results = load_analysis_results()
    
    if not analysis_results:
        print("No analysis results found. Run analyze_transcripts.py first.")
        return
    
    print(f"Found {len(analysis_results)} analyzed videos")
    print()
    
    # Organize each video
    print("Organizing videos...")
    success_count = 0
    claim_a_count = 0
    claim_b_count = 0
    
    for analysis in analysis_results:
        video_id = analysis.get('video_id', '')
        if not video_id:
            continue
        
        print(f"\nProcessing {video_id}...")
        if organize_video(video_id, analysis, source_dir, dest_dir):
            success_count += 1
            if analysis.get('claim_type') == 'Claim_A':
                claim_a_count += 1
            elif analysis.get('claim_type') == 'Claim_B':
                claim_b_count += 1
    
    print()
    print("=" * 70)
    print("ORGANIZATION COMPLETE")
    print("=" * 70)
    print(f"Successfully organized: {success_count}/{len(analysis_results)} videos")
    print()
    
    # Generate evidence CSV
    print("Generating evidence CSV...")
    generate_evidence_csv(analysis_results, Path("downloads/evidence_final.csv"))
    
    # Generate summary report
    total_videos = len(list(source_dir.glob("*.mp4")))
    generate_summary_report(success_count, total_videos, claim_a_count, claim_b_count)
    
    print()
    print("All outputs complete!")
    print(f"  Videos: {dest_dir}/")
    print(f"  Evidence: downloads/evidence_final.csv")


if __name__ == '__main__':
    main()
