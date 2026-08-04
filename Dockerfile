FROM python:3.13-slim

LABEL maintainer="JARVIS Team"
LABEL description="JARVIS AI Desktop Assistant API Server"

# System dependencies
RUN apt-get update && apt-get install -y \
    # Audio
    portaudio19-dev \
    alsa-utils \
    ffmpeg \
    espeak-ng \
    # X11 for system control
    xdotool \
    xclip \
    scrot \
    # Utilities
    libnotify-bin \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source code
COPY . .

# Create data directory
RUN mkdir -p data logs

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV APP_ENV=production

EXPOSE 8765

# Health check
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8765/health || exit 1

CMD ["python", "main.py", "serve", "--host", "0.0.0.0", "--port", "8765"]
