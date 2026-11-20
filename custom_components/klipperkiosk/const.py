"""Constants for the KlipperKiosk integration."""

from __future__ import annotations

DOMAIN = "klipperkiosk"

CONF_PIN = "pin"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_NAME = "KlipperKiosk"
DEFAULT_HOST = "klipper-tablet.local"
DEFAULT_PORT = 8765
DEFAULT_PIN = "1234"
DEFAULT_SCAN_INTERVAL = 30
MIN_SCAN_INTERVAL = 5
MAX_SCAN_INTERVAL = 300

DEFAULT_TIMEOUT = 10

HEADER_PIN = "X-Kiosk-Pin"

# Service names
SERVICE_ADD_TAB = "add_tab"
SERVICE_UPDATE_TAB = "update_tab"
SERVICE_DELETE_TAB = "delete_tab"
SERVICE_ACTIVATE_TAB = "activate_tab"
SERVICE_REORDER_TABS = "reorder_tabs"
SERVICE_NAVIGATE = "navigate"
SERVICE_SET_PIN = "set_pin"
SERVICE_SEND_IR = "send_ir"
SERVICE_SAVE_IR_COMMAND = "save_ir_command"
SERVICE_DELETE_IR_COMMAND = "delete_ir_command"

# Service attributes
ATTR_TAB_ID = "tab_id"
ATTR_TITLE = "title"
ATTR_URL = "url"
ATTR_ACTIVATE = "activate"
ATTR_IDS = "ids"
ATTR_PIN = "pin"
ATTR_FREQUENCY = "frequency"
ATTR_PATTERN = "pattern"
ATTR_PRONTO_HEX = "pronto_hex"
ATTR_BROADLINK_B64 = "broadlink_b64"
ATTR_NEC_HEX = "nec_hex"
ATTR_REPEAT = "repeat"
ATTR_REPEAT_DELAY_MS = "repeat_delay_ms"
ATTR_COMMAND = "command"
ATTR_IR_DEVICE = "ir_device"
