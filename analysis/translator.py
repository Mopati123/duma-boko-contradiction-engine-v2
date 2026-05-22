#!/usr/bin/env python3
"""
translator.py - Translate non-English segments to English.

Input: outputs/claims/routed_segments.json
Output: outputs/claims/translated_segments.json

Translation approach:
1. Try local HuggingFace model (Helsinki-NLP/opus-mt-mul-en) if available
2. If model unavailable or translation fails, keep original and mark as failed
3. Never require paid API

Preserves original text always. Adds translated_text and translation_status.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from evidence.evidence_schema import TranslatedSegment, save_json, load_json

# Translation model settings
TRANSLATION_MODEL = "Helsinki-NLP/opus-mt-mul-en"


def load_translation_model():
    """
    Attempt to load local HuggingFace translation model.
    Returns model pipeline or None if unavailable.
    """
    try:
        from transformers import pipeline
        print(f"Loading translation model: {TRANSLATION_MODEL}")
        translator = pipeline("translation", model=TRANSLATION_MODEL, device=-1)  # CPU
        print(f"  ✓ Model loaded successfully")
        return translator
    except ImportError:
        print("  ⚠ transformers library not installed. Translation will be marked as failed.")
        return None
    except Exception as e:
        print(f"  ⚠ Failed to load model: {e}")
        return None


def translate_text(text: str, translator, source_lang: str) -> tuple:
    """
    Translate text using the loaded model.
    
    Args:
        text: Text to translate
        translator: HuggingFace translation pipeline or None
        source_lang: Source language code
    
    Returns:
        (translated_text, status)
        status is "success" or "failed"
    """
    if not translator:
        return text, "failed"
    
    if not text or not text.strip():
        return text, "success"  # Empty text doesn't need translation
    
    try:
        # Truncate very long text (model may have length limits)
        max_chars = 512
        truncated = text[:max_chars] if len(text) > max_chars else text
        
        # Perform translation
        result = translator(truncated, max_length=512)
        
        if result and len(result) > 0:
            translated = result[0].get('translation_text', '').strip()
            if translated:
                return translated, "success"
        
        return text, "failed"
        
    except Exception as e:
        print(f"    Translation error: {e}")
        return text, "failed"


def translate_segments(
    routed_segments_path: Path,
    output_path: Path,
    skip_translation: bool = False,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    Translate all segments that require translation.
    
    Args:
        routed_segments_path: Path to routed_segments.json
        output_path: Where to save translated_segments.json
        skip_translation: If True, mark all as "not_required" or "failed"
        test_mode: If True, process only first 10 segments
    
    Returns:
        Dictionary with processing results and statistics
    """
    # Load routed segments
    data = load_json(routed_segments_path)
    segments = data.get('segments', [])
    
    print(f"Loaded {len(segments)} routed segments")
    
    if test_mode:
        segments = segments[:10]
        print(f"[TEST MODE] Processing only first {len(segments)} segments")
    
    # Load translation model (if not skipping)
    translator = None if skip_translation else load_translation_model()
    
    translated_segments = []
    stats = {
        'total_segments': len(segments),
        'not_required': 0,
        'translated': 0,
        'failed': 0
    }
    
    print(f"\nTranslating segments...")
    
    for i, seg in enumerate(segments):
        segment_id = seg['segment_id']
        language = seg['language']
        original_text = seg['original_text']
        requires_translation = seg['requires_translation']
        
        # Determine translation status
        if not requires_translation:
            # Already English
            translated_text = original_text
            translation_status = "not_required"
            stats['not_required'] += 1
        elif skip_translation or not translator:
            # Translation skipped or model unavailable
            translated_text = original_text
            translation_status = "failed"
            stats['failed'] += 1
        else:
            # Attempt translation
            translated_text, translation_status = translate_text(
                original_text, translator, language
            )
            
            if translation_status == "success":
                stats['translated'] += 1
            else:
                stats['failed'] += 1
        
        # Create translated segment record
        translated_seg = TranslatedSegment(
            segment_id=segment_id,
            source_video_id=seg['source_video_id'],
            source_transcript_file=seg['source_transcript_file'],
            start=seg['start'],
            end=seg['end'],
            language=language,
            original_text=original_text,
            translated_text=translated_text,
            translation_status=translation_status,
            translation_model=TRANSLATION_MODEL if translation_status == "success" else None,
            metadata=seg.get('metadata', {})
        )
        
        translated_segments.append(translated_seg)
        
        # Progress update
        if (i + 1) % 100 == 0 or i == len(segments) - 1:
            print(f"  Processed {i + 1}/{len(segments)} segments...")
    
    # Build output
    output = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'pipeline_stage': 'translation',
            'version': '1.0',
            'test_mode': test_mode,
            'skip_translation': skip_translation,
            'model_used': TRANSLATION_MODEL if translator else None
        },
        'statistics': stats,
        'segments': [seg.to_dict() for seg in translated_segments]
    }
    
    # Save output
    os.makedirs(output_path.parent, exist_ok=True)
    save_json(output, str(output_path))
    
    print(f"\n✓ Translation complete")
    print(f"  Total segments: {stats['total_segments']}")
    print(f"  Not required (English): {stats['not_required']}")
    print(f"  Translated: {stats['translated']}")
    print(f"  Failed (preserved original): {stats['failed']}")
    print(f"  Output: {output_path}")
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Translate non-English segments'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='outputs/claims/routed_segments.json',
        help='Input routed segments file'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='outputs/claims/translated_segments.json',
        help='Output file path'
    )
    parser.add_argument(
        '--test-one',
        action='store_true',
        help='Process only first 10 segments (test mode)'
    )
    parser.add_argument(
        '--skip-translation',
        action='store_true',
        help='Skip translation (mark all as failed/not_required)'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        print("Run language_router.py first.")
        sys.exit(1)
    
    result = translate_segments(
        input_path,
        output_path,
        skip_translation=args.skip_translation,
        test_mode=args.test_one
    )
    
    # Return success
    sys.exit(0)


if __name__ == '__main__':
    main()
