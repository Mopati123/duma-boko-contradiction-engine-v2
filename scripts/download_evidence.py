import json
import os
import subprocess
from pathlib import Path

def download_evidence():
    cases_path = Path('outputs/cases/targeted_cases.json')
    output_dir = Path('outputs/evidence_videos')
    output_dir.mkdir(parents=True, exist_ok=True)

    if not cases_path.exists():
        print(f"Error: {cases_path} not found.")
        return

    with open(cases_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    urls = set()
    for case in data.get('cases', []):
        # Primary evidence
        if case.get('earlier_position', {}).get('url'):
            urls.add(case['earlier_position']['url'])
        if case.get('later_position', {}).get('url'):
            urls.add(case['later_position']['url'])
        
        # Supporting evidence (limit to top 3 for speed)
        for src in case.get('all_earlier_sources', [])[:2]:
            if src.get('url'): urls.add(src['url'])
        for src in case.get('all_later_sources', [])[:2]:
            if src.get('url'): urls.add(src['url'])

    print(f"Found {len(urls)} unique evidence URLs to download.")

    for url in urls:
        if 'youtube.com' in url or 'youtu.be' in url:
            print(f"Downloading: {url}")
            try:
                import sys
                cmd = [
                    sys.executable, '-m', 'yt_dlp',
                    '-f', 'bestvideo[height<=720]+bestaudio/best[height<=720]',
                    '--merge-output-format', 'mp4',
                    '-o', str(output_dir / '%(title)s [%(id)s].%(ext)s'),
                    url
                ]
                subprocess.run(cmd, check=True)
            except Exception as e:
                print(f"Failed to download {url}: {e}")
        else:
            print(f"Skipping non-YouTube URL (Manual Verification Needed): {url}")

if __name__ == "__main__":
    download_evidence()
