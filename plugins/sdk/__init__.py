"""
Plugin SDK — Base classes and registry for JARVIS plugins.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from loguru import logger


@dataclass
class PluginManifest:
    """Plugin metadata."""
    name: str
    display_name: str
    version: str
    description: str = ""
    author: str = ""
    commands: list[str] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)


@dataclass
class PluginCommand:
    """A command registered by a plugin."""
    name: str
    description: str
    handler: Callable
    parameters: dict[str, Any] = field(default_factory=dict)


class BasePlugin(ABC):
    """Base class all plugins must inherit from."""

    manifest: PluginManifest  # Must be defined in subclass

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}
        self._commands: list[PluginCommand] = []
        self._enabled = True

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the plugin. Return True on success."""
        ...

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""
        ...

    def register_command(
        self,
        name: str,
        description: str,
        handler: Callable,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """Register a command this plugin handles."""
        self._commands.append(PluginCommand(
            name=name,
            description=description,
            handler=handler,
            parameters=parameters or {},
        ))

    async def handle_command(self, command: str, **kwargs: Any) -> str:
        """Route a command to the appropriate handler."""
        for cmd in self._commands:
            if cmd.name == command:
                result = cmd.handler(**kwargs)
                if asyncio.iscoroutine(result):
                    return await result
                return str(result)
        return f"Unknown command: {command}"

    def get_commands(self) -> list[PluginCommand]:
        return self._commands


# ── Plugin Registry ───────────────────────────────────────────────────────────

class PluginRegistry:
    """Manages plugin loading, unloading, and command routing."""

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._command_map: dict[str, tuple[BasePlugin, PluginCommand]] = {}

    async def load_plugin(self, plugin_path: Path, config: dict | None = None) -> bool:
        """Dynamically load a plugin from a directory or .py file."""
        try:
            if plugin_path.is_dir():
                init_file = plugin_path / "plugin.py"
                if not init_file.exists():
                    logger.warning(f"Plugin directory missing plugin.py: {plugin_path}")
                    return False
                spec_path = init_file
            else:
                spec_path = plugin_path

            # Add to sys.path temporarily
            sys.path.insert(0, str(spec_path.parent))
            module_name = spec_path.stem

            module = importlib.import_module(module_name)

            # Find BasePlugin subclass
            plugin_class = None
            for obj in vars(module).values():
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, BasePlugin)
                    and obj is not BasePlugin
                ):
                    plugin_class = obj
                    break

            if not plugin_class:
                logger.error(f"No BasePlugin subclass found in {spec_path}")
                return False

            instance = plugin_class(config or {})
            success = await instance.initialize()

            if success:
                name = instance.manifest.name
                self._plugins[name] = instance
                # Register commands
                for cmd in instance.get_commands():
                    self._command_map[cmd.name] = (instance, cmd)
                logger.info(f"✅ Plugin loaded: {name} v{instance.manifest.version}")
                return True
            else:
                logger.error(f"Plugin initialization failed: {spec_path}")
                return False

        except Exception as e:
            logger.error(f"Plugin load error ({plugin_path}): {e}")
            return False

    async def unload_plugin(self, name: str) -> bool:
        plugin = self._plugins.pop(name, None)
        if plugin:
            await plugin.shutdown()
            # Remove commands
            for cmd_name, (p, _) in list(self._command_map.items()):
                if p is plugin:
                    del self._command_map[cmd_name]
            logger.info(f"Plugin unloaded: {name}")
            return True
        return False

    async def execute_command(self, command: str, **kwargs: Any) -> Optional[str]:
        if command in self._command_map:
            plugin, cmd = self._command_map[command]
            return await plugin.handle_command(command, **kwargs)
        return None

    def get_all_commands(self) -> list[dict[str, Any]]:
        return [
            {
                "command": name,
                "plugin": plugin.manifest.name,
                "description": cmd.description,
                "parameters": cmd.parameters,
            }
            for name, (plugin, cmd) in self._command_map.items()
        ]

    def list_plugins(self) -> list[dict[str, Any]]:
        return [
            {
                "name": p.manifest.name,
                "display_name": p.manifest.display_name,
                "version": p.manifest.version,
                "enabled": p._enabled,
                "commands": [c.name for c in p.get_commands()],
            }
            for p in self._plugins.values()
        ]


plugin_registry = PluginRegistry()
