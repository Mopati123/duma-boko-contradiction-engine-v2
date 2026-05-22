"""
Video analysis module for extracting quotes, finding timestamps,
and classifying claims.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class QuoteMatch:
    """Represents a matched quote in a transcript."""
    phrase: str
    text: str
    start_time: float
    end_time: float
    confidence: float
    match_type: str  # exact or fuzzy
    segment_id: int


@dataclass
class AnalysisResult:
    """Complete analysis result for a video."""
    video_id: str
    platform: str
    case_id: str
    claim_type: str
    quote_type: str
    quote_text: str
    start_time: str  # formatted as HH:MM:SS
    end_time: str
    context_summary: str
    confidence_score: float
    all_matches: List[QuoteMatch]
    transcript_path: str


class VideoAnalyzer:
    """Analyze video transcripts to extract evidence."""
    
    def __init__(self, config: Dict):
        """
        Initialize analyzer with configuration.
        
        Args:
            config: Configuration dictionary with cases, analysis settings
        """
        self.config = config
        self.cases = config.get('cases', {})
        self.analysis_config = config.get('analysis', {})
        self.context_window = self.analysis_config.get('context_window_seconds', 30)
        self.fuzzy_threshold = self.analysis_config.get('fuzzy_match_threshold', 0.8)
    
    def analyze_video(self, metadata: Dict, transcript: Dict,
                      case_id: str = "AUTO") -> Optional[AnalysisResult]:
        """
        Analyze a video transcript to find relevant quotes.
        
        Args:
            metadata: Video metadata from downloader
            transcript: Transcript from transcriber
            case_id: Case ID to analyze against, or "AUTO" to detect
            
        Returns:
            AnalysisResult with extracted quote and timestamps, or None if no matches
        """
        video_id = metadata.get('video_id', 'unknown')
        platform = metadata.get('platform', 'unknown')
        
        # Determine which case to use
        if case_id == "AUTO":
            case_id = self._detect_case(transcript)
        
        if case_id not in self.cases:
            print(f"  Unknown case: {case_id}")
            return None
        
        case = self.cases[case_id]
        
        # Search for Claim A phrases
        claim_a_matches = self._search_transcript(
            transcript, 
            case['claim_a']['phrases']
        )
        
        # Search for Claim B phrases
        claim_b_matches = self._search_transcript(
            transcript,
            case['claim_b']['phrases']
        )
        
        # Determine which claim type has stronger evidence
        if claim_a_matches and claim_b_matches:
            # Both found - pick the higher confidence one
            best_a = max(claim_a_matches, key=lambda x: x.confidence)
            best_b = max(claim_b_matches, key=lambda x: x.confidence)
            
            if best_a.confidence >= best_b.confidence:
                best_match = best_a
                claim_type = case['claim_a']['type']
                quote_type = case['claim_a']['quote_type']
            else:
                best_match = best_b
                claim_type = case['claim_b']['type']
                quote_type = case['claim_b']['quote_type']
                
        elif claim_a_matches:
            best_match = max(claim_a_matches, key=lambda x: x.confidence)
            claim_type = case['claim_a']['type']
            quote_type = case['claim_a']['quote_type']
            
        elif claim_b_matches:
            best_match = max(claim_b_matches, key=lambda x: x.confidence)
            claim_type = case['claim_b']['type']
            quote_type = case['claim_b']['quote_type']
            
        else:
            print(f"  No matching quotes found in video")
            return None
        
        # Generate context summary
        context_summary = self._generate_context(
            transcript, 
            best_match,
            metadata
        )
        
        # Format timestamps
        start_formatted = self._format_time(best_match.start_time)
        end_formatted = self._format_time(best_match.end_time)
        
        # Combine all matches for record
        all_matches = claim_a_matches + claim_b_matches
        
        return AnalysisResult(
            video_id=video_id,
            platform=platform,
            case_id=case_id,
            claim_type=claim_type,
            quote_type=quote_type,
            quote_text=best_match.text,
            start_time=start_formatted,
            end_time=end_formatted,
            context_summary=context_summary,
            confidence_score=best_match.confidence,
            all_matches=all_matches,
            transcript_path=transcript.get('audio_file', '')
        )
    
    def _detect_case(self, transcript: Dict) -> str:
        """Auto-detect which case this video belongs to based on transcript."""
        full_text = transcript.get('full_text', '').lower()
        
        # Check each case for matching keywords
        for case_id, case in self.cases.items():
            # Check for Duma Boko or Botswana references
            if 'duma boko' in full_text or 'batswana' in full_text:
                return case_id
            
            # Check for case-specific phrases
            for phrase_list in [case['claim_a']['phrases'], case['claim_b']['phrases']]:
                for phrase in phrase_list:
                    if phrase.lower() in full_text:
                        return case_id
        
        # Default to first case if no match
        return list(self.cases.keys())[0] if self.cases else "CASE_1"
    
    def _search_transcript(self, transcript: Dict, phrases: List[str]) -> List[QuoteMatch]:
        """Search transcript for phrases and return matches."""
        matches = []
        segments = transcript.get('segments', [])
        
        try:
            from difflib import SequenceMatcher
            
            for phrase in phrases:
                phrase_lower = phrase.lower()
                
                for segment in segments:
                    seg_text = segment.get('text', '')
                    seg_text_lower = seg_text.lower()
                    
                    # Exact match
                    if phrase_lower in seg_text_lower:
                        matches.append(QuoteMatch(
                            phrase=phrase,
                            text=seg_text.strip(),
                            start_time=segment.get('start', 0),
                            end_time=segment.get('end', 0),
                            confidence=1.0,
                            match_type='exact',
                            segment_id=segment.get('id', 0)
                        ))
                    else:
                        # Fuzzy match - check similarity
                        similarity = SequenceMatcher(
                            None, 
                            phrase_lower, 
                            seg_text_lower
                        ).ratio()
                        
                        if similarity >= self.fuzzy_threshold:
                            matches.append(QuoteMatch(
                                phrase=phrase,
                                text=seg_text.strip(),
                                start_time=segment.get('start', 0),
                                end_time=segment.get('end', 0),
                                confidence=similarity,
                                match_type='fuzzy',
                                segment_id=segment.get('id', 0)
                            ))
            
            # Sort by confidence
            matches.sort(key=lambda x: x.confidence, reverse=True)
            return matches
            
        except Exception as e:
            print(f"  Search error: {e}")
            return []
    
    def _generate_context(self, transcript: Dict, match: QuoteMatch,
                          metadata: Dict) -> str:
        """Generate context summary around the matched quote."""
        segments = transcript.get('segments', [])
        
        # Find segments within context window
        context_segments = []
        for seg in segments:
            seg_start = seg.get('start', 0)
            seg_end = seg.get('end', 0)
            
            # Check if segment overlaps with context window
            if (seg_start >= match.start_time - self.context_window and
                seg_end <= match.end_time + self.context_window):
                context_segments.append(seg.get('text', ''))
        
        # Build context summary
        context_text = ' '.join(context_segments)
        
        # Add speaker/topic if available from metadata
        title = metadata.get('title', '')
        if title:
            context_summary = f"In '{title}', speaker says: {context_text[:200]}"
        else:
            context_summary = context_text[:250]
        
        return context_summary.strip()
    
    def _format_time(self, seconds: float) -> str:
        """Format seconds as HH:MM:SS or MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    def save_analysis(self, result: AnalysisResult, output_path: Path):
        """Save analysis result to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'video_id': result.video_id,
            'platform': result.platform,
            'case_id': result.case_id,
            'claim_type': result.claim_type,
            'quote_type': result.quote_type,
            'quote_text': result.quote_text,
            'start_time': result.start_time,
            'end_time': result.end_time,
            'context_summary': result.context_summary,
            'confidence_score': result.confidence_score,
            'all_matches': [
                {
                    'phrase': m.phrase,
                    'text': m.text,
                    'start_time': m.start_time,
                    'end_time': m.end_time,
                    'confidence': m.confidence,
                    'match_type': m.match_type
                }
                for m in result.all_matches
            ],
            'transcript_path': result.transcript_path
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Analysis saved: {output_path}")


def analyze_video(metadata: Dict, transcript: Dict, config: Dict,
                  case_id: str = "AUTO") -> Optional[AnalysisResult]:
    """
    Convenience function for single video analysis.
    
    Example:
        result = analyze_video(metadata, transcript, config, "CASE_1")
    """
    analyzer = VideoAnalyzer(config)
    return analyzer.analyze_video(metadata, transcript, case_id)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python analyzer.py <metadata.json> <transcript.json> [case_id]")
        print("Example: python analyzer.py metadata.json transcript.json CASE_1")
        sys.exit(1)
    
    # Load files
    with open(sys.argv[1], 'r') as f:
        metadata = json.load(f)
    with open(sys.argv[2], 'r') as f:
        transcript = json.load(f)
    
    case_id = sys.argv[3] if len(sys.argv) > 3 else "AUTO"
    
    # Load config
    try:
        with open('config.yaml', 'r') as f:
            import yaml
            config = yaml.safe_load(f)
    except:
        print("Warning: Could not load config.yaml, using defaults")
        config = {
            'cases': {
                'CASE_1': {
                    'claim_a': {'phrases': ['fulfil'], 'type': 'Claim_A', 'quote_type': 'promise'},
                    'claim_b': {'phrases': ['contract'], 'type': 'Claim_B', 'quote_type': 'denial'}
                }
            },
            'analysis': {'context_window_seconds': 30, 'fuzzy_match_threshold': 0.8}
        }
    
    # Analyze
    result = analyze_video(metadata, transcript, config, case_id)
    
    if result:
        print(f"\nAnalysis complete!")
        print(f"Case: {result.case_id}")
        print(f"Claim type: {result.claim_type}")
        print(f"Quote: {result.quote_text[:100]}...")
        print(f"Timestamp: {result.start_time} - {result.end_time}")
        print(f"Confidence: {result.confidence_score:.2f}")
    else:
        print("\nNo relevant quotes found in video")
