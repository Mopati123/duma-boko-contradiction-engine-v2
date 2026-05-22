#!/usr/bin/env python3
"""
Analyze YouTube Transcripts for Contradictions
Finds Claim A (promise_fulfil) vs Claim B (not_legal_contract) statements.
Uses fuzzy matching for robust phrase detection.
"""

import json
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from difflib import SequenceMatcher


@dataclass
class QuoteFinding:
    """A found quote with context."""
    video_id: str
    quote_text: str
    start_time: float
    end_time: float
    context_before: str
    context_after: str
    claim_type: str  # Claim_A or Claim_B
    quote_type: str  # promise_fulfil or not_legal_contract
    confidence: float
    matched_phrase: str


class TranscriptAnalyzer:
    """Analyzes transcripts for contradictions."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.cases = config.get('cases', {})
        
    def fuzzy_match(self, text: str, phrase: str, threshold: float = 0.6) -> Tuple[bool, float, str]:
        """Check if phrase appears in text with fuzzy matching."""
        text_lower = text.lower()
        phrase_lower = phrase.lower()
        
        # Direct match (substring)
        if phrase_lower in text_lower:
            return True, 1.0, phrase
        
        # Keyword matching - check if all key words appear
        key_words = [w for w in phrase_lower.split() if len(w) > 3]
        if len(key_words) >= 2:
            matches = sum(1 for word in key_words if word in text_lower)
            if matches >= len(key_words) * 0.7:  # 70% of keywords match
                return True, 0.85, phrase
        
        # Word-level fuzzy matching
        text_words = text_lower.split()
        phrase_words = phrase_lower.split()
        phrase_len = len(phrase_words)
        
        if phrase_len == 0 or len(text_words) < phrase_len:
            return False, 0.0, ""
        
        best_ratio = 0.0
        best_match = ""
        
        # Slide window over text
        for i in range(len(text_words) - phrase_len + 1):
            window = text_words[i:i + phrase_len]
            window_text = " ".join(window)
            
            ratio = SequenceMatcher(None, phrase_lower, window_text).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = window_text
        
        return best_ratio >= threshold, best_ratio, best_match
    
    def find_quotes_in_transcript(self, video_id: str, transcript_data: List[Dict], 
                                   phrases: List[str], claim_type: str, 
                                   quote_type: str) -> List[QuoteFinding]:
        """Find all occurrences of target phrases in transcript."""
        findings = []
        
        # Build full text with segment mapping
        segments = transcript_data
        
        for i, segment in enumerate(segments):
            text = segment.get('text', '')
            start_time = segment.get('start', 0)
            duration = segment.get('duration', 0)
            end_time = start_time + duration
            
            # Check each target phrase
            for phrase in phrases:
                matched, confidence, matched_text = self.fuzzy_match(
                    text, phrase, 
                    threshold=self.config.get('analysis', {}).get('fuzzy_match_threshold', 0.8)
                )
                
                if matched:
                    # Get context (30 seconds before and after)
                    context_window = self.config.get('analysis', {}).get('context_window_seconds', 30)
                    
                    context_before_segments = []
                    context_after_segments = []
                    
                    # Look backwards for context
                    j = i - 1
                    while j >= 0 and (start_time - segments[j].get('start', 0)) <= context_window:
                        context_before_segments.insert(0, segments[j].get('text', ''))
                        j -= 1
                    
                    # Look forwards for context
                    j = i + 1
                    while j < len(segments) and (segments[j].get('start', 0) - end_time) <= context_window:
                        context_after_segments.append(segments[j].get('text', ''))
                        j += 1
                    
                    finding = QuoteFinding(
                        video_id=video_id,
                        quote_text=text,
                        start_time=start_time,
                        end_time=end_time,
                        context_before=" ".join(context_before_segments),
                        context_after=" ".join(context_after_segments),
                        claim_type=claim_type,
                        quote_type=quote_type,
                        confidence=confidence,
                        matched_phrase=matched_text
                    )
                    findings.append(finding)
        
        return findings
    
    def analyze_video(self, video_id: str, transcript_file: Path) -> List[QuoteFinding]:
        """Analyze a single video transcript."""
        findings = []
        
        # Load transcript
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"  Error loading {transcript_file}: {e}")
            return findings
        
        if not data.get('success', False):
            return findings
        
        transcript = data.get('transcript', [])
        if not transcript:
            return findings
        
        # Analyze each case
        for case_id, case_config in self.cases.items():
            # Claim A phrases
            claim_a_config = case_config.get('claim_a', {})
            claim_a_phrases = claim_a_config.get('phrases', [])
            
            if claim_a_phrases:
                claim_a_findings = self.find_quotes_in_transcript(
                    video_id, transcript, claim_a_phrases,
                    'Claim_A', claim_a_config.get('quote_type', 'promise_fulfil')
                )
                findings.extend(claim_a_findings)
            
            # Claim B phrases
            claim_b_config = case_config.get('claim_b', {})
            claim_b_phrases = claim_b_config.get('phrases', [])
            
            if claim_b_phrases:
                claim_b_findings = self.find_quotes_in_transcript(
                    video_id, transcript, claim_b_phrases,
                    'Claim_B', claim_b_config.get('quote_type', 'not_legal_contract')
                )
                findings.extend(claim_b_findings)
        
        return findings
    
    def analyze_all_transcripts(self, transcripts_dir: str = "transcripts_youtube",
                                output_csv: str = "analysis_youtube.csv") -> List[QuoteFinding]:
        """Analyze all transcripts and export results."""
        
        print("=" * 70)
        print("ANALYZING TRANSCRIPTS FOR CONTRADICTIONS")
        print("=" * 70)
        print()
        
        transcripts_path = Path(transcripts_dir)
        if not transcripts_path.exists():
            print(f"Error: {transcripts_dir} not found")
            return []
        
        # Find all transcript files
        transcript_files = list(transcripts_path.glob("*_youtube.json"))
        print(f"Found {len(transcript_files)} transcript files")
        print()
        
        all_findings = []
        
        for i, transcript_file in enumerate(transcript_files, 1):
            video_id = transcript_file.stem.replace('_youtube', '')
            
            print(f"[{i}/{len(transcript_files)}] Analyzing {video_id}...", end=" ")
            
            findings = self.analyze_video(video_id, transcript_file)
            
            if findings:
                claim_a_count = sum(1 for f in findings if f.claim_type == 'Claim_A')
                claim_b_count = sum(1 for f in findings if f.claim_type == 'Claim_B')
                print(f"[FOUND] Claim A: {claim_a_count}, Claim B: {claim_b_count}")
                all_findings.extend(findings)
            else:
                print("[No matches]")
        
        print()
        print("=" * 70)
        print("ANALYSIS COMPLETE")
        print("=" * 70)
        print(f"Total findings: {len(all_findings)}")
        
        if all_findings:
            claim_a_total = sum(1 for f in all_findings if f.claim_type == 'Claim_A')
            claim_b_total = sum(1 for f in all_findings if f.claim_type == 'Claim_B')
            print(f"  Claim A (Promise Fulfil): {claim_a_total}")
            print(f"  Claim B (Not Legal Contract): {claim_b_total}")
            
            # High confidence findings
            high_conf = [f for f in all_findings if f.confidence >= 0.9]
            print(f"  High confidence (>90%): {len(high_conf)}")
        
        print()
        
        # Export to CSV
        self.export_findings(all_findings, output_csv)
        
        return all_findings
    
    def export_findings(self, findings: List[QuoteFinding], output_csv: str):
        """Export findings to CSV."""
        if not findings:
            print("No findings to export")
            return
        
        output_path = Path(output_csv)
        
        fieldnames = [
            'video_id', 'claim_type', 'quote_type', 'confidence',
            'start_time', 'end_time', 'quote_text', 'matched_phrase',
            'context_before', 'context_after'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for finding in findings:
                row = asdict(finding)
                # Truncate long fields for CSV readability
                row['context_before'] = row['context_before'][:200]
                row['context_after'] = row['context_after'][:200]
                writer.writerow(row)
        
        print(f"Exported to: {output_csv}")


def load_config(config_path: str = "config.yaml") -> Dict:
    """Load configuration from YAML."""
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze transcripts for contradictions')
    parser.add_argument('--input', default='transcripts_youtube', help='Transcripts directory')
    parser.add_argument('--output', default='analysis_youtube.csv', help='Output CSV file')
    parser.add_argument('--config', default='config.yaml', help='Config file')
    
    args = parser.parse_args()
    
    # Load config
    print("Loading configuration...")
    config = load_config(args.config)
    
    # Create analyzer
    analyzer = TranscriptAnalyzer(config)
    
    # Analyze all transcripts
    findings = analyzer.analyze_all_transcripts(args.input, args.output)
    
    print()
    print("Next steps:")
    print("1. Review analysis_youtube.csv for high-confidence findings")
    print("2. Manually verify top findings using verify_findings.py")
    print("3. Organize verified videos into PROCESSED/ folder")


if __name__ == '__main__':
    main()
