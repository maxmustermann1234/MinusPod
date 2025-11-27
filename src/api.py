"""REST API for podcast server web UI."""
import logging
import os
import time
from datetime import datetime
from flask import Blueprint, jsonify, request, send_file, Response
from functools import wraps

logger = logging.getLogger('podcast.api')

# Track server start time for uptime calculation
_start_time = time.time()

api = Blueprint('api', __name__, url_prefix='/api/v1')


def get_storage():
    """Get storage instance."""
    from storage import Storage
    return Storage()


def get_database():
    """Get database instance."""
    from database import Database
    return Database()


def log_request(f):
    """Decorator to log API requests."""
    @wraps(f)
    def decorated(*args, **kwargs):
        logger.info(f"API {request.method} {request.path}")
        try:
            result = f(*args, **kwargs)
            return result
        except Exception as e:
            logger.error(f"API error: {request.method} {request.path} - {e}")
            raise
    return decorated


def json_response(data, status=200):
    """Create JSON response with proper headers."""
    response = jsonify(data)
    response.status_code = status
    return response


def error_response(message, status=400, details=None):
    """Create error response."""
    data = {'error': message, 'status': status}
    if details:
        data['details'] = details
    return json_response(data, status)


# ========== Feed Endpoints ==========

@api.route('/feeds', methods=['GET'])
@log_request
def list_feeds():
    """List all podcast feeds with metadata."""
    db = get_database()
    storage = get_storage()

    podcasts = db.get_all_podcasts()

    feeds = []
    for podcast in podcasts:
        # Build feed URL
        base_url = os.environ.get('BASE_URL', 'http://localhost:8000')
        feed_url = f"{base_url}/{podcast['slug']}"

        feeds.append({
            'slug': podcast['slug'],
            'title': podcast['title'] or podcast['slug'],
            'sourceUrl': podcast['source_url'],
            'feedUrl': feed_url,
            'artworkUrl': f"/api/v1/feeds/{podcast['slug']}/artwork" if podcast.get('artwork_cached') else podcast.get('artwork_url'),
            'episodeCount': podcast.get('episode_count', 0),
            'processedCount': podcast.get('processed_count', 0),
            'lastRefreshed': podcast.get('last_checked_at'),
            'createdAt': podcast.get('created_at')
        })

    return json_response({'feeds': feeds})


@api.route('/feeds', methods=['POST'])
@log_request
def add_feed():
    """Add a new podcast feed."""
    data = request.get_json()

    if not data or 'sourceUrl' not in data:
        return error_response('sourceUrl is required', 400)

    source_url = data['sourceUrl'].strip()
    if not source_url:
        return error_response('sourceUrl cannot be empty', 400)

    # Generate slug from URL or use provided slug
    slug = data.get('slug', '').strip()
    if not slug:
        # Generate slug from URL
        from slugify import slugify as make_slug
        from urllib.parse import urlparse

        parsed = urlparse(source_url)
        # Use path or hostname as base for slug
        slug_base = parsed.path.strip('/').split('/')[-1] or parsed.netloc
        slug_base = slug_base.replace('.xml', '').replace('.rss', '')
        slug = make_slug(slug_base)

    if not slug:
        return error_response('Could not generate valid slug', 400)

    db = get_database()

    # Check if slug already exists
    existing = db.get_podcast_by_slug(slug)
    if existing:
        return error_response(f'Feed with slug "{slug}" already exists', 409)

    # Create podcast
    try:
        podcast_id = db.create_podcast(slug, source_url)
        logger.info(f"Created new feed: {slug} -> {source_url}")

        # Trigger initial refresh in background
        try:
            from main import refresh_rss_feed
            refresh_rss_feed(slug, source_url)
        except Exception as e:
            logger.warning(f"Initial refresh failed for {slug}: {e}")

        base_url = os.environ.get('BASE_URL', 'http://localhost:8000')

        return json_response({
            'slug': slug,
            'sourceUrl': source_url,
            'feedUrl': f"{base_url}/{slug}",
            'message': 'Feed added successfully'
        }, 201)

    except Exception as e:
        logger.error(f"Failed to add feed: {e}")
        return error_response(f'Failed to add feed: {str(e)}', 500)


@api.route('/feeds/<slug>', methods=['GET'])
@log_request
def get_feed(slug):
    """Get a single podcast feed by slug."""
    db = get_database()

    podcast = db.get_podcast_by_slug(slug)
    if not podcast:
        return error_response('Feed not found', 404)

    base_url = os.environ.get('BASE_URL', 'http://localhost:8000')
    feed_url = f"{base_url}/{slug}"

    return json_response({
        'slug': podcast['slug'],
        'title': podcast['title'] or podcast['slug'],
        'sourceUrl': podcast['source_url'],
        'feedUrl': feed_url,
        'artworkUrl': f"/api/v1/feeds/{podcast['slug']}/artwork" if podcast.get('artwork_cached') else podcast.get('artwork_url'),
        'episodeCount': podcast.get('episode_count', 0),
        'processedCount': podcast.get('processed_count', 0),
        'lastRefreshed': podcast.get('last_checked_at'),
        'createdAt': podcast.get('created_at')
    })


@api.route('/feeds/<slug>', methods=['DELETE'])
@log_request
def delete_feed(slug):
    """Delete a podcast feed and all associated data."""
    db = get_database()
    storage = get_storage()

    podcast = db.get_podcast_by_slug(slug)
    if not podcast:
        return error_response('Feed not found', 404)

    try:
        # Delete from database (cascade deletes episodes)
        db.delete_podcast(slug)

        # Delete files
        storage.cleanup_podcast_dir(slug)

        logger.info(f"Deleted feed: {slug}")
        return json_response({'message': 'Feed deleted', 'slug': slug})

    except Exception as e:
        logger.error(f"Failed to delete feed {slug}: {e}")
        return error_response(f'Failed to delete feed: {str(e)}', 500)


@api.route('/feeds/<slug>/refresh', methods=['POST'])
@log_request
def refresh_feed(slug):
    """Refresh a single podcast feed."""
    db = get_database()

    podcast = db.get_podcast_by_slug(slug)
    if not podcast:
        return error_response('Feed not found', 404)

    if not podcast.get('source_url'):
        return error_response('Feed has no source URL', 400)

    try:
        from main import refresh_rss_feed
        refresh_rss_feed(slug, podcast['source_url'])

        # Get updated info
        podcast = db.get_podcast_by_slug(slug)
        episodes, total = db.get_episodes(slug)

        logger.info(f"Refreshed feed: {slug}")
        return json_response({
            'slug': slug,
            'message': 'Feed refreshed',
            'episodeCount': total,
            'lastRefreshed': podcast.get('last_checked_at')
        })

    except Exception as e:
        logger.error(f"Failed to refresh feed {slug}: {e}")
        return error_response(f'Failed to refresh feed: {str(e)}', 500)


@api.route('/feeds/refresh', methods=['POST'])
@log_request
def refresh_all_feeds():
    """Refresh all podcast feeds."""
    try:
        from main import refresh_all_feeds as do_refresh
        do_refresh()

        db = get_database()
        podcasts = db.get_all_podcasts()

        logger.info("Refreshed all feeds")
        return json_response({
            'message': 'All feeds refreshed',
            'feedCount': len(podcasts)
        })

    except Exception as e:
        logger.error(f"Failed to refresh all feeds: {e}")
        return error_response(f'Failed to refresh feeds: {str(e)}', 500)


@api.route('/feeds/<slug>/artwork', methods=['GET'])
@log_request
def get_artwork(slug):
    """Get cached artwork for a podcast."""
    storage = get_storage()

    artwork = storage.get_artwork(slug)
    if not artwork:
        # Try to get from database and download
        db = get_database()
        podcast = db.get_podcast_by_slug(slug)
        if podcast and podcast.get('artwork_url'):
            storage.download_artwork(slug, podcast['artwork_url'])
            artwork = storage.get_artwork(slug)

    if not artwork:
        return error_response('Artwork not found', 404)

    image_data, content_type = artwork
    return Response(image_data, mimetype=content_type)


# ========== Episode Endpoints ==========

@api.route('/feeds/<slug>/episodes', methods=['GET'])
@log_request
def list_episodes(slug):
    """List episodes for a podcast."""
    db = get_database()

    podcast = db.get_podcast_by_slug(slug)
    if not podcast:
        return error_response('Feed not found', 404)

    # Get query params
    status = request.args.get('status', 'all')
    limit = min(int(request.args.get('limit', 50)), 200)
    offset = int(request.args.get('offset', 0))

    episodes, total = db.get_episodes(slug, status=status, limit=limit, offset=offset)

    episode_list = []
    for ep in episodes:
        time_saved = 0
        if ep.get('original_duration') and ep.get('new_duration'):
            time_saved = ep['original_duration'] - ep['new_duration']

        episode_list.append({
            'episodeId': ep['episode_id'],
            'title': ep['title'],
            'status': ep['status'],
            'createdAt': ep['created_at'],
            'processedAt': ep['processed_at'],
            'originalDuration': ep['original_duration'],
            'newDuration': ep['new_duration'],
            'adsRemoved': ep['ads_removed'],
            'timeSaved': time_saved,
            'error': ep.get('error_message')
        })

    return json_response({
        'episodes': episode_list,
        'total': total,
        'limit': limit,
        'offset': offset
    })


@api.route('/feeds/<slug>/episodes/<episode_id>', methods=['GET'])
@log_request
def get_episode(slug, episode_id):
    """Get detailed episode information including transcript and ad markers."""
    db = get_database()

    episode = db.get_episode(slug, episode_id)
    if not episode:
        return error_response('Episode not found', 404)

    base_url = os.environ.get('BASE_URL', 'http://localhost:8000')

    # Parse ad markers if present
    ad_markers = []
    if episode.get('ad_markers_json'):
        try:
            import json
            ad_markers = json.loads(episode['ad_markers_json'])
        except:
            pass

    time_saved = 0
    if episode.get('original_duration') and episode.get('new_duration'):
        time_saved = episode['original_duration'] - episode['new_duration']

    return json_response({
        'episodeId': episode['episode_id'],
        'title': episode['title'],
        'status': episode['status'],
        'originalUrl': episode['original_url'],
        'processedUrl': f"{base_url}/episodes/{slug}/{episode_id}.mp3",
        'createdAt': episode['created_at'],
        'processedAt': episode['processed_at'],
        'originalDuration': episode['original_duration'],
        'newDuration': episode['new_duration'],
        'adsRemoved': episode['ads_removed'],
        'timeSaved': time_saved,
        'adMarkers': ad_markers,
        'transcriptAvailable': bool(episode.get('transcript_text')),
        'error': episode.get('error_message')
    })


@api.route('/feeds/<slug>/episodes/<episode_id>/transcript', methods=['GET'])
@log_request
def get_transcript(slug, episode_id):
    """Get episode transcript."""
    storage = get_storage()

    transcript = storage.get_transcript(slug, episode_id)
    if not transcript:
        return error_response('Transcript not found', 404)

    return json_response({
        'episodeId': episode_id,
        'transcript': transcript
    })


# ========== Settings Endpoints ==========

@api.route('/settings', methods=['GET'])
@log_request
def get_settings():
    """Get all settings."""
    db = get_database()
    from database import DEFAULT_SYSTEM_PROMPT, DEFAULT_USER_PROMPT_TEMPLATE
    from ad_detector import AdDetector, DEFAULT_MODEL

    settings = db.get_all_settings()

    # Get current model setting
    current_model = settings.get('claude_model', {}).get('value', DEFAULT_MODEL)

    return json_response({
        'systemPrompt': {
            'value': settings.get('system_prompt', {}).get('value', DEFAULT_SYSTEM_PROMPT),
            'isDefault': settings.get('system_prompt', {}).get('is_default', True)
        },
        'userPromptTemplate': {
            'value': settings.get('user_prompt_template', {}).get('value', DEFAULT_USER_PROMPT_TEMPLATE),
            'isDefault': settings.get('user_prompt_template', {}).get('is_default', True)
        },
        'claudeModel': {
            'value': current_model,
            'isDefault': settings.get('claude_model', {}).get('is_default', True)
        },
        'retentionPeriodMinutes': int(settings.get('retention_period_minutes', {}).get('value', '1440')),
        'defaults': {
            'systemPrompt': DEFAULT_SYSTEM_PROMPT,
            'userPromptTemplate': DEFAULT_USER_PROMPT_TEMPLATE,
            'claudeModel': DEFAULT_MODEL
        }
    })


@api.route('/settings/ad-detection', methods=['PUT'])
@log_request
def update_ad_detection_settings():
    """Update ad detection settings."""
    data = request.get_json()

    if not data:
        return error_response('Request body required', 400)

    db = get_database()

    if 'systemPrompt' in data:
        db.set_setting('system_prompt', data['systemPrompt'], is_default=False)
        logger.info("Updated system prompt")

    if 'userPromptTemplate' in data:
        db.set_setting('user_prompt_template', data['userPromptTemplate'], is_default=False)
        logger.info("Updated user prompt template")

    if 'claudeModel' in data:
        db.set_setting('claude_model', data['claudeModel'], is_default=False)
        logger.info(f"Updated Claude model to: {data['claudeModel']}")

    return json_response({'message': 'Settings updated'})


@api.route('/settings/ad-detection/reset', methods=['POST'])
@log_request
def reset_ad_detection_settings():
    """Reset ad detection settings to defaults."""
    db = get_database()

    db.reset_setting('system_prompt')
    db.reset_setting('user_prompt_template')
    db.reset_setting('claude_model')

    logger.info("Reset ad detection settings to defaults")
    return json_response({'message': 'Settings reset to defaults'})


@api.route('/settings/models', methods=['GET'])
@log_request
def get_available_models():
    """Get list of available Claude models."""
    from ad_detector import AdDetector

    ad_detector = AdDetector()
    models = ad_detector.get_available_models()

    return json_response({'models': models})


# ========== System Endpoints ==========

@api.route('/system/status', methods=['GET'])
@log_request
def get_system_status():
    """Get system status and statistics."""
    db = get_database()
    storage = get_storage()

    stats = db.get_stats()
    storage_stats = storage.get_storage_stats()

    # Get retention setting
    retention = int(db.get_setting('retention_period_minutes') or
                    os.environ.get('RETENTION_PERIOD', '1440'))

    return json_response({
        'status': 'running',
        'version': _get_version(),
        'uptime': int(time.time() - _start_time),
        'feeds': {
            'total': stats['podcast_count']
        },
        'episodes': {
            'total': stats['episode_count'],
            'byStatus': stats['episodes_by_status']
        },
        'storage': {
            'usedMb': storage_stats['total_size_mb'],
            'fileCount': storage_stats['file_count']
        },
        'settings': {
            'retentionPeriodMinutes': retention,
            'whisperModel': os.environ.get('WHISPER_MODEL', 'small'),
            'whisperDevice': os.environ.get('WHISPER_DEVICE', 'cuda'),
            'baseUrl': os.environ.get('BASE_URL', 'http://localhost:8000')
        }
    })


@api.route('/system/cleanup', methods=['POST'])
@log_request
def trigger_cleanup():
    """Trigger manual cleanup of old episodes."""
    db = get_database()

    deleted_count, freed_mb = db.cleanup_old_episodes()

    logger.info(f"Manual cleanup: {deleted_count} episodes, {freed_mb:.1f} MB freed")
    return json_response({
        'message': 'Cleanup complete',
        'episodesRemoved': deleted_count,
        'spaceFreedMb': round(freed_mb, 2)
    })


def _get_version():
    """Get application version."""
    try:
        import sys
        from pathlib import Path
        # Add parent directory to path for version module
        parent_dir = str(Path(__file__).parent.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        from version import __version__
        return __version__
    except ImportError:
        return 'unknown'
