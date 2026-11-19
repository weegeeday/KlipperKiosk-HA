"""Config flow for the KlipperKiosk integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import (
    KlipperKioskApiClient,
    KlipperKioskAuthError,
    KlipperKioskConnectionError,
    KlipperKioskError,
    normalize_host,
)
from .const import (
    CONF_PIN,
    CONF_SCAN_INTERVAL,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_PIN,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


class KlipperKioskConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for KlipperKiosk."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovered_host: str | None = None
        self._discovered_port: int = DEFAULT_PORT
        self._discovered_name: str = DEFAULT_NAME

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: ConfigEntry,
    ) -> KlipperKioskOptionsFlowHandler:
        """Return the options flow handler."""
        return KlipperKioskOptionsFlowHandler()

    async def _async_validate_connection(
        self, host: str, port: int, pin: str
    ) -> str | None:
        """Validate host reachability and PIN; return error key or None on success."""
        session = async_get_clientsession(self.hass)
        client = KlipperKioskApiClient(session, host=host, port=port, pin=pin)
        try:
            await client.async_health()
            await client.async_get_status()
        except KlipperKioskAuthError:
            return "invalid_auth"
        except KlipperKioskConnectionError:
            return "cannot_connect"
        except KlipperKioskError:
            return "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected error validating KlipperKiosk connection")
            return "unknown"
        return None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle manual user setup."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            port = int(user_input[CONF_PORT])
            pin = str(user_input[CONF_PIN])
            name = (user_input.get(CONF_NAME) or DEFAULT_NAME).strip() or DEFAULT_NAME

            error = await self._async_validate_connection(host, port, pin)
            if error is None:
                await self.async_set_unique_id(f"{host.lower()}:{port}")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PIN: pin,
                    },
                )
            errors["base"] = error

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=(user_input or {}).get(CONF_HOST, DEFAULT_HOST),
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=(user_input or {}).get(CONF_PORT, DEFAULT_PORT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(
                    CONF_PIN,
                    default=(user_input or {}).get(CONF_PIN, DEFAULT_PIN),
                ): str,
                vol.Optional(
                    CONF_NAME,
                    default=(user_input or {}).get(CONF_NAME, DEFAULT_NAME),
                ): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo
    ) -> ConfigFlowResult:
        """Handle mDNS / Zeroconf discovery of klipper-tablet.local."""
        host = normalize_host(discovery_info.hostname or discovery_info.host)
        port = discovery_info.port or DEFAULT_PORT

        await self.async_set_unique_id(f"{host.lower()}:{port}")
        self._abort_if_unique_id_configured(
            updates={CONF_HOST: host, CONF_PORT: port}
        )

        # Verify the discovered HTTP service is actually KlipperKiosk
        session = async_get_clientsession(self.hass)
        client = KlipperKioskApiClient(session, host=host, port=port)
        try:
            health = await client.async_health()
        except KlipperKioskError:
            return self.async_abort(reason="cannot_connect")

        if health.get("app") != "KlipperKiosk":
            return self.async_abort(reason="not_klipperkiosk")

        self._discovered_host = host
        self._discovered_port = port
        self._discovered_name = DEFAULT_NAME
        self.context["title_placeholders"] = {
            "name": self._discovered_name,
            "host": host,
        }
        return await self.async_step_zeroconf_confirm()

    async def async_step_zeroconf_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm setup of a discovered KlipperKiosk tablet."""
        errors: dict[str, str] = {}
        assert self._discovered_host is not None

        if user_input is not None:
            pin = str(user_input[CONF_PIN])
            name = (
                user_input.get(CONF_NAME) or self._discovered_name
            ).strip() or DEFAULT_NAME
            error = await self._async_validate_connection(
                self._discovered_host, self._discovered_port, pin
            )
            if error is None:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_HOST: self._discovered_host,
                        CONF_PORT: self._discovered_port,
                        CONF_PIN: pin,
                    },
                )
            errors["base"] = error

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_PIN,
                    default=(user_input or {}).get(CONF_PIN, DEFAULT_PIN),
                ): str,
                vol.Optional(
                    CONF_NAME,
                    default=(user_input or {}).get(CONF_NAME, self._discovered_name),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="zeroconf_confirm",
            data_schema=schema,
            description_placeholders={
                "host": self._discovered_host,
                "port": str(self._discovered_port),
            },
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when the PIN has changed on the tablet."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Prompt user for the updated PIN."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()
        host = reauth_entry.data[CONF_HOST]
        port = reauth_entry.data[CONF_PORT]

        if user_input is not None:
            pin = str(user_input[CONF_PIN])
            error = await self._async_validate_connection(host, port, pin)
            if error is None:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data_updates={CONF_PIN: pin},
                )
            errors["base"] = error

        schema = vol.Schema({vol.Required(CONF_PIN): str})
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            description_placeholders={"host": host},
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Allow reconfiguring host, port, and PIN from the UI."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = normalize_host(user_input[CONF_HOST])
            port = int(user_input[CONF_PORT])
            pin = str(user_input[CONF_PIN])

            error = await self._async_validate_connection(host, port, pin)
            if error is None:
                await self.async_set_unique_id(f"{host.lower()}:{port}")
                self._abort_if_unique_id_mismatch()
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_PIN: pin,
                    },
                )
            errors["base"] = error

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_HOST,
                    default=(user_input or reconfigure_entry.data).get(
                        CONF_HOST, DEFAULT_HOST
                    ),
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=(user_input or reconfigure_entry.data).get(
                        CONF_PORT, DEFAULT_PORT
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Required(
                    CONF_PIN,
                    default=(user_input or reconfigure_entry.data).get(
                        CONF_PIN, DEFAULT_PIN
                    ),
                ): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )


class KlipperKioskOptionsFlowHandler(OptionsFlow):
    """Handle KlipperKiosk options (polling interval)."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL, default=current_interval
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)

