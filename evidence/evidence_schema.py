"""
evidence_schema.py - Stable JSON schema definitions for evidence cases.

v3.0: Reframed to "Governance Divergence" engine. 
Added GovernanceDivergenceCase and refined EvidencePosition.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from datetime import datetime
import json


@dataclass
class EvidencePosition:
    """A single evidence position (promise or outcome)."""
    quote: str
    source: str
    url: str
    date: str
    evidence_type: str                 # "manifesto", "article", "video", "speech"
    platform: str                      # "youtube", "facebook", "news", "transcript"
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    screenshot_path: Optional[str] = None
    confidence: float = 0.0
    speaker: str = "Duma Boko"
    matched_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceObject:
    """A normalized, reportable evidence record linked to a claim."""
    evidence_id: str
    case_id: str
    claim_role: str
    quote: str
    source: str
    url: str
    date: str
    evidence_type: str
    platform: str
    verification_status: str = "source_linked"
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    screenshot_path: Optional[str] = None
    confidence: float = 0.0
    speaker: str = "Duma Boko"
    matched_terms: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GovernanceDivergenceCase:
    """
    A complete divergence case from the reconstruction engine.
    """
    case_id: str
    topic: str

    # Evidence positions (Reframed)
    promise: Dict[str, Any]             # EvidencePosition.to_dict()
    outcome_or_position: Dict[str, Any] # EvidencePosition.to_dict()

    # Divergence details
    divergence_type: str                # from new taxonomy
    analysis: str                       # detailed reconstruction
    evidence_strength: str              # "low", "medium", "high"
    verification_status: str            # "verified", "partial", "pending"

    # Supporting data
    description: str = ""
    all_promise_sources: List[Dict[str, Any]] = field(default_factory=list)
    all_outcome_sources: List[Dict[str, Any]] = field(default_factory=list)
    raw_urls: List[str] = field(default_factory=list)
    evidence_objects: List[Dict[str, Any]] = field(default_factory=list)
    claim_evidence_links: Dict[str, List[str]] = field(default_factory=dict)

    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    pipeline_version: str = "divergence_engine_v3.0"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# JSON Utilities
class EvidenceEncoder(json.JSONEncoder):
    def default(self, obj):
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()
        return super().default(obj)

def save_json(data: Any, filepath: str) -> None:
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, cls=EvidenceEncoder, indent=2, ensure_ascii=False)

def load_json(filepath: str) -> Any:
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)
