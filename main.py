"""
JARVIS Main Entry Point
Supports: desktop UI, API server only, or CLI mode.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import click
from loguru import logger

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import settings
from utils.logging import setup_logging


@click.group()
def cli() -> None:
    """JARVIS AI Desktop Assistant"""
    setup_logging()


@cli.command()
@click.option("--host", default=settings.API_HOST, help="API host")
@click.option("--port", default=settings.API_PORT, help="API port")
@click.option("--reload", is_flag=True, default=settings.API_RELOAD)
def serve(host: str, port: int, reload: bool) -> None:
    """Start the JARVIS API server."""
    import uvicorn

    logger.info(f"🚀 Starting JARVIS API on {host}:{port}")
    uvicorn.run(
        "api.app:app",
        host=host,
        port=port,
        reload=reload,
        log_level=settings.LOG_LEVEL.lower(),
    )


@cli.command()
def desktop() -> None:
    """Launch the JARVIS desktop application (requires PySide6)."""
    try:
        from ui.main_window import run_desktop_app
        logger.info("🖥️  Launching JARVIS Desktop UI")
        run_desktop_app()
    except ImportError as e:
        logger.error(f"PySide6 not installed: {e}")
        logger.info("Install with: pip install PySide6")
        sys.exit(1)


@cli.command()
@click.argument("message")
def chat(message: str) -> None:
    """Send a single chat message and print the response."""

    async def _chat() -> None:
        from ai.engine import ai_engine
        from ai.interpreter import CommandInterpreter
        from system.controller import system

        await ai_engine.initialize()
        interpreter = CommandInterpreter(ai_engine, system)
        cmd = await interpreter.parse(message)
        response, _ = await interpreter.execute(cmd)
        click.echo(f"\n🤖 JARVIS: {response}\n")

    asyncio.run(_chat())


@cli.command()
def voice() -> None:
    """Start JARVIS in voice-only mode."""

    async def _voice() -> None:
        from voice.pipeline import voice_pipeline
        from ai.engine import ai_engine
        from ai.interpreter import CommandInterpreter
        from system.controller import system

        interpreter = CommandInterpreter(ai_engine, system)
        await ai_engine.initialize()

        async def handler(text: str) -> None:
            response, _ = await interpreter.execute(await interpreter.parse(text))
            await voice_pipeline.speak(response)

        voice_pipeline.on_command(handler)
        await voice_pipeline.initialize()
        await voice_pipeline.start()

        logger.info("Voice mode active. Press Ctrl+C to stop.")
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await voice_pipeline.stop()

    asyncio.run(_voice())


@cli.command()
def setup() -> None:
    """Interactive first-time setup."""
    click.echo("\n" + "=" * 60)
    click.echo("  JARVIS — First Time Setup")
    click.echo("=" * 60 + "\n")

    env_file = Path(".env")
    if not env_file.exists():
        import shutil
        shutil.copy(".env.example", ".env")
        click.echo("✅ Created .env from template\n")

    click.echo("Edit .env to configure your settings:")
    click.echo("  - Set OLLAMA_MODEL to your preferred model")
    click.echo("  - Add OPENAI_API_KEY if using OpenAI")
    click.echo("  - Configure GITHUB_TOKEN for notifications")
    click.echo("\nRun 'jarvis serve' to start the API")
    click.echo("Run 'jarvis desktop' to launch the desktop UI\n")


@cli.command()
def status() -> None:
    """Check JARVIS service status."""

    async def _check() -> None:
        import httpx
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"http://localhost:{settings.API_PORT}/health", timeout=3)
                data = resp.json()
                click.echo(f"✅ JARVIS API: {data}")
        except Exception:
            click.echo("❌ JARVIS API not running. Start with: jarvis serve")

    asyncio.run(_check())


if __name__ == "__main__":
    cli()
