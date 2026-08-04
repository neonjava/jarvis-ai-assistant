#!/usr/bin/env bash
# Start JARVIS API server as a background service
cd PROJECT_ROOT/jarvis
export PYTHONPATH=PROJECT_ROOT/jarvis

# Start Ollama if not running
if ! curl -sf http://localhost:11434/ > /dev/null 2>&1; then
    echo "Starting Ollama..."
    nohup ollama serve > /tmp/ollama.log 2>&1 &
    sleep 3
fi

# Start JARVIS API
echo "Starting JARVIS API..."
exec python3 -m uvicorn api.app:app \
    --host 0.0.0.0 \
    --port 8765 \
    --log-level warning \
    2>&1
