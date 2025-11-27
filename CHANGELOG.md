# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.5] - 2025-11-27

### Fixed
- Claude API 404 error - corrected model IDs (claude-sonnet-4-5-20250929, not 20250514)
- Duplicate log entries - clear existing handlers before adding new ones
- Feed slugs defaulting to "rss" - now generates slug from podcast title

### Changed
- Slug generation now fetches RSS feed to get podcast name (e.g., "tosh-show" instead of "rss")
- Added Claude Opus 4.5 to available models list
- Model validation now checks against VALID_MODELS list

---

## [0.1.3] - 2025-11-27

### Fixed
- Claude API 404 error - corrected invalid model IDs in DEFAULT_MODEL and fallback models
- Empty assets folder in Docker image - assets/replace.mp3 now properly included

### Changed
- Default model changed from invalid claude-opus-4-5-20250929 to claude-sonnet-4-5-20250514
- Updated fallback model list with correct model IDs:
  - claude-sonnet-4-5-20250514 (Claude Sonnet 4.5)
  - claude-sonnet-4-20250514 (Claude Sonnet 4)
  - claude-opus-4-1-20250414 (Claude Opus 4.1)
  - claude-3-5-sonnet-20241022 (Claude 3.5 Sonnet)

### Note
- Users must re-select model from Settings UI after update to save a valid model ID to database

---

## [0.1.2] - 2025-11-26

### Fixed
- Version display showing "unknown" - fixed Python import path for version.py
- GET /api/v1/feeds/{slug} returning 405 - added missing GET endpoint
- openapi.yaml 404 - added COPY to Dockerfile
- Copy URL showing "undefined" - updated frontend types to use camelCase (feedUrl, sourceUrl, etc.)
- Request logging disabled - changed werkzeug log level from WARNING to INFO

### Changed
- Removed User Prompt Template from Settings UI (unnecessary - system prompt contains all instructions)
- Added API Documentation link to Settings page

### Technical
- Docker image: ttlequals0/podcast-server:0.1.2

---

## [0.1.0] - 2025-11-26

### Added
- Web-based management UI (React + Vite) served at /ui/
- SQLite database for configuration and episode metadata storage
- REST API for feed management, settings, and system status
- Automatic migration from JSON files to SQLite on first startup
- Podcast artwork caching during feed refresh
- Configurable ad detection system prompt and Claude model via web UI
- Episode retention with automatic and manual cleanup
- Structured logging for all operations
- Dark/Light theme support in web UI
- Feed management: add, delete, refresh single or all feeds
- Copy-to-clipboard for feed URLs
- System status and statistics endpoint
- Cloudflared tunnel service in docker-compose for secure remote access
- OpenAPI documentation (openapi.yaml)

### Changed
- Data storage migrated from JSON files to SQLite database
- Ad detection prompts now stored in database and editable via UI
- Claude model is now configurable via API/UI
- Removed config/ directory dependency (feeds now managed via UI/API)
- Improved logging with categorized loggers and structured format

### Technical
- Added flask-cors for development CORS support
- Multi-stage Docker build for frontend assets
- Added RETENTION_PERIOD environment variable for episode cleanup
- Docker image: ttlequals0/podcast-server:0.1.0
