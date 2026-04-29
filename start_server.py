#!/usr/bin/env python3
"""
Startup script to run both FastAPI (uvicorn) and Celery worker together.
This script manages both processes and handles graceful shutdown.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Add the current directory to Python path
sys.path.insert(0, str(Path(__file__).parent))


def run_uvicorn():
    """Run the FastAPI application with uvicorn."""
    cmd = [
        sys.executable, "-m", "uvicorn",
        "app.main:app",
        "--host", "0.0.0.0",
        "--port", "8000",
        "--reload"
    ]
    return subprocess.Popen(cmd, cwd=Path(__file__).parent)


def run_celery_worker():
    """Run the Celery worker."""
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "app.celery_app",
        "worker",
        "--loglevel=info",
        "--concurrency=4"
    ]
    return subprocess.Popen(cmd, cwd=Path(__file__).parent)


def run_celery_beat():
    """Run the Celery beat scheduler (optional)."""
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "app.celery_app",
        "beat",
        "--loglevel=info"
    ]
    return subprocess.Popen(cmd, cwd=Path(__file__).parent)


def main():
    """Main function to run all services."""
    processes = []
    
    print("🚀 Starting Checklist App Services...")
    
    try:
        # Start Celery worker
        print("📋 Starting Celery worker...")
        celery_worker = run_celery_worker()
        processes.append(("Celery Worker", celery_worker))
        
        # Optional: Start Celery beat if you have scheduled tasks
        # Uncomment the following lines if you need periodic tasks
        # print("⏰ Starting Celery beat scheduler...")
        # celery_beat = run_celery_beat()
        # processes.append(("Celery Beat", celery_beat))
        
        # Give Celery a moment to start
        time.sleep(2)
        
        # Start FastAPI server
        print("🌐 Starting FastAPI server...")
        uvicorn_process = run_uvicorn()
        processes.append(("FastAPI", uvicorn_process))
        
        print("✅ All services started successfully!")
        print("📊 Service Status:")
        for name, process in processes:
            status = "🟢 Running" if process.poll() is None else "🔴 Stopped"
            print(f"   {name}: {status}")
        
        print("\n🎯 Services are running. Press Ctrl+C to stop all services.")
        
        # Wait for processes and handle shutdown
        while True:
            # Check if any process has stopped
            for name, process in processes:
                if process.poll() is not None:
                    print(f"⚠️  {name} has stopped with return code {process.returncode}")
                    # Stop all other processes
                    stop_all_processes(processes)
                    sys.exit(1)
            
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Received interrupt signal. Shutting down gracefully...")
        stop_all_processes(processes)
        print("✅ All services stopped.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error starting services: {e}")
        stop_all_processes(processes)
        sys.exit(1)


def stop_all_processes(processes):
    """Stop all running processes gracefully."""
    for name, process in processes:
        if process.poll() is None:  # Process is still running
            print(f"🛑 Stopping {name}...")
            try:
                # Try graceful shutdown first
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                print(f"⚡ Force killing {name}...")
                process.kill()
                process.wait()
            except Exception as e:
                print(f"❌ Error stopping {name}: {e}")


if __name__ == "__main__":
    main()
