# Arma Reforger Server Management Panel

A lightweight, self-hosted web panel for managing your **Arma Reforger dedicated server** on Linux. The all-in-one installer sets up everything from scratch — SteamCMD, the game server, and the panel — on a clean Ubuntu VPS.

> **Live demo:** [demoarma.mateuszgolebiewski.pl](https://demoarma.mateuszgolebiewski.pl) — password: `demo`

---

## Features

- **One-command install** — sets up SteamCMD, downloads the Arma Reforger server and installs the panel automatically
- **Server control** — Start, stop and restart your server from the browser
- **Real-time monitoring** — Live CPU and RAM charts updated every 3 seconds
- **Live log streaming** — Server console logs with aligned columns and colour-coded output (errors, warnings, network events)
- **Log history** — Every past server session, each downloadable as a zip of its console, error and script logs
- **Players** — Player count read from the server's A2S (Steam query) port, and the names and identity IDs of connected players read over RCON when it is enabled in `config.json`; shown as unavailable rather than guessed when the server doesn't answer
- **Mission selector** — 41 built-in missions including all vanilla and RHS — Status Quo scenarios
- **Gameplay settings** — View distances, third-person view, voice chat UI, BattlEye, join queue size and AI limit
- **Persistence** — Keep the server's save defaults, set custom autosave settings or turn saving off, and flush the session saves
- **Mod sets** — Keep several named mod lists and pick the one the server loads at its next start; add, remove or import Workshop mods in each
- **Config editor** — Edit server name, scenario, passwords, max players, server browser visibility and crossplay without touching the filesystem
- **PWA support** — Installable as a native app on Android and iOS
- **English and French** — Switch the interface language from the panel header or the login screen
- **Single config file** — All settings in one `config.env`, no code editing required

---

## Requirements

| Component | Requirement |
|-----------|-------------|
| OS | Ubuntu 20.04 / 22.04 / 24.04 |
| Architecture | x86_64 |
| RAM | 4 GB minimum, 8 GB recommended |
| Disk | 20 GB free (Arma server is ~15 GB) |
| Python | 3.10+ (installed automatically) |

---

## Installation

### Option A — Full install (recommended for a fresh VPS)

Sets up everything: SteamCMD, Arma Reforger Dedicated Server, and the management panel.

```bash
git clone https://github.com/mateuszgolebiewski-code/arma-reforger-panel.git
cd arma-reforger-panel
sudo bash install.sh
```

The installer will ask you for:
- System username (default: `arma`)
- Server name, game password, admin password
- Max players, game port, public IP
- Panel web password and port
- Optionally, a domain name for the panel (see [HTTPS / Domain](#https--domain-optional))
- Optionally, whether to set up the UFW firewall (see [Firewall](#firewall-optional))

After ~15 minutes your server is running and the panel is accessible at:
```
http://YOUR_SERVER_IP:8888
```
or at `https://your.domain` if you gave one.

The generated `config.json` enables RCON on `127.0.0.1` with a random password, so the panel can show the names of the connected players (see [Player names](#player-names-rcon)).

---

### Option B — Panel only (server already installed)

If you already have Arma Reforger server running and only want the web panel:

```bash
git clone https://github.com/mateuszgolebiewski-code/arma-reforger-panel.git
cd arma-reforger-panel
sudo bash install.sh --panel-only
```

The installer will ask for your existing server paths (`SERVER_DIR`, `config.json`, log directory).

---

### Option C — Update panel files only

After pulling a new version from GitHub:

```bash
git pull
sudo bash install.sh --update
```

This copies updated panel files and restarts the service. Your `config.env` is preserved.

---

## Configuration

All settings live in `config.env` (created automatically by the installer):

```env
# Password for the panel web UI
PANEL_PASSWORD=changeme

# Port the panel listens on
PANEL_PORT=8888

# Address the panel listens on (127.0.0.1 when nginx serves it)
PANEL_HOST=0.0.0.0

# true when every request comes through nginx on this machine
PANEL_BEHIND_PROXY=false

# Path to your Arma Reforger server binary directory
SERVER_DIR=/home/arma/server

# Full path to your server config.json
SERVER_CONFIG=/home/arma/server/config.json

# Arma Reforger log directory
LOG_DIR=/home/arma/.config/ArmaReforger/logs

# Server FPS cap (passed as -maxFPS on startup)
MAX_FPS=60
```

After editing, restart the panel:
```bash
sudo systemctl restart arma-panel
```

### Player names (RCON)

The player count comes from the server's A2S port. The names and identity IDs of the connected players are read over RCON, which the server only starts when `config.json` has an `rcon` block with a password:

```json
"rcon": {
    "address": "127.0.0.1",
    "port": 19999,
    "password": "a-random-password",
    "permission": "monitor"
}
```

The full install writes this block with a random password. On an existing server, add it at the top level, next to `a2s`, and restart the server. The password needs at least 3 characters and no spaces. With `127.0.0.1` the port is only reachable from the server itself, and `monitor` is read-only. The panel reads the address, port and password from `config.json`, so nothing has to be added to `config.env`.

The names are only shown when the server's answer is complete and lists as many players as the A2S count. Otherwise the Players card keeps the count and says why, and `journalctl -u arma-panel` has the details.

### config.json backups

Before each change it makes to the server's `config.json`, the panel copies the current file to `config-backups/` in the panel directory and keeps the 20 most recent copies. To roll back, copy one of them over `config.json`. If `config.json` can't be parsed (e.g. after a manual edit), the panel shows a warning and refuses to save until the file is fixed.

### Mod sets

Mod sets are stored in `modsets/` in the panel directory: one `<id>.json` file per set (`{"name": ..., "mods": [...]}`) and an `active` file holding the id of the set in use. The server itself only reads `game.mods` in `config.json`: choosing a set copies its mods there, and changes to the set in use are written to both. On first start the panel creates a "Default" set from the mods already in `config.json`. If `game.mods` is later edited by hand, the Mods card shows that it no longer matches the set in use.

Export downloads the selected set as a JSON file in the import format. Mods that don't name a version get the version the server has downloaded, read from the addon's `meta` file in `WORKSHOP_DIR`. Mods the server hasn't downloaded yet are exported without a version, and the panel lists them.

---

## Useful Commands

```bash
# ── Panel ──────────────────────────────────────────────────
sudo systemctl status arma-panel      # check panel status
sudo systemctl restart arma-panel     # restart panel
sudo journalctl -u arma-panel -f      # live panel logs

# ── Arma Server ────────────────────────────────────────────
sudo systemctl start arma-server      # start server
sudo systemctl stop arma-server       # stop server
sudo systemctl status arma-server     # check server status
sudo journalctl -u arma-server -f     # live server logs

# ── Update ─────────────────────────────────────────────────
git pull && sudo bash install.sh --update
```

---

## HTTPS / Domain (optional)

The full and panel-only installs ask whether to serve the panel on a domain. Before answering yes, point the domain's DNS `A` record to the server and make sure ports 80 and 443 can be reached. The installer then:

- installs nginx and certbot, and writes `/etc/nginx/sites-available/<domain>`, which forwards to the panel;
- disables nginx's default welcome page;
- allows 80/tcp and 443/tcp in UFW if UFW is active or the installer sets it up (an inactive firewall is otherwise left alone);
- gets a Let's Encrypt certificate, redirects HTTP to HTTPS and sends an HSTS header, so browsers only use HTTPS for the domain from then on. `certbot.timer` renews the certificate;
- makes the panel listen on `127.0.0.1` only (`PANEL_HOST`), so it can't be reached around nginx, and sets `PANEL_BEHIND_PROXY=true`.

If the certificate can't be obtained (usually because DNS doesn't point to the server yet), the panel stays on plain HTTP through nginx and the installer prints the `certbot` command to run once DNS is fixed.

To put an existing install behind nginx by hand, use the same site as the installer:

```nginx
server {
    listen 80;
    listen [::]:80;
    server_name panel.example.com;

    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:8888;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

Then get the certificate with `sudo certbot --nginx -d panel.example.com --redirect --hsts`, add `PANEL_HOST=127.0.0.1` and `PANEL_BEHIND_PROXY=true` to `config.env`, and restart the panel. Without `PANEL_BEHIND_PROXY`, the panel sees every visitor as nginx itself, so one person's failed logins would lock everyone out. `install.sh --update` reminds you of this when it finds such a site.

If you use **HestiaCP**, add a subdomain through its web interface — it handles SSL automatically. The two `config.env` settings above apply there too.

---

## Firewall (optional)

The full and panel-only installs ask whether to set up the firewall. Only UFW is supported. If you answer yes, the installer installs UFW if it's missing, then:

- allows SSH on the ports sshd listens on. It asks you to confirm them, since a wrong port locks you out of the server;
- allows the game port and the A2S query port (UDP). For an existing server (`--panel-only`), they are read from its `config.json`, and if that fails the firewall is left alone;
- allows the panel port (TCP), or 80/tcp and 443/tcp when the panel is served on a domain;
- sets the default policies to `deny incoming` and `allow outgoing`, and turns UFW on.

Every other incoming port is blocked, so on a machine that runs other services, answer no or add their rules first. Rules already in UFW are kept. RCON listens on `127.0.0.1` only and needs no rule.

If you answer no, the firewall isn't touched and the installer prints the `ufw` commands to run yourself, including the SSH rule and the default policies.

---

## Project Structure

```
arma-reforger-panel/
├── app.py                   # Entry point started by systemd
├── arma_panel/              # Flask application
│   ├── __init__.py              # App factory
│   ├── config.py                # Settings loaded from config.env
│   ├── i18n.py                  # Translation helpers
│   ├── translations/            # en.json, fr.json
│   ├── security.py              # Auth, CSRF, rate limiting, headers
│   ├── routes/                  # Blueprints: pages, auth, status, server, config, mods, persistence, scenarios
│   └── services/                # Server process, config.json, metrics, logs, mods and mod sets, saves, scenario discovery
├── templates/
│   ├── index.html               # Main panel UI
│   ├── login.html               # Login screen
│   └── partials/                # Language switch, embedded translations
├── static/
│   ├── css/                     # Stylesheets
│   ├── js/                      # Front-end scripts (ES modules)
│   ├── fonts/                   # Marianne web fonts
│   ├── img/                     # Commando Kieffer logo
│   ├── manifest.json            # PWA manifest
│   ├── service-worker.js        # PWA service worker
│   ├── icon-192.png             # App icon
│   └── icon-512.png             # App icon (large)
├── tests/                   # Unit tests (standard library unittest)
├── config.env               # Your local config (excluded from git)
├── config.env.example       # Config template
├── install.sh               # All-in-one installer
└── README.md
```

## Tests

The tests need Flask and bcrypt, which the installer already provides on the server:

```bash
python3 -m unittest discover tests
```

---

## RHS — Status Quo

The panel includes mission IDs for all RHS — Status Quo scenarios. They appear automatically in the mission dropdown once you add the [RHS mod](https://reforger.armaplatform.com/workshop/595F2BF2F44836FB-RHS-Status-Quo) to your server.

---

## Contributing

Pull requests and issues are welcome. Open an issue on GitHub if you run into problems or want to suggest a feature.

---

## License

MIT — free to use, modify and distribute.

---

*Built by [Mateusz Gołębiewski](https://mateuszgolebiewski.pl)*
