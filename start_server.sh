#!/bin/bash

# Startup script to run both FastAPI and Celery services
# This script manages both processes and handles graceful shutdown

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}[SERVER]${NC} $1"
}

# Function to cleanup processes
cleanup() {
    print_header "Shutting down services..."
    
    # Kill background processes
    if [ ! -z "$CELERY_PID" ]; then
        print_status "Stopping Celery worker (PID: $CELERY_PID)..."
        kill $CELERY_PID 2>/dev/null || true
        wait $CELERY_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$UVICORN_PID" ]; then
        print_status "Stopping FastAPI server (PID: $UVICORN_PID)..."
        kill $UVICORN_PID 2>/dev/null || true
        wait $UVICORN_PID 2>/dev/null || true
    fi
    
    print_status "All services stopped."
    exit 0
}

# Set up signal handlers for graceful shutdown
trap cleanup SIGINT SIGTERM

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    print_warning "Virtual environment not detected. Activating..."
    source venv/bin/activate
fi

# Check if Redis is running (required for Celery)
print_status "Checking Redis connection..."
if ! python -c "import redis; r=redis.Redis(host='localhost', port=6379, decode_responses=True); r.ping()" 2>/dev/null; then
    print_error "Redis is not running. Please start Redis first:"
    echo "  redis-server"
    echo "  or"
    echo "  docker run -d -p 6379:6379 redis:alpine"
    exit 1
fi

print_status "Redis is running."

# Start services
print_header "Starting Checklist App Services..."

# Start Celery worker in background
print_status "Starting Celery worker..."
celery -A app.celery_app worker --loglevel=info --concurrency=4 &
CELERY_PID=$!

# Give Celery a moment to start
sleep 2

# Start FastAPI server in background
print_status "Starting FastAPI server..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
UVICORN_PID=$!

print_status "Services started successfully!"
print_header "Service Status:"
print_status "FastAPI Server: http://localhost:8000"
print_status "API Docs: http://localhost:8000/docs"
print_status "Celery Worker: Running (PID: $CELERY_PID)"
print_status "Redis: Connected"

echo ""
print_header "Press Ctrl+C to stop all services"

# Wait for processes
wait $UVICORN_PID $CELERY_PID
