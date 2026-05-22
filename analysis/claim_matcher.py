#!/usr/bin/env python3
"""
claim_matcher.py - Weighted scoring engine for governance divergence matching.

Reframed for v3.0: Governance Promise-Delivery Divergence Reconstruction Engine.
"""

import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# ─────────────────────────────────────────
# OPPOSITION PATTERNS
# ─────────────────────────────────────────

# Patterns that signal divergence between promise and outcome
DIVERGENCE_PATTERNS = [
    (r'\bnot\b', r'\bwill\b'),
    (r'\bnever\b', r'\balways\b'),
    (r'\bdenied\b', r'\bpromised\b'),
    (r'\bcannot\b', r'\bcan\b'),
    (r'\bwon\'t\b', r'\bwill\b'),
    (r'\bfailed\b', r'\bsucceed\b'),
    (r'\bnot binding\b', r'\bbinding\b'),
    (r'\bnot legal\b', r'\blegal\b'),
    (r'\bshortage\b', r'\baccess\b'),
    (r'\bemergency\b', r'\bfixing\b'),
    (r'\bdownturn\b', r'\bgrow\b'),
    (r'\bconstraints\b', r'\btransform\b'),
]

# Antonym pairs for divergence
ANTONYM_PAIRS = [
    ('promise', 'outcome'),
    ('commitment', 'divergence'),
    ('deliver', 'fail'),
    ('create', 'constraint'),
    ('build', 'delay'),
    ('growth', 'downturn'),
    ('success', 'emergency'),
    ('free', 'shortage'),
    ('binding', 'not binding'),
    ('accountable', 'distancing'),
]

# Source credibility tiers
SOURCE_CREDIBILITY = {
    'official_speech': 1.0,
    'manifesto': 1.0,
    'government_declaration': 1.0,
    'interview': 0.9,
    'parliament': 0.9,
    'press_conference': 0.9,
    'kgotla_meeting': 0.85,
    'video': 0.8,
    'news_article': 0.7,
    'dailynews': 0.7,
    'facebook': 0.5,
    'social_media': 0.4,
    'transcript': 0.6,
    'unknown': 0.3,
}


class ClaimMatcher:
    """
    Weighted scoring engine for Governance Divergence.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = {
            'same_speaker': 0.25,
            'same_topic': 0.20,
            'semantic_opposition': 0.30,
            'source_credibility': 0.15,
            'transcript_confidence': 0.10,
        }
        if weights:
            self.weights.update(weights)

    def score_same_speaker(self, promise: Dict[str, Any], outcome: Dict[str, Any]) -> Tuple[float, str]:
        p_speaker = promise.get('speaker', '').lower()
        o_speaker = outcome.get('speaker', '').lower()
        boko_indicators = ['duma boko', 'boko', 'president', 'udc leader']

        p_is_boko = any(ind in p_speaker for ind in boko_indicators) if p_speaker else False
        o_is_boko = any(ind in o_speaker for ind in boko_indicators) if o_speaker else False

        if p_is_boko and o_is_boko:
            return 1.0, "Both attributed to Duma Boko"
        elif p_is_boko:
            return 0.8, "Promise attributed to Duma Boko; Outcome is system/govt event"
        else:
            return 0.4, "Speaker attribution unclear"

    def score_same_topic(self, promise: Dict[str, Any], outcome: Dict[str, Any], target_topic: str) -> Tuple[float, str]:
        if promise.get('topic') == outcome.get('topic') or target_topic in str(promise) + str(outcome):
            return 1.0, f"Topic alignment: {target_topic}"
        return 0.5, "Implicit topic alignment"

    def score_semantic_opposition(self, p_text: str, o_text: str, p_terms: List[str], o_terms: List[str]) -> Tuple[float, str]:
        p_lower = p_text.lower()
        o_lower = o_text.lower()
        score = 0.0
        reasons = []

        # 1. Antonyms
        for word_a, word_b in ANTONYM_PAIRS:
            if word_a in p_lower and word_b in o_lower:
                score += 0.3
                reasons.append(f"Divergence detected: {word_a} vs {word_b}")

        # 2. Negation
        for neg, pos in DIVERGENCE_PATTERNS:
            if re.search(pos, p_lower) and re.search(neg, o_lower):
                score += 0.3
                reasons.append(f"Negation of promise: {neg}")

        # 3. Term matching
        p_hits = sum(1 for t in p_terms if t.lower() in p_lower)
        o_hits = sum(1 for t in o_terms if t.lower() in o_lower)
        if p_hits > 0 and o_hits > 0:
            score += 0.4
            reasons.append(f"Matched {p_hits} promise terms and {o_hits} outcome indicators")

        score = min(score, 1.0)
        return score, '; '.join(reasons) if reasons else "Low semantic divergence detected"

    def score_pair(self, promise: Dict[str, Any], outcome: Dict[str, Any], target: Dict[str, Any]) -> Dict[str, Any]:
        p_text = promise.get('quote', promise.get('snippet', ''))
        o_text = outcome.get('quote', outcome.get('snippet', ''))
        
        speaker_s, speaker_r = self.score_same_speaker(promise, outcome)
        topic_s, topic_r = self.score_same_topic(promise, outcome, target.get('topic', ''))
        semantic_s, semantic_r = self.score_semantic_opposition(
            p_text, o_text, target.get('promise_indicators', []), target.get('failure_indicators', [])
        )
        
        # Simple credibility/confidence
        cred_s = (SOURCE_CREDIBILITY.get(promise.get('platform', 'unknown'), 0.5) + 
                  SOURCE_CREDIBILITY.get(outcome.get('platform', 'unknown'), 0.5)) / 2
        conf_s = (promise.get('confidence', 0.5) + outcome.get('confidence', 0.5)) / 2

        final_score = (
            speaker_s * self.weights['same_speaker'] +
            topic_s * self.weights['same_topic'] +
            semantic_s * self.weights['semantic_opposition'] +
            cred_s * self.weights['source_credibility'] +
            conf_s * self.weights['transcript_confidence']
        )
        
        strength = 'high' if final_score >= 0.7 else 'medium' if final_score >= 0.5 else 'low'

        return {
            'final_score': round(final_score, 3),
            'evidence_strength': strength,
            'analysis': f"Speaker: {speaker_r}. Topic: {topic_r}. Divergence: {semantic_r}."
        }
