"""
Volume/loudness analysis for detecting dynamically inserted ads.

Key insight: Dynamically inserted ads are often mastered louder and with
more compression than host content, causing noticeable volume changes.
"""

import subprocess
import json
import logging
from typing import List, Tuple, Optional
import os

from .base import AudioSegmentSignal, LoudnessFrame, SignalType

logger = logging.getLogger('podcast.audio_analysis.volume')


class VolumeAnalyzer:
    """
    Analyzes volume/loudness patterns to detect ad transitions.

    Uses ffmpeg's loudnorm filter to measure integrated loudness (LUFS)
    and detect regions where volume differs significantly from baseline.
    """

    def __init__(
        self,
        frame_duration: float = 5.0,
        anomaly_threshold_db: float = 3.0,
        min_anomaly_duration: float = 15.0
    ):
        """
        Initialize the volume analyzer.

        Args:
            frame_duration: Analysis window size in seconds
            anomaly_threshold_db: dB deviation from baseline to flag as anomaly
            min_anomaly_duration: Minimum duration to report as anomaly
        """
        self.frame_duration = frame_duration
        self.anomaly_threshold_db = anomaly_threshold_db
        self.min_anomaly_duration = min_anomaly_duration

    def analyze(self, audio_path: str) -> Tuple[List[AudioSegmentSignal], Optional[float]]:
        """
        Analyze audio for volume anomalies.

        Args:
            audio_path: Path to the audio file

        Returns:
            Tuple of (list of volume anomaly signals, baseline loudness in LUFS)
        """
        if not os.path.exists(audio_path):
            logger.error(f"Audio file not found: {audio_path}")
            return [], None

        # Get audio duration
        duration = self._get_duration(audio_path)
        if duration is None or duration < self.frame_duration:
            logger.warning(f"Audio too short for volume analysis: {duration}s")
            return [], None

        logger.info(f"Analyzing volume for {duration:.1f}s audio ({duration/60:.1f} min)")

        # Measure loudness in frames
        frames = self._measure_loudness_frames(audio_path, duration)
        if not frames:
            logger.warning("No loudness frames extracted")
            return [], None

        # Calculate baseline
        loudness_values = [f.loudness_lufs for f in frames if f.loudness_lufs > -70]
        if not loudness_values:
            logger.warning("No valid loudness measurements")
            return [], None

        # Use median as baseline (robust to outliers)
        loudness_values.sort()
        mid = len(loudness_values) // 2
        baseline = loudness_values[mid]

        logger.info(f"Loudness baseline: {baseline:.1f} LUFS")

        # Find anomalies
        anomalies = self._find_anomalies(frames, baseline)

        logger.info(f"Found {len(anomalies)} volume anomalies")
        return anomalies, baseline

    def _get_duration(self, audio_path: str) -> Optional[float]:
        """Get audio duration using ffprobe."""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'json',
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                logger.warning(f"ffprobe failed: {result.stderr}")
                return None
            data = json.loads(result.stdout)
            return float(data['format']['duration'])
        except Exception as e:
            logger.error(f"Failed to get duration: {e}")
            return None

    def _measure_loudness_frames(
        self,
        audio_path: str,
        total_duration: float
    ) -> List[LoudnessFrame]:
        """Measure loudness for each frame of the audio."""
        frames = []
        current_time = 0.0

        while current_time < total_duration:
            frame_duration = min(self.frame_duration, total_duration - current_time)
            if frame_duration < 1.0:
                break

            loudness, peak = self._measure_frame(audio_path, current_time, frame_duration)

            frames.append(LoudnessFrame(
                start=current_time,
                end=current_time + frame_duration,
                loudness_lufs=loudness,
                peak_dbfs=peak
            ))

            current_time += self.frame_duration

        return frames

    def _measure_frame(
        self,
        audio_path: str,
        start: float,
        duration: float
    ) -> Tuple[float, float]:
        """Measure loudness for a specific time range using ffmpeg loudnorm."""
        try:
            cmd = [
                'ffmpeg', '-v', 'quiet',
                '-ss', str(start),
                '-t', str(duration),
                '-i', audio_path,
                '-af', 'loudnorm=print_format=json',
                '-f', 'null', '-'
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )

            # Parse JSON from stderr (loudnorm outputs there)
            stderr = result.stderr
            json_start = stderr.rfind('{')
            json_end = stderr.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                data = json.loads(stderr[json_start:json_end])
                loudness = float(data.get('input_i', -24))
                peak = float(data.get('input_tp', -1))
                return loudness, peak

        except subprocess.TimeoutExpired:
            logger.warning(f"Loudness measurement timeout at {start:.1f}s")
        except json.JSONDecodeError:
            pass
        except Exception as e:
            logger.debug(f"Loudness measurement failed at {start:.1f}s: {e}")

        # Return default values on failure
        return -24.0, -1.0

    def _find_anomalies(
        self,
        frames: List[LoudnessFrame],
        baseline: float
    ) -> List[AudioSegmentSignal]:
        """Find regions where volume deviates significantly from baseline."""
        anomalies = []
        in_anomaly = False
        anomaly_start = 0.0
        anomaly_type = ""
        deviations = []

        for frame in frames:
            deviation = frame.loudness_lufs - baseline

            if abs(deviation) > self.anomaly_threshold_db:
                if not in_anomaly:
                    # Start new anomaly
                    in_anomaly = True
                    anomaly_start = frame.start
                    anomaly_type = "increase" if deviation > 0 else "decrease"
                    deviations = []
                deviations.append(abs(deviation))
            else:
                if in_anomaly:
                    # End current anomaly
                    anomaly_end = frame.start
                    duration = anomaly_end - anomaly_start

                    if duration >= self.min_anomaly_duration:
                        avg_deviation = sum(deviations) / len(deviations)
                        # Confidence based on deviation magnitude
                        confidence = min(0.5 + (avg_deviation / 10), 0.95)

                        signal_type = (
                            SignalType.VOLUME_INCREASE.value
                            if anomaly_type == "increase"
                            else SignalType.VOLUME_DECREASE.value
                        )

                        anomalies.append(AudioSegmentSignal(
                            start=anomaly_start,
                            end=anomaly_end,
                            signal_type=signal_type,
                            confidence=confidence,
                            details={
                                'deviation_db': round(avg_deviation, 1),
                                'baseline_lufs': round(baseline, 1),
                                'direction': anomaly_type
                            }
                        ))

                    in_anomaly = False

        # Handle anomaly at end of audio
        if in_anomaly and frames:
            anomaly_end = frames[-1].end
            duration = anomaly_end - anomaly_start

            if duration >= self.min_anomaly_duration:
                avg_deviation = sum(deviations) / len(deviations)
                confidence = min(0.5 + (avg_deviation / 10), 0.95)

                signal_type = (
                    SignalType.VOLUME_INCREASE.value
                    if anomaly_type == "increase"
                    else SignalType.VOLUME_DECREASE.value
                )

                anomalies.append(AudioSegmentSignal(
                    start=anomaly_start,
                    end=anomaly_end,
                    signal_type=signal_type,
                    confidence=confidence,
                    details={
                        'deviation_db': round(avg_deviation, 1),
                        'baseline_lufs': round(baseline, 1),
                        'direction': anomaly_type
                    }
                ))

        return anomalies
