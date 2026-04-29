# Server Startup Guide

Run the Checklist App with both FastAPI and Celery services.

## Quick Start

### Option 1: Python Script (Recommended)
```bash
# Activate virtual environment
source venv/bin/activate

# Run server with Celery
python start_server.py
```

### Option 2: Shell Script
```bash
# Activate virtual environment
source venv/bin/activate

# Run server with Celery
./start_server.sh
```

## Services Started

1. **FastAPI Server** - http://localhost:8000
   - Main API with auto-reload
   - API docs: http://localhost:8000/docs

2. **Celery Worker** (Background)
   - Processes async tasks
   - Uses Redis as broker

## Prerequisites

- Redis server running on localhost:6379
- Virtual environment activated

## Start Redis (if not running)
```bash
redis-server
```

## Stop Services
Press `Ctrl+C` to stop all services gracefully.

## Troubleshooting

**Redis Error**: Start Redis with `redis-server`
**Port 8000 in use**: Kill process with `lsof -ti:8000 | xargs kill -9`
**Celery Command Error**: The scripts now use correct Celery 5.x syntax: `celery -A app.celery_app worker`
