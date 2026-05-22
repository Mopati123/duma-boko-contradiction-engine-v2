#!/usr/bin/env python3
"""
Analyze Video Metadata for Instant Preliminary Results
Searches titles, descriptions, and tags for target phrases.
Fast alternative to audio transcription.
"""

import json
import csv
from pathlib import Path
from typing import Dict, List, Tuple
from difflib import SequenceMatcher


def fuzzy_match(text: str, phrase: str, threshold: float = 0.6) -> Tuple[bool, float]:
    """Fuzzy match phrase in text."""
    text_lower = text.lower()
    phrase_lower = phrase.lower()
    
    if phrase_lower in text_lower:
        return True, 1.0
    
    # Keyword matching
    key_words = [w for w in phrase_lower.split() if len(w) > 3]
    if len(key_words) >= 2:
        matches = sum(1 for word in key_words if word in text_lower)
        if matches >= len(key_words) * 0.7:
            return True, 0.85
    
    return False, 0.0


def analyze_video_metadata(info_path: Path) -> Dict:
    """Analyze a single video's metadata."""
    try:
        with open(info_path, 'r', encoding='utf-8') as f:
            info = json.load(f)
    except:
        return None
    
    video_id = info_path.stem.replace('youtube_', '').replace('.info', '')
    
    # Combine all text fields
    title = info.get('title', '')
    description = info.get('description', '')
    tags = ' '.join(info.get('tags', []))
    full_text = f"{title} {description} {tags}".lower()
    
    # Target phrases
    claim_a_phrases = [
        "government will fulfil promises",
        "fulfil promises",
        "deliver promises",
        "no backing down",
        "promises made to Batswana"
    ]
    
    claim_b_phrases = [
        "promise to voters is not a legal contract",
        "not a legal contract",
        "not legally binding",
        "not binding contracts",
        "votes aren't contracts",
        "not a social contract"
    ]
    
    findings = {
        'video_id': video_id,
        'title': title,
        'upload_date': info.get('upload_date', ''),
        'url': info.get('webpage_url', f"https://youtube.com/watch?v={video_id}"),
        'claim_a_matches': [],
        'claim_b_matches': [],
        'confidence': 0.0
    }
    
    # Check Claim A phrases
    for phrase in claim_a_phrases:
        matched, conf = fuzzy_match(full_text, phrase)
        if matched:
            findings['claim_a_matches'].append((phrase, conf))
    
    # Check Claim B phrases
    for phrase in claim_b_phrases:
        matched, conf = fuzzy_match(full_text, phrase)
        if matched:
            findings['claim_b_matches'].append((phrase, conf))
    
    # Calculate overall confidence
    if findings['claim_a_matches'] and findings['claim_b_matches']:
        findings['confidence'] = 0.9  # Both claims found
    elif findings['claim_a_matches'] or findings['claim_b_matches']:
        findings['confidence'] = 0.6  # One claim found
    
    return findings


def main():
    """Analyze all video metadata."""
    print("=" * 70)
    print("ANALYZING VIDEO METADATA (Titles & Descriptions)")
    print("=" * 70)
    print()
    
    downloads_dir = Path("downloads/AUTO/Unknown")
    if not downloads_dir.exists():
        print("Error: Downloads directory not found")
        return
    
    # Find all info.json files
    info_files = list(downloads_dir.glob("*.info.json"))
    print(f"Found {len(info_files)} videos to analyze")
    print()
    
    results = []
    claim_a_videos = []
    claim_b_videos = []
    both_claims = []
    
    for i, info_file in enumerate(info_files, 1):
        result = analyze_video_metadata(info_file)
        if not result:
            continue
        
        results.append(result)
        
        if result['claim_a_matches'] and result['claim_b_matches']:
            both_claims.append(result)
            print(f"[{i}] {result['video_id']}: BOTH CLAIMS FOUND [HIGH PRIORITY]")
        elif result['claim_a_matches']:
            claim_a_videos.append(result)
            print(f"[{i}] {result['video_id']}: Claim A (Promise Fulfil)")
        elif result['claim_b_matches']:
            claim_b_videos.append(result)
            print(f"[{i}] {result['video_id']}: Claim B (Not Legal Contract)")
    
    print()
    print("=" * 70)
    print("METADATA ANALYSIS COMPLETE")
    print("=" * 70)
    print()
    print(f"Total videos analyzed: {len(results)}")
    print(f"Both claims found: {len(both_claims)} [PRIORITY for transcription]")
    print(f"Only Claim A: {len(claim_a_videos)}")
    print(f"Only Claim B: {len(claim_b_videos)}")
    print(f"No matches: {len(results) - len(both_claims) - len(claim_a_videos) - len(claim_b_videos)}")
    print()
    
    # Export results
    with open('metadata_analysis.csv', 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['video_id', 'title', 'upload_date', 'url', 
                        'claim_a_count', 'claim_b_count', 'confidence'])
        for r in results:
            writer.writerow([
                r['video_id'],
                r['title'][:80],
                r['upload_date'],
                r['url'],
                len(r['claim_a_matches']),
                len(r['claim_b_matches']),
                r['confidence']
            ])
    
    print("Exported: metadata_analysis.csv")
    
    # Return priority list for Whisper
    priority_videos = both_claims + claim_a_videos + claim_b_videos
    return priority_videos[:10]  # Top 10 for transcription


if __name__ == '__main__':
    main()
