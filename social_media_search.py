#!/usr/bin/env python3
"""
Comprehensive social media search for Duma Boko content.
Uses multiple methods: yt-dlp, web scraping, API attempts.
"""
import subprocess
import json
import re
from pathlib import Path
from typing import List, Dict, Optional

# Known Duma Boko related terms
SEARCH_TERMS = [
    "Duma Boko",
    "President Boko",
    "Botswana President",
    "UDC leader",
    "Umbrella for Democratic Change",
    "Duma Boko speech",
    "Boko Botswana"
]

# Platform-specific search approaches
PLATFORM_CONFIG = {
    'facebook': {
        'search_patterns': [
            'site:facebook.com Duma Boko video',
            'site:fb.watch Duma Boko',
            'facebook.com/dumaboko',
        ],
        'download_enabled': True,
        'watermark_type': 'light'
    },
    'tiktok': {
        'search_patterns': [
            'site:tiktok.com Duma Boko',
            'site:tiktok.com @dumaboko',
            'Duma Boko tiktok video',
        ],
        'download_enabled': True,
        'watermark_type': 'heavy'
    }
}

def search_with_yt_dlp(query: str, platform: str) -> List[Dict]:
    """
    Try to search using yt-dlp's generic search.
    Note: Limited for Facebook/TikTok without direct URLs.
    """
    results = []
    
    print(f"\nSearching with yt-dlp: '{query}'")
    
    try:
        # yt-dlp can sometimes extract from pages
        # but TikTok and Facebook block automated access
        
        # For TikTok, we can try known patterns
        if platform == 'tiktok':
            # Common TikTok username patterns for politicians
            possible_urls = [
                "https://www.tiktok.com/@dumaboko",
                "https://www.tiktok.com/search?q=Duma%20Boko",
            ]
            
            for url in possible_urls:
                # Test if URL is accessible
                try:
                    cmd = ['yt-dlp', '--dump-json', '--no-download', url]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        data = json.loads(result.stdout)
                        results.append({
                            'url': url,
                            'title': data.get('title', 'Unknown'),
                            'platform': 'tiktok',
                            'method': 'yt-dlp'
                        })
                        print(f"  [FOUND] {url}")
                except:
                    pass
        
        # For Facebook, try common patterns
        if platform == 'facebook':
            # Try Facebook search
            search_url = f"https://www.facebook.com/search/videos?q={query.replace(' ', '%20')}"
            print(f"  [INFO] Facebook requires manual URL entry or API access")
            print(f"  [INFO] Search URL template: {search_url}")
            
    except Exception as e:
        print(f"  [ERROR] Search failed: {e}")
    
    return results

def find_videos_via_google_search(query: str, platform: str) -> List[str]:
    """
    Use Google search to find video URLs.
    Note: Requires web scraping or API.
    """
    urls = []
    
    # Construct Google search query
    search_query = f"site:{platform}.com {query} video"
    
    print(f"\n[Google Search] {search_query}")
    print(f"  [INFO] To find videos manually, search:")
    print(f"  https://www.google.com/search?q={search_query.replace(' ', '+')}")
    
    return urls

def create_url_templates():
    """Create URL templates for manual searching."""
    templates = {
        'facebook': {
            'search_url': 'https://www.facebook.com/search/videos/?q=Duma%20Boko',
            'possible_pages': [
                'https://www.facebook.com/dumaboko',
                'https://www.facebook.com/UDCBotswana',
                'https://www.facebook.com/BotswanaGovernment',
            ],
            'video_patterns': [
                'https://www.facebook.com/watch/?v={VIDEO_ID}',
                'https://fb.watch/{SHORT_CODE}',
            ]
        },
        'tiktok': {
            'search_url': 'https://www.tiktok.com/search?q=Duma%20Boko',
            'possible_usernames': [
                '@dumaboko',
                '@udcbotswana',
                '@botswana_news',
            ],
            'video_patterns': [
                'https://www.tiktok.com/@{USERNAME}/video/{VIDEO_ID}',
            ]
        }
    }
    
    return templates

def generate_search_urls():
    """Generate search URLs for manual use."""
    templates = create_url_templates()
    
    print("="*70)
    print("MANUAL SEARCH URLS")
    print("="*70)
    
    print("\n🔍 FACEBOOK:")
    print(f"  Search: {templates['facebook']['search_url']}")
    print("\n  Possible Pages to Check:")
    for page in templates['facebook']['possible_pages']:
        print(f"    - {page}")
    
    print("\n🔍 TIKTOK:")
    print(f"  Search: {templates['tiktok']['search_url']}")
    print("\n  Possible Usernames to Check:")
    for username in templates['tiktok']['possible_usernames']:
        print(f"    - https://www.tiktok.com/{username}")
    
    print("\n" + "="*70)
    print("INSTRUCTIONS:")
    print("="*70)
    print("1. Visit the Facebook search URL above")
    print("2. Find Duma Boko videos")
    print("3. Copy video URLs (right-click > Copy link)")
    print("4. Paste them into manual_urls.txt")
    print("5. Repeat for TikTok")
    print("6. Run: python search_download_social.py")
    print("7. Then run: python remove_watermarks.py")
    print("="*70)
    
    # Save to file
    with open('search_urls_guide.txt', 'w') as f:
        f.write("Duma Boko Video Search URLs\n")
        f.write("="*50 + "\n\n")
        f.write("FACEBOOK:\n")
        f.write(f"Search: {templates['facebook']['search_url']}\n\n")
        f.write("Pages to check:\n")
        for page in templates['facebook']['possible_pages']:
            f.write(f"  {page}\n")
        
        f.write("\nTIKTOK:\n")
        f.write(f"Search: {templates['tiktok']['search_url']}\n\n")
        f.write("Usernames to check:\n")
        for username in templates['tiktok']['possible_usernames']:
            f.write(f"  https://www.tiktok.com/{username}\n")

def try_yt_dlp_direct_downloads():
    """Try to download from known patterns."""
    found_urls = []
    
    # Try some common patterns that might work
    test_urls = {
        'facebook': [
            # These would need to be real URLs found by user
        ],
        'tiktok': [
            # These would need to be real URLs found by user  
        ]
    }
    
    print("\n" + "="*70)
    print("DIRECT DOWNLOAD ATTEMPT")
    print("="*70)
    
    for platform, urls in test_urls.items():
        if urls:
            print(f"\n{platform.upper()}:")
            for url in urls:
                print(f"  Testing: {url}")
                # Test if yt-dlp can access it
                try:
                    cmd = ['yt-dlp', '--no-download', '--dump-json', url]
                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        print(f"    [OK] Accessible")
                        found_urls.append({'url': url, 'platform': platform})
                    else:
                        print(f"    [BLOCKED] Cannot access")
                except:
                    print(f"    [ERROR] Failed to test")
    
    return found_urls

def main():
    """Main entry point."""
    print("="*70)
    print("SOCIAL MEDIA SEARCH FOR DUMA BOKO VIDEOS")
    print("="*70)
    
    # Step 1: Generate search URLs
    generate_search_urls()
    
    # Step 2: Try limited automated search
    print("\n" + "="*70)
    print("AUTOMATED SEARCH ATTEMPT")
    print("="*70)
    print("\nNote: Facebook and TikTok actively block automated scraping.")
    print("Manual URL entry is required.\n")
    
    # Try yt-dlp search
    for term in SEARCH_TERMS[:2]:  # Try first 2 terms
        search_with_yt_dlp(term, 'facebook')
        search_with_yt_dlp(term, 'tiktok')
    
    # Step 3: Create manual URL template
    print("\n" + "="*70)
    print("NEXT STEPS")
    print("="*70)
    print("\n1. Visit the search URLs above in your browser")
    print("2. Find Duma Boko videos")
    print("3. Copy URLs and add to: manual_urls.txt")
    print("4. Run: python search_download_social.py")
    print("5. Then run: python remove_watermarks.py")
    
    print("\n" + "="*70)
    print("SEARCH COMPLETE")
    print("="*70)
    print("\nCheck search_urls_guide.txt for all search URLs")
    print("Add found URLs to manual_urls.txt")

if __name__ == "__main__":
    main()
