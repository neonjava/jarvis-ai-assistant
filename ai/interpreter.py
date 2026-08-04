"""
Command Interpreter — Natural Language → System Actions
Uses AI to understand intent and maps it to system commands.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Optional

from loguru import logger

from ai.engine import AIEngine
from system.controller import SystemController, CommandResult


@dataclass
class ParsedCommand:
    action: str
    target: Optional[str] = None
    params: dict[str, Any] = None
    raw: str = ""
    requires_confirmation: bool = False
    danger_message: str = ""

    def __post_init__(self) -> None:
        if self.params is None:
            self.params = {}


# ── Rule-based fast path ──────────────────────────────────────────────────────

COMMAND_PATTERNS: list[tuple[str, str, dict[str, Any]]] = [
    # (regex pattern, action, extra_params)
    (r"open\s+(.+)", "open_app", {}),
    (r"close\s+(.+)", "close_app", {}),
    (r"kill\s+(.+)", "kill_app", {"requires_confirmation": True}),
    (r"shut\s*down|power\s*off", "shutdown", {"requires_confirmation": True}),
    (r"restart|reboot", "restart", {"requires_confirmation": True}),
    (r"suspend|sleep", "suspend", {}),
    (r"hibernate", "hibernate", {"requires_confirmation": True}),
    (r"lock\s*screen|lock\s*pc", "lock_screen", {}),
    (r"volume\s+(\d+)|set\s+volume\s+to\s+(\d+)", "set_volume", {}),
    (r"mute(?:\s+mic(?:rophone)?)?", "mute", {}),
    (r"unmute", "unmute", {}),
    (r"brightness\s+(\d+)|set\s+brightness\s+to\s+(\d+)", "set_brightness", {}),
    (r"screenshot|take\s+(?:a\s+)?screenshot", "screenshot", {}),
    (r"search\s+(?:google\s+for\s+)?(.+)", "search_google", {}),
    (r"open\s+(?:website|url|site)\s+(.+)", "open_website", {}),
    (r"type\s+(.+)", "type_text", {}),
    (r"wifi\s+on|enable\s+wifi", "wifi_on", {}),
    (r"wifi\s+off|disable\s+wifi", "wifi_off", {}),
    (r"bluetooth\s+on|enable\s+bluetooth", "bluetooth_on", {}),
    (r"bluetooth\s+off|disable\s+bluetooth", "bluetooth_off", {}),
    (r"clipboard|what.s in (?:my\s+)?clipboard", "get_clipboard", {}),
]

DANGEROUS_ACTIONS = {"shutdown", "restart", "hibernate", "kill_app", "delete"}


class CommandInterpreter:
    """
    Two-stage command processing:
    1. Fast rule-based regex matching for common commands
    2. AI fallback for complex / ambiguous commands
    """

    def __init__(self, ai: AIEngine, system: SystemController) -> None:
        self.ai = ai
        self.system = system

    def _rule_parse(self, text: str) -> Optional[ParsedCommand]:
        """Try to parse command using regex rules."""
        text_lower = text.lower().strip()

        for pattern, action, extra in COMMAND_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                target = None
                # Extract first non-None group as target
                if match.groups():
                    target = next((g for g in match.groups() if g), None)

                requires_conf = extra.get("requires_confirmation", False) or action in DANGEROUS_ACTIONS
                return ParsedCommand(
                    action=action,
                    target=target,
                    params=extra,
                    raw=text,
                    requires_confirmation=requires_conf,
                    danger_message=f"This will {action.replace('_', ' ')}. Confirm?" if requires_conf else "",
                )
        return None

    async def _ai_parse(self, text: str) -> Optional[ParsedCommand]:
        """Use AI to parse complex commands."""
        prompt = f"""Parse this command into a JSON action. Return ONLY valid JSON.

Command: "{text}"

Available actions: open_app, close_app, kill_app, shutdown, restart, suspend, hibernate, 
lock_screen, set_volume, mute, unmute, set_brightness, screenshot, search_google, 
open_website, type_text, wifi_on, wifi_off, bluetooth_on, bluetooth_off, get_clipboard,
set_clipboard, list_files, create_file, delete_file, move_file, run_command, chat

JSON format:
{{"action": "action_name", "target": "target_name_or_null", "params": {{}}, "requires_confirmation": false}}

If this is just a conversation (not a system command), use action "chat"."""

        try:
            response = await self.ai.chat(prompt, context="You are a command parser. Return only JSON.")
            # Extract JSON from response
            json_match = re.search(r'\{[^}]+\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return ParsedCommand(
                    action=data.get("action", "chat"),
                    target=data.get("target"),
                    params=data.get("params", {}),
                    raw=text,
                    requires_confirmation=data.get("requires_confirmation", False),
                )
        except Exception as e:
            logger.debug(f"AI parse failed: {e}")

        return ParsedCommand(action="chat", raw=text)

    async def parse(self, text: str) -> ParsedCommand:
        """Parse a natural language command."""
        cmd = self._rule_parse(text)
        if cmd and cmd.action != "chat":
            logger.debug(f"Rule-parsed: {cmd.action} → {cmd.target}")
            return cmd

        cmd = await self._ai_parse(text)
        logger.debug(f"AI-parsed: {cmd.action} → {cmd.target}")
        return cmd

    async def execute(self, cmd: ParsedCommand) -> tuple[str, CommandResult | None]:
        """Execute a parsed command and return (response_text, result)."""
        action = cmd.action
        target = cmd.target or ""
        params = cmd.params or {}

        logger.info(f"Executing: {action}({target})")

        try:
            # ── App Control ──────────────────────────────────────────
            if action == "open_app":
                result = await self.system.apps.open_app(target)
                return f"Opening {target}." if result.success else f"Couldn't open {target}: {result.error}", result

            elif action == "close_app":
                result = await self.system.apps.close_app(target)
                return f"Closing {target}.", result

            elif action == "kill_app":
                result = await self.system.apps.kill_app(target)
                return f"Killed {target}.", result

            # ── Power ────────────────────────────────────────────────
            elif action == "shutdown":
                result = await self.system.power.shutdown()
                return "Shutting down.", result

            elif action == "restart":
                result = await self.system.power.restart()
                return "Restarting.", result

            elif action == "suspend":
                result = await self.system.power.suspend()
                return "Suspending.", result

            elif action == "hibernate":
                result = await self.system.power.hibernate()
                return "Hibernating.", result

            elif action == "lock_screen":
                result = await self.system.power.lock_screen()
                return "Screen locked.", result

            # ── Audio ────────────────────────────────────────────────
            elif action == "set_volume":
                level = int(target) if target and target.isdigit() else params.get("level", 50)
                result = await self.system.audio.set_volume(level)
                return f"Volume set to {level}%.", result

            elif action == "mute":
                result = await self.system.audio.mute()
                return "Muted.", result

            elif action == "unmute":
                result = await self.system.audio.unmute()
                return "Unmuted.", result

            # ── Brightness ───────────────────────────────────────────
            elif action == "set_brightness":
                level = int(target) if target and target.isdigit() else 50
                result = await self.system.brightness.set_brightness(level)
                return f"Brightness set to {level}%.", result

            # ── Screenshot ───────────────────────────────────────────
            elif action == "screenshot":
                result = await self.system.media.screenshot()
                return "Screenshot taken." if result.success else f"Screenshot failed: {result.error}", result

            # ── Web ──────────────────────────────────────────────────
            elif action == "search_google":
                result = await self.system.apps.search_google(target)
                return f"Searching Google for: {target}", result

            elif action == "open_website":
                result = await self.system.apps.open_website(target)
                return f"Opening {target}.", result

            # ── Input ────────────────────────────────────────────────
            elif action == "type_text":
                result = await self.system.input.type_text(target)
                return f"Typed: {target}", result

            # ── Network ──────────────────────────────────────────────
            elif action == "wifi_on":
                result = await self.system.network.wifi_on()
                return "Wi-Fi enabled.", result

            elif action == "wifi_off":
                result = await self.system.network.wifi_off()
                return "Wi-Fi disabled.", result

            elif action == "bluetooth_on":
                result = await self.system.network.bluetooth_on()
                return "Bluetooth enabled.", result

            elif action == "bluetooth_off":
                result = await self.system.network.bluetooth_off()
                return "Bluetooth disabled.", result

            # ── Clipboard ────────────────────────────────────────────
            elif action == "get_clipboard":
                result = await self.system.clipboard.get()
                return f"Clipboard: {result.output}", result

            # ── Shell command ────────────────────────────────────────
            elif action == "run_command":
                result = await self.system.execute_shell(target)
                return result.output or result.error, result

            # ── Chat (no system action) ──────────────────────────────
            elif action == "chat":
                response = await self.ai.chat(cmd.raw)
                return response, None

            else:
                response = await self.ai.chat(cmd.raw)
                return response, None

        except Exception as e:
            logger.error(f"Command execution error: {e}")
            return f"Error executing command: {e}", None
