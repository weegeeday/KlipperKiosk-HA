# KlipperKiosk for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

Home Assistant custom integration (HACS-compatible) to monitor and control a **KlipperKiosk** Android tablet over its local Remote Management REST API (`http://klipper-tablet.local:8765`).

## Features

- **Automatic mDNS discovery** (`klipper-tablet.local`) or manual IP/hostname setup via the Home Assistant UI
- **Tab control**: switch the active tab with a native `select` entity, reload the active tab, reset tabs to defaults, or add/update/delete/reorder tabs via services
- **Temporary navigation**: push any URL to the active WebView without altering saved tabs
- **Kiosk lock controls**: toggle top-bar controls (`↻` / `⚙`) visibility and Android Device Owner Lock Task Mode
- **IR blaster support**: detect built-in IR emitter capabilities and transmit raw microsecond or Pronto Hex IR codes from automations
- **PIN management & re-auth**: change the tablet's Settings PIN from Home Assistant (auto-updating HA's stored PIN) with built-in re-authentication if changed on-device
- **Diagnostics & configurable polling**: adjust polling interval (5–300 s) in Options and export PIN-redacted diagnostics

---

## Installation

### Option 1: HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=weegeeday&repository=KlipperKiosk-HA&category=integration)

Or manually:

1. Open **HACS** in Home Assistant.
2. Click the three-dot menu (`⋮`) in the top right and select **Custom repositories**.
3. Add `https://github.com/weegeeday/KlipperKiosk-HA` with category **Integration**.
4. Search for **KlipperKiosk**, click **Download**, and restart Home Assistant.

### Option 2: Manual

1. Copy `custom_components/klipperkiosk` into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

---

## Configuration

1. Go to **Settings → Devices & Services → Add Integration** (or accept the auto-discovered **KlipperKiosk** card if mDNS is available on your network).
2. Search for **KlipperKiosk**.
3. Enter:
   - **Host or IP address** (default: `klipper-tablet.local`)
   - **Port** (default: `8765`)
   - **Settings PIN** (default: `1234`)
   - **Device name** (optional)

---

## Entities

| Platform | Entity | Description |
| --- | --- | --- |
| `select` | **Active tab** | Shows and switches the active tab. Attributes include `active_tab_id`, `active_tab_url`, `active_tab_resolved_url`, and the full `tabs` list. |
| `switch` | **Hide top bar controls** | Toggles `POST /api/kiosk/lock` (hides/shows `↻` and `⚙`). |
| `switch` | **Lock task mode** | Enters (`POST /api/kiosk/enter`) or exits (`POST /api/kiosk/exit`) Android Device Owner Lock Task Mode. |
| `button` | **Reload active tab** | Re-resolves DNS/mDNS and reloads the active tab (`POST /api/reload`). |
| `button` | **Reset tabs to defaults** | Restores the tablet's bundled default tabs (`POST /api/tabs/reset`). |
| `sensor` | **Active tab URL** | URL of the active tab (`resolved_url`, `tab_id`, `tab_title` in attributes). |
| `sensor` | **Tab count** | Number of configured tabs. |
| `sensor` | **Device IP** | Tablet's reported LAN IP (diagnostic, `port` in attributes). |
| `binary_sensor` | **IR emitter** | Whether the tablet has a built-in IR blaster (diagnostic, `carrier_frequencies` in attributes). |

---

## Services

All services support targeting a specific KlipperKiosk device (optional if only one tablet is configured).

### `klipperkiosk.add_tab`
Add a new tab (`POST /api/tabs`).
```yaml
action: klipperkiosk.add_tab
data:
  title: Voron
  url: http://voron.local
  activate: true
```

### `klipperkiosk.update_tab`
Update an existing tab's `title` and/or `url` (`PUT /api/tabs/{id}`).
```yaml
action: klipperkiosk.update_tab
data:
  tab_id: site-1
  title: Voron 2.4
  url: http://voron24.local
```

### `klipperkiosk.delete_tab`
Delete a tab by ID (`DELETE /api/tabs/{id}`).
```yaml
action: klipperkiosk.delete_tab
data:
  tab_id: site-2
```

### `klipperkiosk.activate_tab`
Switch to a tab by ID (`POST /api/tabs/{id}/activate`).
```yaml
action: klipperkiosk.activate_tab
data:
  tab_id: site-2
```

### `klipperkiosk.reorder_tabs`
Reorder the top tab bar (`POST /api/tabs/reorder`).
```yaml
action: klipperkiosk.reorder_tabs
data:
  ids:
    - site-2
    - site-1
```

### `klipperkiosk.navigate`
Load a temporary URL without changing saved tabs (`POST /api/navigate`).
```yaml
action: klipperkiosk.navigate
data:
  url: http://pi-klipper.local/console
```

### `klipperkiosk.set_pin`
Change the tablet's Settings PIN (`POST /api/pin`) and automatically update the PIN stored in Home Assistant.
```yaml
action: klipperkiosk.set_pin
data:
  pin: "5678"
```

### `klipperkiosk.send_ir`
Transmit an IR signal (`POST /api/ir/transmit`) using either a raw microsecond `pattern` or `pronto_hex`.
```yaml
# Raw microsecond pattern
action: klipperkiosk.send_ir
data:
  frequency: 38000
  pattern: [9000, 4500, 560, 560, 560, 1690, 560]
  repeat: 1
  repeat_delay_ms: 100
```
```yaml
# Pronto Hex
action: klipperkiosk.send_ir
data:
  pronto_hex: "0000 006D 0002 0000 0157 00AC 0015 0016"
```

