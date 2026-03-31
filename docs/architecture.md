# Architecture

## Overview

YouMuDow is a Python desktop application built with PyQt6.

## Components

### App Layer
- `controller.py` - Application controller
- `state.py` - Application state management
- `events.py` - Event handling

### UI Layer
- `window.py` - Main window
- `widgets/` - Custom widgets
- `styles/` - UI styles
- `dialogs/` - Dialog windows

### Services Layer
- `search_service.py` - Search functionality
- `download_service.py` - Download handling
- `metadata_service.py` - Metadata extraction
- `thumbnail_service.py` - Thumbnail handling
- `clipboard_service.py` - Clipboard integration

### Adapters Layer
- `ytdlp_adapter.py` - yt-dlp integration
- `ffmpeg_adapter.py` - FFmpeg integration
- `browser_cookies_adapter.py` - Cookie extraction
- `filesystem_adapter.py` - File system operations

### Domain Layer
- `models.py` - Data models
- `enums.py` - Enumerations
- `validators.py` - Input validation

### Utils Layer
- `formatting.py` - Formatting utilities
- `parsing.py` - Parsing utilities
- `paths.py` - Path utilities
- `errors.py` - Error definitions
- `logging.py` - Logging utilities

### Integrations Layer
- `youtube.py` - YouTube API integration
- `external_tools.py` - External tools integration
