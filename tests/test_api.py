"""Unit tests for the KlipperKiosk API client and helpers."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COMPONENT_DIR = ROOT / "custom_components" / "klipperkiosk"


def _load_api_module():
    """Load const.py and api.py without requiring homeassistant installed."""
    # Provide a minimal aiohttp stub if aiohttp is not installed locally
    if "aiohttp" not in sys.modules:
        try:
            import aiohttp  # noqa: F401
        except ImportError:
            stub = types.ModuleType("aiohttp")

            class ClientError(Exception):
                pass

            class ContentTypeError(ClientError):
                pass

            class ClientTimeout:
                def __init__(self, total: int | None = None) -> None:
                    self.total = total

            class ClientSession:
                pass

            stub.ClientError = ClientError
            stub.ContentTypeError = ContentTypeError
            stub.ClientTimeout = ClientTimeout
            stub.ClientSession = ClientSession
            sys.modules["aiohttp"] = stub

    pkg = types.ModuleType("custom_components.klipperkiosk")
    pkg.__path__ = [str(COMPONENT_DIR)]
    sys.modules["custom_components"] = types.ModuleType("custom_components")
    sys.modules["custom_components.klipperkiosk"] = pkg

    for name in ("const", "api"):
        spec = importlib.util.spec_from_file_location(
            f"custom_components.klipperkiosk.{name}",
            COMPONENT_DIR / f"{name}.py",
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)

    return sys.modules["custom_components.klipperkiosk.api"]


api = _load_api_module()


class FakeResponse:
    def __init__(self, status: int, body: Any) -> None:
        self.status = status
        self._body = body
        self.reason = f"Status {status}"

    async def json(self, content_type=None) -> Any:
        if isinstance(self._body, str):
            raise ValueError("Not JSON")
        return self._body

    async def text(self) -> str:
        return str(self._body)


class FakeSession:
    def __init__(self, responses: list[FakeResponse]) -> None:
        self.responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    @asynccontextmanager
    async def request(self, method: str, url: str, **kwargs: Any):
        self.calls.append({"method": method, "url": url, **kwargs})
        yield self.responses.pop(0)


class TestKlipperKioskApi(unittest.TestCase):
    def test_normalize_host(self) -> None:
        self.assertEqual(api.normalize_host("klipper-tablet.local."), "klipper-tablet.local")
        self.assertEqual(api.normalize_host("http://192.168.4.150:8765/api"), "192.168.4.150")
        self.assertEqual(api.normalize_host("https://tablet.lan/"), "tablet.lan")

    def test_health_is_unauthenticated(self) -> None:
        session = FakeSession([FakeResponse(200, {"status": "ok", "app": "KlipperKiosk"})])
        client = api.KlipperKioskApiClient(session, "klipper-tablet.local", 8765, "1234")
        result = asyncio.run(client.async_health())
        self.assertEqual(result["app"], "KlipperKiosk")
        self.assertEqual(session.calls[0]["headers"], {})
        self.assertEqual(session.calls[0]["url"], "http://klipper-tablet.local:8765/api/health")

    def test_get_status_and_active_tab(self) -> None:
        payload = {
            "activeTabId": "site-1",
            "tabs": [
                {
                    "id": "site-1",
                    "title": "Farz",
                    "url": "http://pi-klipper.local",
                    "resolvedUrl": "http://192.168.4.202",
                },
                {
                    "id": "site-2",
                    "title": "Klip",
                    "url": "http://pi-klipper2.local",
                },
            ],
            "kioskLocked": False,
            "lockTaskMode": True,
            "deviceIp": "192.168.4.150",
            "port": 8765,
        }
        session = FakeSession([FakeResponse(200, payload)])
        client = api.KlipperKioskApiClient(session, "192.168.4.150", 8765, "1234")
        status = asyncio.run(client.async_get_status())
        self.assertEqual(status.active_tab_id, "site-1")
        self.assertIsNotNone(status.active_tab)
        self.assertEqual(status.active_tab.resolved_url, "http://192.168.4.202")
        self.assertEqual(len(status.tabs), 2)
        self.assertTrue(status.lock_task_mode)
        self.assertFalse(status.kiosk_locked)
        self.assertEqual(session.calls[0]["headers"]["X-Kiosk-Pin"], "1234")

    def test_invalid_pin_raises_auth_error(self) -> None:
        session = FakeSession(
            [FakeResponse(401, {"ok": False, "error": "Unauthorized: invalid or missing PIN"})]
        )
        client = api.KlipperKioskApiClient(session, "192.168.4.150", 8765, "9999")
        with self.assertRaises(api.KlipperKioskAuthError):
            asyncio.run(client.async_get_status())

    def test_set_pin_updates_client_pin(self) -> None:
        session = FakeSession(
            [
                FakeResponse(200, {"ok": True, "message": "PIN updated"}),
                FakeResponse(200, {"ok": True, "message": "Reloading active tab"}),
            ]
        )
        client = api.KlipperKioskApiClient(session, "192.168.4.150", 8765, "1234")
        asyncio.run(client.async_set_pin("5678"))
        asyncio.run(client.async_reload())
        self.assertEqual(session.calls[0]["headers"]["X-Kiosk-Pin"], "1234")
        self.assertEqual(session.calls[0]["json"], {"pin": "5678"})
        self.assertEqual(session.calls[1]["headers"]["X-Kiosk-Pin"], "5678")

    def test_transmit_ir_raw_and_pronto(self) -> None:
        session = FakeSession(
            [
                FakeResponse(200, {"ok": True, "frequency": 38000, "pulses": 7, "repeat": 1}),
                FakeResponse(200, {"ok": True, "frequency": 38000, "pulses": 4, "repeat": 2}),
            ]
        )
        client = api.KlipperKioskApiClient(session, "192.168.4.150", 8765, "1234")

        asyncio.run(
            client.async_transmit_ir(
                frequency=38000, pattern=[9000, 4500, 560, 560, 560, 1690, 560]
            )
        )
        self.assertEqual(
            session.calls[0]["json"],
            {
                "frequency": 38000,
                "pattern": [9000, 4500, 560, 560, 560, 1690, 560],
                "repeat": 1,
                "repeatDelayMs": 100,
            },
        )

        asyncio.run(
            client.async_transmit_ir(
                pronto_hex="0000 006D 0002 0000 0157 00AC 0015 0016",
                repeat=2,
                repeat_delay_ms=250,
            )
        )
        self.assertEqual(
            session.calls[1]["json"],
            {
                "prontoHex": "0000 006D 0002 0000 0157 00AC 0015 0016",
                "repeat": 2,
                "repeatDelayMs": 250,
            },
        )

    def test_metadata_json_files_valid(self) -> None:
        for path in (
            ROOT / "hacs.json",
            COMPONENT_DIR / "manifest.json",
            COMPONENT_DIR / "strings.json",
            COMPONENT_DIR / "translations" / "en.json",
        ):
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(data, dict, f"Invalid JSON in {path}")

        strings = json.loads((COMPONENT_DIR / "strings.json").read_text(encoding="utf-8"))
        en = json.loads(
            (COMPONENT_DIR / "translations" / "en.json").read_text(encoding="utf-8")
        )
        self.assertEqual(strings, en)


if __name__ == "__main__":
    unittest.main()

