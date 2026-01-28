"""
Processing Queue - Singleton class to prevent concurrent episode processing.

Only one episode can be processed at a time to prevent OOM issues from
multiple Whisper transcriptions and FFMPEG processes running simultaneously.
"""
import logging
import threading
import time
from typing import Optional, Tuple

# Must match StatusService.MAX_JOB_DURATION for consistency
MAX_JOB_DURATION = 1800  # 30 minutes - auto-clear stuck jobs

logger = logging.getLogger('podcast.processing_queue')


class ProcessingQueue:
    """Single-episode processing queue to prevent OOM from concurrent processing."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._processing_lock = threading.Lock()
                    cls._instance._current_episode: Optional[Tuple[str, str]] = None
                    cls._instance._acquired_at: Optional[float] = None
        return cls._instance

    def _is_stale(self) -> bool:
        """Check if current job has exceeded max duration."""
        if self._current_episode is None or self._acquired_at is None:
            return False
        return (time.time() - self._acquired_at) > MAX_JOB_DURATION

    def _force_clear_stale(self) -> bool:
        """Force-clear stale state. Returns True if state was cleared.

        This handles cases where a worker's processing thread hangs or is
        SIGKILL'd - the lock may still be held by a dead thread, and
        _current_episode will never be cleared by release().
        """
        if not self._is_stale():
            return False

        elapsed = time.time() - self._acquired_at
        slug, episode_id = self._current_episode
        logger.warning(
            f"Auto-clearing stale ProcessingQueue state: {slug}:{episode_id} "
            f"(running {elapsed/60:.0f} min, max {MAX_JOB_DURATION/60:.0f} min)"
        )

        self._current_episode = None
        self._acquired_at = None

        # Try to release lock if possible (may fail if held by other thread)
        try:
            self._processing_lock.release()
        except RuntimeError:
            pass  # Lock wasn't held by this thread

        return True

    def _sync_with_status_service(self):
        """Check if StatusService agrees queue is busy.

        StatusService uses file-based storage shared across all workers,
        making it the cross-worker truth source. If StatusService says
        no job is running but ProcessingQueue thinks one is, trust
        StatusService and clear our state.
        """
        try:
            from status_service import StatusService
            status = StatusService()
            current_job = status.get_status().current_job
            if current_job is None and self._current_episode is not None:
                # StatusService says free but ProcessingQueue says busy
                logger.warning(
                    f"ProcessingQueue/StatusService mismatch: clearing stale state "
                    f"for {self._current_episode[0]}:{self._current_episode[1]}"
                )
                self._current_episode = None
                self._acquired_at = None
                try:
                    self._processing_lock.release()
                except RuntimeError:
                    pass
        except Exception:
            pass  # Don't fail on sync check

    def acquire(self, slug: str, episode_id: str, timeout: float = 0) -> bool:
        """
        Try to acquire processing lock for an episode.

        Args:
            slug: Podcast slug
            episode_id: Episode ID
            timeout: How long to wait for lock (0 = non-blocking)

        Returns:
            True if lock acquired, False if busy
        """
        # Clear stale state before attempting to acquire
        self._force_clear_stale()
        self._sync_with_status_service()

        acquired = self._processing_lock.acquire(blocking=timeout > 0, timeout=timeout if timeout > 0 else -1)
        if acquired:
            self._current_episode = (slug, episode_id)
            self._acquired_at = time.time()
        return acquired

    def release(self):
        """Release processing lock."""
        try:
            self._processing_lock.release()
        except RuntimeError:
            pass  # Lock wasn't held
        self._current_episode = None
        self._acquired_at = None

    def get_current(self) -> Optional[Tuple[str, str]]:
        """Get currently processing episode (slug, episode_id) or None.

        Performs staleness check before returning.
        """
        self._force_clear_stale()
        return self._current_episode

    def is_processing(self, slug: str, episode_id: str) -> bool:
        """Check if specific episode is currently being processed.

        Performs staleness check before returning.
        """
        self._force_clear_stale()
        current = self._current_episode
        return current is not None and current == (slug, episode_id)

    def is_busy(self) -> bool:
        """Check if any episode is currently being processed.

        Performs staleness check and sync with StatusService before
        returning to prevent false positives from dead workers.
        """
        self._force_clear_stale()
        self._sync_with_status_service()
        return self._current_episode is not None
