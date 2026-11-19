# KlipperKiosk — Remote Management API

The Android kiosk app runs a lightweight local HTTP JSON server on port **`8765`** and advertises itself via mDNS as **`klipper-tablet.local`**, so you don't need a static IP.

The tablet's hostname and current LAN IP are also displayed at the top of the on-device **⚙ Kiosk Settings** dialog (`Remote API: http://klipper-tablet.local:8765 (<ip>)`).

---

## Base URL

```text
http://klipper-tablet.local:8765
```
*(Or `http://<tablet-ip>:8765` if your network doesn't forward mDNS.)*

---

## Authentication

All endpoints **except** `GET /api/health` require the same **Settings PIN** configured on the tablet (default: `1234`).

You can pass the PIN in any of three ways:

1. **Header (recommended):**
   ```http
   X-Kiosk-Pin: 1234
   ```
2. **Bearer token header:**
   ```http
   Authorization: Bearer 1234
   ```
3. **Query parameter:**
   ```text
   ?pin=1234
   ```

If the PIN is missing or invalid, the server returns `401 Unauthorized`:

```json
{
  "ok": false,
  "error": "Unauthorized: invalid or missing PIN"
}
```

CORS is enabled (`Access-Control-Allow-Origin: *`), so local web dashboards can call the API directly from a browser.

---

## Endpoints

### 1. Health Check (Unauthenticated)

`GET /api/health`

Checks whether the remote management server is reachable.

**Response (`200 OK`):**
```json
{
  "status": "ok",
  "app": "KlipperKiosk"
}
```

---

### 2. Get Full Kiosk Status

`GET /api/status`

Returns active tab, all tabs (with resolved IPs when available), UI lock state, Device Owner Lock Task state, and device IP/port.

**Response (`200 OK`):**
```json
{
  "activeTabId": "site-1",
  "tabs": [
    {
      "id": "site-1",
      "title": "Farz",
      "url": "http://pi-klipper.local",
      "resolvedUrl": "http://192.168.4.202"
    },
    {
      "id": "site-2",
      "title": "Klip",
      "url": "http://pi-klipper2.local"
    }
  ],
  "kioskLocked": false,
  "lockTaskMode": true,
  "deviceIp": "192.168.4.150",
  "port": 8765
}
```

---

### 3. List Tabs

`GET /api/tabs`

**Response (`200 OK`):**
```json
{
  "activeTabId": "site-1",
  "tabs": [
    {
      "id": "site-1",
      "title": "Farz",
      "url": "http://pi-klipper.local",
      "resolvedUrl": "http://192.168.4.202"
    }
  ]
}
```

---

### 4. Add a Tab

`POST /api/tabs`

Both IP addresses and `.local` mDNS hostnames are supported (automatically resolved natively on the tablet).

**Request Body:**
```json
{
  "title": "Voron",
  "url": "http://voron.local",
  "activate": true
}
```
- `url` *(required)*: Target URL (`http://` is prepended automatically if omitted).
- `title` *(optional)*: Tab label. Defaults to the hostname/URL without scheme.
- `activate` *(optional, default `true`)*: Whether to immediately switch to the new tab.

**Response (`201 Created`):**
```json
{
  "id": "tab-1763574600000",
  "title": "Voron",
  "url": "http://voron.local"
}
```

---

### 5. Update a Tab

`PUT /api/tabs/{id}`

Updates a tab's `title` and/or `url`. If the tab is currently active and its URL changed, it is re-resolved and reloaded automatically.

**Request Body:**
```json
{
  "title": "Voron 2.4",
  "url": "http://voron24.local"
}
```

**Response (`200 OK`):** Returns the updated tab JSON, or `404 Not Found` if `{id}` does not exist.

---

### 6. Delete a Tab

`DELETE /api/tabs/{id}`

Deletes the tab by ID. If it was active, the kiosk switches to the first remaining tab.

**Response (`200 OK`):**
```json
{
  "ok": true,
  "message": "Tab deleted"
}
```

---

### 7. Switch Active Tab

`POST /api/tabs/{id}/activate`

Switches the kiosk to the specified tab ID.

**Response (`200 OK`):**
```json
{
  "ok": true,
  "message": "Tab activated"
}
```

---

### 8. Reorder Tabs

`POST /api/tabs/reorder`

Reorders the top tab strip according to the provided array of tab IDs. Any omitted existing tabs are appended at the end.

**Request Body:**
```json
{
  "ids": ["site-2", "site-1"]
}
```

**Response (`200 OK`):** Returns the updated `{ "activeTabId", "tabs" }` payload.

---

### 9. Reset Tabs to `sites.ts` Defaults

`POST /api/tabs/reset`

Clears custom saved tabs and restores the default list bundled from `src/config/sites.ts`.

**Response (`200 OK`):** Returns the restored `{ "activeTabId", "tabs" }` payload.

---

### 10. Reload Active Tab

`POST /api/reload`

Clears the cached hostname resolution for the active tab, re-resolves DNS/mDNS, and reloads the page.

**Response (`200 OK`):**
```json
{
  "ok": true,
  "message": "Reloading active tab"
}
```

---

### 11. Navigate Active View (Temporary URL)

`POST /api/navigate`

Loads a URL in the active WebView without permanently modifying the saved tab list.

**Request Body:**
```json
{
  "url": "http://pi-klipper.local/console"
}
```

**Response (`200 OK`):**
```json
{
  "ok": true,
  "message": "Navigating to http://pi-klipper.local/console"
}
```

---

### 12. Hide / Show Top Bar Controls (`↻` and `⚙`)

`POST /api/kiosk/lock`

Hides or shows the reload (`↻`) and settings (`⚙`) buttons in the top-right corner of the tab bar. When hidden, tapping the active tab 5× prompts for the Settings PIN.

**Request Body:**
```json
{
  "locked": true
}
```

**Response (`200 OK`):**
```json
{
  "ok": true,
  "message": "Controls hidden",
  "kioskLocked": true
}
```

---

### 13. Exit / Re-Enter Android Kiosk Lock Task Mode

- `POST /api/kiosk/exit` — Exits Device Owner Lock Task Mode, re-enables the status bar, and clears persistent Home launcher lock so you can access Android Settings.
- `POST /api/kiosk/enter` — Re-applies Device Owner kiosk lock, disables the status bar, and re-enters Lock Task Mode.

**Response (`200 OK`):**
```json
{
  "ok": true,
  "message": "Exited kiosk lock task mode"
}
```

---

### 14. Change the PIN

`POST /api/pin`

Updates the PIN used by **both** the on-device Settings screen and this Remote Management API. Persisted across reboots.

**Request Body:**
```json
{
  "pin": "5678"
}
```

**Response (`200 OK`):**
```json
{
  "ok": true,
  "message": "PIN updated"
}
```

---

### 15. Check IR Blaster Capabilities

`GET /api/ir`

Reports whether the tablet has a built-in IR emitter (`ConsumerIrManager`) and its supported carrier frequency ranges in Hz.

**Response (`200 OK`):**
```json
{
  "hasIrEmitter": true,
  "carrierFrequencies": [
    { "min": 30000, "max": 60000 }
  ]
}
```

---

### 16. Transmit IR Pulses

`POST /api/ir/transmit` *(alias: `POST /api/ir`)*

Transmits an infrared pulse pattern through the tablet's built-in IR blaster. Supports either **raw microsecond patterns** or **Pronto Hex** strings.

**Option A — Raw microsecond pattern:**
```json
{
  "frequency": 38000,
  "pattern": [9000, 4500, 560, 560, 560, 1690, 560],
  "repeat": 1,
  "repeatDelayMs": 100
}
```
- `frequency` *(optional, default `38000`)*: Carrier frequency in Hz (`10000`–`100000`).
- `pattern` *(required unless `prontoHex` is given)*: Array of positive integers representing alternating **ON / OFF** pulse durations in **microseconds**.
- `repeat` *(optional, default `1`, max `10`)*: Number of times to transmit the pattern.
- `repeatDelayMs` *(optional, default `100`, max `2000`)*: Delay in milliseconds between repeats.

**Option B — Pronto Hex string:**
```json
{
  "prontoHex": "0000 006D 0022 0002 0157 00AC 0015 0016 0015 0041",
  "repeat": 1,
  "repeatDelayMs": 100
}
```

**Response (`200 OK`):**
```json
{
  "ok": true,
  "frequency": 38000,
  "pulses": 7,
  "repeat": 1
}
```

---

## Examples

### `curl`

```bash
# Check status
curl -H "X-Kiosk-Pin: 1234" http://192.168.4.150:8765/api/status

# Add a printer tab
curl -X POST -H "X-Kiosk-Pin: 1234" -H "Content-Type: application/json" \
  -d '{"title":"Voron","url":"http://voron.local"}' \
  http://192.168.4.150:8765/api/tabs

# Switch to tab site-2
curl -X POST -H "X-Kiosk-Pin: 1234" \
  http://192.168.4.150:8765/api/tabs/site-2/activate

# Reload active tab
curl -X POST -H "X-Kiosk-Pin: 1234" \
  http://192.168.4.150:8765/api/reload

# Hide top-right controls
curl -X POST -H "X-Kiosk-Pin: 1234" -H "Content-Type: application/json" \
  -d '{"locked":true}' \
  http://192.168.4.150:8765/api/kiosk/lock

# Update PIN
curl -X POST -H "X-Kiosk-Pin: 1234" -H "Content-Type: application/json" \
  -d '{"pin":"5678"}' \
  http://192.168.4.150:8765/api/pin

# Check IR blaster capabilities
curl -H "X-Kiosk-Pin: 1234" http://192.168.4.150:8765/api/ir

# Send raw 38kHz IR pulses (microseconds)
curl -X POST -H "X-Kiosk-Pin: 1234" -H "Content-Type: application/json" \
  -d '{"frequency":38000,"pattern":[9000,4500,560,560,560,1690,560]}' \
  http://192.168.4.150:8765/api/ir/transmit

# Send Pronto Hex IR code
curl -X POST -H "X-Kiosk-Pin: 1234" -H "Content-Type: application/json" \
  -d '{"prontoHex":"0000 006D 0002 0000 0157 00AC 0015 0016"}' \
  http://192.168.4.150:8765/api/ir/transmit
```

### PowerShell

```powershell
$headers = @{ "X-Kiosk-Pin" = "1234" }

# Get status
Invoke-RestMethod -Uri "http://192.168.4.150:8765/api/status" -Headers $headers

# Reload active tab
Invoke-RestMethod -Method Post -Uri "http://192.168.4.150:8765/api/reload" -Headers $headers

# Add a new tab
Invoke-RestMethod -Method Post -Uri "http://192.168.4.150:8765/api/tabs" `
  -Headers $headers -ContentType "application/json" `
  -Body '{"title":"Voron","url":"http://voron.local"}'
```

### Testing over USB (ADB)

```powershell
adb forward tcp:8765 tcp:8765
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/status" -Headers @{ "X-Kiosk-Pin" = "1234" }
```

