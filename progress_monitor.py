#!/usr/bin/env python3
"""
Progress Monitor for Batch Video Processing
Shows real-time progress, timer, and ETA while videos are being processed.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime, timedelta


class ProgressMonitor:
    """Monitor and display batch processing progress."""
    
    def __init__(self):
        self.start_time = datetime.now()
        self.total_videos = 41
        
        # Directory paths
        self.source_dir = Path("downloads/AUTO/Unknown")
        self.audio_dir = Path("downloads/AUDIO")
        self.transcript_dir = Path("downloads/TRANSCRIPTS")
        self.processed_dir = Path("downloads/PROCESSED")
        self.evidence_csv = Path("downloads/evidence_auto_filled.csv")
        self.log_file = Path("batch_process_log.txt")
        
        # Statistics tracking
        self.last_counts = {}
        self.video_times = []  # Track time per video for ETA
        
    def count_files(self):
        """Count files in each processing stage."""
        counts = {
            'mp4_total': 0,
            'mp3_extracted': 0,
            'transcripts': 0,
            'analyses': 0,
            'processed': 0,
            'evidence_rows': 0
        }
        
        # Count MP4s
        if self.source_dir.exists():
            counts['mp4_total'] = len(list(self.source_dir.glob("*.mp4")))
        
        # Count MP3s
        if self.audio_dir.exists():
            counts['mp3_extracted'] = len(list(self.audio_dir.glob("*.mp3")))
        
        # Count transcripts
        if self.transcript_dir.exists():
            counts['transcripts'] = len(list(self.transcript_dir.glob("*.transcript.json")))
            counts['analyses'] = len(list(self.transcript_dir.glob("*.analysis.json")))
        
        # Count processed videos
        if self.processed_dir.exists():
            counts['processed'] = len(list(self.processed_dir.glob("*.mp4")))
        
        # Count evidence rows
        if self.evidence_csv.exists():
            try:
                with open(self.evidence_csv, 'r', encoding='utf-8') as f:
                    # Subtract 1 for header
                    counts['evidence_rows'] = max(0, sum(1 for _ in f) - 1)
            except:
                pass
        
        return counts
    
    def get_current_video(self):
        """Determine which video is currently being processed."""
        # Find MP4 that has audio but no transcript yet
        counts = self.count_files()
        
        if counts['mp3_extracted'] > counts['transcripts']:
            # Currently transcribing
            mp3_files = set(f.stem for f in self.audio_dir.glob("*.mp3"))
            transcript_files = set(f.stem.replace('.transcript', '') for f in self.transcript_dir.glob("*.transcript.json"))
            current = list(mp3_files - transcript_files)
            if current:
                return current[0], "Transcribing audio..."
        
        elif counts['transcripts'] > counts['analyses']:
            # Currently analyzing
            transcript_files = set(f.stem.replace('.transcript', '') for f in self.transcript_dir.glob("*.transcript.json"))
            analysis_files = set(f.stem.replace('.analysis', '') for f in self.transcript_dir.glob("*.analysis.json"))
            current = list(transcript_files - analysis_files)
            if current:
                return current[0], "Analyzing transcript..."
        
        elif counts['mp4_total'] > counts['mp3_extracted']:
            # Currently extracting audio
            mp4_files = [f for f in self.source_dir.glob("*.mp4")]
            mp3_files = set(f.stem for f in self.audio_dir.glob("*.mp3"))
            for mp4 in mp4_files:
                if mp4.stem.replace('youtube_', '') not in mp3_files:
                    return mp4.name, "Extracting audio..."
        
        elif counts['analyses'] > counts['processed']:
            # Currently organizing
            analysis_files = set(f.stem.replace('.analysis', '') for f in self.transcript_dir.glob("*.analysis.json"))
            processed_files = set(f.stem for f in self.processed_dir.glob("*.mp4"))
            current = list(analysis_files - processed_files)
            if current:
                return current[0], "Organizing video..."
        
        return None, "Waiting..."
    
    def get_recent_activity(self, n=5):
        """Get recent log entries."""
        if not self.log_file.exists():
            return []
        
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                # Get last n non-empty lines
                recent = [line.strip() for line in lines if line.strip()][-n:]
                return recent
        except:
            return []
    
    def format_time(self, seconds):
        """Format seconds as HH:MM:SS."""
        return str(timedelta(seconds=int(seconds)))
    
    def draw_progress_bar(self, current, total, width=40):
        """Draw ASCII progress bar."""
        if total == 0:
            return "[" + " " * width + "]"
        
        filled = int(width * current / total)
        bar = "█" * filled + "░" * (width - filled)
        percentage = int(100 * current / total)
        return f"[{bar}] {current}/{total} ({percentage}%)"
    
    def clear_screen(self):
        """Clear console screen."""
        if os.name == 'nt':
            os.system('cls')
        else:
            os.system('clear')
    
    def display(self):
        """Display current progress."""
        self.clear_screen()
        
        # Get counts
        counts = self.count_files()
        current_video, current_step = self.get_current_video()
        recent_activity = self.get_recent_activity(5)
        
        # Calculate times
        elapsed = datetime.now() - self.start_time
        elapsed_seconds = elapsed.total_seconds()
        
        # Estimate remaining time
        completed = counts['processed']
        if completed > 0:
            avg_time_per_video = elapsed_seconds / completed
            remaining_videos = self.total_videos - completed
            eta_seconds = remaining_videos * avg_time_per_video
            eta = self.format_time(eta_seconds)
            completion_time = datetime.now() + timedelta(seconds=eta_seconds)
        else:
            eta = "Calculating..."
            completion_time = None
        
        # Build display
        print("╔" + "═" * 68 + "╗")
        print("║" + " VIDEO EVIDENCE PROCESSING - PROGRESS MONITOR ".center(68) + "║")
        print("╠" + "═" * 68 + "╣")
        
        # Time info
        print(f"║ Started: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}    Elapsed: {self.format_time(elapsed_seconds)}".ljust(69) + "║")
        print("║" + " " * 68 + "║")
        
        # Progress bar
        progress_bar = self.draw_progress_bar(completed, self.total_videos)
        print(f"║ PROGRESS: {progress_bar}".ljust(69) + "║")
        print("║" + " " * 68 + "║")
        
        # Current video
        if current_video:
            video_display = current_video[:50] + "..." if len(current_video) > 53 else current_video
            print(f"║ Current: {video_display}".ljust(69) + "║")
            print(f"║ Step: {current_step}".ljust(69) + "║")
            print("║" + " " * 68 + "║")
        
        # Statistics
        print("║ Statistics:".ljust(69) + "║")
        print(f"║   Videos downloaded:     {counts['mp4_total']}/{self.total_videos}  [OK]".ljust(69) + "║")
        print(f"║   Audio extracted:       {counts['mp3_extracted']}/{self.total_videos}  {'[OK]' if counts['mp3_extracted'] == self.total_videos else '[in progress]'}".ljust(69) + "║")
        print(f"║   Transcribed:          {counts['transcripts']}/{self.total_videos}  {'[OK]' if counts['transcripts'] == self.total_videos else '[in progress]'}".ljust(69) + "║")
        print(f"║   Analyzed:             {counts['analyses']}/{self.total_videos}  {'[OK]' if counts['analyses'] == self.total_videos else '[in progress]'}".ljust(69) + "║")
        print(f"║   Processed/Organized:   {counts['processed']}/{self.total_videos}  {'[OK]' if counts['processed'] == self.total_videos else '[in progress]'}".ljust(69) + "║")
        print(f"║   Evidence exported:     {counts['evidence_rows']} rows".ljust(69) + "║")
        print("║" + " " * 68 + "║")
        
        # Time estimates
        print("║ Time Estimates:".ljust(69) + "║")
        if completed > 0:
            avg_time = self.format_time(elapsed_seconds / completed)
            print(f"║   Avg per video:  {avg_time}".ljust(69) + "║")
        print(f"║   Time remaining: {eta}".ljust(69) + "║")
        if completion_time:
            print(f"║   Completion:     ~{completion_time.strftime('%H:%M')} today".ljust(69) + "║")
        print("║" + " " * 68 + "║")
        
        # Recent activity
        if recent_activity:
            print("║ Recent Activity:".ljust(69) + "║")
            for line in recent_activity[-5:]:
                # Truncate long lines
                display_line = line[:63] + "..." if len(line) > 66 else line
                print(f"║   {display_line}".ljust(69) + "║")
        
        print("╚" + "═" * 68 + "╝")
        
        # Check if complete
        if completed >= self.total_videos:
            print("\n" + "=" * 70)
            print("PROCESSING COMPLETE!")
            print(f"All {self.total_videos} videos have been processed.")
            print("=" * 70)
            return True
        
        return False
    
    def run(self):
        """Run the monitor loop."""
        print("Starting progress monitor...")
        print("Monitoring batch_processor.py output...")
        print("Press Ctrl+C to stop\n")
        time.sleep(2)
        
        try:
            while True:
                complete = self.display()
                if complete:
                    break
                time.sleep(5)  # Update every 5 seconds
        except KeyboardInterrupt:
            print("\n\nMonitor stopped by user.")
            print(f"Processing continues in background.")
            print(f"Check {self.processed_dir} for completed videos.")


def main():
    """Main entry point."""
    monitor = ProgressMonitor()
    monitor.run()


if __name__ == '__main__':
    main()
