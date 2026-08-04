"""
System Info Plugin — Example plugin demonstrating the JARVIS Plugin SDK.
"""
from __future__ import annotations

import platform
from typing import Any

import psutil

from plugins.sdk import BasePlugin, PluginManifest


class SystemInfoPlugin(BasePlugin):

    manifest = PluginManifest(
        name="system_info",
        display_name="System Information",
        version="1.0.0",
        description="Provides detailed system information commands",
        author="JARVIS Team",
        commands=["sysinfo", "diskinfo", "netinfo"],
    )

    async def initialize(self) -> bool:
        self.register_command(
            "sysinfo",
            "Get full system information",
            self.get_sysinfo,
        )
        self.register_command(
            "diskinfo",
            "Get disk partition information",
            self.get_diskinfo,
        )
        self.register_command(
            "netinfo",
            "Get network interface information",
            self.get_netinfo,
        )
        return True

    async def shutdown(self) -> None:
        pass

    def get_sysinfo(self) -> str:
        info = {
            "os": platform.system(),
            "version": platform.version(),
            "machine": platform.machine(),
            "cpu_count": psutil.cpu_count(),
            "ram_gb": round(psutil.virtual_memory().total / 1024**3, 1),
        }
        return "\n".join(f"{k}: {v}" for k, v in info.items())

    def get_diskinfo(self) -> str:
        lines = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                lines.append(
                    f"{part.device} → {part.mountpoint} "
                    f"({usage.percent:.0f}% used, {usage.free // 1024**3}GB free)"
                )
            except Exception:
                continue
        return "\n".join(lines)

    def get_netinfo(self) -> str:
        lines = []
        for iface, addrs in psutil.net_if_addrs().items():
            for addr in addrs:
                if addr.family.name == "AF_INET":
                    lines.append(f"{iface}: {addr.address}")
        return "\n".join(lines)
