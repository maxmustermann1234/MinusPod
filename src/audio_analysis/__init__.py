"""
Audio analysis module for podcast ad detection.

Provides volume, music bed, and speaker diarization analysis to enhance
Claude-based ad detection with audio-level signals.
"""

import logging

logger = logging.getLogger('podcast.audio_analysis')

# Check for optional dependencies
LIBROSA_AVAILABLE = False
PYANNOTE_AVAILABLE = False

try:
    import librosa
    LIBROSA_AVAILABLE = True
except ImportError:
    logger.debug("librosa not available - music detection disabled")

try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    logger.debug("pyannote.audio not available - speaker diarization disabled")

# Export main classes
from .base import AudioSegmentSignal, AudioAnalysisResult
from .audio_analyzer import AudioAnalyzer

__all__ = [
    'AudioAnalyzer',
    'AudioSegmentSignal',
    'AudioAnalysisResult',
    'LIBROSA_AVAILABLE',
    'PYANNOTE_AVAILABLE',
]
