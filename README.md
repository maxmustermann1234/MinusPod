# Podcast Ad Removal Server

Automatically removes advertisements from podcast episodes using AI-powered detection and audio processing.

## Features

- Fetches and caches RSS feeds
- Just-In-Time (JIT) audio processing
- Transcribes episodes using Faster Whisper
- Detects ads using Claude API
- Removes ads and replaces with 1-second beep
- Serves modified RSS feeds and processed audio files

## Setup

1. **Add your beep audio file:**
   - Place a 1-second beep/tone audio file named `replace.mp3` in the `assets/` directory

2. **Configure your API key:**
   ```bash
   cp .env.example .env
   # Edit .env and add your ANTHROPIC_API_KEY
   ```

3. **Configure podcast feeds:**
   - Edit `config/feeds.json` to add your podcast RSS feeds
   - Example configuration is already included for universe1

4. **Build and run with Docker:**
   ```bash
   docker-compose up --build
   ```

## Usage

Once running, your modified podcast RSS feeds will be available at:
- `http://localhost:8000/universe1` (or whatever slug you configured)

Add this URL to your podcast app. When you play an episode:
1. First request triggers processing (may take a few minutes)
2. Subsequent requests serve cached processed files
3. Failed processing falls back to original audio

## Directory Structure

```
data/                    # Auto-created, stores all processed data
├── universe1/          # One directory per podcast
│   ├── data.json       # Episode tracking metadata
│   ├── modified-rss.xml # Cached modified RSS feed
│   └── episodes/       # Processed episodes
│       ├── {id}.mp3
│       ├── {id}-transcript.txt
│       └── {id}-ads.json
```

## Monitoring

Check logs with:
```bash
docker-compose logs -f
```

Logs show:
- RSS feed refresh cycles (every 15 minutes)
- Episode processing stages
- Cache hits/misses
- Processing times and statistics

## Notes

- First episode processing can take 5-10 minutes depending on length
- Transcription requires significant CPU/memory
- Failed episodes won't retry (serves original)
- All data persists in `./data` directory