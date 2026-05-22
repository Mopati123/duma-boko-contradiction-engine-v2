#!/usr/bin/env python3
"""
web_searcher.py - Execute searches against web platforms and return structured results.

The key missing piece that makes the engine actually FIND evidence.

Supports:
1. YouTube Data API search + transcript extraction
2. Web/news article scraping via requests + BeautifulSoup
3. Known URL extraction (pre-seeded sources)
4. Local transcript corpus search
5. Generated search URLs for manual follow-up (Facebook etc.)

Usage:
    from analysis.web_searcher import WebSearcher
    searcher = WebSearcher(config)
    results = searcher.search_platform("youtube", "Duma Boko social contract")
"""

import os
import sys
import re
import json
import time
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import quote_plus, urljoin

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from evidence.evidence_schema import SearchResult, save_json, load_json

logger = logging.getLogger(__name__)


class WebSearcher:
    """
    Multi-platform search engine for contradiction evidence.
    
    Executes searches against YouTube API, web pages, and local transcripts.
    Returns structured SearchResult objects.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize with config containing API keys and paths.
        
        Args:
            config: Dictionary with youtube_api_key, downloads_path, etc.
        """
        self.youtube_api_key = config.get('youtube_api_key', '')
        self.downloads_path = Path(config.get('downloads_path', './downloads'))
        self.transcripts_dir = self.downloads_path / 'TRANSCRIPTS'
        self.rate_limit_delay = config.get('rate_limit_delay', 1.0)
        self._youtube_service = None

    # ─────────────────────────────────────────
    # YOUTUBE SEARCH
    # ─────────────────────────────────────────

    def _get_youtube_service(self):
        """Lazy-init YouTube API service."""
        if self._youtube_service is not None:
            return self._youtube_service

        if not self.youtube_api_key:
            logger.warning("No YouTube API key configured")
            return None

        try:
            from googleapiclient.discovery import build
            self._youtube_service = build(
                'youtube', 'v3',
                developerKey=self.youtube_api_key,
                cache_discovery=False
            )
            return self._youtube_service
        except Exception as e:
            logger.error(f"Failed to init YouTube API: {e}")
            return None

    def search_youtube(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search YouTube via Data API v3.
        
        Args:
            query: Search query string
            max_results: Maximum results to return
            
        Returns:
            List of SearchResult objects
        """
        service = self._get_youtube_service()
        if not service:
            logger.warning("YouTube API unavailable, generating search URLs instead")
            return [SearchResult(
                title=f"[MANUAL SEARCH] YouTube: {query}",
                url=f"https://www.youtube.com/results?search_query={quote_plus(query)}",
                snippet="YouTube API unavailable. Use this URL to search manually.",
                platform="youtube",
                date="",
                relevance_score=0.0,
                metadata={"manual_search": True, "query": query}
            )]

        results = []
        try:
            request = service.search().list(
                q=query,
                part='snippet',
                type='video',
                maxResults=max_results,
                order='date',
                relevanceLanguage='en'
            )
            response = request.execute()

            for item in response.get('items', []):
                snippet = item.get('snippet', {})
                video_id = item.get('id', {}).get('videoId', '')

                result = SearchResult(
                    title=snippet.get('title', ''),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    snippet=snippet.get('description', '')[:500],
                    platform="youtube",
                    date=snippet.get('publishedAt', '')[:10],
                    video_id=video_id,
                    has_transcript=False,
                    metadata={
                        'channel': snippet.get('channelTitle', ''),
                        'thumbnail': snippet.get('thumbnails', {}).get('default', {}).get('url', '')
                    }
                )
                results.append(result)

            time.sleep(self.rate_limit_delay)

        except Exception as e:
            logger.error(f"YouTube search failed for '{query}': {e}")

        return results

    def fetch_youtube_transcript(self, video_id: str) -> Optional[str]:
        """
        Fetch transcript for a YouTube video.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Full transcript text or None
        """
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
            transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=['en', 'st', 'tn'])
            full_text = ' '.join([entry['text'] for entry in transcript_list])
            return full_text
        except Exception as e:
            logger.debug(f"No transcript for {video_id}: {e}")
            return None

    # ─────────────────────────────────────────
    # WEB / NEWS SEARCH
    # ─────────────────────────────────────────

    def search_web(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search the web for news articles about the query.
        
        Uses DuckDuckGo HTML search (no API key needed).
        
        Args:
            query: Search query string
            max_results: Maximum results to return
            
        Returns:
            List of SearchResult objects
        """
        results = []

        try:
            import requests
            from bs4 import BeautifulSoup

            # DuckDuckGo HTML search
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # Parse DuckDuckGo results
            for result_div in soup.select('.result')[:max_results]:
                title_tag = result_div.select_one('.result__title a')
                snippet_tag = result_div.select_one('.result__snippet')

                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)
                link = title_tag.get('href', '')
                snippet_text = snippet_tag.get_text(strip=True) if snippet_tag else ''

                # Skip irrelevant results
                if not link or 'duckduckgo.com' in link:
                    continue

                result = SearchResult(
                    title=title,
                    url=link,
                    snippet=snippet_text[:500],
                    platform="news_article",
                    date="",
                    relevance_score=0.0,
                    metadata={'search_engine': 'duckduckgo', 'query': query}
                )
                results.append(result)

            time.sleep(self.rate_limit_delay)

        except ImportError:
            logger.error("requests/beautifulsoup4 not installed")
        except Exception as e:
            logger.error(f"Web search failed for '{query}': {e}")

        return results

    def extract_article_text(self, url: str) -> Optional[str]:
        """
        Extract main text content from a news article URL.
        
        Args:
            url: Article URL
            
        Returns:
            Extracted text or None
        """
        try:
            import requests
            from bs4 import BeautifulSoup

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'lxml')

            # Remove script and style elements
            for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                tag.decompose()

            # Try to find article body
            article = soup.find('article') or soup.find('main') or soup.find('body')
            if article:
                paragraphs = article.find_all('p')
                text = '\n'.join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 30)
                return text[:5000] if text else None

            return None

        except Exception as e:
            logger.debug(f"Failed to extract text from {url}: {e}")
            return None

    # ─────────────────────────────────────────
    # FACEBOOK (manual URL generation)
    # ─────────────────────────────────────────

    def generate_facebook_search_urls(self, query: str) -> List[SearchResult]:
        """
        Generate Facebook search URLs for manual follow-up.
        Facebook blocks automated scraping, so we provide URLs.
        
        Args:
            query: Search query string
            
        Returns:
            List of SearchResult objects with search URLs
        """
        urls = [
            f"https://www.facebook.com/search/posts/?q={quote_plus(query)}",
            f"https://www.facebook.com/search/videos/?q={quote_plus(query)}",
        ]

        results = []
        for url in urls:
            results.append(SearchResult(
                title=f"[MANUAL SEARCH] Facebook: {query}",
                url=url,
                snippet="Facebook requires manual search. Open this URL in a browser.",
                platform="facebook",
                date="",
                relevance_score=0.0,
                metadata={"manual_search": True, "query": query}
            ))

        return results

    # ─────────────────────────────────────────
    # KNOWN SOURCES
    # ─────────────────────────────────────────

    def process_known_sources(self, known_sources: List[Dict[str, Any]]) -> List[SearchResult]:
        """
        Convert pre-seeded known source URLs into SearchResult objects.
        Attempts to extract content from each URL.
        
        Args:
            known_sources: List of known source dictionaries from targets config
            
        Returns:
            List of SearchResult objects
        """
        results = []

        for source in known_sources:
            url = source.get('url', '')
            if not url:
                continue

            platform = source.get('platform', 'unknown')
            description = source.get('description', '')

            # Try to extract content
            full_text = None
            if platform in ('news_article', 'dailynews', 'web'):
                full_text = self.extract_article_text(url)

            result = SearchResult(
                title=description or f"Known source: {url[:80]}",
                url=url,
                snippet=description,
                platform=platform,
                date=source.get('date', ''),
                relevance_score=0.9,  # High score for known/verified sources
                full_text=full_text,
                metadata={
                    'known_source': True,
                    'position': source.get('position', 'unknown')
                }
            )
            results.append(result)

        return results

    # ─────────────────────────────────────────
    # LOCAL TRANSCRIPT SEARCH
    # ─────────────────────────────────────────

    def search_local_transcripts(self, search_terms: List[str], min_score: float = 0.3) -> List[SearchResult]:
        """
        Search local Whisper transcripts for matching segments.
        
        Args:
            search_terms: List of phrases to search for
            min_score: Minimum match score
            
        Returns:
            List of SearchResult objects
        """
        results = []

        if not self.transcripts_dir.exists():
            return results

        for transcript_file in self.transcripts_dir.glob('*.transcript.json'):
            try:
                with open(transcript_file, 'r', encoding='utf-8') as f:
                    transcript = json.load(f)

                video_id = transcript.get('video_id', transcript_file.stem.replace('.transcript', ''))
                segments = transcript.get('segments', [])

                for segment in segments:
                    text = segment.get('text', '').lower()
                    if not text or len(text) < 10:
                        continue

                    # Score against search terms
                    score = 0.0
                    matched = []
                    for term in search_terms:
                        term_lower = term.lower()
                        if term_lower in text:
                            score += 0.5
                            matched.append(term)
                        else:
                            # Partial word match
                            words = term_lower.split()
                            match_count = sum(1 for w in words if w in text)
                            if match_count > 0:
                                partial = (match_count / len(words)) * 0.3
                                score += partial
                                if partial > 0.15:
                                    matched.append(f"{term}(partial)")

                    score = min(score, 1.0)

                    if score >= min_score and matched:
                        start = segment.get('start', 0)
                        end = segment.get('end', 0)

                        result = SearchResult(
                            title=f"Transcript: {video_id}",
                            url=f"https://www.youtube.com/watch?v={video_id}&t={int(start)}",
                            snippet=segment.get('text', '')[:500],
                            platform="transcript",
                            date="",
                            relevance_score=score,
                            video_id=video_id,
                            has_transcript=True,
                            full_text=segment.get('text', ''),
                            metadata={
                                'start': start,
                                'end': end,
                                'matched_terms': matched,
                                'language': transcript.get('language', 'unknown'),
                                'source_file': str(transcript_file)
                            }
                        )
                        results.append(result)

            except Exception as e:
                logger.debug(f"Error reading transcript {transcript_file}: {e}")

        # Sort by relevance
        results.sort(key=lambda r: r.relevance_score, reverse=True)
        return results

    # ─────────────────────────────────────────
    # UNIFIED SEARCH
    # ─────────────────────────────────────────

    def search_platform(self, platform: str, query: str, max_results: int = 10) -> List[SearchResult]:
        """
        Search a specific platform.
        
        Args:
            platform: One of "youtube", "facebook", "news_articles", "dailynews", "transcript"
            query: Search query
            max_results: Maximum results
            
        Returns:
            List of SearchResult objects
        """
        if platform == 'youtube':
            return self.search_youtube(query, max_results)
        elif platform == 'facebook':
            return self.generate_facebook_search_urls(query)
        elif platform in ('news_articles', 'dailynews', 'news'):
            return self.search_web(query, max_results)
        elif platform == 'transcript':
            return self.search_local_transcripts(query.split(',') if isinstance(query, str) else query)
        else:
            logger.warning(f"Unknown platform: {platform}")
            return []

    def search_all_platforms(
        self,
        queries: Dict[str, List[str]],
        known_sources: List[Dict[str, Any]] = None,
        max_per_query: int = 5
    ) -> Dict[str, List[SearchResult]]:
        """
        Search all platforms with platform-specific queries.
        
        Args:
            queries: Dict mapping platform → list of query strings
            known_sources: Pre-seeded source URLs
            max_per_query: Max results per query
            
        Returns:
            Dict mapping platform → list of SearchResult
        """
        all_results = {}

        # Process known sources first
        if known_sources:
            known_results = self.process_known_sources(known_sources)
            if known_results:
                all_results['known'] = known_results
                print(f"    Known sources: {len(known_results)} pre-verified")

        # Search each platform
        for platform, query_list in queries.items():
            platform_results = []

            for query in query_list:
                results = self.search_platform(platform, query, max_per_query)
                platform_results.extend(results)

            # Deduplicate by URL
            seen_urls = set()
            deduped = []
            for r in platform_results:
                if r.url not in seen_urls:
                    seen_urls.add(r.url)
                    deduped.append(r)

            all_results[platform] = deduped
            print(f"    {platform}: {len(deduped)} results from {len(query_list)} queries")

        return all_results


def main():
    """CLI test interface."""
    import yaml

    config_path = Path('config.yaml')
    if config_path.exists():
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    searcher = WebSearcher(config)

    # Test YouTube search
    print("\n=== YouTube Search Test ===")
    results = searcher.search_youtube('Duma Boko "social contract"', max_results=3)
    for r in results:
        print(f"  [{r.platform}] {r.title[:60]} — {r.url}")

    # Test web search
    print("\n=== Web Search Test ===")
    results = searcher.search_web('Duma Boko promises not legal contracts', max_results=3)
    for r in results:
        print(f"  [{r.platform}] {r.title[:60]} — {r.url}")

    # Test local transcript search
    print("\n=== Local Transcript Search Test ===")
    results = searcher.search_local_transcripts(['contract', 'promise', 'deliver'], min_score=0.2)
    print(f"  Found {len(results)} matching segments")
    for r in results[:3]:
        print(f"  [{r.relevance_score:.2f}] {r.snippet[:80]}...")


if __name__ == '__main__':
    main()
