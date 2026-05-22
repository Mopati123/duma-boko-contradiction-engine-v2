#!/usr/bin/env python3
"""
Remove platform watermarks from videos.
Uses FFmpeg to crop out watermark regions.
"""
import json
import subprocess
from pathlib import Path
from typing import Optional
import shutil

def get_video_dimensions(video_path: Path) -> tuple:
    """Get video width and height using FFmpeg."""
    try:
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=s=x:p=0"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            width, height = result.stdout.strip().split('x')
            return int(width), int(height)
    except:
        pass
    return None, None

def remove_tiktok_watermark(input_path: Path, output_path: Path) -> bool:
    """
    Remove TikTok watermark by cropping top and bottom banners.
    TikTok watermarks are typically 60-100px at top and bottom.
    """
    print(f"  Processing TikTok watermark removal...")
    
    try:
        # Get original dimensions
        width, height = get_video_dimensions(input_path)
        if not width or not height:
            print(f"    [ERROR] Could not get video dimensions")
            return False
        
        print(f"    Original: {width}x{height}")
        
        # TikTok typically has:
        # - Top banner: ~60-80px (username, music info)
        # - Bottom banner: ~80-100px (captions, buttons)
        # We'll crop conservatively to preserve content
        
        # Remove 80px from top, 100px from bottom
        crop_top = 80
        crop_bottom = 100
        new_height = height - crop_top - crop_bottom
        
        if new_height < height * 0.7:  # Don't crop more than 30%
            print(f"    [WARNING] Crop would remove too much content, reducing crop size")
            crop_top = 60
            crop_bottom = 60
            new_height = height - crop_top - crop_bottom
        
        # Use FFmpeg crop filter
        # crop=width:height:x:y
        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-vf", f"crop={width}:{new_height}:0:{crop_top}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",  # Quality setting
            "-c:a", "copy",  # Copy audio as-is
            "-y",  # Overwrite output
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and output_path.exists():
            print(f"    [OK] Watermark removed: {output_path.name}")
            print(f"    New dimensions: {width}x{new_height}")
            return True
        else:
            print(f"    [ERROR] FFmpeg failed: {result.stderr[:200]}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"    [ERROR] Processing timeout")
        return False
    except Exception as e:
        print(f"    [ERROR] Exception: {e}")
        return False

def remove_facebook_watermark(input_path: Path, output_path: Path) -> bool:
    """
    Remove Facebook watermark if present.
    Facebook watermarks are typically less intrusive - often just a small logo.
    We'll crop slightly if needed or just copy if minimal.
    """
    print(f"  Processing Facebook video...")
    
    # Facebook watermarks are usually small and in corners
    # For now, we'll do a light crop or just copy
    # More aggressive removal can be added if needed
    
    try:
        # Get dimensions
        width, height = get_video_dimensions(input_path)
        if not width or not height:
            print(f"    [WARNING] Could not detect dimensions, copying as-is")
            shutil.copy(input_path, output_path)
            return True
        
        # Light crop (2% from each edge) to remove edge watermarks
        crop_percent = 0.02
        crop_x = int(width * crop_percent)
        crop_y = int(height * crop_percent)
        new_width = width - (2 * crop_x)
        new_height = height - (2 * crop_y)
        
        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-vf", f"crop={new_width}:{new_height}:{crop_x}:{crop_y}",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "copy",
            "-y",
            str(output_path)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0 and output_path.exists():
            print(f"    [OK] Processed: {output_path.name}")
            return True
        else:
            # Fallback: just copy
            print(f"    [WARNING] FFmpeg crop failed, copying original")
            shutil.copy(input_path, output_path)
            return True
            
    except Exception as e:
        print(f"    [ERROR] {e}, copying original")
        shutil.copy(input_path, output_path)
        return True

def process_all_videos():
    """Process all downloaded videos for watermark removal."""
    print("="*70)
    print("WATERMARK REMOVAL")
    print("="*70)
    
    processed = {
        'facebook': [],
        'tiktok': []
    }
    
    # Process Facebook videos
    fb_raw_dir = Path("downloads/FACEBOOK/raw")
    fb_clean_dir = Path("downloads/FACEBOOK/clean")
    fb_clean_dir.mkdir(parents=True, exist_ok=True)
    
    if fb_raw_dir.exists():
        fb_videos = list(fb_raw_dir.glob("*.mp4"))
        print(f"\nFacebook videos to process: {len(fb_videos)}")
        
        for video in fb_videos:
            print(f"\n[{video.name}]")
            output_path = fb_clean_dir / f"clean_{video.name}"
            
            if remove_facebook_watermark(video, output_path):
                processed['facebook'].append({
                    'original': str(video),
                    'cleaned': str(output_path),
                    'platform': 'facebook'
                })
    
    # Process TikTok videos
    tt_raw_dir = Path("downloads/TIKTOK/raw")
    tt_clean_dir = Path("downloads/TIKTOK/clean")
    tt_clean_dir.mkdir(parents=True, exist_ok=True)
    
    if tt_raw_dir.exists():
        tt_videos = list(tt_raw_dir.glob("*.mp4"))
        print(f"\nTikTok videos to process: {len(tt_videos)}")
        
        for video in tt_videos:
            print(f"\n[{video.name}]")
            output_path = tt_clean_dir / f"clean_{video.name}"
            
            if remove_tiktok_watermark(video, output_path):
                processed['tiktok'].append({
                    'original': str(video),
                    'cleaned': str(output_path),
                    'platform': 'tiktok'
                })
    
    # Save processing log
    total_processed = len(processed['facebook']) + len(processed['tiktok'])
    
    if total_processed > 0:
        log_file = Path("downloads/metadata/watermark_removal_log.json")
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total_processed': total_processed,
                'facebook_count': len(processed['facebook']),
                'tiktok_count': len(processed['tiktok']),
                'processed_videos': processed,
                'method': 'FFmpeg crop filter',
                'note': 'Original watermarked versions preserved in raw/ directories'
            }, f, indent=2)
        
        print(f"\n{'='*70}")
        print("WATERMARK REMOVAL COMPLETE")
        print(f"{'='*70}")
        print(f"Total processed: {total_processed}")
        print(f"Facebook: {len(processed['facebook'])}")
        print(f"TikTok: {len(processed['tiktok'])}")
        print(f"\nClean videos saved to:")
        print(f"  - downloads/FACEBOOK/clean/")
        print(f"  - downloads/TIKTOK/clean/")
        print(f"\nOriginals preserved in raw/ directories")
        print(f"Log saved to: {log_file}")
    else:
        print(f"\n{'='*70}")
        print("NO VIDEOS TO PROCESS")
        print(f"{'='*70}")
        print("Please run search_download_social.py first to download videos")

def main():
    """Main entry point."""
    process_all_videos()

if __name__ == "__main__":
    main()
