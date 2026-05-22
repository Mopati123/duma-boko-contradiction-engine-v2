"""
Audio transcription module using OpenAI Whisper.
Supports local Whisper installation or Whisper API.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Union
import warnings

# Suppress FP16 warnings from Whisper
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")


class AudioTranscriber:
    """Transcribe audio files using Whisper."""
    
    def __init__(self, model: str = "base", use_api: bool = False, 
                 api_key: Optional[str] = None, language: str = "auto"):
        """
        Initialize transcriber.
        
        Args:
            model: Whisper model size (tiny, base, small, medium, large)
            use_api: Use OpenAI Whisper API instead of local model
            api_key: OpenAI API key (required if use_api=True)
            language: Language code (auto for auto-detect)
        """
        self.model = model
        self.use_api = use_api
        self.api_key = api_key
        self.language = None if language == "auto" else language
        
        self.whisper_model = None
        
        if not use_api:
            self._load_local_model()
    
    def _load_local_model(self):
        """Load local Whisper model."""
        try:
            import whisper
            print(f"Loading Whisper model: {self.model}")
            self.whisper_model = whisper.load_model(self.model)
            print(f"✓ Model loaded")
        except ImportError:
            raise ImportError(
                "Whisper not installed. Run: pip install openai-whisper"
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load Whisper model: {e}")
    
    def transcribe(self, audio_path: Union[str, Path], 
                   output_path: Optional[Union[str, Path]] = None) -> Dict:
        """
        Transcribe audio file.
        
        Args:
            audio_path: Path to audio file (mp3, wav, m4a, etc.)
            output_path: Optional path to save transcript JSON
            
        Returns:
            Dictionary with transcript segments and metadata
        """
        audio_path = Path(audio_path)
        
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        print(f"  Transcribing: {audio_path.name}")
        
        if self.use_api:
            result = self._transcribe_api(audio_path)
        else:
            result = self._transcribe_local(audio_path)
        
        # Save transcript if output path provided
        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"  ✓ Transcript saved: {output_path}")
        
        return result
    
    def _transcribe_local(self, audio_path: Path) -> Dict:
        """Transcribe using local Whisper model."""
        if self.whisper_model is None:
            self._load_local_model()
        
        # Set decode options
        decode_options = {
            'language': self.language,
            'task': 'transcribe',
            'fp16': False  # Use FP32 on CPU
        }
        
        # Run transcription
        result = self.whisper_model.transcribe(
            str(audio_path),
            **decode_options
        )
        
        # Format output
        return self._format_result(result, audio_path)
    
    def _transcribe_api(self, audio_path: Path) -> Dict:
        """Transcribe using OpenAI Whisper API."""
        if not self.api_key:
            raise ValueError("OpenAI API key required for API transcription")
        
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)
            
            with open(audio_path, 'rb') as audio_file:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"]
                )
            
            # Convert API response to standard format
            result = {
                'text': transcript.text,
                'segments': [
                    {
                        'id': i,
                        'start': seg.start,
                        'end': seg.end,
                        'text': seg.text.strip()
                    }
                    for i, seg in enumerate(transcript.segments)
                ],
                'language': transcript.language
            }
            
            return self._format_result(result, audio_path)
            
        except Exception as e:
            raise RuntimeError(f"API transcription failed: {e}")
    
    def _format_result(self, result: Dict, audio_path: Path) -> Dict:
        """Format transcription result with metadata."""
        formatted = {
            'audio_file': str(audio_path),
            'full_text': result.get('text', ''),
            'language': result.get('language', 'unknown'),
            'duration': self._get_audio_duration(audio_path),
            'model': 'whisper-1' if self.use_api else f'whisper-{self.model}',
            'segments': []
        }
        
        # Process segments with word-level timestamps if available
        segments = result.get('segments', [])
        for seg in segments:
            formatted['segments'].append({
                'id': seg.get('id', len(formatted['segments'])),
                'start': seg.get('start', 0.0),
                'end': seg.get('end', 0.0),
                'text': seg.get('text', '').strip(),
                'confidence': seg.get('avg_logprob', 0.0)
            })
        
        return formatted
    
    def _get_audio_duration(self, audio_path: Path) -> float:
        """Get audio file duration using ffprobe."""
        try:
            import subprocess
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                str(audio_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return float(result.stdout.strip())
        except:
            pass
        return 0.0
    
    def search_transcript(self, transcript: Dict, phrases: List[str],
                          fuzzy_threshold: float = 0.8) -> List[Dict]:
        """
        Search transcript for specific phrases.
        
        Args:
            transcript: Transcript dictionary from transcribe()
            phrases: List of phrases to search for
            fuzzy_threshold: Minimum similarity for fuzzy matching (0-1)
            
        Returns:
            List of matches with segment info and timestamps
        """
        matches = []
        
        try:
            from difflib import SequenceMatcher
            
            for phrase in phrases:
                phrase_lower = phrase.lower()
                
                for segment in transcript.get('segments', []):
                    seg_text = segment.get('text', '').lower()
                    
                    # Exact match
                    if phrase_lower in seg_text:
                        matches.append({
                            'phrase': phrase,
                            'segment_id': segment['id'],
                            'start': segment['start'],
                            'end': segment['end'],
                            'text': segment['text'],
                            'match_type': 'exact',
                            'confidence': 1.0
                        })
                    else:
                        # Fuzzy match
                        similarity = SequenceMatcher(None, phrase_lower, seg_text).ratio()
                        if similarity >= fuzzy_threshold:
                            matches.append({
                                'phrase': phrase,
                                'segment_id': segment['id'],
                                'start': segment['start'],
                                'end': segment['end'],
                                'text': segment['text'],
                                'match_type': 'fuzzy',
                                'confidence': similarity
                            })
            
            # Sort by confidence
            matches.sort(key=lambda x: x['confidence'], reverse=True)
            return matches
            
        except Exception as e:
            print(f"  Warning: Search error: {e}")
            return []


def transcribe_audio(audio_path: str, output_path: Optional[str] = None,
                     model: str = "base", language: str = "auto") -> Dict:
    """
    Convenience function for single-file transcription.
    
    Example:
        result = transcribe_audio("video.mp3", "transcript.json")
    """
    transcriber = AudioTranscriber(model=model, language=language)
    return transcriber.transcribe(audio_path, output_path)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python transcriber.py <audio_file> [output.json]")
        print("Example: python transcriber.py video.mp3 transcript.json")
        sys.exit(1)
    
    audio_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None
    
    print(f"Transcribing: {audio_file}")
    result = transcribe_audio(audio_file, output_file)
    
    print(f"\nTranscription complete!")
    print(f"Language: {result['language']}")
    print(f"Duration: {result['duration']:.1f}s")
    print(f"Segments: {len(result['segments'])}")
    print(f"\nFirst 200 chars: {result['full_text'][:200]}...")
