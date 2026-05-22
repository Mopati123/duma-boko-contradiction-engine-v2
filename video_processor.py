#!/usr/bin/env python3
"""
Video Evidence Analysis System - Main Orchestrator

This script coordinates the full pipeline:
1. Discover videos (YouTube API or manual URLs)
2. Download videos with organized folder structure
3. Transcribe audio to text
4. Analyze transcripts for target quotes
5. Export findings to evidence CSV

Usage:
    # YouTube discovery mode
    python video_processor.py --mode youtube --config config.yaml
    
    # Manual single URL
    python video_processor.py --mode manual --url "https://..." --case CASE_1 --claim Claim_A
    
    # Batch from CSV
    python video_processor.py --mode batch --input manual_urls.csv
    
    # Just analyze existing transcript
    python video_processor.py --mode analyze --transcript transcript.json --metadata metadata.json
"""

import argparse
import csv
import sys
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
except ImportError:
    print("Error: PyYAML not installed. Run: pip install pyyaml")
    sys.exit(1)

from downloader import VideoDownloader, download_video
from transcriber import AudioTranscriber, transcribe_audio
from analyzer import VideoAnalyzer, analyze_video, AnalysisResult
from evidence_exporter import EvidenceExporter, export_evidence


def load_config(config_path: str) -> Dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def discover_youtube_videos(config: Dict) -> List[Dict]:
    """Search YouTube for target phrases."""
    print("\n[INFO] DISCOVERING YOUTUBE VIDEOS")
    print("=" * 50)
    
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    
    api_key = config['youtube_api_key']
    phrases = config.get('search_phrases', [])
    max_results = 20
    
    if not api_key or api_key == "YOUR_YOUTUBE_API_KEY_HERE":
        print("Error: YouTube API key not configured")
        return []
    
    youtube = build('youtube', 'v3', developerKey=api_key)
    videos = []
    
    for phrase in phrases:
        print(f"\nSearching: '{phrase}'")
        try:
            response = youtube.search().list(
                q=phrase,
                part='id,snippet',
                type='video',
                maxResults=max_results,
                order='date'
            ).execute()
            
            for item in response.get("items", []):
                video = {
                    'search_phrase': phrase,
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'url': f"https://youtube.com/watch?v={item['id']['videoId']}",
                    'platform': 'youtube',
                    'upload_date': item['snippet']['publishedAt'][:10],
                    'description': item['snippet']['description'][:200]
                }
                videos.append(video)
                try:
                    print(f"  Found: {video['title'][:60]}...")
                except UnicodeEncodeError:
                    print(f"  Found: {video['video_id']} (title contains Unicode)")
                
        except HttpError as e:
            print(f"  Error: {e}")
    
    print(f"\nTotal videos discovered: {len(videos)}")
    return videos


def process_video(video_info: Dict, config: Dict, case_id: str = "AUTO",
                  claim_type: str = "Unknown", output_csv: str = None) -> bool:
    """
    Process a single video through the full pipeline.
    
    Returns True if successful and evidence was found.
    """
    url = video_info['url']
    video_id = video_info.get('video_id', 'unknown')
    platform = video_info.get('platform', 'unknown')
    
    print(f"\n{'='*60}")
    print(f"[INFO] PROCESSING: {platform.upper()} - {video_id}")
    print(f"URL: {url}")
    print(f"{'='*60}")
    
    # Step 1: Download
    print("\n[STEP 1] Downloading video...")
    downloads_path = config.get('downloads_path', './downloads')
    
    downloader = VideoDownloader(downloads_path)
    success, metadata = downloader.download(url, case_id, claim_type, platform)
    
    if not success:
        print(f"Download failed: {metadata.get('error', 'Unknown error')}")
        return False
    
    video_path = Path(metadata['video_path'])
    audio_path = metadata.get('audio_path')
    
    if not audio_path:
        print("No audio extracted for transcription")
        return False
    
    # Step 2: Transcribe
    print("\n[STEP 2] Transcribing audio...")
    analysis_config = config.get('analysis', {})
    
    transcriber = AudioTranscriber(
        model=analysis_config.get('transcription_model', 'base'),
        use_api=analysis_config.get('use_whisper_api', False),
        api_key=config.get('openai_api_key'),
        language=analysis_config.get('language', 'auto')
    )
    
    transcript_path = video_path.with_suffix('.transcript.json')
    
    try:
        transcript = transcriber.transcribe(audio_path, transcript_path)
        print(f"Transcribed: {len(transcript['segments'])} segments, "
              f"{transcript['duration']:.1f}s duration")
    except Exception as e:
        print(f"Transcription failed: {e}")
        return False
    
    # Step 3: Analyze
    print("\n[STEP 3] Analyzing transcript...")
    
    analyzer = VideoAnalyzer(config)
    result = analyzer.analyze_video(metadata, transcript, case_id)
    
    if not result:
        print("No target quotes found in video")
        return False
    
    print(f"Found match: {result.quote_type}")
    print(f"Quote: {result.quote_text[:80]}...")
    print(f"Time: {result.start_time} - {result.end_time}")
    print(f"Confidence: {result.confidence_score:.2f}")
    
    # Save analysis JSON
    analysis_path = video_path.with_suffix('.analysis.json')
    analyzer.save_analysis(result, analysis_path)
    
    # Step 4: Export to CSV
    print("\n[STEP 4] Exporting to evidence CSV...")
    
    csv_path = output_csv or config.get('output_csv', './evidence_auto_filled.csv')
    
    # Merge video info with metadata
    full_metadata = {**metadata, **video_info, 'cases': config.get('cases', {})}
    
    exporter = EvidenceExporter(csv_path)
    added = exporter.add_evidence(
        metadata=full_metadata,
        analysis_result=result,
        source_type='clip',
        event_type='kgotla',
        speaker='Duma Boko',
        notes=f"Auto-analyzed from {platform}"
    )
    
    if added:
        print(f"Evidence added to: {csv_path}")
    
    print(f"\nCOMPLETE: Video processed successfully")
    return True


def process_youtube_mode(config: Dict, args):
    """Process YouTube discovery mode."""
    # Discover videos
    videos = discover_youtube_videos(config)
    
    if not videos:
        print("No videos found")
        return
    
    # Filter for Botswana/Duma Boko content
    print("\nFILTERING for relevant content...")
    keywords = ['boko', 'botswana', 'batswana', 'udc', 'kgotla', 'president']
    
    relevant = []
    for video in videos:
        text = f"{video['title']} {video['description']}".lower()
        if any(kw in text for kw in keywords):
            relevant.append(video)
            try:
                print(f"  [RELEVANT] {video['title'][:60]}...")
            except UnicodeEncodeError:
                print(f"  [RELEVANT] {video['video_id']}")
    
    print(f"Found {len(relevant)} relevant videos out of {len(videos)} total")
    
    # Process each relevant video
    success_count = 0
    for video in relevant:
        try:
            if process_video(video, config, output_csv=args.output):
                success_count += 1
        except Exception as e:
            print(f"Error processing video: {e}")
            continue
    
    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE: {success_count}/{len(relevant)} videos processed")
    print(f"Evidence CSV: {args.output or config.get('output_csv')}")


def process_manual_mode(config: Dict, args):
    """Process single manual URL."""
    video_info = {
        'url': args.url,
        'video_id': 'manual',
        'platform': args.platform or 'unknown',
        'title': 'Manual entry',
        'upload_date': '',
        'description': ''
    }
    
    process_video(video_info, config, args.case, args.claim, args.output)


def process_batch_mode(config: Dict, args):
    """Process batch from CSV file."""
    print(f"\nBATCH MODE: Reading {args.input}")
    
    with open(args.input, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        videos = list(reader)
    
    print(f"Found {len(videos)} videos to process")
    
    success_count = 0
    for video in videos:
        try:
            case = video.get('case_id', 'CASE_1')
            claim = video.get('case_type', 'Unknown')
            
            if process_video(video, config, case, claim, args.output):
                success_count += 1
        except Exception as e:
            print(f"Error: {e}")
            continue
    
    print(f"\n[SUCCESS] BATCH COMPLETE: {success_count}/{len(videos)} videos processed")


def main():
    parser = argparse.ArgumentParser(
        description='Video Evidence Analysis System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # YouTube discovery
  python video_processor.py --mode youtube --config config.yaml
  
  # Manual URL
  python video_processor.py --mode manual --url "https://youtube.com/watch?v=..." \\
                            --case CASE_1 --claim Claim_A
  
  # Batch from CSV (columns: url, case_id, case_type)
  python video_processor.py --mode batch --input urls.csv --output evidence.csv
        """
    )
    
    parser.add_argument('--mode', required=True,
                        choices=['youtube', 'manual', 'batch', 'analyze'],
                        help='Processing mode')
    parser.add_argument('--config', default='config.yaml',
                        help='Configuration file path')
    parser.add_argument('--output', help='Output CSV path (overrides config)')
    
    # Manual mode args
    parser.add_argument('--url', help='Video URL (manual mode)')
    parser.add_argument('--platform', help='Platform (youtube/facebook/tiktok)')
    parser.add_argument('--case', default='AUTO',
                        help='Case ID (e.g., CASE_1)')
    parser.add_argument('--claim', default='Unknown',
                        help='Claim type (Claim_A or Claim_B)')
    
    # Batch mode args
    parser.add_argument('--input', help='Input CSV file (batch mode)')
    
    args = parser.parse_args()
    
    # Load config
    print(f"[INFO] Loading configuration: {args.config}")
    try:
        config = load_config(args.config)
        print("Configuration loaded")
    except Exception as e:
        print(f"Error loading config: {e}")
        sys.exit(1)
    
    # Dispatch to mode handler
    if args.mode == 'youtube':
        process_youtube_mode(config, args)
    elif args.mode == 'manual':
        if not args.url:
            print("Error: --url required for manual mode")
            sys.exit(1)
        process_manual_mode(config, args)
    elif args.mode == 'batch':
        if not args.input:
            print("Error: --input required for batch mode")
            sys.exit(1)
        process_batch_mode(config, args)
    else:
        print("Analyze mode not yet implemented")
    
    print("\n[SUCCESS] Processing complete!")


if __name__ == '__main__':
    main()
