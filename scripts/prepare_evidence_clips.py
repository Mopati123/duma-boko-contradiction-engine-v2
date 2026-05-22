import os
import subprocess
import json
from pathlib import Path

def prepare_clips():
    output_dir = Path('outputs/evidence_videos')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    evidence = [
        {
            "id": "CASE_002_Jobs",
            "url": "https://www.youtube.com/watch?v=e0MLzB5nGDc",
            "start": "00:00:00",
            "end": "00:05:00"
        },
        {
            "id": "CASE_006_Health_Outcome",
            "url": "https://www.youtube.com/watch?v=ZsxLObyHUYE",
            "start": "00:00:00",
            "end": "00:05:00"
        },
        {
            "id": "CASE_006_Health_Promise",
            "url": "https://www.youtube.com/watch?v=NcF35I0GiTM",
            "start": "00:10:00",
            "end": "00:15:00"
        },
        {
            "id": "CASE_004_Economy",
            "url": "https://www.youtube.com/watch?v=NcF35I0GiTM",
            "start": "00:03:00",
            "end": "00:08:00"
        },
        {
            "id": "CASE_003_Corruption",
            "url": "https://www.youtube.com/watch?v=R90F8eS0P1s",
            "start": "00:00:00",
            "end": "00:05:00"
        }
    ]
    
    for item in evidence:
        filename = f"{item['id']}_Evidence.mp4"
        final_path = output_dir / filename
        temp_full = output_dir / f"temp_{item['id']}_full.mp4"
        
        print(f"--- Processing {item['id']} ---")
        
        # 1. Download full video (low res)
        cmd_dl = [
            "python", "-m", "yt_dlp",
            "-f", "worst[ext=mp4]/worst", 
            "-o", str(temp_full),
            item['url']
        ]
        
        try:
            print(f"Downloading full video for {item['id']} (low res)...")
            subprocess.run(cmd_dl, check=True)
            
            # 2. Clip with ffmpeg
            cmd_clip = [
                "ffmpeg", "-ss", item['start'], "-i", str(temp_full),
                "-to", item['end'], "-c", "copy", str(final_path), "-y"
            ]
            print(f"Clipping {filename}...")
            subprocess.run(cmd_clip, check=True)
            
            # 3. Cleanup
            if temp_full.exists():
                temp_full.unlink()
                
            print(f"Successfully created {filename}")
        except Exception as e:
            print(f"Error processing {item['id']}: {e}")

if __name__ == "__main__":
    prepare_clips()
