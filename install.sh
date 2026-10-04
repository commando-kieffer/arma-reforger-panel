#!/bin/bash
# ============================================================
# Arma Reforger — All-in-One Installer v4.0
# https://github.com/mateuszgolebiewski-code/arma-reforger-panel
#
# Modes:
#   sudo bash install.sh              — full install (SteamCMD + server + panel)
#   sudo bash install.sh --panel-only — install panel only (server already exists)
#   sudo bash install.sh --update     — update panel files only
#
# The full and panel-only installs can also serve the panel on a custom
# domain, through nginx with a Let's Encrypt certificate.
# ============================================================

set -e

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

# ── Defaults ──────────────────────────────────────────────────────────────────
ARMA_USER="arma"
ARMA_HOME="/home/arma"
STEAM_DIR="/home/arma/steamcmd"
SERVER_DIR="/home/arma/server"
SERVER_CONFIG="/home/arma/server/config.json"
LOG_DIR="/home/arma/.config/ArmaReforger/logs"
PANEL_DIR="/home/arma/panel"
PANEL_PORT="8888"
ARMA_APP_ID="1874900"
ARMA_BINARY="ArmaReforgerServer"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RCON_PORT="19999"
DOMAIN=""
LE_EMAIL=""

# ── Input checks ──────────────────────────────────────────────────────────────
# The domain ends up in the nginx config and in file names, so only plain
# host names are accepted.
valid_domain() {
    local re='^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$'
    [[ ${#1} -le 253 && $1 =~ $re ]]
}

valid_email() {
    local re='^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$'
    [[ $1 =~ $re ]]
}

MODE="full"
if [[ "$1" == "--panel-only" ]]; then MODE="panel"; fi
if [[ "$1" == "--update" ]];      then MODE="update"; fi

# ── Header ────────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${CYAN}║   Arma Reforger — All-in-One Installer v4.0     ║${NC}"
echo -e "${BOLD}${CYAN}║   github.com/mateuszgolebiewski-code             ║${NC}"
echo -e "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}"
echo ""

if [[ "$MODE" == "full" ]];   then echo -e "  Mode: ${GREEN}Full install${NC} (SteamCMD + Arma server + Panel)"; fi
if [[ "$MODE" == "panel" ]];  then echo -e "  Mode: ${YELLOW}Panel only${NC} (skip SteamCMD and server download)"; fi
if [[ "$MODE" == "update" ]]; then echo -e "  Mode: ${CYAN}Update${NC} (panel files only)"; fi
echo ""

# ── Root check ────────────────────────────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}ERROR: Please run as root: sudo bash install.sh${NC}"
    exit 1
fi

# ── OS check ──────────────────────────────────────────────────────────────────
if ! grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
    echo -e "${YELLOW}WARNING: This installer is tested on Ubuntu 20.04/22.04/24.04.${NC}"
    read -p "  Continue anyway? [y/N]: " CONTINUE
    [[ "$CONTINUE" =~ ^[Yy]$ ]] || exit 1
fi

# ── Disk space check ──────────────────────────────────────────────────────────
if [[ "$MODE" == "full" ]]; then
    FREE_GB=$(df / | awk 'NR==2 {printf "%d", $4/1024/1024}')
    if [ "$FREE_GB" -lt 20 ]; then
        echo -e "${RED}ERROR: Not enough disk space.${NC}"
        echo -e "  Available: ${FREE_GB} GB — Required: at least 20 GB"
        echo -e "  (Arma Reforger server is ~15 GB)"
        exit 1
    fi
    echo -e "  ${GREEN}✓${NC} Disk space: ${FREE_GB} GB available"
fi

# ── UPDATE mode ───────────────────────────────────────────────────────────────
if [[ "$MODE" == "update" ]]; then
    echo -e "${YELLOW}Updating panel files...${NC}"
    if [ ! -d "$PANEL_DIR" ]; then
        echo -e "${RED}ERROR: Panel not found at ${PANEL_DIR}${NC}"
        echo -e "  Run the full installer first: sudo bash install.sh"
        exit 1
    fi
    # Read existing user from panel service
    EXISTING_USER=$(grep "^User=" /etc/systemd/system/arma-panel.service 2>/dev/null | cut -d= -f2 || echo "arma")
    PANEL_DIR_EXISTING=$(grep "^WorkingDirectory=" /etc/systemd/system/arma-panel.service 2>/dev/null | cut -d= -f2 || echo "$PANEL_DIR")
    cp    "$SCRIPT_DIR/app.py"     "$PANEL_DIR_EXISTING/"
    cp -r "$SCRIPT_DIR/arma_panel" "$PANEL_DIR_EXISTING/"
    cp -r "$SCRIPT_DIR/templates"  "$PANEL_DIR_EXISTING/"
    cp -r "$SCRIPT_DIR/static/"*   "$PANEL_DIR_EXISTING/static/"
    chown -R "$EXISTING_USER:$EXISTING_USER" "$PANEL_DIR_EXISTING"
    systemctl restart arma-panel
    echo -e "${GREEN}✓ Panel updated and restarted.${NC}"
    echo ""
    # Panels put behind nginx by hand predate PANEL_BEHIND_PROXY. config.env
    # is the user's file, so point the change out rather than making it.
    PANEL_ENV="$PANEL_DIR_EXISTING/config.env"
    EXISTING_PORT=$(grep "^PANEL_PORT=" "$PANEL_ENV" 2>/dev/null | cut -d= -f2)
    if ! grep -q "^PANEL_BEHIND_PROXY=" "$PANEL_ENV" 2>/dev/null \
        && grep -qs "proxy_pass http://127.0.0.1:${EXISTING_PORT:-8888}" /etc/nginx/sites-enabled/*; then
        echo -e "${YELLOW}nginx forwards requests to this panel, but config.env doesn't say so.${NC}"
        echo -e "  Add these lines to ${PANEL_ENV}, then run ${YELLOW}sudo systemctl restart arma-panel${NC}:"
        echo -e "    ${CYAN}PANEL_HOST=127.0.0.1${NC}"
        echo -e "    ${CYAN}PANEL_BEHIND_PROXY=true${NC}"
        echo -e "  ${DIM}Without them the login rate limit sees every visitor as nginx itself, and${NC}"
        echo -e "  ${DIM}the panel can still be reached on port ${EXISTING_PORT:-8888} without going through nginx.${NC}"
        echo ""
    fi
    exit 0
fi

# ── Collect configuration ─────────────────────────────────────────────────────
echo -e "${BOLD}━━━ Configuration ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

if [[ "$MODE" == "full" ]]; then
    read -p "  System user for Arma [arma]: " INPUT_USER
    ARMA_USER="${INPUT_USER:-arma}"
    ARMA_HOME="/home/$ARMA_USER"
    STEAM_DIR="$ARMA_HOME/steamcmd"
    SERVER_DIR="$ARMA_HOME/server"
    SERVER_CONFIG="$SERVER_DIR/config.json"
    LOG_DIR="$ARMA_HOME/.config/ArmaReforger/logs"
    PANEL_DIR="$ARMA_HOME/panel"
    echo ""
    echo -e "  ${CYAN}Game server settings:${NC}"
    read -p "  Server name [My Arma Reforger Server]: " SERVER_NAME
    SERVER_NAME="${SERVER_NAME:-My Arma Reforger Server}"
    read -p "  Game password (leave empty for public): " GAME_PASSWORD
    read -p "  Admin password: " ADMIN_PASSWORD
    while [ -z "$ADMIN_PASSWORD" ]; do
        echo -e "  ${RED}Admin password cannot be empty.${NC}"
        read -p "  Admin password: " ADMIN_PASSWORD
    done
    read -p "  Max players [32]: " MAX_PLAYERS
    MAX_PLAYERS="${MAX_PLAYERS:-32}"
    read -p "  Game port [2001]: " GAME_PORT
    GAME_PORT="${GAME_PORT:-2001}"
    read -p "  Public IP (leave empty to auto-detect): " PUBLIC_IP
    if [ -z "$PUBLIC_IP" ]; then
        PUBLIC_IP=$(curl -s ifconfig.me 2>/dev/null || curl -s api.ipify.org 2>/dev/null || echo "YOUR_SERVER_IP")
        echo -e "  ${DIM}Auto-detected: $PUBLIC_IP${NC}"
    fi
fi

echo ""
echo -e "  ${CYAN}Panel settings:${NC}"
read -p "  Panel web password: " PANEL_PASSWORD
while [ -z "$PANEL_PASSWORD" ]; do
    echo -e "  ${RED}Panel password cannot be empty.${NC}"
    read -p "  Panel web password: " PANEL_PASSWORD
done
read -p "  Panel port [8888]: " INPUT_PORT
PANEL_PORT="${INPUT_PORT:-8888}"
read -p "  Max FPS cap [60]: " MAX_FPS
MAX_FPS="${MAX_FPS:-60}"

if [[ "$MODE" == "panel" ]]; then
    echo ""
    read -p "  Arma server directory [$SERVER_DIR]: " INPUT_SERVER_DIR
    SERVER_DIR="${INPUT_SERVER_DIR:-$SERVER_DIR}"
    read -p "  config.json path [$SERVER_CONFIG]: " INPUT_CONFIG
    SERVER_CONFIG="${INPUT_CONFIG:-$SERVER_CONFIG}"
    read -p "  Log directory [$LOG_DIR]: " INPUT_LOG
    LOG_DIR="${INPUT_LOG:-$LOG_DIR}"
    read -p "  Arma system user [$ARMA_USER]: " INPUT_ARMA_USER
    ARMA_USER="${INPUT_ARMA_USER:-$ARMA_USER}"
    PANEL_DIR="/home/$ARMA_USER/panel"
fi

echo ""
echo -e "  ${CYAN}Custom domain (optional):${NC}"
echo -e "  ${DIM}Serves the panel at https://<domain> through nginx, with a Let's Encrypt${NC}"
echo -e "  ${DIM}certificate. The domain's DNS record must already point to this server and${NC}"
echo -e "  ${DIM}ports 80 and 443 must be reachable from the Internet.${NC}"
read -p "  Configure a custom domain for the panel? [y/N]: " INPUT_USE_DOMAIN
if [[ "$INPUT_USE_DOMAIN" =~ ^[Yy]$ ]]; then
    read -p "  Domain name (e.g. panel.example.com): " DOMAIN
    DOMAIN="${DOMAIN,,}"
    while ! valid_domain "$DOMAIN"; do
        echo -e "  ${RED}Enter a domain name such as panel.example.com (no http://, no path).${NC}"
        read -p "  Domain name: " DOMAIN
        DOMAIN="${DOMAIN,,}"
    done
    read -p "  Email for Let's Encrypt notices (optional): " LE_EMAIL
    while [ -n "$LE_EMAIL" ] && ! valid_email "$LE_EMAIL"; do
        echo -e "  ${RED}Enter a valid email address, or leave it empty.${NC}"
        read -p "  Email for Let's Encrypt notices (optional): " LE_EMAIL
    done
    echo -e "  ${DIM}Requesting the certificate accepts the Let's Encrypt terms of service:${NC}"
    echo -e "  ${DIM}https://letsencrypt.org/repository/${NC}"
fi

# ── Confirm ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}━━━ Summary ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
if [[ "$MODE" == "full" ]]; then
    echo -e "  System user   : ${CYAN}$ARMA_USER${NC}"
    echo -e "  Server dir    : ${CYAN}$SERVER_DIR${NC}"
    echo -e "  Server name   : ${CYAN}$SERVER_NAME${NC}"
    echo -e "  Public IP     : ${CYAN}$PUBLIC_IP:$GAME_PORT${NC}"
    echo -e "  Max players   : ${CYAN}$MAX_PLAYERS${NC}"
fi
echo -e "  Panel dir     : ${CYAN}$PANEL_DIR${NC}"
echo -e "  Panel port    : ${CYAN}$PANEL_PORT${NC}"
if [ -n "$DOMAIN" ]; then
    echo -e "  Panel URL     : ${CYAN}https://$DOMAIN${NC}"
fi
echo ""
read -p "  Proceed? [Y/n]: " CONFIRM
[[ "$CONFIRM" =~ ^[Nn]$ ]] && exit 0
echo ""

# Step numbers: the full install has 6 steps, the panel-only install 1, and
# the custom domain adds one at the end.
if [[ "$MODE" == "full" ]]; then TOTAL_STEPS=6; else TOTAL_STEPS=1; fi
PANEL_STEP=$TOTAL_STEPS
if [ -n "$DOMAIN" ]; then
    TOTAL_STEPS=$((TOTAL_STEPS + 1))
    DOMAIN_STEP=$TOTAL_STEPS
fi

# ── FULL MODE: steps 1-5 ──────────────────────────────────────────────────────
if [[ "$MODE" == "full" ]]; then

    # Step 1: System user
    echo -e "${YELLOW}[1/${TOTAL_STEPS}] Creating system user '${ARMA_USER}'...${NC}"
    if id "$ARMA_USER" &>/dev/null; then
        echo -e "      ${DIM}User already exists — skipping.${NC}"
    else
        useradd -m -s /bin/bash "$ARMA_USER"
        echo -e "      ${GREEN}✓ Done.${NC}"
    fi

    # Step 2: Dependencies
    echo -e "${YELLOW}[2/${TOTAL_STEPS}] Installing system dependencies...${NC}"
    dpkg --add-architecture i386
    apt-get update -qq
    # Install Flask and bcrypt via apt rather than pip — avoids the "Cannot
    # uninstall blinker, RECORD file not found" error caused by pip trying
    # to replace apt-managed dependencies on Ubuntu 24.04.
    apt-get install -y -qq python3 curl lib32gcc-s1 binutils python3-flask python3-bcrypt
    echo -e "      ${GREEN}✓ Done.${NC}"

    # Step 3: SteamCMD
    echo -e "${YELLOW}[3/${TOTAL_STEPS}] Installing SteamCMD...${NC}"
    mkdir -p "$STEAM_DIR"
    if [ ! -f "$STEAM_DIR/steamcmd.sh" ]; then
        curl -sqL "https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz" \
            | tar xz -C "$STEAM_DIR"
    fi
    chown -R "$ARMA_USER:$ARMA_USER" "$STEAM_DIR"
    echo -e "      ${GREEN}✓ Done.${NC}"

    # Step 4: Download Arma server
    echo -e "${YELLOW}[4/${TOTAL_STEPS}] Downloading Arma Reforger Dedicated Server (~15 GB)...${NC}"
    echo -e "      ${DIM}This may take 10–30 minutes depending on your connection.${NC}"
    mkdir -p "$SERVER_DIR"
    chown -R "$ARMA_USER:$ARMA_USER" "$SERVER_DIR"
    # NOTE: +force_install_dir MUST come before +login, otherwise SteamCMD
    # fails with "Please use force_install_dir before logon!"
    sudo -u "$ARMA_USER" "$STEAM_DIR/steamcmd.sh" \
        +force_install_dir "$SERVER_DIR" \
        +login anonymous \
        +app_update "$ARMA_APP_ID" validate \
        +quit
    echo -e "      ${GREEN}✓ Arma Reforger Server downloaded.${NC}"

    # Step 5: config.json
    echo -e "${YELLOW}[5/${TOTAL_STEPS}] Generating server config.json...${NC}"
    mkdir -p "$(dirname "$SERVER_CONFIG")"
    # RCON is how the panel lists the connected players' names and identity
    # IDs. It listens on the loopback interface only, so it needs no firewall
    # rule, and "monitor" makes it read-only: the password can't kick, ban or
    # restart. Hex keeps the password free of spaces, which RCON rejects.
    RCON_PASSWORD=$(python3 -c 'import secrets; print(secrets.token_hex(16))')
    cat > "$SERVER_CONFIG" << EOF
{
	"bindAddress": "0.0.0.0",
	"bindPort": ${GAME_PORT},
	"publicAddress": "${PUBLIC_IP}",
	"publicPort": ${GAME_PORT},
	"a2s": {
		"address": "${PUBLIC_IP}",
		"port": 17777
	},
	"rcon": {
		"address": "127.0.0.1",
		"port": ${RCON_PORT},
		"password": "${RCON_PASSWORD}",
		"permission": "monitor"
	},
	"game": {
		"name": "${SERVER_NAME}",
		"password": "${GAME_PASSWORD}",
		"passwordAdmin": "${ADMIN_PASSWORD}",
		"scenarioId": "{ECC61978EDCC2B5A}Missions/23_Campaign.conf",
		"maxPlayers": ${MAX_PLAYERS},
		"visible": true,
		"crossPlatform": true,
		"gameProperties": {
			"serverMaxViewDistance": 2500,
			"serverMinGrassDistance": 50,
			"networkViewDistance": 1000,
			"disableThirdPerson": false,
			"fastValidation": true,
			"battlEye": true
		},
		"mods": []
	}
}
EOF
    chown "$ARMA_USER:$ARMA_USER" "$SERVER_CONFIG"
    # It holds the game, admin and RCON passwords. The server and the panel
    # both run as the Arma user, and the panel keeps the mode when it saves.
    chmod 600 "$SERVER_CONFIG"
    echo -e "      ${GREEN}✓ config.json generated.${NC}"

    # Firewall is intentionally NOT touched — see post-install summary.
    # The user is expected to manage their own firewall (UFW recommended).

    # Arma server systemd service
    cat > /etc/systemd/system/arma-server.service << EOF
[Unit]
Description=Arma Reforger Dedicated Server
After=network.target

[Service]
Type=simple
User=${ARMA_USER}
WorkingDirectory=${SERVER_DIR}
ExecStart=${SERVER_DIR}/${ARMA_BINARY} -config ${SERVER_CONFIG} -loadSessionSave -maxFPS=${MAX_FPS}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    systemctl enable arma-server
    echo -e "      ${GREEN}✓ Arma server service created.${NC}"

fi  # end full mode

# ── PANEL install (both full and panel-only modes) ────────────────────────────
echo -e "${YELLOW}[${PANEL_STEP}/${TOTAL_STEPS}] Installing management panel...${NC}"

# Dependencies (panel-only mode)
if [[ "$MODE" == "panel" ]]; then
    apt-get update -qq
    apt-get install -y -qq python3 binutils python3-flask python3-bcrypt
fi

mkdir -p "$PANEL_DIR/static"

# Copy files from script directory
for f in app.py arma_panel templates; do
    if [ -e "$SCRIPT_DIR/$f" ]; then
        cp -r "$SCRIPT_DIR/$f" "$PANEL_DIR/"
    else
        echo -e "      ${RED}WARNING: $f not found in script directory.${NC}"
    fi
done
for f in manifest.json service-worker.js icon-192.png icon-512.png css js fonts img; do
    if [ -e "$SCRIPT_DIR/static/$f" ]; then
        cp -r "$SCRIPT_DIR/static/$f" "$PANEL_DIR/static/"
    fi
done

# Hash the panel password with bcrypt so it isn't stored in plaintext.
# Falls back to plaintext only if bcrypt isn't available (shouldn't happen).
PANEL_PASSWORD_HASH=$(python3 -c "
import bcrypt, sys
print(bcrypt.hashpw(sys.argv[1].encode(), bcrypt.gensalt()).decode())
" "$PANEL_PASSWORD" 2>/dev/null || true)

# Default workshop dir for the addons that the Reforger server downloads.
WORKSHOP_DIR="${ARMA_HOME}/.local/share/Arma Reforger/addons"
# Default profile dir: where Reforger writes session saves. Linux dedicated
# layout puts them under `{ARMA_HOME}/.config/ArmaReforger/profile/.save/`.
PROFILE_DIR="${ARMA_HOME}/.config/ArmaReforger/profile"

# With a custom domain, nginx is the only way in: the panel listens on the
# loopback interface and trusts the client address and scheme nginx forwards.
if [ -n "$DOMAIN" ]; then
    PANEL_HOST="127.0.0.1"
    PANEL_BEHIND_PROXY="true"
else
    PANEL_HOST="0.0.0.0"
    PANEL_BEHIND_PROXY="false"
fi

cat > "$PANEL_DIR/config.env" << EOF
# bcrypt-hashed admin password. Generated at install time.
PANEL_PASSWORD_HASH=${PANEL_PASSWORD_HASH}
PANEL_PORT=${PANEL_PORT}
PANEL_HOST=${PANEL_HOST}
PANEL_BEHIND_PROXY=${PANEL_BEHIND_PROXY}
SERVER_DIR=${SERVER_DIR}
SERVER_CONFIG=${SERVER_CONFIG}
LOG_DIR=${LOG_DIR}
WORKSHOP_DIR=${WORKSHOP_DIR}
PROFILE_DIR=${PROFILE_DIR}
MAX_FPS=${MAX_FPS}
EOF
chmod 600 "$PANEL_DIR/config.env"
chown -R "$ARMA_USER:$ARMA_USER" "$PANEL_DIR"

cat > /etc/systemd/system/arma-panel.service << EOF
[Unit]
Description=Arma Reforger Management Panel
After=network.target

[Service]
Type=simple
User=${ARMA_USER}
WorkingDirectory=${PANEL_DIR}
ExecStart=/usr/bin/python3 ${PANEL_DIR}/app.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable arma-panel
systemctl restart arma-panel

# Firewall is intentionally NOT touched — see post-install summary.

echo -e "      ${GREEN}✓ Panel installed and started.${NC}"

if [ -z "$PUBLIC_IP" ]; then
    PUBLIC_IP=$(curl -4 -s ifconfig.me 2>/dev/null || echo "YOUR_SERVER_IP")
fi

# ── Custom domain: nginx reverse proxy and Let's Encrypt certificate ─────────
HTTPS_READY=""
UFW_OPENED=""
if [ -n "$DOMAIN" ]; then
    echo -e "${YELLOW}[${DOMAIN_STEP}/${TOTAL_STEPS}] Serving the panel on ${DOMAIN} with nginx and HTTPS...${NC}"
    apt-get install -y -qq nginx certbot python3-certbot-nginx
    systemctl enable --now nginx

    # Plain HTTP site; certbot adds the HTTPS server and the redirect to it.
    # The panel doesn't use WebSockets, so no Upgrade/Connection headers.
    NGINX_SITE="/etc/nginx/sites-available/${DOMAIN}"
    cat > "$NGINX_SITE" << EOF
# Arma Reforger panel, written by install.sh.
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    # Same limit as the panel's own upload cap (mod list imports).
    client_max_body_size 2m;

    location / {
        proxy_pass http://127.0.0.1:${PANEL_PORT};
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
EOF
    ln -sf "$NGINX_SITE" "/etc/nginx/sites-enabled/${DOMAIN}"
    # The stock welcome page would answer every other name pointing at this
    # server. Only the link is removed; sites-available/default is kept.
    rm -f /etc/nginx/sites-enabled/default
    nginx -t
    systemctl reload nginx
    echo -e "      ${GREEN}✓ nginx forwards http://${DOMAIN} to the panel.${NC}"

    # Port 80 is needed for the certificate check and the redirect, 443 for
    # the panel itself. A firewall left inactive is left alone.
    if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "^Status: active"; then
        ufw allow 80/tcp >/dev/null
        ufw allow 443/tcp >/dev/null
        UFW_OPENED="yes"
        echo -e "      ${GREEN}✓ Ports 80/tcp and 443/tcp allowed in UFW.${NC}"
    fi

    # Let's Encrypt checks the domain from the Internet; a wrong DNS record is
    # the usual reason for a failure, so say so before trying.
    DOMAIN_IPS=$(getent ahostsv4 "$DOMAIN" | awk '{print $1}' | sort -u | tr '\n' ' ')
    if [[ $PUBLIC_IP =~ ^[0-9.]+$ && " $DOMAIN_IPS " != *" $PUBLIC_IP "* ]]; then
        echo -e "      ${YELLOW}${DOMAIN} resolves to: ${DOMAIN_IPS:-nothing}; this server is ${PUBLIC_IP}.${NC}"
        echo -e "      ${YELLOW}The certificate request will fail unless the DNS record points here.${NC}"
    fi

    # --redirect sends every HTTP request to HTTPS, --hsts tells browsers to
    # never use HTTP for this domain again. Renewal runs from certbot.timer.
    CERTBOT_ARGS=(--nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect --hsts)
    if [ -n "$LE_EMAIL" ]; then
        CERTBOT_ARGS+=(-m "$LE_EMAIL")
    else
        CERTBOT_ARGS+=(--register-unsafely-without-email)
    fi
    if certbot "${CERTBOT_ARGS[@]}"; then
        HTTPS_READY="yes"
        echo -e "      ${GREEN}✓ Certificate installed; HTTP now redirects to HTTPS.${NC}"
    else
        echo -e "      ${RED}The certificate could not be obtained; the panel is served over HTTP for now.${NC}"
    fi
fi

# ── Final summary ─────────────────────────────────────────────────────────────
echo ""
echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║           Installation complete!                 ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════╝${NC}"
echo ""
if [[ "$MODE" == "full" ]]; then
echo -e "  ${BOLD}Arma Reforger Server:${NC}"
echo -e "    Address : ${CYAN}${PUBLIC_IP}:${GAME_PORT}${NC}"
echo -e "    Start   : ${YELLOW}sudo systemctl start arma-server${NC}"
echo -e "    Status  : ${YELLOW}sudo systemctl status arma-server${NC}"
echo ""
fi
if [ -n "$HTTPS_READY" ]; then
    PANEL_URL="https://${DOMAIN}"
elif [ -n "$DOMAIN" ]; then
    PANEL_URL="http://${DOMAIN}"
else
    PANEL_URL="http://${PUBLIC_IP}:${PANEL_PORT}"
fi
echo -e "  ${BOLD}Management Panel:${NC}"
echo -e "    URL      : ${CYAN}${PANEL_URL}${NC}"
if [ -n "$HTTPS_READY" ]; then
echo -e "    HTTPS    : ${DIM}HTTP redirects to HTTPS; the certificate renews automatically (certbot.timer)${NC}"
elif [ -n "$DOMAIN" ]; then
echo -e "    HTTPS    : ${YELLOW}not set up yet.${NC} Once ${DOMAIN} points to ${PUBLIC_IP} and port 80 is open, run:"
echo -e "               ${YELLOW}sudo certbot ${CERTBOT_ARGS[*]}${NC}"
fi
echo -e "    Password : ${DIM}(the one you entered — it has been bcrypt-hashed in config.env)${NC}"
echo -e "    Restart  : ${YELLOW}sudo systemctl restart arma-panel${NC}"
echo -e "    Logs     : ${YELLOW}sudo journalctl -u arma-panel -f${NC}"
echo ""
echo -e "  ${BOLD}Update panel in the future:${NC}"
echo -e "    ${YELLOW}git pull && sudo bash install.sh --update${NC}"
echo ""

# Ports still to open, as "port|purpose". RCON listens on 127.0.0.1 only and
# with a domain the panel does too, so neither is listed.
FIREWALL_RULES=()
if [[ "$MODE" == "full" ]]; then
    FIREWALL_RULES+=("${GAME_PORT}/udp|Reforger game port" "17777/udp|A2S server-browser query")
fi
if [ -z "$DOMAIN" ]; then
    FIREWALL_RULES+=("${PANEL_PORT}/tcp|Panel web UI")
elif [ -z "$UFW_OPENED" ]; then
    FIREWALL_RULES+=("80/tcp|HTTP, redirected to HTTPS" "443/tcp|Panel over HTTPS")
fi
if [ ${#FIREWALL_RULES[@]} -gt 0 ]; then
    echo -e "${BOLD}${YELLOW}⚠  Firewall — action required${NC}"
    echo -e "  Open the following ports yourself so players (and you) can reach the"
    echo -e "  server and panel:"
    echo ""
    for rule in "${FIREWALL_RULES[@]}"; do
        printf "    ${CYAN}%-28s${NC} ${DIM}# %s${NC}\n" "sudo ufw allow ${rule%%|*}" "${rule#*|}"
    done
    echo -e "    ${CYAN}sudo ufw reload${NC}"
    echo ""
fi
if [ -z "$DOMAIN" ]; then
    echo -e "  ${DIM}Tip: bind the panel to 127.0.0.1 and SSH-tunnel instead of opening${NC}"
    echo -e "  ${DIM}${PANEL_PORT}/tcp publicly — even with the hashed password, HTTP is sniffable.${NC}"
    echo ""
fi
if [[ "$MODE" == "panel" ]] && ! python3 -c 'import json, sys; sys.exit(not isinstance(json.load(open(sys.argv[1])).get("rcon"), dict))' "$SERVER_CONFIG" 2>/dev/null; then
    echo -e "  ${DIM}Tip: to see the connected players' names in the panel, add an \"rcon\" block${NC}"
    echo -e "  ${DIM}to ${SERVER_CONFIG} and restart the server (README: Player names).${NC}"
    echo ""
fi
if [[ "$MODE" == "full" ]]; then
echo -e "  ${DIM}Tip: Connect in-game via Multiplayer → Direct Connect → ${PUBLIC_IP}:${GAME_PORT}${NC}"
echo ""
fi
