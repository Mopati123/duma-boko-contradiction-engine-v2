#!/usr/bin/env python3
"""
Compile evidence from all transcript files into a comprehensive CSV.
"""
import json
import csv
from pathlib import Path
from datetime import datetime
from typing import List, Dict

# Target phrases for contradiction detection
TARGET_PHRASES = [
    "unconstitutional",
    "illegal", 
    "breach",
    "violation",
    "against the law",
    "not lawful",
    "invalid",
    "null and void",
    "abuse of power",
    "misuse of authority",
    "conflict of interest",
    "not transparent",
    "lack of accountability",
    "dishonest",
    "corrupt",
    "fraudulent",
    "deceptive",
    "misleading",
    "false statement",
    "not true",
    "lie",
    "lying",
    "untruthful",
    "inconsistent",
    "contradict",
    "contradiction",
    "flip-flop",
    "backtrack",
    "reversal",
    "changed position",
    "different from before",
    "opposite of",
    "not what I said",
    "misquoted",
    "taken out of context",
]

def load_transcript(transcript_path: Path) -> Dict:
    """Load transcript from JSON file."""
    try:
        with open(transcript_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"  [ERROR] Failed to load {transcript_path}: {e}")
        return {}

def find_contradictions_in_transcript(video_id: str, transcript: List[Dict]) -> List[Dict]:
    """Find contradictions in transcript segments."""
    findings = []
    
    for segment in transcript:
        text = segment.get('text', '').lower()
        start_time = segment.get('start', 0)
        end_time = segment.get('end', 0)
        
        # Check for target phrases
        for phrase in TARGET_PHRASES:
            if phrase.lower() in text:
                # Found a potential contradiction
                finding = {
                    'video_id': video_id,
                    'timestamp': f"{start_time:.1f}-{end_time:.1f}",
                    'start_time': start_time,
                    'end_time': end_time,
                    'category': 'contradiction_indicator',
                    'matched_phrase': phrase,
                    'text': segment.get('text', '').strip(),
                    'confidence': 0.7,  # Base confidence
                    'full_text': text
                }
                findings.append(finding)
                break  # One finding per segment is enough
    
    return findings

def compile_all_evidence():
    """Compile evidence from all transcript files."""
    print("="*70)
    print("COMPILING EVIDENCE FROM ALL TRANSCRIPTS")
    print("="*70)
    
    transcript_dir = Path("downloads/TRANSCRIPTS")
    output_csv = Path("downloads/evidence_final.csv")
    
    if not transcript_dir.exists():
        print(f"[ERROR] Transcript directory not found: {transcript_dir}")
        return
    
    # Find all transcript files
    transcript_files = list(transcript_dir.glob("*.transcript.json"))
    print(f"\nFound {len(transcript_files)} transcript files")
    
    all_findings = []
    
    for i, transcript_file in enumerate(transcript_files, 1):
        print(f"\n[{i}/{len(transcript_files)}] Processing {transcript_file.name}...")
        
        # Load transcript
        data = load_transcript(transcript_file)
        if not data:
            continue
        
        video_id = data.get('video_id', transcript_file.stem.replace('.transcript', ''))
        transcript = data.get('transcript', [])
        
        print(f"  Video ID: {video_id}")
        print(f"  Segments: {len(transcript)}")
        
        # Find contradictions
        findings = find_contradictions_in_transcript(video_id, transcript)
        
        if findings:
            print(f"  [FOUND] {len(findings)} potential contradictions")
            all_findings.extend(findings)
            
            # Also save individual analysis file
            analysis_path = transcript_file.with_suffix('.analysis.json')
            analysis_data = {
                'video_id': video_id,
                'processed_at': datetime.now().isoformat(),
                'findings_count': len(findings),
                'findings': findings
            }
            with open(analysis_path, 'w', encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=2, ensure_ascii=False)
            print(f"  [SAVED] Analysis: {analysis_path.name}")
        else:
            print(f"  [OK] No contradictions found")
    
    # Compile to CSV
    print(f"\n{'='*70}")
    print("COMPILING CSV")
    print(f"{'='*70}")
    
    if all_findings:
        # Sort by confidence
        all_findings.sort(key=lambda x: x['confidence'], reverse=True)
        
        # Write CSV
        fieldnames = ['video_id', 'timestamp', 'start_time', 'end_time', 'category', 
                      'matched_phrase', 'text', 'confidence', 'full_text']
        
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_findings)
        
        print(f"[SUCCESS] Compiled {len(all_findings)} findings to {output_csv}")
        
        # Show top findings
        print(f"\n[TOP 10 FINDINGS]")
        for i, finding in enumerate(all_findings[:10], 1):
            print(f"  {i}. [{finding['video_id']}] {finding['matched_phrase']}")
            print(f"     Time: {finding['timestamp']}")
            print(f"     Text: {finding['text'][:100]}...")
            print()
    else:
        print(f"[WARNING] No findings to export")
        # Create empty CSV with headers
        fieldnames = ['video_id', 'timestamp', 'start_time', 'end_time', 'category', 
                      'matched_phrase', 'text', 'confidence', 'full_text']
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        print(f"[OK] Created empty CSV with headers: {output_csv}")
    
    # Summary
    print(f"\n{'='*70}")
    print("COMPILATION COMPLETE")
    print(f"{'='*70}")
    print(f"Total videos analyzed: {len(transcript_files)}")
    print(f"Total findings: {len(all_findings)}")
    print(f"Output file: {output_csv}")
    print(f"\nNext: Review {output_csv} for manual verification")

if __name__ == "__main__":
    compile_all_evidence()
