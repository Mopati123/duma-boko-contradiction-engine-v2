# Duma Boko Video Evidence Analysis System - Architecture Overview

Complete repository structure, file purposes, and data flow architecture for the automated video evidence collection and contradiction detection system.

---

## 1. FULL DIRECTORY TREE

```
Duma Boko/
├── .gitignore                          # Git exclusions (API keys, temp files)
├── README.md                           # Project overview and setup instructions
├── requirements.txt                    # Python dependencies
│
├── config.yaml                         # Main configuration (API keys, search terms, cases)
├── config.example.yaml                 # Template for config.yaml (no real keys)
│
├── # CORE PROCESSING PIPELINE
├── batch_processor.py                  # Main orchestrator - runs full pipeline end-to-end
├── process_priority_videos.py          # Processes only largest/highest-priority videos
│
├── # VIDEO ACQUISITION
├── search_boko_youtube.py            # YouTube Data API search for Duma Boko videos
├── youtube_transcript_fetcher.py     # Downloads YouTube transcripts (not audio)
├── downloader.py                     # yt-dlp video/audio downloader
│
├── # AUDIO PROCESSING
├── video_processor.py                # MoviePy-based audio extraction
├── analyze_metadata.py               # Extracts video metadata (duration, title, etc.)
│
├── # TRANSCRIPTION
├── transcriber.py                    # OpenAI Whisper audio-to-text transcriber
├── whisper_batch.py                  # Batch Whisper processing for multiple files
├── whisper_sample.py                 # Single-file transcription test
│
├── # STATEMENT EXTRACTION & ANALYSIS
├── extract_statements.py             # Extracts "I-statements" and policy claims from transcripts
├── extract_segments.py               # Extracts all transcript segments with metadata
├── extract_all_statements.py         # Bulk extraction without filtering
├── extract_swahili_statements.py     # Swahili-language statement extractor
├── find_english_segments.py          # Filters transcripts for English-only content
│
├── # CONTRADICTION DETECTION
├── analyzer.py                       # Generic contradiction analyzer (fuzzy matching)
├── analyze_transcripts.py            # Compares transcript pairs for contradictions
├── analyze_target_contradictions.py  # Targeted contradiction search (specific statements)
├── compile_evidence.py               # Compiles findings into evidence CSV
│
├── # EVIDENCE EXPORT & REVIEW
├── evidence_exporter.py              # Exports evidence in multiple formats
├── evidence_review.py                # Launches web server for manual evidence review
├── evidence_review.html              # Static HTML review interface (standalone)
├── evidence_template.csv             # CSV template for evidence cataloging
│
├── # SOCIAL MEDIA EXPANSION
├── search_download_social.py         # Downloads videos from Facebook/TikTok URLs
├── social_media_search.py            # URL discovery helpers for social platforms
├── remove_watermarks.py              # FFmpeg-based watermark removal (TikTok/FB)
│
├── # UTILITIES
├── organize_videos.py                # Renames and sorts videos by metadata
├── progress_monitor.py               # Tracks processing progress across sessions
│
├── # DATA OUTPUT (generated during processing)
├── downloads/
│   ├── AUTO/
│   │   └── Unknown/                  # Raw downloaded videos from YouTube
│   ├── PROCESSED/                    # Renamed/organized video files
│   ├── TRANSCRIPTS/                  # Whisper transcript JSON files (*.transcript.json)
│   ├── FACEBOOK/
│   │   ├── raw/                      # Original Facebook videos (with watermarks)
│   │   └── clean/                    # Watermark-removed versions
│   ├── TIKTOK/
│   │   ├── raw/                      # Original TikTok videos (with watermarks)
│   │   └── clean/                    # Watermark-removed versions
│   └── metadata/                     # Download catalogs and processing logs
│
├── transcripts_whisper/              # Alternative transcript storage
├── transcripts_youtube/              # YouTube API transcript downloads
│
├── # ANALYSIS OUTPUT (generated)
├── duma_statements_extracted.json    # Auto-extracted key statements
├── extracted_segments.json             # All transcript segments (3,805 segments)
├── english_segments.json             # English-only segments (62 segments)
├── swahili_statements_extracted.json # Swahili statement extraction results
├── all_statements_extracted.json     # Unfiltered statement extraction
│
├── contradictions_analysis.json      # Contradiction detection results (currently empty)
├── contradictions_evidence.csv       # Evidence export CSV (currently empty)
│
├── # LOGS & REPORTS
├── batch_process_log.txt             # Main processing log (228 KB)
├── download_log.txt                  # Download operation logs
├── transcript_fetch_log.txt          # YouTube transcript fetch logs
├── whisper_batch_log.txt             # Whisper batch processing logs
├── whisper_log.txt                   # Single-file transcription logs
├── analysis_log.txt                  # Analysis output logs
├── analysis_results.txt              # Duplicate of analysis_log.txt
├── analysis_v2.txt                   # Duplicate of analysis_log.txt
├── priority_processing_log.txt       # Priority video processing logs
├── fetcher_output.txt                # YouTube fetcher output
├── fetcher_v2.txt                    # Duplicate fetcher output
│
├── # DOCUMENTATION & REPORTS
├── ANALYSIS_SUMMARY.md               # Technical analysis findings and limitations
├── FINAL_STATUS_REPORT.md            # Social media download completion report
├── SOCIAL_MEDIA_IMPLEMENTATION_SUMMARY.md  # TikTok/Facebook search results
├── manual_urls.txt                   # Manually collected social media URLs
├── search_urls_guide.txt             # Search URL templates for manual browsing
├── metadata_analysis.csv             # Video metadata analysis results
├── metadata_results.txt              # Metadata extraction summary
├── boko_youtube_results.csv          # YouTube search result catalog
│
├── # TEMPORARY FILES
├── temp_*.mp3                        # Temporary audio files during extraction
│   ├── temp_34AMXm-AVjU.mp3 (115 MB)
│   ├── temp_JwCS_jac_jI.mp3 (193 MB)
│   ├── temp_sxAFtLv5oV4.mp3 (134 MB)
│   └── temp_xwj_bkZ4sJU.mp3 (107 MB)
│
├── # VIRTUAL ENVIRONMENTS
├── venv/                             # Original Python virtual environment
├── venv_new/                         # Updated virtual environment (active)
│
├── # EXTERNAL TOOLS
├── ffmpeg/                           # FFmpeg binary directory
├── ffmpeg.zip                        # FFmpeg archive (20 MB)
├── ffmpeg_github.zip                 # FFmpeg GitHub release (146 MB)
├── ffmpeg_new.zip                    # FFmpeg updated build (109 MB)
│
├── # PYTHON CACHE
└── __pycache__/                      # Compiled Python bytecode

# WINDSURF PLANS (outside project root)
C:\Users\Dataentry\.windsurf\plans\
├── video-evidence-analysis-system-5a6503.md
├── youtube-search-evidence-system-5a6503.md
├── analyze-organize-videos-5a6503.md
├── batch-complete-analysis-5a6503.md
├── full-execution-parallel-5a6503.md
├── progress-monitor-with-timer-5a6503.md
├── hybrid-contradiction-detection-5a6503.md
├── hybrid-accuracy-approach-5a6503.md
├── facebook-tiktok-search-watermark-removal-5a6503.md
└── [other project plans from different sessions]
```

---

## 2. SYSTEM DATA FLOW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW ARCHITECTURE                            │
└─────────────────────────────────────────────────────────────────────────────┘

PHASE 1: DISCOVERY
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────────────┐
│ YouTube API     │────>│ search_boko_     │────>│ boko_youtube_results    │
│ (config.yaml)   │     │ youtube.py       │     │ .csv                    │
└─────────────────┘     └──────────────────┘     └─────────────────────────┘
                              │
                              v
┌─────────────────┐     ┌──────────────────┐
│ Facebook/TikTok │────>│ social_media_    │
│ URLs (manual)   │     │ search.py        │
└─────────────────┘     └──────────────────┘
                              │
                              v
                    ┌──────────────────┐
                    │ manual_urls.txt  │
                    └──────────────────┘

PHASE 2: ACQUISITION
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────────────┐
│ boko_youtube_    │────>│ downloader.py    │────>│ downloads/AUTO/Unknown/  │
│ results.csv      │     │ (yt-dlp)         │     │ (raw video files)        │
└──────────────────┘     └──────────────────┘     └──────────────────────────┘
                              │
                              ├────────────────────────────────────────┐
                              v                                        v
                    ┌──────────────────┐                    ┌──────────────────┐
                    │ video_processor  │                    │ search_download_ │
                    │ .py (audio)      │                    │ social.py (FB/   │
                    │                  │                    │ TikTok videos)   │
                    └──────────────────┘                    └──────────────────┘
                              │                                        │
                              v                                        v
                    ┌──────────────────┐                    ┌──────────────────┐
                    │ temp_*.mp3       │                    │ downloads/       │
                    │ (audio files)    │                    │ FACEBOOK/ &      │
                    └──────────────────┘                    │ TIKTOK/          │
                                                            └──────────────────┘
                                                                     │
                                                                     v
                                                            ┌──────────────────┐
                                                            │ remove_watermarks│
                                                            │ .py (FFmpeg)     │
                                                            └──────────────────┘
                                                                     │
                                                                     v
                                                            ┌──────────────────┐
                                                            │ clean/           │
                                                            │ (no watermarks)  │
                                                            └──────────────────┘

PHASE 3: TRANSCRIPTION
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────────────────┐
│ temp_*.mp3       │────>│ transcriber.py   │────>│ downloads/TRANSCRIPTS/         │
│ (audio)          │     │ (Whisper base)   │     │ *.transcript.json              │
└──────────────────┘     └──────────────────┘     └──────────────────────────────┘
                              │
                              v
                    ┌──────────────────┐
                    │ whisper_batch.py │
                    │ (batch mode)     │
                    └──────────────────┘

PHASE 4: ANALYSIS
┌──────────────────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ downloads/TRANSCRIPTS/       │────>│ extract_         │────>│ duma_statements_│
│ *.transcript.json            │     │ statements.py    │     │ extracted.json  │
└──────────────────────────────┘     └──────────────────┘     └─────────────────┘
                              │
                              ├────────────────────────────────────────┐
                              v                                        v
                    ┌──────────────────┐                    ┌──────────────────┐
                    │ extract_         │                    │ find_english_    │
                    │ segments.py      │                    │ segments.py      │
                    │ (all segments)   │                    │ (English only)   │
                    └──────────────────┘                    └──────────────────┘
                              │                                        │
                              v                                        v
                    ┌──────────────────┐                    ┌──────────────────┐
                    │ extracted_       │                    │ english_         │
                    │ segments.json    │                    │ segments.json    │
                    │ (3,805 segments) │                    │ (62 segments)    │
                    └──────────────────┘                    └──────────────────┘
                              │
                              v
                    ┌──────────────────┐
                    │ analyze_target_  │
                    │ contradictions.py│
                    │ (fuzzy matching) │
                    └──────────────────┘
                              │
                              v
                    ┌──────────────────┐
                    │ contradictions_  │
                    │ analysis.json    │
                    │ (currently 0)    │
                    └──────────────────┘

PHASE 5: EVIDENCE COMPILATION
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────────────┐
│ contradictions_  │────>│ compile_         │────>│ evidence_template.csv    │
│ analysis.json    │     │ evidence.py      │     │ contradictions_          │
│                  │     │                  │     │ evidence.csv             │
└──────────────────┘     └──────────────────┘     └──────────────────────────┘
                              │
                              v
                    ┌──────────────────┐
                    │ evidence_exporter  │
                    │ .py              │
                    └──────────────────┘
                              │
                              v
                    ┌──────────────────┐
                    │ evidence_review  │
                    │ .py (web UI)     │
                    └──────────────────┘
                              │
                              v
                    ┌──────────────────┐
                    │ evidence_review  │
                    │ .html            │
                    └──────────────────┘

PHASE 6: ORGANIZATION
┌──────────────────────────┐     ┌──────────────────┐     ┌──────────────────────┐
│ downloads/AUTO/Unknown │────>│ organize_videos  │────>│ downloads/PROCESSED/ │
│ (raw downloads)          │     │ .py              │     │ (renamed by content)  │
└──────────────────────────┘     └──────────────────┘     └──────────────────────┘
```

---

## 3. COMPONENT DESCRIPTIONS

### Core Pipeline (`batch_processor.py`)
- **Purpose**: Master orchestrator that runs the entire workflow
- **Input**: Config from `config.yaml`, video files
- **Output**: Organized videos, transcripts, analysis results
- **Key Functions**:
  - `extract_audio()` - Uses MoviePy (with FFmpeg fallback) for reliable audio extraction
  - `transcribe_audio()` - Calls Whisper API or local model
  - `analyze_contradictions()` - Scans transcripts for target phrases
  - `organize_output()` - Moves processed files to proper directories

### Configuration (`config.yaml`)
- **API Keys**: YouTube Data API v3 key, optional OpenAI key
- **Search Phrases**: Target search terms for video discovery
- **Case Definitions**: Structured contradiction frameworks (e.g., CASE_1: "Promise fulfillment vs contract denial")
  - `claim_a`: "government will fulfil promises" (promise_fulfil type)
  - `claim_b`: "not a legal contract" (not_legal_contract type)
  - `contradiction_type`: "Framing inversion"

### Video Acquisition Layer
- `search_boko_youtube.py` - Searches YouTube API for Duma Boko content
- `downloader.py` - yt-dlp wrapper for video/audio download
- `youtube_transcript_fetcher.py` - Fetches existing YouTube captions (faster than Whisper)

### Audio Processing (`video_processor.py`)
- Uses **MoviePy** for primary audio extraction
- **FFmpeg** as fallback if MoviePy fails
- Output: 16kHz mono MP3 (optimal for Whisper)

### Transcription Layer
- **Primary**: `transcriber.py` - OpenAI Whisper (base model)
- **Batch**: `whisper_batch.py` - Processes multiple files sequentially
- **Output Format**:
  ```json
  {
    "video_id": "...",
    "audio_file": "...",
    "language": "sw",
    "duration": 1234.5,
    "full_text": "...",
    "segments": [
      {"id": 0, "start": 0.0, "end": 5.2, "text": "...", "confidence": 0.95}
    ]
  }
  ```

### Statement Extraction Layer
- `extract_statements.py` - Identifies first-person policy statements using regex patterns
- Scoring algorithm: Keyword matches + sentence structure + governance terms
- Output: `duma_statements_extracted.json` with importance scores

### Contradiction Detection (`analyze_target_contradictions.py`)
- **Method**: Fuzzy string matching + keyword overlap
- **Targets**: User-provided statements + auto-extracted statements
- **Matching Criteria**:
  - Keyword overlap >= 30%
  - Similarity score >= 50%
  - Opposite sentiment indicators ("will" vs "won't")
- **Output**: JSON with contradiction type, confidence, timestamps

### Evidence Compilation (`compile_evidence.py`)
- Scans all transcript files for matches against `config.yaml` target phrases
- Produces CSV with: video ID, timestamp, matched text, contradiction type, confidence

### Review Interface (`evidence_review.py`)
- **Type**: Flask web application
- **Features**:
  - Browse contradiction findings
  - Mark entries as "Verified", "Rejected", or "Needs Review"
  - Export confirmed evidence to CSV
- **Alternative**: `evidence_review.html` (static HTML, no server needed)

### Social Media Expansion
- `search_download_social.py` - Downloads from provided URLs (not automated search)
- `remove_watermarks.py` - FFmpeg crop filter to remove TikTok/Facebook banners
- **Limitation**: Facebook requires authentication; TikTok accessible via yt-dlp

---

## 4. KEY DATA FILES

| File | Size | Content | Status |
|------|------|---------|--------|
| `extracted_segments.json` | 1,047 KB | All 3,805 transcript segments | ✅ Complete |
| `english_segments.json` | 205 KB | 62 English-only segments | ✅ Complete |
| `duma_statements_extracted.json` | 191 B | Auto-extracted statements | ✅ Empty (language mismatch) |
| `contradictions_analysis.json` | 255 B | Contradiction results | ✅ Empty |
| `contradictions_evidence.csv` | 98 B | Evidence CSV | ✅ Empty (no findings) |
| `batch_process_log.txt` | 228 KB | Full processing log | ✅ Complete |

---

## 5. CRITICAL FINDINGS & LIMITATIONS

### The Language Problem
- **98.4% of transcripts are in Swahili** (not English)
- Our contradiction detection uses **English keywords**
- Result: Zero contradictions found across 18 videos, 3,805 segments

### The English Content
- Only **62 English segments** found (1.6%)
- Mostly from single video: `AittyT1pssk` (CSIR conference)
- Key statements found:
  - "Things are going to be done very quickly, very efficiently"
  - "I say go ahead and protest"
  - "The people of this country don't have time to wait"

### Why No Contradictions
1. Language mismatch: English targets on Swahili content
2. Insufficient English data: Only 62 segments
3. Single-source English: Most from one speech
4. Need Swahili speaker or translation for further analysis

---

## 6. USAGE WORKFLOWS

### Full Pipeline (Automated)
```bash
# 1. Configure
edit config.yaml  # Add API keys, set paths

# 2. Search
python search_boko_youtube.py

# 3. Download & Process
python batch_processor.py

# 4. Transcribe
python whisper_batch.py

# 5. Extract Statements
python extract_statements.py

# 6. Find Contradictions
python analyze_target_contradictions.py

# 7. Compile Evidence
python compile_evidence.py

# 8. Review
python evidence_review.py
```

### Social Media Add-On
```bash
# 1. Add URLs to manual_urls.txt
# 2. Download
python search_download_social.py

# 3. Remove Watermarks
python remove_watermarks.py

# 4. Add to pipeline (transcribe → analyze)
```

### Manual Review Only
```bash
# Launch web interface for existing findings
python evidence_review.py
# Open browser to http://localhost:5000
```

---

## 7. TECHNOLOGY STACK

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.x |
| Video Download | yt-dlp | Latest |
| Audio Extraction | MoviePy + FFmpeg | 1.0.x + 6.x |
| Transcription | OpenAI Whisper | base model |
| Text Matching | difflib (SequenceMatcher) | Built-in |
| Web Framework | Flask | 2.x |
| Config Format | YAML | PyYAML |
| Data Format | JSON | Built-in |

---

## 8. FILE SIZE SUMMARY

| Category | Count | Approximate Size |
|----------|-------|------------------|
| Python Scripts | 30 | ~300 KB total |
| Downloaded Videos | ~20 | ~500 MB |
| Audio Temp Files | 4 | ~550 MB |
| Transcripts | 18 | ~10 MB |
| JSON Data Files | 6 | ~1.3 MB |
| Log Files | 8 | ~500 KB |
| Documentation | 6 | ~100 KB |
| External Tools | 3 | ~275 MB (FFmpeg) |
| **TOTAL** | | **~1.4 GB** |

---

**Document Generated**: April 28, 2026  
**System Version**: Iteration 6 (Social Media Phase Added)  
**Status**: Functional but awaiting Swahili analysis or more English content
