#!/usr/bin/env python3
"""
Evidence Video Downloader
Downloads all YouTube videos that support contradiction claims
"""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

def extract_video_urls(evidence_file):
    """Extract unique YouTube video URLs from evidence file"""
    with open(evidence_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    video_urls = set()
    video_details = []
    
    # Extract from all_earlier_sources
    for target in data.get('target_results', []):
        case_id = target.get('case_id')
        
        for source in target.get('all_earlier_sources', []):
            if source.get('url') and 'youtube.com/watch' in source.get('url'):
                url = source['url']
                video_id = extract_video_id(url)
                if video_id and video_id not in [v['id'] for v in video_urls]:
                    video_details.append({
                        'case_id': case_id,
                        'video_id': video_id,
                        'url': f"https://www.youtube.com/watch?v={video_id}",
                        'quote': source.get('quote', '')[:100],
                        'timestamp': extract_timestamp(url)
                    })
                    video_urls.add(video_id)
    
    # Extract from raw_urls
    for url in data.get('target_results', [{}])[0].get('raw_urls', []):
        if 'youtube.com/watch' in url:
            video_id = extract_video_id(url)
            if video_id and video_id not in [v['id'] for v in video_urls]:
                video_details.append({
                    'case_id': 'MULTIPLE',
                    'video_id': video_id,
                    'url': f"https://www.youtube.com/watch?v={video_id}",
                    'quote': 'Multiple evidence quotes',
                    'timestamp': extract_timestamp(url)
                })
                video_urls.add(video_id)
    
    return video_details

def extract_video_id(url):
    """Extract YouTube video ID from URL"""
    if 'youtube.com/watch' in url:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return params.get('v', [None])[0]
    return None

def extract_timestamp(url):
    """Extract timestamp from URL if present"""
    if 'youtube.com/watch' in url:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        return params.get('t', [None])[0]
    return None

def download_video(video_details, output_dir):
    """Download video using yt-dlp"""
    video_id = video_details['video_id']
    url = video_details['url']
    
    # Create case-specific subdirectory
    case_dir = output_dir / f"CASE_{video_details['case_id']}"
    case_dir.mkdir(parents=True, exist_ok=True)
    
    # Download with metadata
    cmd = [
        'yt-dlp',
        '--format', 'mp4',
        '--output', str(case_dir / f"{video_id}.mp4"),
        '--write-info-json',
        '--write-thumbnail',
        '--write-subtitles',
        '--sub-langs', 'en',
        url
    ]
    
    print(f"\n📥 Downloading {video_id} for CASE_{video_details['case_id']}")
    print(f"   Quote: {video_details['quote']}")
    print(f"   Timestamp: {video_details['timestamp']}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print(f"   ✅ Successfully downloaded {video_id}")
            
            # Save metadata
            metadata_file = case_dir / f"{video_id}_metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(video_details, f, indent=2, ensure_ascii=False)
            print(f"   📄 Saved metadata to {metadata_file}")
            
            return True
        else:
            print(f"   ❌ Failed to download {video_id}: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"   ⏰ Timeout downloading {video_id}")
        return False
    except Exception as e:
        print(f"   💥 Error downloading {video_id}: {e}")
        return False

def main():
    """Main download function"""
    evidence_file = Path("outputs/target_search_results.json")
    output_dir = Path("downloads/EVIDENCE_VIDEOS")
    
    if not evidence_file.exists():
        print(f"❌ Evidence file not found: {evidence_file}")
        return
    
    print("🎥 Evidence Video Downloader")
    print("=" * 50)
    
    # Extract video URLs
    video_details = extract_video_urls(evidence_file)
    
    if not video_details:
        print("❌ No YouTube videos found in evidence")
        return
    
    print(f"\n📋 Found {len(video_details)} unique videos to download:")
    for video in video_details:
        print(f"   {video['video_id']} - CASE_{video['case_id']}")
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Download videos
    success_count = 0
    for video in video_details:
        if download_video(video, output_dir):
            success_count += 1
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 DOWNLOAD SUMMARY")
    print("=" * 50)
    print(f"Total videos found: {len(video_details)}")
    print(f"Successfully downloaded: {success_count}")
    print(f"Failed: {len(video_details) - success_count}")
    print(f"Output directory: {output_dir}")
    
    # Create index file
    index_file = output_dir / "video_index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump({
            'download_date': '2026-05-12',
            'total_videos': len(video_details),
            'successful_downloads': success_count,
            'videos': video_details
        }, f, indent=2, ensure_ascii=False)
    
    print(f"📄 Created video index: {index_file}")

if __name__ == '__main__':
    main()
