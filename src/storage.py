"""Storage management with dynamic directory creation."""
import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
import tempfile
import shutil

logger = logging.getLogger(__name__)

class Storage:
    def __init__(self, data_dir: str = "/app/data"):
        self.data_dir = Path(data_dir)
        # Ensure base data directory exists
        self.data_dir.mkdir(exist_ok=True)
        logger.info(f"Storage initialized with data_dir: {self.data_dir}")

    def get_podcast_dir(self, slug: str) -> Path:
        """Get podcast directory, creating if necessary."""
        podcast_dir = self.data_dir / slug
        podcast_dir.mkdir(exist_ok=True)

        # Ensure episodes directory exists
        episodes_dir = podcast_dir / "episodes"
        episodes_dir.mkdir(exist_ok=True)

        logger.info(f"[{slug}] Podcast directory ready: {podcast_dir}")
        return podcast_dir

    def load_data_json(self, slug: str) -> Dict[str, Any]:
        """Load data.json for a podcast, creating if necessary."""
        podcast_dir = self.get_podcast_dir(slug)
        data_file = podcast_dir / "data.json"

        if data_file.exists():
            try:
                with open(data_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"[{slug}] Loaded data.json with {len(data.get('episodes', {}))} episodes")
                    return data
            except json.JSONDecodeError as e:
                logger.error(f"[{slug}] Invalid data.json, creating new: {e}")

        # Create default structure
        data = {
            "episodes": {},
            "last_checked": None
        }
        self.save_data_json(slug, data)
        return data

    def save_data_json(self, slug: str, data: Dict[str, Any]) -> None:
        """Save data.json atomically."""
        podcast_dir = self.get_podcast_dir(slug)
        data_file = podcast_dir / "data.json"

        # Atomic write: write to temp, then rename
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=podcast_dir, suffix='.tmp') as tmp:
            json.dump(data, tmp, indent=2)
            tmp_path = tmp.name

        shutil.move(tmp_path, data_file)
        logger.info(f"[{slug}] Saved data.json")

    def get_episode_path(self, slug: str, episode_id: str, extension: str = ".mp3") -> Path:
        """Get path for episode file."""
        podcast_dir = self.get_podcast_dir(slug)
        return podcast_dir / "episodes" / f"{episode_id}{extension}"

    def save_rss(self, slug: str, content: str) -> None:
        """Save modified RSS feed."""
        podcast_dir = self.get_podcast_dir(slug)
        rss_file = podcast_dir / "modified-rss.xml"

        # Atomic write
        with tempfile.NamedTemporaryFile(mode='w', delete=False, dir=podcast_dir, suffix='.tmp') as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        shutil.move(tmp_path, rss_file)
        logger.info(f"[{slug}] Saved modified RSS feed")

    def get_rss(self, slug: str) -> Optional[str]:
        """Get cached RSS feed."""
        podcast_dir = self.get_podcast_dir(slug)
        rss_file = podcast_dir / "modified-rss.xml"

        if rss_file.exists():
            with open(rss_file, 'r') as f:
                return f.read()
        return None

    def save_transcript(self, slug: str, episode_id: str, transcript: str) -> None:
        """Save episode transcript."""
        path = self.get_episode_path(slug, episode_id, "-transcript.txt")
        with open(path, 'w') as f:
            f.write(transcript)
        logger.info(f"[{slug}:{episode_id}] Saved transcript")

    def save_ads_json(self, slug: str, episode_id: str, ads_data: Any) -> None:
        """Save Claude's ad detection response."""
        path = self.get_episode_path(slug, episode_id, "-ads.json")
        with open(path, 'w') as f:
            json.dump(ads_data, f, indent=2)
        logger.info(f"[{slug}:{episode_id}] Saved ads detection data")