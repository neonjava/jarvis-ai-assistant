"""
System Control Module
All Linux system operations JARVIS can perform.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import psutil
from loguru import logger


@dataclass
class CommandResult:
    success: bool
    output: str = ""
    error: str = ""
    return_code: int = 0
    data: dict[str, Any] = field(default_factory=dict)


# ── Shell Execution ───────────────────────────────────────────────────────────

async def run_shell(cmd: str, timeout: int = 30, shell: bool = True) -> CommandResult:
    """Run a shell command asynchronously."""
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            shell=shell,
        ) if shell else await asyncio.create_subprocess_exec(
            *cmd.split(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        success = proc.returncode == 0
        return CommandResult(
            success=success,
            output=stdout.decode().strip(),
            error=stderr.decode().strip(),
            return_code=proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        return CommandResult(success=False, error=f"Command timed out after {timeout}s")
    except Exception as e:
        return CommandResult(success=False, error=str(e))


# ── Application Control ───────────────────────────────────────────────────────

class AppController:
    """Open, close, and manage applications."""

    APP_MAP: dict[str, str] = {
        "firefox": "firefox",
        "chrome": "google-chrome",
        "chromium": "chromium-browser",
        "terminal": "gnome-terminal",
        "files": "nautilus",
        "calculator": "gnome-calculator",
        "text editor": "gedit",
        "settings": "gnome-control-center",
        "software": "gnome-software",
        "calendar": "gnome-calendar",
        "photos": "eog",
        "music": "rhythmbox",
        "video": "totem",
        "vscode": "code",
        "discord": "discord",
        "spotify": "spotify",
        "steam": "steam",
        "obs": "obs",
        "vlc": "vlc",
    }

    async def open_app(self, app_name: str) -> CommandResult:
        """Launch an application by name."""
        normalized = app_name.lower().strip()
        cmd = self.APP_MAP.get(normalized, normalized)
        result = await run_shell(f"nohup {cmd} &>/dev/null & disown")
        if result.success:
            logger.info(f"Opened application: {app_name}")
        return result

    async def close_app(self, app_name: str) -> CommandResult:
        """Gracefully close application."""
        result = await run_shell(f"pkill -TERM -f '{app_name}'")
        return result

    async def kill_app(self, app_name: str) -> CommandResult:
        """Force kill application."""
        result = await run_shell(f"pkill -9 -f '{app_name}'")
        return result

    async def list_running(self) -> list[dict[str, Any]]:
        """List running processes."""
        procs = []
        for p in psutil.process_iter(["pid", "name", "status", "cpu_percent", "memory_percent"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return procs

    async def open_website(self, url: str) -> CommandResult:
        """Open URL in default browser."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        return await run_shell(f"xdg-open '{url}'")

    async def search_google(self, query: str) -> CommandResult:
        """Search Google in default browser."""
        import urllib.parse
        encoded = urllib.parse.quote(query)
        return await self.open_website(f"https://www.google.com/search?q={encoded}")


# ── System Power ──────────────────────────────────────────────────────────────

class PowerController:
    """System power management."""

    DANGEROUS = True  # Marks this as requiring confirmation

    async def shutdown(self, delay: int = 0) -> CommandResult:
        return await run_shell(f"systemctl poweroff" + (f" --delay {delay}" if delay else ""))

    async def restart(self) -> CommandResult:
        return await run_shell("systemctl reboot")

    async def suspend(self) -> CommandResult:
        return await run_shell("systemctl suspend")

    async def hibernate(self) -> CommandResult:
        return await run_shell("systemctl hibernate")

    async def lock_screen(self) -> CommandResult:
        # Try multiple methods for different DEs
        for cmd in ["loginctl lock-session", "gnome-screensaver-command -l", "xdg-screensaver lock"]:
            result = await run_shell(cmd)
            if result.success:
                return result
        return CommandResult(success=False, error="Could not lock screen")


# ── Volume & Audio ────────────────────────────────────────────────────────────

class AudioController:
    """System volume and audio control."""

    async def set_volume(self, percent: int) -> CommandResult:
        percent = max(0, min(100, percent))
        return await run_shell(f"pactl set-sink-volume @DEFAULT_SINK@ {percent}%")

    async def get_volume(self) -> int:
        result = await run_shell(
            "pactl get-sink-volume @DEFAULT_SINK@ | grep -oP '\\d+(?=%)' | head -1"
        )
        try:
            return int(result.output)
        except ValueError:
            return 0

    async def mute(self) -> CommandResult:
        return await run_shell("pactl set-sink-mute @DEFAULT_SINK@ 1")

    async def unmute(self) -> CommandResult:
        return await run_shell("pactl set-sink-mute @DEFAULT_SINK@ 0")

    async def toggle_mute(self) -> CommandResult:
        return await run_shell("pactl set-sink-mute @DEFAULT_SINK@ toggle")

    async def mute_mic(self) -> CommandResult:
        return await run_shell("pactl set-source-mute @DEFAULT_SOURCE@ 1")

    async def unmute_mic(self) -> CommandResult:
        return await run_shell("pactl set-source-mute @DEFAULT_SOURCE@ 0")


# ── Brightness ────────────────────────────────────────────────────────────────

class BrightnessController:
    """Display brightness control."""

    async def set_brightness(self, percent: int) -> CommandResult:
        percent = max(1, min(100, percent))
        # Try brightnessctl first, then xrandr
        result = await run_shell(f"brightnessctl set {percent}%")
        if not result.success:
            result = await run_shell(
                f"xrandr --output $(xrandr | grep ' connected' | cut -d' ' -f1 | head -1) "
                f"--brightness {percent/100:.2f}"
            )
        return result

    async def get_brightness(self) -> int:
        result = await run_shell("brightnessctl get")
        max_result = await run_shell("brightnessctl max")
        try:
            current = int(result.output)
            maximum = int(max_result.output)
            return int((current / maximum) * 100)
        except Exception:
            return -1


# ── File System ───────────────────────────────────────────────────────────────

class FileController:
    """File and directory operations."""

    @staticmethod
    def _safe_path(path: str) -> Path:
        """Resolve and validate path."""
        p = Path(path).expanduser().resolve()
        return p

    async def list_dir(self, path: str = "~") -> CommandResult:
        p = self._safe_path(path)
        if not p.exists():
            return CommandResult(success=False, error=f"Path not found: {path}")
        items = []
        for item in sorted(p.iterdir()):
            items.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
            })
        return CommandResult(success=True, data={"items": items, "path": str(p)})

    async def create_file(self, path: str, content: str = "") -> CommandResult:
        p = self._safe_path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return CommandResult(success=True, output=f"Created: {p}")

    async def delete(self, path: str, recursive: bool = False) -> CommandResult:
        p = self._safe_path(path)
        if not p.exists():
            return CommandResult(success=False, error=f"Not found: {path}")
        if p.is_dir():
            if recursive:
                shutil.rmtree(p)
            else:
                p.rmdir()
        else:
            p.unlink()
        return CommandResult(success=True, output=f"Deleted: {p}")

    async def move(self, src: str, dst: str) -> CommandResult:
        shutil.move(self._safe_path(src), self._safe_path(dst))
        return CommandResult(success=True, output=f"Moved: {src} → {dst}")

    async def copy(self, src: str, dst: str) -> CommandResult:
        s, d = self._safe_path(src), self._safe_path(dst)
        if s.is_dir():
            shutil.copytree(s, d)
        else:
            shutil.copy2(s, d)
        return CommandResult(success=True, output=f"Copied: {src} → {dst}")

    async def rename(self, path: str, new_name: str) -> CommandResult:
        p = self._safe_path(path)
        new_path = p.parent / new_name
        p.rename(new_path)
        return CommandResult(success=True, output=f"Renamed to: {new_name}")

    async def read_file(self, path: str) -> CommandResult:
        p = self._safe_path(path)
        if not p.is_file():
            return CommandResult(success=False, error=f"Not a file: {path}")
        content = p.read_text(errors="replace")
        return CommandResult(success=True, output=content[:50000])  # limit

    async def search_files(self, directory: str, pattern: str) -> CommandResult:
        result = await run_shell(f"find '{directory}' -name '*{pattern}*' 2>/dev/null | head -50")
        files = [f for f in result.output.split("\n") if f]
        return CommandResult(success=True, data={"files": files}, output=result.output)


# ── Screenshot & Recording ────────────────────────────────────────────────────

class MediaController:
    """Screen capture and recording."""

    async def screenshot(self, path: Optional[str] = None) -> CommandResult:
        if not path:
            path = str(Path.home() / "Pictures" / "screenshot.png")
        # Try gnome-screenshot, then scrot, then import
        for cmd in [
            f"gnome-screenshot -f '{path}'",
            f"scrot '{path}'",
            f"import -window root '{path}'",
        ]:
            result = await run_shell(cmd)
            if result.success:
                return CommandResult(success=True, output=f"Screenshot saved: {path}", data={"path": path})
        return CommandResult(success=False, error="No screenshot tool available")

    async def start_recording(self, path: Optional[str] = None) -> CommandResult:
        if not path:
            path = str(Path.home() / "Videos" / "recording.mp4")
        result = await run_shell(
            f"nohup ffmpeg -y -f x11grab -r 30 -s $(xdpyinfo | grep dimensions | awk '{{print $2}}') "
            f"-i :0.0 -f alsa -i default '{path}' &>/dev/null & echo $!"
        )
        return CommandResult(success=result.success, output=f"Recording PID: {result.output}", data={"path": path})

    async def stop_recording(self) -> CommandResult:
        return await run_shell("pkill -SIGINT ffmpeg")


# ── Clipboard ─────────────────────────────────────────────────────────────────

class ClipboardController:
    async def get(self) -> CommandResult:
        result = await run_shell("xclip -selection clipboard -o 2>/dev/null || xsel --clipboard --output")
        return result

    async def set(self, text: str) -> CommandResult:
        proc = await asyncio.create_subprocess_shell(
            "xclip -selection clipboard",
            stdin=asyncio.subprocess.PIPE,
        )
        await proc.communicate(input=text.encode())
        return CommandResult(success=True, output="Clipboard updated")


# ── Keyboard / Mouse ──────────────────────────────────────────────────────────

class InputController:
    """Keyboard and mouse automation."""

    async def type_text(self, text: str) -> CommandResult:
        try:
            import pyautogui
            pyautogui.typewrite(text, interval=0.02)
            return CommandResult(success=True)
        except Exception as e:
            return await run_shell(f"xdotool type '{text}'")

    async def keyboard_shortcut(self, keys: str) -> CommandResult:
        """e.g. 'ctrl+c', 'super+d'"""
        return await run_shell(f"xdotool key {keys.replace('+', '--clearmodifiers --key ')}")

    async def press_key(self, key: str) -> CommandResult:
        return await run_shell(f"xdotool key {key}")


# ── Network ───────────────────────────────────────────────────────────────────

class NetworkController:
    async def get_status(self) -> dict[str, Any]:
        result = await run_shell("nmcli -t -f TYPE,STATE,CONNECTION dev status")
        connections: list[dict[str, str]] = []
        for line in result.output.strip().split("\n"):
            parts = line.split(":")
            if len(parts) >= 3:
                connections.append({"type": parts[0], "state": parts[1], "name": parts[2]})
        return {"connections": connections}

    async def wifi_on(self) -> CommandResult:
        return await run_shell("nmcli radio wifi on")

    async def wifi_off(self) -> CommandResult:
        return await run_shell("nmcli radio wifi off")

    async def bluetooth_on(self) -> CommandResult:
        return await run_shell("rfkill unblock bluetooth")

    async def bluetooth_off(self) -> CommandResult:
        return await run_shell("rfkill block bluetooth")

    async def list_wifi(self) -> CommandResult:
        return await run_shell("nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list")

    async def connect_wifi(self, ssid: str, password: str = "") -> CommandResult:
        if password:
            return await run_shell(f"nmcli dev wifi connect '{ssid}' password '{password}'")
        return await run_shell(f"nmcli dev wifi connect '{ssid}'")


# ── System Info ───────────────────────────────────────────────────────────────

class SystemMonitor:
    """Real-time system metrics."""

    async def get_metrics(self) -> dict[str, Any]:
        cpu = psutil.cpu_percent(interval=0.1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        net = psutil.net_io_counters()
        battery = psutil.sensors_battery()

        # CPU temperature
        temps: Optional[float] = None
        try:
            sensor_data = psutil.sensors_temperatures()
            for key in ("coretemp", "k10temp", "cpu_thermal"):
                if key in sensor_data:
                    temps = max(t.current for t in sensor_data[key])
                    break
        except Exception:
            pass

        return {
            "cpu": {
                "percent": cpu,
                "cores": psutil.cpu_count(),
                "freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else None,
                "temperature": temps,
            },
            "ram": {
                "percent": mem.percent,
                "used_gb": round(mem.used / 1024**3, 2),
                "total_gb": round(mem.total / 1024**3, 2),
                "available_gb": round(mem.available / 1024**3, 2),
            },
            "disk": {
                "percent": disk.percent,
                "used_gb": round(disk.used / 1024**3, 2),
                "total_gb": round(disk.total / 1024**3, 2),
                "free_gb": round(disk.free / 1024**3, 2),
            },
            "network": {
                "bytes_sent": net.bytes_sent,
                "bytes_recv": net.bytes_recv,
            },
            "battery": {
                "percent": battery.percent if battery else None,
                "plugged": battery.power_plugged if battery else None,
                "secs_left": battery.secsleft if battery else None,
            },
        }

    async def get_top_processes(self, n: int = 10) -> list[dict[str, Any]]:
        procs = []
        for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent", "status"]):
            try:
                procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return sorted(procs, key=lambda x: x.get("cpu_percent") or 0, reverse=True)[:n]


# ── Facade ────────────────────────────────────────────────────────────────────

class SystemController:
    """Unified facade for all system operations."""

    def __init__(self) -> None:
        self.apps = AppController()
        self.power = PowerController()
        self.audio = AudioController()
        self.brightness = BrightnessController()
        self.files = FileController()
        self.media = MediaController()
        self.clipboard = ClipboardController()
        self.input = InputController()
        self.network = NetworkController()
        self.monitor = SystemMonitor()

    # Convenience aliases
    async def execute_shell(self, command: str) -> CommandResult:
        """Execute arbitrary shell command (use with caution)."""
        logger.warning(f"Shell execution: {command}")
        return await run_shell(command)


system = SystemController()
