"""
Notification Monitor — Watches system, Discord, GitHub, Gmail
and broadcasts to all connected clients.
"""
from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from typing import Any, Optional

import psutil
from loguru import logger

from config.settings import settings


@dataclass
class JarvisNotification:
    title: str
    body: str
    source: str
    priority: str = "normal"
    icon: Optional[str] = None
    action_url: Optional[str] = None


class SystemNotificationMonitor:
    """Monitor system health and emit alerts."""

    def __init__(self) -> None:
        self._prev_battery: Optional[float] = None
        self._alerted: set[str] = set()

    async def check(self) -> list[JarvisNotification]:
        notifications: list[JarvisNotification] = []

        # Battery warning
        battery = psutil.sensors_battery()
        if battery and not battery.power_plugged:
            pct = battery.percent
            if pct <= settings.BATTERY_WARNING_THRESHOLD and "battery_low" not in self._alerted:
                notifications.append(JarvisNotification(
                    title="⚠️ Low Battery",
                    body=f"Battery at {pct:.0f}%. Please plug in.",
                    source="system",
                    priority="high",
                    icon="battery",
                ))
                self._alerted.add("battery_low")
            elif pct > settings.BATTERY_WARNING_THRESHOLD:
                self._alerted.discard("battery_low")

        # CPU alert
        cpu = psutil.cpu_percent(interval=0)
        if cpu >= settings.CPU_ALERT_THRESHOLD and "cpu_high" not in self._alerted:
            notifications.append(JarvisNotification(
                title="🔥 High CPU Usage",
                body=f"CPU at {cpu:.0f}%",
                source="system",
                priority="normal",
            ))
            self._alerted.add("cpu_high")
        elif cpu < settings.CPU_ALERT_THRESHOLD - 10:
            self._alerted.discard("cpu_high")

        # RAM alert
        ram = psutil.virtual_memory()
        if ram.percent >= settings.RAM_ALERT_THRESHOLD and "ram_high" not in self._alerted:
            notifications.append(JarvisNotification(
                title="💾 High RAM Usage",
                body=f"RAM at {ram.percent:.0f}%",
                source="system",
                priority="normal",
            ))
            self._alerted.add("ram_high")
        elif ram.percent < settings.RAM_ALERT_THRESHOLD - 10:
            self._alerted.discard("ram_high")

        return notifications


class GitHubMonitor:
    """Monitor GitHub notifications."""

    def __init__(self) -> None:
        self._last_etag: Optional[str] = None

    async def check(self) -> list[JarvisNotification]:
        if not settings.GITHUB_TOKEN:
            return []

        try:
            import httpx
            headers = {
                "Authorization": f"token {settings.GITHUB_TOKEN}",
                "Accept": "application/vnd.github.v3+json",
            }
            if self._last_etag:
                headers["If-None-Match"] = self._last_etag

            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    "https://api.github.com/notifications",
                    headers=headers,
                    timeout=10,
                )

                if resp.status_code == 304:
                    return []

                self._last_etag = resp.headers.get("ETag")
                data = resp.json()

                notifs = []
                for n in data[:5]:  # Max 5 per check
                    notifs.append(JarvisNotification(
                        title=f"GitHub: {n.get('repository', {}).get('full_name', '')}",
                        body=n.get("subject", {}).get("title", "New notification"),
                        source="github",
                        action_url=n.get("url", ""),
                    ))
                return notifs
        except Exception as e:
            logger.debug(f"GitHub monitor error: {e}")
            return []


class NotificationService:
    """
    Orchestrates all monitors and broadcasts notifications
    via WebSocket to all connected clients.
    """

    def __init__(self) -> None:
        self.system_monitor = SystemNotificationMonitor()
        self.github_monitor = GitHubMonitor()
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        if not settings.NOTIFICATIONS_ENABLED:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("✅ Notification service started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

    async def _loop(self) -> None:
        check_count = 0
        while self._running:
            try:
                # System checks every cycle
                system_notifs = await self.system_monitor.check()
                await self._broadcast_all(system_notifs)

                # GitHub every 60s (12 * 5s)
                if check_count % 12 == 0:
                    github_notifs = await self.github_monitor.check()
                    await self._broadcast_all(github_notifs)

                check_count += 1
                await asyncio.sleep(settings.MONITOR_INTERVAL)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Notification loop error: {e}")
                await asyncio.sleep(5)

    async def _broadcast_all(self, notifs: list[JarvisNotification]) -> None:
        if not notifs:
            return
        try:
            from api.websocket import broadcast_notification
            for n in notifs:
                await broadcast_notification(n.title, n.body, n.source)
                # Also show desktop notification
                await self._desktop_notify(n)
        except Exception as e:
            logger.debug(f"Broadcast error: {e}")

    @staticmethod
    async def _desktop_notify(n: JarvisNotification) -> None:
        try:
            import subprocess
            subprocess.Popen(
                ["notify-send", "-a", "JARVIS", n.title, n.body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


notification_service = NotificationService()
