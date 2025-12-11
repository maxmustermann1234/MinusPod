"""
Base data structures for audio analysis.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum


class SignalType(Enum):
    """Types of audio signals that can be detected."""
    VOLUME_INCREASE = "volume_increase"
    VOLUME_DECREASE = "volume_decrease"
    MUSIC_BED = "music_bed"
    MONOLOGUE = "monologue"
    SPEAKER_CHANGE = "speaker_change"


@dataclass
class AudioSegmentSignal:
    """
    Represents an audio signal detected in a time range.

    Attributes:
        start: Start time in seconds
        end: End time in seconds
        signal_type: Type of signal (volume_change, music_bed, monologue, etc.)
        confidence: Confidence score from 0.0 to 1.0
        details: Additional analyzer-specific data
    """
    start: float
    end: float
    signal_type: str
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Duration of this signal in seconds."""
        return self.end - self.start

    def overlaps(self, other: 'AudioSegmentSignal', tolerance: float = 0) -> bool:
        """Check if this signal overlaps with another."""
        return self.start <= other.end + tolerance and self.end >= other.start - tolerance

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'start': self.start,
            'end': self.end,
            'signal_type': self.signal_type,
            'confidence': self.confidence,
            'duration': self.duration,
            'details': self.details
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AudioSegmentSignal':
        """Create from dictionary."""
        return cls(
            start=data['start'],
            end=data['end'],
            signal_type=data['signal_type'],
            confidence=data['confidence'],
            details=data.get('details', {})
        )


@dataclass
class LoudnessFrame:
    """
    Loudness measurement for a single analysis frame.

    Attributes:
        start: Frame start time in seconds
        end: Frame end time in seconds
        loudness_lufs: Integrated loudness in LUFS
        peak_dbfs: True peak in dBFS
    """
    start: float
    end: float
    loudness_lufs: float
    peak_dbfs: float = 0.0


@dataclass
class SpeakerSegment:
    """
    A segment of audio attributed to a specific speaker.

    Attributes:
        start: Segment start time in seconds
        end: Segment end time in seconds
        speaker: Speaker identifier (e.g., "SPEAKER_00")
    """
    start: float
    end: float
    speaker: str

    @property
    def duration(self) -> float:
        """Duration of this segment in seconds."""
        return self.end - self.start


@dataclass
class ConversationMetrics:
    """
    Overall conversation pattern metrics for an episode.

    Attributes:
        num_speakers: Number of distinct speakers detected
        speaker_balance: 0 = one speaker dominates, 1 = equal participation
        avg_turn_duration: Average duration of each speaking turn
        turn_frequency: Number of speaker changes per minute
        is_conversational: True if this appears to be a multi-speaker conversation
        primary_speaker: ID of the speaker with most airtime (likely host)
    """
    num_speakers: int
    speaker_balance: float
    avg_turn_duration: float
    turn_frequency: float
    is_conversational: bool
    primary_speaker: Optional[str] = None


@dataclass
class AudioAnalysisResult:
    """
    Combined results from all audio analyzers.

    Attributes:
        signals: List of all detected audio signals
        loudness_baseline: Median loudness of the episode in LUFS
        speaker_count: Number of distinct speakers detected
        conversation_metrics: Detailed conversation pattern analysis
        analysis_time_seconds: How long the analysis took
        errors: List of any errors that occurred during analysis
    """
    signals: List[AudioSegmentSignal] = field(default_factory=list)
    loudness_baseline: Optional[float] = None
    speaker_count: Optional[int] = None
    conversation_metrics: Optional[ConversationMetrics] = None
    analysis_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)

    def get_signals_in_range(self, start: float, end: float) -> List[AudioSegmentSignal]:
        """Get all signals that overlap with the given time range."""
        return [
            s for s in self.signals
            if s.start < end and s.end > start
        ]

    def get_signals_by_type(self, signal_type: str) -> List[AudioSegmentSignal]:
        """Get all signals of a specific type."""
        return [s for s in self.signals if s.signal_type == signal_type]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            'signals': [s.to_dict() for s in self.signals],
            'loudness_baseline': self.loudness_baseline,
            'speaker_count': self.speaker_count,
            'analysis_time_seconds': self.analysis_time_seconds,
            'errors': self.errors
        }
        if self.conversation_metrics:
            result['conversation_metrics'] = {
                'num_speakers': self.conversation_metrics.num_speakers,
                'speaker_balance': self.conversation_metrics.speaker_balance,
                'avg_turn_duration': self.conversation_metrics.avg_turn_duration,
                'turn_frequency': self.conversation_metrics.turn_frequency,
                'is_conversational': self.conversation_metrics.is_conversational,
                'primary_speaker': self.conversation_metrics.primary_speaker
            }
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AudioAnalysisResult':
        """Create from dictionary."""
        signals = [AudioSegmentSignal.from_dict(s) for s in data.get('signals', [])]

        conversation_metrics = None
        if 'conversation_metrics' in data and data['conversation_metrics']:
            cm = data['conversation_metrics']
            conversation_metrics = ConversationMetrics(
                num_speakers=cm['num_speakers'],
                speaker_balance=cm['speaker_balance'],
                avg_turn_duration=cm['avg_turn_duration'],
                turn_frequency=cm['turn_frequency'],
                is_conversational=cm['is_conversational'],
                primary_speaker=cm.get('primary_speaker')
            )

        return cls(
            signals=signals,
            loudness_baseline=data.get('loudness_baseline'),
            speaker_count=data.get('speaker_count'),
            conversation_metrics=conversation_metrics,
            analysis_time_seconds=data.get('analysis_time_seconds', 0.0),
            errors=data.get('errors', [])
        )
