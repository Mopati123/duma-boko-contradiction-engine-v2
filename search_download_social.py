#!/usr/bin/env python3
"""
Search and download Duma Boko videos from Facebook and TikTok.
Uses yt-dlp for downloading with platform-specific options.
"""
import json
import subprocess
import re
from pathlib import Path
from typing import List, Dict, Optional

# Known Duma Boko social media accounts/URLs to check
KNOWN_FACEBOOK_URLS = [
    "https://www.facebook.com/watch/?v=example1",  # Placeholder - will search
]

KNOWN_TIKTOK_URLS = [
    "https://www.tiktok.com/@dumaboko",  # Hypothetical username
]

# Search queries
SEARCH_QUERIES = [
    "Duma Boko",
    "President Boko Botswana",
    "UDC Duma Boko",
    "Botswana president speech"
]

def run_yt_dlp_search(query: str, platform: str, max_results: int = 10) -> List[Dict]:
    """Search for videos using yt-dlp generic search."""
    print(f"\nSearching {platform}: '{query}'")
    
    try:
        # Use yt-dlp to search - note: this searches via YouTube's search
        # For Facebook/TikTok, we need direct URLs or use their APIs
        
        # For TikTok, we can try direct user scraping
        if platform == "tiktok":
            return search_tiktok_direct(query, max_results)
        elif platform == "facebook":
            return search_facebook_direct(query, max_results)
        
    except Exception as e:
        print(f"  [ERROR] Search failed: {e}")
    
    return []

def search_tiktok_direct(query: str, max_results: int = 10) -> List[Dict]:
    """Attempt to find TikTok videos with Duma Boko content."""
    results = []
    
    # Try to download from known TikTok patterns
    # Since we don't have API access, we'll try yt-dlp with TikTok URLs
    
    search_terms = [
        f"https://www.tiktok.com/search?q={query.replace(' ', '%20')}",
    ]
    
    # Note: TikTok blocks automated scraping, so this is limited
    print(f"  [INFO] TikTok blocks automated search. Manual URL input required.")
    print(f"  [INFO] Please provide TikTok URLs directly if known.")
    
    return results

def search_facebook_direct(query: str, max_results: int = 10) -> List[Dict]:
    """Attempt to find Facebook videos with Duma Boko content."""
    results = []
    
    # Facebook also blocks scraping without API
    print(f"  [INFO] Facebook requires API access or manual URL input.")
    print(f"  [INFO] Please provide Facebook video URLs directly if known.")
    
    return results

def download_video(url: str, platform: str, output_dir: Path) -> Optional[Dict]:
    """Download a video using yt-dlp."""
    print(f"\n[{platform.upper()}] Downloading: {url}")
    
    # Extract video ID from URL
    video_id = extract_video_id(url, platform)
    if not video_id:
        video_id = "unknown"
    
    output_template = str(output_dir / f"{video_id}_%(title).50s.%(ext)s")
    
    try:
        # yt-dlp command with best quality
        cmd = [
            "yt-dlp",
            "--no-warnings",
            "--format", "best[ext=mp4]/best",  # Best quality MP4
            "--output", output_template,
            "--write-info-json",  # Save metadata
            "--write-thumbnail",  # Save thumbnail
            "--no-playlist",  # Single video only
            "--retries", "3",
            url
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300
        )
        
        if result.returncode == 0:
            print(f"  [OK] Downloaded successfully")
            
            # Find downloaded file
            downloaded_files = list(output_dir.glob(f"{video_id}_*"))
            video_files = [f for f in downloaded_files if f.suffix == '.mp4']
            
            if video_files:
                video_path = video_files[0]
                
                # Load metadata
                json_files = [f for f in downloaded_files if f.suffix == '.info.json']
                metadata = {}
                if json_files:
                    with open(json_files[0], 'r', encoding='utf-8') as f:
                        metadata = json.load(f)
                
                return {
                    'url': url,
                    'platform': platform,
                    'video_id': video_id,
                    'local_path': str(video_path),
                    'title': metadata.get('title', 'Unknown'),
                    'uploader': metadata.get('uploader', 'Unknown'),
                    'upload_date': metadata.get('upload_date', 'Unknown'),
                    'duration': metadata.get('duration', 0),
                    'view_count': metadata.get('view_count', 0),
                    'metadata': metadata
                }
        else:
            print(f"  [ERROR] Download failed: {result.stderr[:200]}")
            return None
            
    except subprocess.TimeoutExpired:
        print(f"  [ERROR] Download timeout")
        return None
    except Exception as e:
        print(f"  [ERROR] Exception: {e}")
        return None

def extract_video_id(url: str, platform: str) -> Optional[str]:
    """Extract video ID from URL."""
    if platform == "facebook":
        # Facebook video ID patterns
        patterns = [
            r'facebook\.com/watch/\?v=(\d+)',
            r'fb\.watch/(\w+)',
            r'facebook\.com/.+/videos/(\d+)',
        ]
    elif platform == "tiktok":
        # TikTok video ID patterns
        patterns = [
            r'tiktok.com/.*/video/(\d+)',
            r'tiktok.com/.*/.*/(\d+)',
        ]
    else:
        return None
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    # Fallback: use URL hash
    import hashlib
    return hashlib.md5(url.encode()).hexdigest()[:12]

def process_manual_urls():
    """Process manually provided URLs since automated search is blocked."""
    
    # Facebook URLs to process (user can add more)
    facebook_urls = [
        # Add known Facebook video URLs here
        # "https://www.facebook.com/watch/?v=1234567890",
    ]
    
    # TikTok URLs to process (user can add more)
    tiktok_urls = [
        # Add known TikTok video URLs here
        # "https://www.tiktok.com/@username/video/1234567890",
    ]
    
    # Also check if user provided URLs via command line or file
    urls_file = Path("manual_urls.txt")
    if urls_file.exists():
        with open(urls_file, 'r') as f:
            for line in f:
                line = line.strip()
                if 'facebook.com' in line or 'fb.watch' in line:
                    facebook_urls.append(line)
                elif 'tiktok.com' in line:
                    tiktok_urls.append(line)
    
    print("="*70)
    print("SOCIAL MEDIA VIDEO DOWNLOADER")
    print("="*70)
    
    print(f"\nFacebook URLs to process: {len(facebook_urls)}")
    print(f"TikTok URLs to process: {len(tiktok_urls)}")
    
    if not facebook_urls and not tiktok_urls:
        print("\n[WARNING] No URLs provided!")
        print("Please add URLs to manual_urls.txt or modify this script.")
        print("\nExpected format in manual_urls.txt:")
        print("  https://www.facebook.com/watch/?v=123456789")
        print("  https://www.tiktok.com/@username/video/987654321")
        return []
    
    all_downloaded = []
    
    # Process Facebook URLs
    fb_output_dir = Path("downloads/FACEBOOK/raw")
    fb_output_dir.mkdir(parents=True, exist_ok=True)
    
    for url in facebook_urls:
        result = download_video(url, "facebook", fb_output_dir)
        if result:
            all_downloaded.append(result)
    
    # Process TikTok URLs
    tt_output_dir = Path("downloads/TIKTOK/raw")
    tt_output_dir.mkdir(parents=True, exist_ok=True)
    
    for url in tiktok_urls:
        result = download_video(url, "tiktok", tt_output_dir)
        if result:
            all_downloaded.append(result)
    
    # Save catalog
    if all_downloaded:
        catalog_file = Path("downloads/metadata/social_media_catalog.json")
        with open(catalog_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_downloaded': len(all_downloaded),
                'facebook_count': len([x for x in all_downloaded if x['platform'] == 'facebook']),
                'tiktok_count': len([x for x in all_downloaded if x['platform'] == 'tiktok']),
                'videos': all_downloaded
            }, f, indent=2, ensure_ascii=False)
        
        print(f"\n{'='*70}")
        print("DOWNLOAD COMPLETE")
        print(f"{'='*70}")
        print(f"Total videos downloaded: {len(all_downloaded)}")
        print(f"Catalog saved to: {catalog_file}")
        print(f"\nNext step: Run watermark removal script")
    else:
        print(f"\n{'='*70}")
        print("NO VIDEOS DOWNLOADED")
        print(f"{'='*70}")
    
    return all_downloaded

def main():
    """Main entry point."""
    process_manual_urls()

if __name__ == "__main__":
    main()
