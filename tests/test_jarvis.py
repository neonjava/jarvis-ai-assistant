"""
JARVIS Test Suite — Core unit and integration tests.
"""
from __future__ import annotations

import asyncio
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Unit Tests ────────────────────────────────────────────────────────────────

class TestCommandInterpreter:
    """Test rule-based command parsing."""

    @pytest.fixture
    def interpreter(self):
        from unittest.mock import AsyncMock, MagicMock
        from ai.interpreter import CommandInterpreter

        mock_ai = MagicMock()
        mock_system = MagicMock()
        return CommandInterpreter(mock_ai, mock_system)

    @pytest.mark.asyncio
    async def test_open_app(self, interpreter):
        from ai.interpreter import CommandInterpreter
        cmd = interpreter._rule_parse("open Firefox")
        assert cmd is not None
        assert cmd.action == "open_app"
        assert cmd.target == "firefox"

    @pytest.mark.asyncio
    async def test_set_volume(self, interpreter):
        cmd = interpreter._rule_parse("set volume to 50")
        assert cmd is not None
        assert cmd.action == "set_volume"
        assert cmd.target == "50"

    @pytest.mark.asyncio
    async def test_shutdown_requires_confirmation(self, interpreter):
        cmd = interpreter._rule_parse("shutdown")
        assert cmd is not None
        assert cmd.requires_confirmation is True

    @pytest.mark.asyncio
    async def test_screenshot(self, interpreter):
        cmd = interpreter._rule_parse("take a screenshot")
        assert cmd is not None
        assert cmd.action == "screenshot"

    @pytest.mark.asyncio
    async def test_search_google(self, interpreter):
        cmd = interpreter._rule_parse("search google for Python tutorials")
        assert cmd is not None
        assert cmd.action == "search_google"
        assert "python tutorials" in (cmd.target or "").lower()

    def test_mute(self, interpreter):
        cmd = interpreter._rule_parse("mute")
        assert cmd is not None
        assert cmd.action == "mute"

    def test_wifi_on(self, interpreter):
        cmd = interpreter._rule_parse("wifi on")
        assert cmd is not None
        assert cmd.action == "wifi_on"


class TestSettings:
    def test_settings_load(self):
        from config.settings import get_settings
        s = get_settings()
        assert s.APP_NAME == "JARVIS"
        assert s.API_PORT == 8765
        assert s.AI_TEMPERATURE <= 2.0

    def test_log_level_validation(self):
        from config.settings import AppSettings
        import pytest
        with pytest.raises(Exception):
            AppSettings(LOG_LEVEL="INVALID")


class TestSecurityAuth:
    def test_password_hash_verify(self):
        from security.auth import hash_password, verify_password
        hashed = hash_password("secret123")
        assert verify_password("secret123", hashed)
        assert not verify_password("wrong", hashed)

    def test_access_token_creation(self):
        from security.auth import create_access_token, decode_token
        token = create_access_token({"sub": "user-123", "is_admin": False})
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["is_admin"] is False

    def test_api_key_format(self):
        from security.auth import generate_api_key
        key = generate_api_key()
        assert key.startswith("jv_")
        assert len(key) > 10


class TestSystemController:
    @pytest.mark.asyncio
    async def test_run_shell_success(self):
        from system.controller import run_shell
        result = await run_shell("echo hello")
        assert result.success
        assert "hello" in result.output

    @pytest.mark.asyncio
    async def test_run_shell_failure(self):
        from system.controller import run_shell
        result = await run_shell("command_that_does_not_exist_xyz")
        assert not result.success

    @pytest.mark.asyncio
    async def test_system_metrics(self):
        from system.controller import SystemMonitor
        monitor = SystemMonitor()
        metrics = await monitor.get_metrics()
        assert "cpu" in metrics
        assert "ram" in metrics
        assert "disk" in metrics
        assert 0 <= metrics["cpu"]["percent"] <= 100

    @pytest.mark.asyncio
    async def test_file_operations(self, tmp_path):
        from system.controller import FileController
        fc = FileController()

        # Create file
        test_file = str(tmp_path / "test.txt")
        result = await fc.create_file(test_file, "Hello JARVIS")
        assert result.success

        # Read file
        result = await fc.read_file(test_file)
        assert result.success
        assert "Hello JARVIS" in result.output

        # Delete file
        result = await fc.delete(test_file)
        assert result.success


class TestPluginSDK:
    @pytest.mark.asyncio
    async def test_builtin_plugin_load(self):
        from plugins.builtin.system_info import SystemInfoPlugin
        plugin = SystemInfoPlugin()
        success = await plugin.initialize()
        assert success
        assert len(plugin.get_commands()) == 3

    @pytest.mark.asyncio
    async def test_plugin_command_execution(self):
        from plugins.builtin.system_info import SystemInfoPlugin
        plugin = SystemInfoPlugin()
        await plugin.initialize()
        result = await plugin.handle_command("sysinfo")
        assert isinstance(result, str)
        assert len(result) > 0


# ── Integration Tests ─────────────────────────────────────────────────────────

class TestAPIIntegration:
    """Integration tests requiring running API."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from api.app import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
