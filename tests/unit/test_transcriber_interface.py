"""Unit tests for Transcriber interface stability."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from transcriber import Transcriber


def test_transcriber_exposes_callable_transcribe_method():
    """Transcriber instances must expose a callable `transcribe` method."""
    transcriber = Transcriber()
    assert hasattr(transcriber, 'transcribe')
    assert callable(transcriber.transcribe)
