# Arma Reforger Server Management Panel

A lightweight, self-hosted web panel for managing your **Arma Reforger dedicated server** on Linux. The all-in-one installer sets up everything from scratch — SteamCMD, the game server, and the panel — on a clean Ubuntu VPS.

> **Live demo:** [demoarma.mateuszgolebiewski.pl](https://demoarma.mateuszgolebiewski.pl) — password: `demo`

---

## Features

- **One-command install** — sets up SteamCMD, downloads the Arma Reforger server and installs the panel automatically
- **Server control** — Start, stop and restart your server from the browser, and force stop a server that doesn't answer a normal stop
- **Real-time monitoring** — Live CPU and RAM charts updated every 3 seconds
- **Live log streaming** — Server console logs with aligned columns and colour-coded output (errors, warnings, network events)
- **Log history** — Every past server session, each downloadable as a zip of its console, error and script logs
- **Players** — Player count read from the server's A2S (Steam query) port, and the player number, name and identity ID of each connected player read over RCON when it is enabled in `config.json`, with a button to kick a player; shown as unavailable rather than guessed when the server doesn't answer
- **Mission selector** — 41 built-in missions including all vanilla and RHS — Status Quo scenarios
- **Gameplay settings** — View distances, third-person view, voice chat UI, BattlEye, join queue size and AI limit
- **Persistence** — Keep the server's save defaults, set custom autosave settings or turn saving off, and flush the session saves
- **Mod sets** — Keep several named mod lists and pick the one the server loads at its next start; add, remove or import Workshop mods in each, and delete downloaded mods from the server's disk
- **Config editor** — Edit server name, scenario, passwords, max players, server browser visibility and crossplay without touching the filesystem; changes in any card are saved together from a bar at the bottom of the page
- **config.json editor** — Edit the whole `config.json` for the settings the cards don't cover (ACE settings, for example), checked as you type before it can be saved
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

The generated `config.json` enables RCON on `127.0.0.1` with a random password, so the panel can show the connected players and kick them (see [Player names](#player-names-rcon)).

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
    "permission": "admin"
}
```

The full install writes this block with a random password. On an existing server, add it at the top level, next to `a2s` (the config.json editor at the bottom of the panel does it), and restart the server. The password needs at least 3 characters and no spaces. With `127.0.0.1` the port is only reachable from the server itself. The panel reads the address, port and password from `config.json`, so nothing has to be added to `config.env`.

The names are only shown when the server's answer is complete and lists as many players as the A2S count. Otherwise the Players card keeps the count and says why, and `journalctl -u arma-panel` has the details.

Each row starts with the player's number in the server's `#players` list, which is what `#kick` takes. The Kick button needs `"permission": "admin"`: with `monitor` (what installs before this version wrote), RCON can only read, and the Players card says so. Before kicking, the panel checks that the number still belongs to the same identity ID, since numbers are reused when players leave and join. The kick only counts as done once the player has left the list; a kicked player can join again (it isn't a ban).

### Force stop

When the server stops responding, **Force stop** (under the Start / Stop / Restart buttons) sends SIGINT to every running `ArmaReforgerServer` process, then SIGKILL to the ones still there after 10 seconds. The game may not get to save, so it's only for when Stop doesn't work. If the server was started by the `arma-server` systemd service, which restarts it after a crash, the service may start it again within 10 seconds: `sudo systemctl stop arma-server` keeps it stopped.

### Saving changes

The configuration cards (server, gameplay, persistence) have no save button of their own: as soon as something differs from the stored file, a bar at the bottom of the page lists the cards with changes, and **Save changes** writes them all in one go. Every card is checked first and nothing is written if one of them is refused. The browser asks for confirmation before leaving the page with unsaved changes.

### config.json editor

The **config.json** card at the bottom of the panel edits the whole file, for the settings the cards don't cover, such as the [ACE settings](https://anvil.acemod.org/components/medical/) in `game.gameProperties.missionHeader`. The text is checked as you type, against the keys documented on the [Bohemia wiki](https://community.bistudio.com/wiki/Arma_Reforger:Server_Config):

- **Errors** block the save: invalid JSON, a key given twice, a documented key with the wrong type or out of its range, a missing `game.scenarioId`, an RCON password that is too short or has spaces, two sockets on the same port, an invalid mod entry.
- **Warnings** don't: keys the wiki doesn't document (a newer server version or a mod may use them, so they can't be told from a typo), a scenario the panel doesn't know.

The server has the final word when it starts: its console log reports what it refuses. The editor can't be used while a card has unsaved changes, and the other way round, since both write the same file. If the file changed since the editor loaded it (from another tab or a mod set), the save is refused rather than overwriting that change. The editor also opens a `config.json` that doesn't parse, so it can repair one.

### config.json backups

Before each change it makes to the server's `config.json`, from the cards or the editor, the panel copies the current file to `config-backups/` in the panel directory and keeps the 20 most recent copies. To roll back, copy one of them over `config.json`. If `config.json` can't be parsed (e.g. after a manual edit), the panel shows a warning and the cards refuse to save until the file is fixed, in the editor for example.

### Mod sets

Mod sets are stored in `modsets/` in the panel directory: one `<id>.json` file per set (`{"name": ..., "mods": [...]}`) and an `active` file holding the id of the set in use. The server itself only reads `game.mods` in `config.json`: choosing a set copies its mods there, and changes to the set in use are written to both. On first start the panel creates a "Default" set from the mods already in `config.json`. If `game.mods` is later edited by hand, the Mods card shows that it no longer matches the set in use.

Export downloads the selected set as a JSON file in the import format. Mods that don't name a version get the version the server has downloaded, read from the addon's `meta` file in `WORKSHOP_DIR`. Mods the server hasn't downloaded yet are exported without a version, and the panel lists them.

**Downloaded on the server**, at the end of the Mods card, lists the mods in `WORKSHOP_DIR` with their size and the sets that hold them. **Remove** deletes a mod's folder to free disk space. It is refused while the server runs, and for a mod in `config.json`'s list (the set in use), which the server would download again at its next start. It downloads a removed mod again too when another mod in use depends on it.

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
│   ├── img/                     # Default banner logo
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
