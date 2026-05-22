"""
Evidence CSV export module.
Integrates analysis results into the evidence spreadsheet.
"""

import csv
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime


class EvidenceExporter:
    """Export analysis results to evidence CSV."""
    
    # Standard CSV columns
    COLUMNS = [
        'source_type',
        'source_url',
        'video_id_or_shortcode',
        'platform',
        'posted_at',
        'mentioned_date',
        'event_type',
        'event_name',
        'speaker',
        'quote_type',
        'quote_text',
        'start_time',
        'end_time',
        'context_summary',
        'case_id',
        'case_type',
        'contradiction_type',
        'ds_score',
        'notes'
    ]
    
    def __init__(self, csv_path: str):
        """
        Initialize exporter.
        
        Args:
            csv_path: Path to evidence CSV file
        """
        self.csv_path = Path(csv_path)
        self.existing_videos = self._load_existing_videos()
    
    def _load_existing_videos(self) -> set:
        """Load set of existing video IDs to avoid duplicates."""
        existing = set()
        
        if not self.csv_path.exists():
            return existing
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    video_id = row.get('video_id_or_shortcode', '')
                    if video_id and video_id != 'video_id_or_shortcode':
                        existing.add(video_id)
        except Exception as e:
            print(f"  Warning: Could not read existing CSV: {e}")
        
        return existing
    
    def add_evidence(self, metadata: Dict, analysis_result,
                     source_type: str = "clip",
                     event_type: str = "kgotla",
                     speaker: str = "Duma Boko",
                     notes: str = "") -> bool:
        """
        Add new evidence row to CSV.
        
        Args:
            metadata: Video metadata
            analysis_result: AnalysisResult from analyzer
            source_type: Type of source (clip, full_speech, etc.)
            event_type: Type of event (kgotla, press_conference, etc.)
            speaker: Name of speaker
            notes: Additional notes
            
        Returns:
            True if added, False if duplicate
        """
        from analyzer import AnalysisResult
        
        if not isinstance(analysis_result, AnalysisResult):
            raise ValueError("analysis_result must be AnalysisResult object")
        
        video_id = metadata.get('video_id', '')
        
        # Check for duplicate
        if video_id in self.existing_videos:
            print(f"  Skipping duplicate: {video_id}")
            return False
        
        # Get case info for contradiction type
        contradiction_type = ""
        if analysis_result.case_id in metadata.get('cases', {}):
            case = metadata['cases'][analysis_result.case_id]
            contradiction_type = case.get('contradiction_type', '')
        
        # Build row
        row = {
            'source_type': source_type,
            'source_url': metadata.get('url', ''),
            'video_id_or_shortcode': video_id,
            'platform': metadata.get('platform', ''),
            'posted_at': metadata.get('upload_date', datetime.now().strftime('%Y-%m-%d')),
            'mentioned_date': metadata.get('upload_date', ''),
            'event_type': event_type,
            'event_name': metadata.get('cases', {}).get(analysis_result.case_id, {}).get('event_name', ''),
            'speaker': speaker,
            'quote_type': analysis_result.quote_type,
            'quote_text': analysis_result.quote_text,
            'start_time': analysis_result.start_time,
            'end_time': analysis_result.end_time,
            'context_summary': analysis_result.context_summary,
            'case_id': analysis_result.case_id,
            'case_type': analysis_result.claim_type,
            'contradiction_type': contradiction_type,
            'ds_score': f"{analysis_result.confidence_score:.2f}",
            'notes': notes
        }
        
        # Write to CSV
        file_exists = self.csv_path.exists()
        
        with open(self.csv_path, 'a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.COLUMNS)
            
            # Write header if new file
            if not file_exists:
                writer.writeheader()
            
            writer.writerow(row)
        
        self.existing_videos.add(video_id)
        print(f"  ✓ Added to evidence CSV: {video_id}")
        
        return True
    
    def export_analysis_json(self, analysis_result, output_path: Path):
        """Export analysis as standalone JSON."""
        from analyzer import AnalysisResult
        
        if not isinstance(analysis_result, AnalysisResult):
            raise ValueError("analysis_result must be AnalysisResult object")
        
        data = {
            'video_id': analysis_result.video_id,
            'platform': analysis_result.platform,
            'case_id': analysis_result.case_id,
            'claim_type': analysis_result.claim_type,
            'quote_type': analysis_result.quote_type,
            'quote_text': analysis_result.quote_text,
            'start_time': analysis_result.start_time,
            'end_time': analysis_result.end_time,
            'context_summary': analysis_result.context_summary,
            'confidence_score': analysis_result.confidence_score,
            'all_matches': [
                {
                    'phrase': m.phrase,
                    'text': m.text,
                    'start_time': m.start_time,
                    'end_time': m.end_time,
                    'confidence': m.confidence,
                    'match_type': m.match_type
                }
                for m in analysis_result.all_matches
            ]
        }
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Analysis exported: {output_path}")
    
    def get_summary(self) -> Dict:
        """Get summary of evidence in CSV."""
        if not self.csv_path.exists():
            return {'total_records': 0, 'cases': {}, 'platforms': {}}
        
        summary = {
            'total_records': 0,
            'cases': {},
            'platforms': {},
            'claim_types': {}
        }
        
        try:
            with open(self.csv_path, 'r', encoding='utf-8', newline='') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    summary['total_records'] += 1
                    
                    case_id = row.get('case_id', 'UNKNOWN')
                    summary['cases'][case_id] = summary['cases'].get(case_id, 0) + 1
                    
                    platform = row.get('platform', 'unknown')
                    summary['platforms'][platform] = summary['platforms'].get(platform, 0) + 1
                    
                    claim_type = row.get('case_type', 'unknown')
                    summary['claim_types'][claim_type] = summary['claim_types'].get(claim_type, 0) + 1
                    
        except Exception as e:
            print(f"  Error reading summary: {e}")
        
        return summary


def export_evidence(metadata: Dict, analysis_result, csv_path: str,
                    event_type: str = "kgotla", speaker: str = "Duma Boko") -> bool:
    """
    Convenience function to export single evidence record.
    
    Example:
        export_evidence(metadata, analysis, "evidence.csv")
    """
    exporter = EvidenceExporter(csv_path)
    return exporter.add_evidence(metadata, analysis_result, event_type=event_type, speaker=speaker)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python evidence_exporter.py <csv_path> [--summary]")
        print("Example: python evidence_exporter.py evidence_template.csv --summary")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    
    exporter = EvidenceExporter(csv_file)
    
    if '--summary' in sys.argv:
        summary = exporter.get_summary()
        print(f"\nEvidence Summary:")
        print(f"Total records: {summary['total_records']}")
        print(f"\nBy case:")
        for case, count in summary['cases'].items():
            print(f"  {case}: {count}")
        print(f"\nBy platform:")
        for platform, count in summary['platforms'].items():
            print(f"  {platform}: {count}")
        print(f"\nBy claim type:")
        for claim, count in summary['claim_types'].items():
            print(f"  {claim}: {count}")
    else:
        print(f"Evidence CSV: {csv_file}")
        print(f"Existing videos: {len(exporter.existing_videos)}")
        print("Use --summary for detailed stats")
