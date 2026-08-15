# Vista Security — self-hosted Envisalink / Vista 20P monitor & control

A two-container, self-hosted app for monitoring and controlling an Ademco/Honeywell
Vista 20P alarm panel through an **Envisalink 4** module over its TPI interface.

- **`api`** — FastAPI. Holds a persistent async TCP link to the Envisalink (TPI, port 4025),
  exposes a REST API + a WebSocket live feed, persists an event log / zone config / push
  subscriptions in SQLite, and sends Web Push (VAPID) notifications.
- **`web`** — React + Vite PWA (installable, offline shell, service worker) served by nginx,
  which proxies `/api` to the `api` container by service name.

The TPI client is implemented strictly against the *EnvisaLink Vista TPI Programmer's Document
v1.03* (Honeywell firmware), targeting the Envisalink 4 (128 zones).

---

## Quick start

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:

| Variable       | Purpose                                                              |
| -------------- | ------------------------------------------------------------------- |
| `EVL_HOST`     | Envisalink IP on your LAN                                            |
| `EVL_PORT`     | TPI port (default `4025`)                                            |
| `EVL_PASSWORD` | Envisalink TPI password (same as its local web page; ≤10 chars EVL4) |
| `APP_SECRET`   | **Required.** Signs sessions + encrypts stored secrets. See below.  |
| `WEB_PORT`     | Host port the UI is published on (behind your HTTPS proxy)          |

Generate a strong `APP_SECRET`:

```bash
openssl rand -hex 32
```

> `APP_SECRET` derives the encryption key for the panel user code + Envisalink password
> stored in the DB, and signs the login cookie. **Changing it later invalidates stored
> secrets and sessions.**

### 2. Run

```bash
docker compose up -d --build
```

The UI is on `http://<host>:${WEB_PORT}` (default `8080`). See the reverse-proxy note below —
**HTTPS is required** for Web Push and for service workers on iOS.

### 3. First-run setup (in the UI)

1. Open the app — you'll be prompted to **create a password** (one-time setup).
2. Go to **Settings → Envisalink connection** and confirm the host/port, set the TPI
   password if not provided via env, and enter your **panel user code** (stored encrypted;
   used to build arm/disarm keystrokes).
3. Go to **Settings → Notifications** and tap **Enable push on this device** (grant the
   browser permission), then **Send test notification** to verify.

---

## VAPID keys (Web Push)

**You don't generate these manually.** On first startup the `api` container creates a VAPID
key pair (EC P-256) and stores it in the SQLite DB. The frontend fetches the public key from
`GET /api/push/public-key` when you enable notifications. Keys persist across restarts on the
`vista-data` volume.

If you ever need to rotate them, delete the `vapid.public` / `vapid.private` rows from the
`settings` table (or reset the volume) and restart; all existing push subscriptions must then
re-subscribe.

### Honest limitation on iOS

Alarm notifications use every attention-grabbing option the Web Push / Notifications API
allows: `requireInteraction: true` (persistent banner), a distinct vibration pattern, urgent
styling, and retriggering while an alarm stays active. They **cannot bypass iOS Do Not
Disturb / Focus** — Apple restricts true "critical alerts" to native apps with a special
entitlement that is not available to Safari Web Push / PWAs. This app does not fake it.

iOS also only delivers Web Push to PWAs **added to the Home Screen** (Share → Add to Home
Screen) and opened from there, over HTTPS.

---

## Reverse proxy / HTTPS

Point your HTTPS reverse proxy (Caddy, nginx, Traefik…) at the `web` container's published
port. All app + API traffic flows through `/` and `/api` on the same origin, so no CORS or
hardcoded IPs are involved. Example (Caddy):

```
vista.example.com {
    reverse_proxy localhost:8080
}
```

The session cookie is issued with `Secure`, so the app must be served over HTTPS.

---

## Development

Backend:

```bash
cd api
python -m venv .venv && .venv/Scripts/Activate.ps1   # PowerShell
pip install -r requirements.txt
$env:APP_SECRET="dev-secret"; $env:DB_PATH="./dev.db"; $env:EVL_HOST="192.168.1.100"
uvicorn app.main:app --reload --port 8000
```

Frontend (Vite dev server proxies `/api` to `http://localhost:8000`):

```bash
cd web
npm install
npm run dev
```

---

## Notifications — what triggers a push

Pushed:

- **State changes:** arm away, arm stay, disarm.
- **Alarms:** any alarm trip (highest priority, persistent, retriggered every 60s while active).
- **Trouble/faults:** low battery, AC power loss, system trouble, fire.

Not pushed: routine sensor activity (a door opening / motion) while disarmed — that would be
noise. It's still recorded in the event log.

---

## Protocol notes / assumptions

- Targets **Envisalink 4** (128 zones; 16-byte zone bitfield; 512-char timer dump).
- Arming keystroke macros (`code+2` away, `code+3` stay, `code+1` disarm, `code+6<zz>` bypass,
  `code+9` chime) are standard Ademco/Vista panel behavior. The TPI doc defines only the
  keystroke transport, not the panel's arming semantics.
- Ademco panels don't report zone *restore* in real time and report no zone data while armed;
  the Envisalink infers restores heuristically (may lag ~60s). See §3.5 of the TPI doc.
