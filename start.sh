#!/bin/bash

# Get port from environment or default to 8080
PORT=${PORT:-8080}

echo "Starting Gunicorn on port $PORT"

# Start Gunicorn with proper port
exec gunicorn --bind 0.0.0.0:$PORT --workers 2 --timeout 120 --keep-alive 2 --max-requests 1000 --max-requests-jitter 100 app:app

