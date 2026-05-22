#!/usr/bin/env python3
"""
Batch Video Processor - Extract, Transcribe, Analyze, and Organize

Processes all downloaded videos through the full pipeline:
1. Extract audio from MP4
2. Transcribe with Whisper
3. Analyze for contradictions (Claim A/B)
4. Organize into single folder with descriptive names
5. Export evidence to CSV

NEW: Semantic Pipeline (use --semantic flag)
Language Routing → Translation → Claim Extraction → Topic Clustering 
→ Temporal Pairing → NLI Contradiction Detection → Case Builder
For non-English/Swahili content with evidence-grade output.
"""

import os
import sys
import csv
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Import our modules
from transcriber import AudioTranscriber
from analyzer import VideoAnalyzer, AnalysisResult
from evidence_exporter import EvidenceExporter

# Import semantic pipeline modules
sys.path.insert(0, str(Path(__file__).parent))
from analysis.language_router import process_all_transcripts as route_languages
from analysis.translator import translate_segments
from analysis.claim_extractor import extract_all_claims
from analysis.topic_clusterer import cluster_claims
from analysis.temporal_pairer import pair_claims
from analysis.contradiction_engine import detect_contradictions
from analysis.target_search import run_target_driven_search
from evidence.case_builder import build_cases, build_cases_from_targets
from evidence.word_exporter import generate_report


def load_config(config_path: str = "config.yaml") -> Dict:
    """Load configuration from YAML."""
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def find_videos(source_dir: Path) -> List[Path]:
    """Find all MP4 files in source directory."""
    videos = []
    for mp4_file in source_dir.rglob("*.mp4"):
        # Skip partial downloads
        if not mp4_file.with_suffix('.mp4.part').exists():
            videos.append(mp4_file)
    return sorted(videos)


def find_partial_downloads(source_dir: Path) -> List[Path]:
    """Find partial downloads that need completion."""
    partials = []
    for part_file in source_dir.rglob("*.mp4.part"):
        mp4_file = part_file.with_suffix('').with_suffix('.mp4')
        if not mp4_file.exists() or mp4_file.stat().st_size < part_file.stat().st_size:
            partials.append(part_file)
    return partials


def extract_audio(video_path: Path, output_dir: Path) -> Optional[Path]:
    """Extract audio from video using moviepy (more reliable than FFmpeg subprocess)."""
    video_id = video_path.stem.replace('youtube_', '')
    audio_path = output_dir / f"{video_id}.mp3"
    
    if audio_path.exists():
        print(f"  Audio already exists: {audio_path.name}")
        return audio_path
    
    print(f"  Extracting audio from {video_path.name}...")
    
    try:
        # Use moviepy for reliable audio extraction
        from moviepy.editor import VideoFileClip
        
        video = VideoFileClip(str(video_path))
        video.audio.write_audiofile(
            str(audio_path),
            fps=16000,  # 16kHz for Whisper
            nbytes=2,
            codec='libmp3lame',
            verbose=False,
            logger=None
        )
        video.close()
        
        if audio_path.exists():
            print(f"  [OK] Audio extracted: {audio_path.name} ({audio_path.stat().st_size / 1024 / 1024:.1f} MB)")
            return audio_path
        else:
            print(f"  [ERROR] Audio file not created")
            return None
            
    except Exception as e:
        print(f"  [ERROR] Audio extraction failed: {e}")
        # Fallback: try FFmpeg directly if moviepy fails
        try:
            cmd = [
                'ffmpeg',
                '-i', str(video_path),
                '-vn',
                '-acodec', 'libmp3lame',
                '-ar', '16000',
                '-ac', '1',
                '-b:a', '128k',
                '-y',
                str(audio_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0 and audio_path.exists():
                print(f"  [OK] Audio extracted via FFmpeg fallback: {audio_path.name}")
                return audio_path
        except:
            pass
        return None


def get_video_metadata(video_path: Path, info_path: Path) -> Dict:
    """Extract metadata from video info.json file."""
    metadata = {
        'video_id': video_path.stem.replace('youtube_', ''),
        'video_path': str(video_path),
        'title': '',
        'description': '',
        'upload_date': '',
        'uploader': '',
        'platform': 'youtube',
        'url': ''
    }
    
    if info_path.exists():
        try:
            with open(info_path, 'r', encoding='utf-8') as f:
                info = json.load(f)
                metadata['title'] = info.get('title', '')
                metadata['description'] = info.get('description', '')[:500]
                metadata['upload_date'] = info.get('upload_date', '')
                metadata['uploader'] = info.get('uploader', '')
                metadata['url'] = info.get('webpage_url', f"https://youtube.com/watch?v={metadata['video_id']}")
        except Exception as e:
            print(f"  Warning: Could not read metadata: {e}")
    
    return metadata


def generate_descriptive_name(metadata: Dict, analysis: Optional[AnalysisResult]) -> str:
    """Generate descriptive filename based on analysis."""
    video_id = metadata.get('video_id', 'unknown')
    upload_date = metadata.get('upload_date', 'unknown')
    title = metadata.get('title', '')
    
    # Extract event name from title
    event_name = "Unknown"
    if 'kgotla' in title.lower():
        # Try to extract kgotla location
        if 'tonota' in title.lower():
            event_name = "TonotaKgotla"
        elif 'tutume' in title.lower():
            event_name = "TutumeKgotla"
        elif 'tlokweng' in title.lower():
            event_name = "TlokwengKgotla"
        elif 'kanye' in title.lower():
            event_name = "KanyeKgotla"
        elif 'ramotswa' in title.lower() or 'gamalete' in title.lower():
            event_name = "RamotswaKgotla"
        elif 'kgagodi' in title.lower():
            event_name = "KgagodiKgotla"
        else:
            event_name = "Kgotla"
    elif 'sona' in title.lower():
        event_name = "SONA"
    elif 'inaugural' in title.lower() or 'un speech' in title.lower():
        event_name = "UNSpeech"
    elif 'press' in title.lower() or 'interview' in title.lower():
        event_name = "PressInterview"
    
    # Determine claim type from analysis
    if analysis:
        case_id = analysis.case_id
        claim_type = analysis.claim_type.replace(' ', '')
        quote_type = analysis.quote_type.replace('_', '').title()
    else:
        # Guess from title keywords
        case_id = "CASE1"
        if any(word in title.lower() for word in ['contract', 'legal', 'binding']):
            claim_type = "ClaimB"
            quote_type = "NotLegalContract"
        elif any(word in title.lower() for word in ['promise', 'fulfil', 'deliver']):
            claim_type = "ClaimA"
            quote_type = "PromiseFulfil"
        else:
            claim_type = "Unclassified"
            quote_type = "Unknown"
    
    # Build filename
    return f"{case_id}_{claim_type}_{quote_type}_{event_name}_{upload_date}_{video_id}.mp4"


def process_single_video(video_path: Path, config: Dict, 
                         audio_dir: Path, transcript_dir: Path,
                         processed_dir: Path, evidence_csv: Path) -> bool:
    """Process a single video through full pipeline."""
    video_id = video_path.stem.replace('youtube_', '')
    
    print(f"\n{'='*70}")
    print(f"[PROCESSING] {video_id}")
    print(f"{'='*70}")
    
    # Get metadata
    info_path = video_path.with_suffix('.info.json')
    metadata = get_video_metadata(video_path, info_path)
    print(f"Title: {metadata['title'][:70]}...")
    print(f"Date: {metadata['upload_date']}")
    
    # Step 1: Extract Audio
    print("\n[STEP 1] Extracting audio...")
    audio_path = extract_audio(video_path, audio_dir)
    
    if not audio_path:
        print("[SKIP] Could not extract audio")
        return False
    
    metadata['audio_path'] = str(audio_path)
    
    # Step 2: Transcribe
    print("\n[STEP 2] Transcribing...")
    analysis_config = config.get('analysis', {})
    
    transcriber = AudioTranscriber(
        model=analysis_config.get('transcription_model', 'base'),
        use_api=analysis_config.get('use_whisper_api', False),
        api_key=config.get('openai_api_key'),
        language=analysis_config.get('language', 'auto')
    )
    
    transcript_path = transcript_dir / f"{video_id}.transcript.json"
    
    try:
        if transcript_path.exists():
            print(f"  Loading existing transcript...")
            with open(transcript_path, 'r', encoding='utf-8') as f:
                transcript = json.load(f)
        else:
            transcript = transcriber.transcribe(audio_path, transcript_path)
        
        print(f"  [OK] Transcript: {len(transcript.get('segments', []))} segments")
        
    except Exception as e:
        print(f"[ERROR] Transcription failed: {e}")
        return False
    
    # Step 3: Analyze
    print("\n[STEP 3] Analyzing for contradictions...")
    
    analyzer = VideoAnalyzer(config)
    analysis_result = analyzer.analyze_video(metadata, transcript, "AUTO")
    
    if analysis_result:
        print(f"  [FOUND] {analysis_result.claim_type}: {analysis_result.quote_type}")
        print(f"  Quote: {analysis_result.quote_text[:80]}...")
        print(f"  Time: {analysis_result.start_time} - {analysis_result.end_time}")
        
        # Save analysis
        analysis_path = transcript_dir / f"{video_id}.analysis.json"
        analyzer.save_analysis(analysis_result, analysis_path)
        
        # Export to evidence CSV
        print("\n[STEP 4] Exporting to evidence CSV...")
        exporter = EvidenceExporter(str(evidence_csv))
        full_metadata = {**metadata, 'cases': config.get('cases', {})}
        exporter.add_evidence(
            metadata=full_metadata,
            analysis_result=analysis_result,
            source_type='clip',
            event_type='kgotla',
            speaker='Duma Boko',
            notes=f"Auto-analyzed from {metadata['platform']}"
        )
    else:
        print("  [NO MATCH] No target quotes found")
        analysis_result = None
    
    # Step 5: Organize
    print("\n[STEP 5] Organizing video...")
    
    new_name = generate_descriptive_name(metadata, analysis_result)
    new_path = processed_dir / new_name
    
    # Copy (not move) to preserve originals until verified
    try:
        import shutil
        shutil.copy2(video_path, new_path)
        print(f"  [OK] Copied to: {new_name}")
        
        # Also copy related files
        for ext in ['.info.json', '.description', '.webp']:
            src = video_path.with_suffix(ext)
            if src.exists():
                dst = new_path.with_suffix(ext)
                shutil.copy2(src, dst)
        
        # Copy transcript and analysis
        if transcript_path.exists():
            shutil.copy2(transcript_path, processed_dir / f"{new_path.stem}.transcript.json")
        analysis_path = transcript_dir / f"{video_id}.analysis.json"
        if analysis_path.exists():
            shutil.copy2(analysis_path, processed_dir / f"{new_path.stem}.analysis.json")
        
    except Exception as e:
        print(f"  [ERROR] Could not organize: {e}")
        return False
    
    print(f"\n[COMPLETE] {video_id} processed successfully")
    return True


def run_semantic_pipeline(
    transcripts_dir: Path,
    outputs_dir: Path,
    test_mode: bool = False,
    skip_translation: bool = False,
    min_contradiction_score: float = 0.3
) -> bool:
    """
    Run the new semantic pipeline for non-English content.
    
    Stages:
    1. Language Routing
    2. Translation (optional)
    3. Claim Extraction
    4. Topic Clustering
    5. Temporal Pairing
    6. Contradiction Detection
    7. Case Building
    
    Returns True if all stages completed successfully.
    """
    print("\n" + "="*70)
    print("SEMANTIC PIPELINE - Evidence-Grade Contradiction Detection")
    print("="*70)
    
    try:
        # Stage 1: Language Routing
        print("\n[1/7] Language Routing...")
        routed_path = outputs_dir / "claims" / "routed_segments.json"
        route_languages(transcripts_dir, routed_path, test_mode=test_mode)
        if not routed_path.exists():
            print("ERROR: Language routing failed")
            return False
        
        # Stage 2: Translation
        print("\n[2/7] Translation...")
        translated_path = outputs_dir / "claims" / "translated_segments.json"
        translate_segments(
            routed_path, translated_path,
            skip_translation=skip_translation,
            test_mode=test_mode
        )
        if not translated_path.exists():
            print("ERROR: Translation failed")
            return False
        
        # Stage 3: Claim Extraction
        print("\n[3/7] Claim Extraction...")
        claims_path = outputs_dir / "claims" / "claims.json"
        extract_all_claims(
            translated_path, claims_path,
            min_confidence=0.5,
            test_mode=test_mode
        )
        if not claims_path.exists():
            print("ERROR: Claim extraction failed")
            return False
        
        # Stage 4: Topic Clustering
        print("\n[4/7] Topic Clustering...")
        clustered_path = outputs_dir / "claims" / "topic_clustered_claims.json"
        topics_config = Path("config/topics.yaml")
        cluster_claims(claims_path, topics_config, clustered_path, test_mode=test_mode)
        if not clustered_path.exists():
            print("ERROR: Topic clustering failed")
            return False
        
        # Stage 5: Temporal Pairing
        print("\n[5/7] Temporal Pairing...")
        pairs_path = outputs_dir / "pairs" / "candidate_pairs.json"
        pair_claims(clustered_path, pairs_path, min_confidence=0.5, test_mode=test_mode)
        if not pairs_path.exists():
            print("ERROR: Temporal pairing failed")
            return False
        
        # Stage 6: Contradiction Detection
        print("\n[6/7] Contradiction Detection...")
        scored_path = outputs_dir / "pairs" / "scored_pairs.json"
        contra_config = Path("config/contradiction_targets.yaml")
        detect_contradictions(
            pairs_path, contra_config, scored_path,
            min_contradiction_score=min_contradiction_score,
            use_nli=False,  # Rule-based only for reliability
            test_mode=test_mode
        )
        if not scored_path.exists():
            print("ERROR: Contradiction detection failed")
            return False
        
        # Stage 7: Case Building
        print("\n[7/7] Case Building...")
        cases_dir = outputs_dir / "cases"
        build_cases(scored_path, clustered_path, cases_dir, test_mode=test_mode)
        
        # Verify outputs
        json_output = cases_dir / "contradiction_cases.json"
        csv_output = cases_dir / "contradiction_cases.csv"
        
        if json_output.exists() and csv_output.exists():
            print("\n" + "="*70)
            print("SEMANTIC PIPELINE COMPLETE")
            print("="*70)
            print(f"Outputs:")
            print(f"  - {routed_path}")
            print(f"  - {translated_path}")
            print(f"  - {claims_path}")
            print(f"  - {clustered_path}")
            print(f"  - {pairs_path}")
            print(f"  - {scored_path}")
            print(f"  - {json_output}")
            print(f"  - {csv_output}")
            return True
        else:
            print("ERROR: Case building did not produce expected outputs")
            return False
            
    except Exception as e:
        print(f"\nERROR in semantic pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_target_driven_pipeline(
    transcripts_dir: Path,
    outputs_dir: Path,
    test_mode: bool = False,
    skip_translation: bool = False,
    min_contradiction_score: float = 0.3,
    export_word: bool = False,
    case_id_filter: Optional[str] = None
) -> bool:
    """
    Run the target-driven contradiction reconstruction pipeline.
    
    Stages:
    1. Language Routing
    2. Translation (optional)
    3. Claim Extraction
    4. Topic Clustering
    5. Target-Driven Search (NEW)
    6. Case Building from Targets (NEW)
    7. Word Document Export (NEW)
    
    Returns True if all stages completed successfully.
    """
    print("\n" + "="*70)
    print("TARGET-DRIVEN PIPELINE - Contradiction Reconstruction Engine")
    print("="*70)
    
    try:
        # Stage 1: Language Routing
        print("\n[1/7] Language Routing...")
        routed_path = outputs_dir / "claims" / "routed_segments.json"
        route_languages(transcripts_dir, routed_path, test_mode=test_mode)
        if not routed_path.exists():
            print("ERROR: Language routing failed")
            return False
        
        # Stage 2: Translation
        print("\n[2/7] Translation...")
        translated_path = outputs_dir / "claims" / "translated_segments.json"
        translate_segments(
            routed_path, translated_path,
            skip_translation=skip_translation,
            test_mode=test_mode
        )
        if not translated_path.exists():
            print("ERROR: Translation failed")
            return False
        
        # Stage 3: Claim Extraction
        print("\n[3/7] Claim Extraction...")
        claims_path = outputs_dir / "claims" / "claims.json"
        extract_all_claims(
            translated_path, claims_path,
            min_confidence=0.5,
            test_mode=test_mode
        )
        if not claims_path.exists():
            print("ERROR: Claim extraction failed")
            return False
        
        # Stage 4: Topic Clustering
        print("\n[4/7] Topic Clustering...")
        clustered_path = outputs_dir / "claims" / "topic_clustered_claims.json"
        topics_config = Path("config/topics.yaml")
        cluster_claims(claims_path, topics_config, clustered_path, test_mode=test_mode)
        if not clustered_path.exists():
            print("ERROR: Topic clustering failed")
            return False
        
        # Stage 5: Target-Driven Search
        print("\n[5/7] Target-Driven Search...")
        targets_config = Path("config/contradiction_targets.yaml")
        target_search_output = outputs_dir / "target_search_results.json"
        target_results = run_target_driven_search(
            targets_config, clustered_path, target_search_output
        )
        
        if not target_search_output.exists():
            print("ERROR: Target search failed")
            return False
        
        # Stage 6: Case Building from Targets
        print("\n[6/7] Case Building from Targets...")
        cases_dir = outputs_dir / "cases"
        case_build_result = build_cases_from_targets(
            target_results, cases_dir, test_mode=test_mode
        )
        
        json_output = cases_dir / "contradiction_cases.json"
        if not json_output.exists():
            print("ERROR: Case building failed")
            return False
        
        # Stage 7: Word Document Export
        if export_word:
            print("\n[7/7] Word Document Export...")
            reports_dir = outputs_dir / "reports"
            reports_dir.mkdir(parents=True, exist_ok=True)
            
            # Load cases for Word export
            import json
            with open(json_output, 'r', encoding='utf-8') as f:
                cases_data = json.load(f)
                cases = cases_data.get('cases', [])
            
            # Filter by case ID if specified
            if case_id_filter:
                cases = [c for c in cases if c.get('case_id') == case_id_filter]
                print(f"  Filtering to case: {case_id_filter}")
            
            if not cases:
                print("WARNING: No cases to export to Word")
                return False
            
            # Generate Word document
            word_output = reports_dir / "duma_boko_contradiction_report.docx"
            metadata = {
                'date': datetime.now().strftime('%B %d, %Y'),
                'classification': 'EVIDENCE FOR REVIEW',
                'status': 'PRELIMINARY ANALYSIS',
                'total_cases': len(cases)
            }
            
            try:
                from evidence.word_exporter import generate_report
                generated_path = generate_report(cases, str(word_output), metadata)
                print(f"  ✓ Word report generated: {generated_path}")
            except Exception as e:
                print(f"  ERROR: Word export failed: {e}")
                return False
        
        # Summary
        print("\n" + "="*70)
        print("TARGET-DRIVEN PIPELINE COMPLETE")
        print("="*70)
        print(f"Outputs:")
        print(f"  - {routed_path}")
        print(f"  - {translated_path}")
        print(f"  - {claims_path}")
        print(f"  - {clustered_path}")
        print(f"  - {target_search_output}")
        print(f"  - {json_output}")
        if export_word:
            print(f"  - {reports_dir / 'duma_boko_contradiction_report.docx'}")
        
        return True
            
    except Exception as e:
        print(f"\nERROR in target-driven pipeline: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main batch processing function."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Batch Video Processor - Extract, Transcribe, Analyze, Organize'
    )
    parser.add_argument(
        '--semantic',
        action='store_true',
        help='Run new semantic pipeline (Language Routing → Translation → Claim Extraction → Topic Clustering → Temporal Pairing → Contradiction Detection → Case Builder)'
    )
    parser.add_argument(
        '--target-driven',
        action='store_true',
        help='Run target-driven contradiction reconstruction engine (NEW)'
    )
    parser.add_argument(
        '--export-word',
        action='store_true',
        help='Generate Microsoft Word document report'
    )
    parser.add_argument(
        '--case-id',
        type=str,
        help='Process specific case ID only (e.g., CASE_001)'
    )
    parser.add_argument(
        '--test-one',
        action='store_true',
        help='Process only one transcript/file (test mode)'
    )
    parser.add_argument(
        '--skip-translation',
        action='store_true',
        help='Skip translation step (preserves original text)'
    )
    parser.add_argument(
        '--min-contradiction-score',
        type=float,
        default=0.3,
        help='Minimum contradiction score threshold (default: 0.3)'
    )
    
    args = parser.parse_args()
    
    print("="*70)
    print("BATCH VIDEO PROCESSOR")
    print("="*70)
    
    # NEW: Run target-driven pipeline if requested
    if args.target_driven:
        transcripts_dir = Path("downloads/TRANSCRIPTS")
        outputs_dir = Path("outputs")
        
        success = run_target_driven_pipeline(
            transcripts_dir,
            outputs_dir,
            test_mode=args.test_one,
            skip_translation=args.skip_translation,
            min_contradiction_score=args.min_contradiction_score,
            export_word=args.export_word,
            case_id_filter=args.case_id
        )
        
        if success:
            print("\n✓ Target-driven pipeline completed successfully")
            return
        else:
            print("\n✗ Target-driven pipeline failed")
            return
    
    # NEW: Run semantic pipeline if requested
    if args.semantic:
        transcripts_dir = Path("downloads/TRANSCRIPTS")
        outputs_dir = Path("outputs")
        
        success = run_semantic_pipeline(
            transcripts_dir,
            outputs_dir,
            test_mode=args.test_one,
            skip_translation=args.skip_translation,
            min_contradiction_score=args.min_contradiction_score
        )
        
        if success:
            print("\n✓ Semantic pipeline completed successfully")
            return
        else:
            print("\n✗ Semantic pipeline failed")
            return
    
    # Load config
    print("\nLoading configuration...")
    config = load_config()
    
    # Setup directories
    source_dir = Path("downloads/AUTO/Unknown")
    audio_dir = Path("downloads/AUDIO")
    transcript_dir = Path("downloads/TRANSCRIPTS")
    processed_dir = Path("downloads/PROCESSED")
    evidence_csv = Path("downloads/evidence_auto_filled.csv")
    
    for dir_path in [audio_dir, transcript_dir, processed_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Created: {dir_path}")
    
    # Find videos
    print(f"\nScanning {source_dir}...")
    videos = find_videos(source_dir)
    partials = find_partial_downloads(source_dir)
    
    print(f"Found {len(videos)} complete videos")
    print(f"Found {len(partials)} partial downloads (will skip)")
    
    if not videos:
        print("\nNo videos to process!")
        return
    
    # Process each video
    success_count = 0
    for i, video_path in enumerate(videos, 1):
        print(f"\n{'='*70}")
        print(f"VIDEO {i}/{len(videos)}")
        print(f"{'='*70}")
        
        try:
            if process_single_video(video_path, config, audio_dir, 
                                   transcript_dir, processed_dir, evidence_csv):
                success_count += 1
        except Exception as e:
            print(f"\n[ERROR] Failed to process {video_path.name}: {e}")
            import traceback
            traceback.print_exc()
            continue
    
    # Summary
    print(f"\n{'='*70}")
    print("BATCH PROCESSING COMPLETE")
    print(f"{'='*70}")
    print(f"Total videos: {len(videos)}")
    print(f"Successful: {success_count}")
    print(f"Failed: {len(videos) - success_count}")
    print(f"\nOutput locations:")
    print(f"  Processed videos: {processed_dir}")
    print(f"  Audio files: {audio_dir}")
    print(f"  Transcripts: {transcript_dir}")
    print(f"  Evidence CSV: {evidence_csv}")


if __name__ == '__main__':
    main()
