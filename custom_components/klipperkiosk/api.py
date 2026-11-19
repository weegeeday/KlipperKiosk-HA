"""Async HTTP API client for KlipperKiosk."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

import aiohttp

from .const import DEFAULT_PORT, DEFAULT_TIMEOUT, HEADER_PIN


class KlipperKioskError(Exception):
    """Base exception for KlipperKiosk API errors."""


class KlipperKioskConnectionError(KlipperKioskError):
    """Raised when the tablet cannot be reached."""


class KlipperKioskAuthError(KlipperKioskError):
    """Raised when the PIN is missing or invalid (HTTP 401)."""


class KlipperKioskApiError(KlipperKioskError):
    """Raised when the API returns a non-success response."""

    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


@dataclass(slots=True)
class KioskTab:
    """Representation of a single kiosk tab."""

    id: str
    title: str
    url: str
    resolved_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KioskTab:
        """Create a KioskTab from API JSON."""
        return cls(
            id=str(data.get("id", "")),
            title=str(data.get("title", "")),
            url=str(data.get("url", "")),
            resolved_url=data.get("resolvedUrl"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize tab for entity attributes."""
        result: dict[str, Any] = {
            "id": self.id,
            "title": self.title,
            "url": self.url,
        }
        if self.resolved_url is not None:
            result["resolved_url"] = self.resolved_url
        return result


@dataclass(slots=True)
class KioskStatus:
    """Representation of GET /api/status."""

    active_tab_id: str | None
    tabs: list[KioskTab] = field(default_factory=list)
    kiosk_locked: bool = False
    lock_task_mode: bool = False
    device_ip: str | None = None
    port: int = DEFAULT_PORT

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KioskStatus:
        """Create a KioskStatus from API JSON."""
        raw_tabs = data.get("tabs") or []
        tabs = [KioskTab.from_dict(tab) for tab in raw_tabs if isinstance(tab, dict)]
        return cls(
            active_tab_id=data.get("activeTabId"),
            tabs=tabs,
            kiosk_locked=bool(data.get("kioskLocked", False)),
            lock_task_mode=bool(data.get("lockTaskMode", False)),
            device_ip=data.get("deviceIp"),
            port=int(data.get("port", DEFAULT_PORT)),
        )

    @property
    def active_tab(self) -> KioskTab | None:
        """Return the currently active tab, if found."""
        if not self.active_tab_id:
            return None
        for tab in self.tabs:
            if tab.id == self.active_tab_id:
                return tab
        return None


@dataclass(slots=True)
class IrCapabilities:
    """Representation of GET /api/ir."""

    has_ir_emitter: bool = False
    carrier_frequencies: list[dict[str, int]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> IrCapabilities:
        """Create IrCapabilities from API JSON."""
        raw_freqs = data.get("carrierFrequencies") or []
        freqs: list[dict[str, int]] = []
        for item in raw_freqs:
            if isinstance(item, dict) and "min" in item and "max" in item:
                freqs.append({"min": int(item["min"]), "max": int(item["max"])})
        return cls(
            has_ir_emitter=bool(data.get("hasIrEmitter", False)),
            carrier_frequencies=freqs,
        )


def normalize_host(host: str) -> str:
    """Strip scheme, path, and trailing dots from a user-provided host."""
    cleaned = host.strip()
    for prefix in ("http://", "https://"):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :]
    cleaned = cleaned.split("/", 1)[0].strip()
    # Strip port suffix if user included it (not IPv6)
    if ":" in cleaned and not cleaned.startswith("["):
        cleaned = cleaned.split(":", 1)[0]
    return cleaned.rstrip(".")


class KlipperKioskApiClient:
    """Async REST API client for KlipperKiosk."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int = DEFAULT_PORT,
        pin: str = "",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        self._session = session
        self._host = normalize_host(host)
        self._port = port
        self._pin = pin
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def host(self) -> str:
        """Return normalized host."""
        return self._host

    @property
    def port(self) -> int:
        """Return API port."""
        return self._port

    @property
    def base_url(self) -> str:
        """Return base URL for the tablet API."""
        return f"http://{self._host}:{self._port}"

    def set_local_pin(self, pin: str) -> None:
        """Update the PIN used by this client for subsequent requests."""
        self._pin = pin

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """Perform an HTTP request against the KlipperKiosk API."""
        url = f"{self.base_url}{path}"
        headers: dict[str, str] = {}
        if authenticated and self._pin:
            headers[HEADER_PIN] = self._pin
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        try:
            async with self._session.request(
                method,
                url,
                headers=headers,
                json=json_body,
                timeout=self._timeout,
            ) as response:
                try:
                    payload = await response.json(content_type=None)
                except (ValueError, aiohttp.ContentTypeError):
                    text = await response.text()
                    payload = {"error": text or response.reason}

                if response.status == 401:
                    msg = (
                        payload.get("error", "Unauthorized: invalid or missing PIN")
                        if isinstance(payload, dict)
                        else "Unauthorized"
                    )
                    raise KlipperKioskAuthError(msg)

                if response.status >= 400:
                    msg = (
                        payload.get("error") or payload.get("message") or f"HTTP {response.status}"
                        if isinstance(payload, dict)
                        else f"HTTP {response.status}"
                    )
                    raise KlipperKioskApiError(str(msg), status=response.status)

                return payload if isinstance(payload, dict) else {}

        except (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError) as err:
            raise KlipperKioskConnectionError(
                f"Failed to communicate with KlipperKiosk at {self.base_url}: {err}"
            ) from err

    # --- Health & Status ---

    async def async_health(self) -> dict[str, Any]:
        """GET /api/health (unauthenticated)."""
        return await self._request("GET", "/api/health", authenticated=False)

    async def async_get_status(self) -> KioskStatus:
        """GET /api/status."""
        data = await self._request("GET", "/api/status")
        return KioskStatus.from_dict(data)

    # --- Tab Management ---

    async def async_get_tabs(self) -> tuple[str | None, list[KioskTab]]:
        """GET /api/tabs."""
        data = await self._request("GET", "/api/tabs")
        tabs = [
            KioskTab.from_dict(tab)
            for tab in (data.get("tabs") or [])
            if isinstance(tab, dict)
        ]
        return data.get("activeTabId"), tabs

    async def async_add_tab(
        self,
        url: str,
        *,
        title: str | None = None,
        activate: bool = True,
    ) -> KioskTab:
        """POST /api/tabs."""
        body: dict[str, Any] = {"url": url, "activate": activate}
        if title:
            body["title"] = title
        data = await self._request("POST", "/api/tabs", json_body=body)
        return KioskTab.from_dict(data)

    async def async_update_tab(
        self,
        tab_id: str,
        *,
        title: str | None = None,
        url: str | None = None,
    ) -> KioskTab:
        """PUT /api/tabs/{id}."""
        body: dict[str, Any] = {}
        if title is not None:
            body["title"] = title
        if url is not None:
            body["url"] = url
        encoded_id = quote(tab_id, safe="")
        data = await self._request("PUT", f"/api/tabs/{encoded_id}", json_body=body)
        return KioskTab.from_dict(data)

    async def async_delete_tab(self, tab_id: str) -> dict[str, Any]:
        """DELETE /api/tabs/{id}."""
        encoded_id = quote(tab_id, safe="")
        return await self._request("DELETE", f"/api/tabs/{encoded_id}")

    async def async_activate_tab(self, tab_id: str) -> dict[str, Any]:
        """POST /api/tabs/{id}/activate."""
        encoded_id = quote(tab_id, safe="")
        return await self._request("POST", f"/api/tabs/{encoded_id}/activate")

    async def async_reorder_tabs(self, ids: list[str]) -> dict[str, Any]:
        """POST /api/tabs/reorder."""
        return await self._request("POST", "/api/tabs/reorder", json_body={"ids": ids})

    async def async_reset_tabs(self) -> dict[str, Any]:
        """POST /api/tabs/reset."""
        return await self._request("POST", "/api/tabs/reset")

    # --- Navigation & Reload ---

    async def async_reload(self) -> dict[str, Any]:
        """POST /api/reload."""
        return await self._request("POST", "/api/reload")

    async def async_navigate(self, url: str) -> dict[str, Any]:
        """POST /api/navigate."""
        return await self._request("POST", "/api/navigate", json_body={"url": url})

    # --- Kiosk Lock Controls ---

    async def async_set_controls_locked(self, locked: bool) -> dict[str, Any]:
        """POST /api/kiosk/lock."""
        return await self._request(
            "POST", "/api/kiosk/lock", json_body={"locked": locked}
        )

    async def async_enter_lock_task_mode(self) -> dict[str, Any]:
        """POST /api/kiosk/enter."""
        return await self._request("POST", "/api/kiosk/enter")

    async def async_exit_lock_task_mode(self) -> dict[str, Any]:
        """POST /api/kiosk/exit."""
        return await self._request("POST", "/api/kiosk/exit")

    # --- Security ---

    async def async_set_pin(self, new_pin: str) -> dict[str, Any]:
        """POST /api/pin."""
        result = await self._request("POST", "/api/pin", json_body={"pin": new_pin})
        self._pin = new_pin
        return result

    # --- IR Blaster ---

    async def async_get_ir_capabilities(self) -> IrCapabilities:
        """GET /api/ir."""
        data = await self._request("GET", "/api/ir")
        return IrCapabilities.from_dict(data)

    async def async_transmit_ir(
        self,
        *,
        pattern: list[int] | None = None,
        frequency: int = 38000,
        pronto_hex: str | None = None,
        repeat: int = 1,
        repeat_delay_ms: int = 100,
    ) -> dict[str, Any]:
        """POST /api/ir/transmit."""
        if not pattern and not pronto_hex:
            raise KlipperKioskApiError("Either 'pattern' or 'pronto_hex' must be provided")

        body: dict[str, Any] = {
            "repeat": repeat,
            "repeatDelayMs": repeat_delay_ms,
        }
        if pronto_hex:
            body["prontoHex"] = pronto_hex
        else:
            body["frequency"] = frequency
            body["pattern"] = pattern

        return await self._request("POST", "/api/ir/transmit", json_body=body)

