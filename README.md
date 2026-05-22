# YouTube Search & Evidence System for Duma Boko Research

This project provides tools to search YouTube for videos containing specific phrases related to Duma Boko's statements, and a standardized CSV template for collecting cross-source evidence.

## Files

- **search_boko_youtube.py** - Python script to search YouTube via Data API v3
- **evidence_template.csv** - CSV template with schema and example rows
- **requirements.txt** - Python dependencies

## Setup

### 1. Enable YouTube Data API v3

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Navigate to **APIs & Services > Library**
4. Search for "YouTube Data API v3" and click **Enable**

### 2. Create API Key

1. Go to **APIs & Services > Credentials**
2. Click **Create Credentials > API Key**
3. Copy the key (starts with `AIza...`)
4. (Optional) Restrict the key to YouTube Data API v3 for security

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install google-api-python-client
```

## Usage

### 1. Configure the Script

Open `search_boko_youtube.py` and replace:
```python
API_KEY = "YOUR_YOUTUBE_API_KEY_HERE"
```

With your actual API key.

### 2. Run the Search

```bash
python search_boko_youtube.py
```

Output: `boko_youtube_results.csv` with columns:
- `search_phrase` - The query that found this video
- `title` - Video title
- `video_id` - YouTube video ID
- `url` - Full YouTube URL
- `published_at` - Publication date (ISO 8601)
- `description` - First 200 characters of description

### 3. Review Results

Open `boko_youtube_results.csv` and filter for Botswana/Duma Boko related videos.

### 4. Collect Evidence

For each relevant video:
1. Open the URL
2. Use YouTube's transcript panel to find timestamps
3. Copy evidence into `evidence_template.csv`

## Evidence CSV Schema

| Column | Description |
|--------|-------------|
| `source_type` | clip, full_speech, repost, news |
| `source_url` | Full URL of video/post |
| `video_id_or_shortcode` | Platform-specific ID |
| `platform` | youtube, facebook, tiktok, instagram, web_article |
| `posted_at` | Date posted (YYYY-MM-DD) |
| `mentioned_date` | Date mentioned in content |
| `event_type` | kgotla, press_conference, SONA, campaign_rally, interview, parliament |
| `event_name` | e.g., "Kgagodi kgotla (Jan 2026)" |
| `speaker` | Person speaking (e.g., Duma Boko) |
| `quote_type` | promise_fulfil, not_legal_contract, social_contract, manifesto_quote |
| `quote_text` | Verbatim quote |
| `start_time` | Timestamp start (HH:MM or HH:MM:SS) |
| `end_time` | Timestamp end |
| `context_summary` | 1-2 sentence context |
| `case_id` | CASE_1, CASE_2, etc. |
| `case_type` | Claim_A, Claim_B |
| `contradiction_type` | Framing inversion, Promise vs outcome, etc. |
| `ds_score` | Float 0-1 (e.g., 0.85) |
| `notes` | Additional notes |

## Workflow

1. Run script → Get YouTube results
2. Manually search Facebook/TikTok with same phrases
3. Paste URLs and timestamps into `evidence_template.csv`
4. Join rows by `case_id` and `case_type` for analysis
5. Mark ΔS-HIGH when same quote_type appears in different events/time ranges

## Search Phrases

The script searches for:
1. "A promise to voters is not a legal contract"
2. "election promises are not legal or social contracts"
3. "election promises are not legally binding contracts"
4. "Votes aren't contracts"
5. "government will fulfil promises"
6. "no backing down from our promises"
7. "President Duma Boko"
8. "Duma Boko kgotla"
9. "Duma Boko 2024 election promises"

## Notes

- API quota: 100 units per search, 10,000 units/day default
- Each phrase uses 1 search = 100 units
- 9 phrases = 900 units per full run
- Results are sorted by date (most recent first)
