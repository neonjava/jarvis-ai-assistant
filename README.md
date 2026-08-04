# JARVIS — AI Desktop Assistant for Fedora Linux

<div align="center">

```
     ██╗ █████╗ ██████╗ ██╗   ██╗██╗███████╗
     ██║██╔══██╗██╔══██╗██║   ██║██║██╔════╝
     ██║███████║██████╔╝██║   ██║██║███████╗
██   ██║██╔══██║██╔══██╗╚██╗ ██╔╝██║╚════██║
╚█████╔╝██║  ██║██║  ██║ ╚████╔╝ ██║███████║
 ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝  ╚═══╝  ╚═╝╚══════╝
```

**Just A Rather Very Intelligent System**

*Your Iron Man-grade AI Desktop Assistant for Fedora Linux*

</div>

---

## ✨ Features

| Feature | Status |
|---------|--------|
| 🎤 Wake word detection ("Jarvis") | ✅ |
| 🗣️ Speech-to-Text (Faster-Whisper) | ✅ |
| 🔊 Text-to-Speech (Piper/espeak) | ✅ |
| 🧠 Local AI via Ollama | ✅ |
| ☁️ OpenAI API fallback | ✅ |
| 💬 Streaming chat responses | ✅ |
| 🖥️ Full system control | ✅ |
| 📊 Real-time system dashboard | ✅ |
| 🔔 Notifications (Discord, GitHub, Gmail) | ✅ |
| 🖱️ Desktop UI (PySide6, glassmorphism) | ✅ |
| 🔌 WebSocket API | ✅ |
| 📱 REST API for mobile | ✅ |
| 🧩 Plugin system | ✅ |
| 🔐 JWT Authentication | ✅ |
| 🐳 Docker deployment | ✅ |

---

## 🚀 Quick Start

### 1. Clone & Setup

```bash
git clone <your-repo>
cd jarvis
chmod +x scripts/setup.sh
./scripts/setup.sh
```

### 2. Start Ollama

```bash
ollama serve &
ollama pull llama3.2
```

### 3. Run JARVIS

```bash
# Activate virtualenv
source .venv/bin/activate

# Start API server
python main.py serve

# Launch desktop UI (separate terminal)
python main.py desktop

# Or use voice only
python main.py voice

# Quick command test
python main.py chat "open Firefox"
```

---

## 📂 Project Structure

```
jarvis/
├── main.py                 # CLI entry point
├── config/
│   └── settings.py         # Pydantic settings (env-based)
├── ai/
│   ├── engine.py           # Multi-provider AI (Ollama + OpenAI)
│   └── interpreter.py      # NLP → System command mapping
├── voice/
│   └── pipeline.py         # Wake word → STT → TTS pipeline
├── system/
│   └── controller.py       # Full Linux system control
├── api/
│   ├── app.py              # FastAPI application
│   ├── websocket.py        # WebSocket hub
│   └── routes/             # REST API routes
│       ├── auth.py         # JWT auth
│       ├── chat.py         # AI chat + streaming
│       ├── system.py       # System control
│       ├── notifications.py
│       ├── plugins.py
│       └── metrics.py
├── database/
│   ├── models/             # SQLAlchemy ORM models
│   └── engine.py           # Async DB engine
├── security/
│   └── auth.py             # JWT, passwords, permissions
├── notifications/
│   └── service.py          # System/GitHub/Gmail monitor
├── plugins/
│   ├── sdk/                # Plugin development SDK
│   └── builtin/            # Built-in plugins
├── ui/
│   └── main_window.py      # PySide6 desktop UI
├── tests/
│   └── test_jarvis.py      # Comprehensive test suite
├── scripts/
│   └── setup.sh            # Fedora setup script
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

---

## 🗣️ Voice Commands

| Say | Action |
|-----|--------|
| "Jarvis, open Firefox" | Opens Firefox browser |
| "Jarvis, take a screenshot" | Captures screen |
| "Jarvis, set volume to 60" | Sets volume to 60% |
| "Jarvis, lock the screen" | Locks your PC |
| "Jarvis, search Google for Python" | Google search |
| "Jarvis, what's my CPU usage?" | System metrics |
| "Jarvis, shutdown the computer" | Shutdown (with confirmation) |
| "Jarvis, wifi off" | Disables Wi-Fi |

---

## 🔌 WebSocket API

Connect to `ws://localhost:8765/ws/{client-id}` and send JSON:

```json
// Chat
{ "type": "chat", "message": "Hello JARVIS" }

// Execute command
{ "type": "command", "message": "open spotify" }

// Stream response
{ "type": "chat", "message": "explain quantum computing", "stream": true }

// Get metrics
{ "type": "metrics" }
```

---

## 🔗 REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat/message` | POST | Chat with AI |
| `/api/v1/chat/command` | POST | Execute command |
| `/api/v1/chat/stream` | POST | SSE streaming |
| `/api/v1/system/status` | GET | System metrics |
| `/api/v1/system/apps/open` | POST | Open app |
| `/api/v1/system/power/shutdown` | POST | Shutdown PC |
| `/api/v1/system/audio/volume` | POST | Set volume |
| `/api/v1/system/screenshot` | POST | Take screenshot |
| `/api/v1/system/files` | GET | List files |
| `/api/v1/plugins` | GET | List plugins |
| `/api/v1/auth/login` | POST | JWT login |

Full docs at: http://localhost:8765/docs

---

## 🧩 Plugin Development

```python
from plugins.sdk import BasePlugin, PluginManifest

class MyPlugin(BasePlugin):
    manifest = PluginManifest(
        name="my_plugin",
        display_name="My Plugin",
        version="1.0.0",
        description="Does something cool",
    )

    async def initialize(self) -> bool:
        self.register_command(
            "my_command",
            "Does something",
            self.my_handler,
        )
        return True

    async def shutdown(self) -> None:
        pass

    def my_handler(self) -> str:
        return "Hello from my plugin!"
```

---

## 🐳 Docker

```bash
# Development
docker-compose up -d

# Production with GPU
docker-compose --profile gpu up -d
```

---

## 🔐 Security

- JWT authentication for all API endpoints
- bcrypt password hashing
- IP whitelist support
- Command confirmation for dangerous operations (shutdown, delete, etc.)
- Sandboxed plugin execution
- Audit log for all commands

---

## ⚙️ Configuration

Copy `.env.example` to `.env` and configure:

```bash
# AI Provider
OLLAMA_MODEL=llama3.2          # or mistral, phi3, codellama
OPENAI_API_KEY=sk-...          # optional cloud fallback

# Voice
WAKE_WORD=jarvis
STT_MODEL=base.en              # tiny|base|small|medium|large

# Notifications
GITHUB_TOKEN=ghp_...
BATTERY_WARNING_THRESHOLD=20
```

---

## 🗺️ Roadmap

- [ ] Face recognition login
- [ ] Browser automation (Playwright)
- [ ] Multi-PC sync
- [ ] Flutter Android app
- [ ] Email assistant
- [ ] Calendar integration
- [ ] OCR / image understanding
- [ ] SSH management
- [ ] Docker management plugin
- [ ] Scheduled automation

---

## 📄 License

MIT License — Build your own JARVIS!
