"""
Video downloader module for YouTube, Facebook, and TikTok.
Uses yt-dlp as the primary tool with fallbacks.
"""

import os
import re
import json
import subprocess
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from typing import Dict, Optional, Tuple


class VideoDownloader:
    """Download videos from various platforms."""
    
    def __init__(self, downloads_path: str, video_quality: str = "720p", 
                 audio_quality: str = "128k"):
        self.downloads_path = Path(downloads_path)
        self.video_quality = video_quality
        self.audio_quality = audio_quality
        
        # Ensure downloads directory exists
        self.downloads_path.mkdir(parents=True, exist_ok=True)
    
    def identify_platform(self, url: str) -> str:
        """Identify the platform from URL."""
        domain = urlparse(url).netloc.lower()
        
        if 'youtube.com' in domain or 'youtu.be' in domain:
            return 'youtube'
        elif 'facebook.com' in domain or 'fb.watch' in domain:
            return 'facebook'
        elif 'tiktok.com' in domain:
            return 'tiktok'
        elif 'instagram.com' in domain:
            return 'instagram'
        else:
            return 'unknown'
    
    def extract_video_id(self, url: str, platform: str) -> str:
        """Extract video ID from URL."""
        if platform == 'youtube':
            # Handle youtu.be short URLs
            if 'youtu.be' in url:
                return url.split('/')[-1].split('?')[0]
            # Handle youtube.com/watch?v= URLs
            parsed = urlparse(url)
            return parse_qs(parsed.query).get('v', ['unknown'])[0]
        
        elif platform == 'facebook':
            # Extract from /videos/123456 format
            match = re.search(r'/videos/(\d+)', url)
            if match:
                return match.group(1)
            # Extract from fb.watch short URLs
            if 'fb.watch' in url:
                return url.split('/')[-1].split('?')[0]
            return 'unknown'
        
        elif platform == 'tiktok':
            # Extract from /video/123456 format
            match = re.search(r'/video/(\d+)', url)
            if match:
                return match.group(1)
            return url.split('/')[-1].split('?')[0]
        
        return 'unknown'
    
    def get_output_path(self, case_id: str, claim_type: str, video_id: str, 
                        platform: str) -> Path:
        """Generate organized output path."""
        # Clean claim type (Claim_A -> Claim_A)
        claim_clean = claim_type.replace(' ', '_')
        
        # Create folder structure: downloads/CASE_1/Claim_A/
        output_dir = self.downloads_path / case_id / claim_clean
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Filename: platform_video_id.mp4
        filename = f"{platform}_{video_id}.mp4"
        return output_dir / filename
    
    def download(self, url: str, case_id: str = "MANUAL", claim_type: str = "Unknown",
                 platform: Optional[str] = None) -> Tuple[bool, Dict]:
        """
        Download video from URL.
        
        Returns:
            Tuple of (success: bool, metadata: dict)
        """
        # Auto-detect platform if not provided
        if platform is None:
            platform = self.identify_platform(url)
        
        video_id = self.extract_video_id(url, platform)
        output_path = self.get_output_path(case_id, claim_type, video_id, platform)
        
        # Skip if already downloaded
        if output_path.exists():
            print(f"  Video already exists: {output_path}")
            metadata = self._extract_metadata(output_path, url, platform, video_id)
            return True, metadata
        
        print(f"  Downloading from {platform}...")
        
        try:
            # Download video + audio simultaneously
            cmd = [
                'yt-dlp',
                '--format', f'best[height<={self.video_quality.replace("p", "")}][ext=mp4]/best[ext=mp4]/best',
                '--output', str(output_path),
                '--no-playlist',
                '--quiet',
                '--no-warnings',
                '--write-info-json',
                '--write-description',
                '--write-thumbnail',
                # Also download audio separately for transcription
                '--extract-audio',
                '--audio-format', 'mp3',
                '--audio-quality', self.audio_quality,
                url
            ]
            
            # Run download
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                print(f"  Error downloading: {result.stderr}")
                return False, {"error": result.stderr}
            
            # Extract metadata
            metadata = self._extract_metadata(output_path, url, platform, video_id)
            
            # Check for audio file
            audio_path = output_path.with_suffix('.mp3')
            if audio_path.exists():
                metadata['audio_path'] = str(audio_path)
                print(f"  ✓ Video + Audio downloaded: {output_path.name}")
            else:
                print(f"  ✓ Video downloaded: {output_path.name}")
            
            return True, metadata
            
        except subprocess.TimeoutExpired:
            print(f"  Timeout downloading video")
            return False, {"error": "Download timeout"}
        except Exception as e:
            print(f"  Error: {e}")
            return False, {"error": str(e)}
    
    def _extract_metadata(self, video_path: Path, url: str, platform: str, 
                        video_id: str) -> Dict:
        """Extract metadata from downloaded video and info.json."""
        metadata = {
            'video_path': str(video_path),
            'url': url,
            'platform': platform,
            'video_id': video_id,
            'title': '',
            'description': '',
            'uploader': '',
            'upload_date': '',
            'duration': 0,
            'thumbnail_path': ''
        }
        
        # Try to read info.json if exists
        info_path = video_path.with_suffix('.info.json')
        if info_path.exists():
            try:
                with open(info_path, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                    metadata['title'] = info.get('title', '')
                    metadata['description'] = info.get('description', '')[:500]
                    metadata['uploader'] = info.get('uploader', '')
                    metadata['upload_date'] = info.get('upload_date', '')
                    metadata['duration'] = info.get('duration', 0)
            except Exception as e:
                print(f"  Warning: Could not read info.json: {e}")
        
        # Check for thumbnail
        thumb_path = video_path.with_suffix('.jpg')
        if thumb_path.exists():
            metadata['thumbnail_path'] = str(thumb_path)
        
        return metadata
    
    def _extract_audio(self, video_path: Path) -> Optional[Path]:
        """Extract audio from video using yt-dlp or FFmpeg."""
        audio_path = video_path.with_suffix('.mp3')
        
        # Skip if audio already exists
        if audio_path.exists():
            return audio_path
        
        # Try yt-dlp to extract audio (doesn't require FFmpeg)
        try:
            print(f"  Extracting audio with yt-dlp...")
            cmd = [
                'yt-dlp',
                '--extract-audio',
                '--audio-format', 'mp3',
                '--audio-quality', self.audio_quality,
                '--output', str(audio_path.with_suffix('')),  # yt-dlp adds extension
                '--no-video',  # Audio only
                '--quiet',
                str(video_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0 and audio_path.exists():
                print(f"  ✓ Audio extracted: {audio_path.name}")
                return audio_path
        except Exception as e:
            print(f"  yt-dlp audio extraction failed: {e}")
        
        # Fallback to FFmpeg if available
        try:
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',
                '-acodec', 'libmp3lame',
                '-ar', '16000',
                '-ac', '1',
                '-b:a', self.audio_quality,
                '-y',
                str(audio_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print(f"  ✓ Audio extracted with FFmpeg: {audio_path.name}")
                return audio_path
        except Exception as e:
            print(f"  FFmpeg not available: {e}")
        
        print(f"  ⚠️ Could not extract audio. Video only downloaded.")
        return None


def download_video(url: str, downloads_path: str = "./downloads", 
                   case_id: str = "MANUAL", claim_type: str = "Unknown") -> Tuple[bool, Dict]:
    """
    Convenience function to download a single video.
    
    Example:
        success, metadata = download_video(
            "https://youtube.com/watch?v=...",
            case_id="CASE_1",
            claim_type="Claim_A"
        )
    """
    downloader = VideoDownloader(downloads_path)
    return downloader.download(url, case_id, claim_type)


if __name__ == "__main__":
    # Test with a sample URL
    import sys
    
    if len(sys.argv) > 1:
        url = sys.argv[1]
        print(f"Testing download: {url}")
        success, metadata = download_video(url)
        
        if success:
            print("\nDownloaded successfully!")
            print(f"Path: {metadata['video_path']}")
            print(f"Title: {metadata.get('title', 'N/A')}")
            print(f"Platform: {metadata['platform']}")
        else:
            print(f"Download failed: {metadata.get('error', 'Unknown error')}")
    else:
        print("Usage: python downloader.py <URL>")
