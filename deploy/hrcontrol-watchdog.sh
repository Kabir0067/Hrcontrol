#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  SoftClub HR Control — watchdog (ҳар 2 дақиқа аз hrcontrol-watchdog.timer)
#
#  Ҳар чизеро, ки вайрон ё нест шудааст, худаш барқарор мекунад:
#    1. корбари системавии hrcontrol
#    2. сирҳо  /etc/hrcontrol/hrcontrol.env      ← сейф (/var/backups/hrcontrol)
#    3. код    /opt/hrcontrol                    ← git-mirror дар сейф
#       venv   /opt/hrcontrol/.venv              ← pip аз requirements.txt
#    4. файлҳои systemd                          ← аз код
#    5. база   /var/lib/hrcontrol/softclub.db    ← навтарин нусхаи эҳтиётӣ
#    6. хидмат: enable, start, health-check (2 хато пай дар пай → restart)
#    7. nginx: enable, start, конфиги сайт ва пайванди sites-enabled
#
#  Таъмир (ки watchdog халал нарасонад):  sudo touch /etc/hrcontrol/maintenance
#  Баъди таъмир:                          sudo rm /etc/hrcontrol/maintenance
# ═══════════════════════════════════════════════════════════════════
set -u

APP=hrcontrol
CODE=/opt/hrcontrol
DATA=/var/lib/hrcontrol
ETC=/etc/hrcontrol
VAULT=/var/backups/hrcontrol
REPO=$VAULT/repo.git
HEALTH_URL="http://127.0.0.1:8901/api/health?strict=1"
NGX_AVAIL=/etc/nginx/sites-available/hrcontrol
NGX_LINK=/etc/nginx/sites-enabled/hrcontrol
FAILS_FILE=/run/hrcontrol-watchdog.fails

log() { logger -t hrcontrol-watchdog -- "$*"; echo "$*"; }

[ -e "$ETC/maintenance" ] && exit 0

restart=0

# 1. корбар
if ! id -u "$APP" >/dev/null 2>&1; then
    useradd --system --home-dir "$DATA" --no-create-home --shell /usr/sbin/nologin "$APP" \
        && log "корбари $APP нест шуда буд → барқарор шуд" && restart=1
fi

# 2. сирҳо
install -d -m 755 "$VAULT"
if [ ! -s "$ETC/hrcontrol.env" ] && [ -s "$VAULT/hrcontrol.env" ]; then
    install -d -m 750 -o root -g "$APP" "$ETC"
    install -m 640 -o root -g "$APP" "$VAULT/hrcontrol.env" "$ETC/hrcontrol.env"
    log "hrcontrol.env нест шуда буд → аз сейф барқарор шуд"
    restart=1
elif [ -s "$ETC/hrcontrol.env" ] && ! cmp -s "$ETC/hrcontrol.env" "$VAULT/hrcontrol.env"; then
    install -m 600 "$ETC/hrcontrol.env" "$VAULT/hrcontrol.env"
fi

# 3. код ва venv
if [ ! -f "$CODE/main.py" ] && [ -d "$REPO" ]; then
    rev=$(git -C "$REPO" rev-parse -q --verify refs/deployed || git -C "$REPO" rev-parse main)
    rm -rf "$CODE.restore"
    if git clone -q "$REPO" "$CODE.restore" && git -C "$CODE.restore" reset -q --hard "$rev"; then
        [ -e "$CODE/.venv" ] && mv "$CODE/.venv" "$CODE.restore/.venv"
        [ -e "$CODE" ] && mv "$CODE" "$CODE.broken.$(date +%s)"
        mv "$CODE.restore" "$CODE"
        log "код нест шуда буд → аз git-mirror барқарор шуд (${rev:0:8})"
        restart=1
    fi
fi
if [ -f "$CODE/requirements.txt" ] && ! "$CODE/.venv/bin/python3" -c "import telebot, aiohttp" >/dev/null 2>&1; then
    rm -rf "$CODE/.venv"
    if python3 -m venv "$CODE/.venv" && "$CODE/.venv/bin/pip" install -q -r "$CODE/requirements.txt"; then
        sha256sum "$CODE/requirements.txt" | cut -c1-16 > "$CODE/.venv/.req"
        log "venv вайрон/нест буд → аз нав сохта шуд"
        restart=1
    fi
fi

# 4. файлҳои systemd
for unit in hrcontrol.service hrcontrol-watchdog.service hrcontrol-watchdog.timer; do
    if [ ! -f "/etc/systemd/system/$unit" ] && [ -f "$CODE/deploy/$unit" ]; then
        install -m 644 "$CODE/deploy/$unit" "/etc/systemd/system/$unit"
        systemctl daemon-reload
        log "$unit нест шуда буд → барқарор шуд"
        restart=1
    fi
done
systemctl is-enabled --quiet hrcontrol-watchdog.timer 2>/dev/null || systemctl enable --now hrcontrol-watchdog.timer >/dev/null 2>&1

# 5. база
install -d -m 750 -o "$APP" -g "$APP" "$DATA" "$DATA/backups"
install -d -m 750 -o root -g "$APP" "$VAULT/db"
if [ ! -s "$DATA/softclub.db" ]; then
    latest=$(ls -t "$DATA"/backups/softclub_*.db "$VAULT"/db/softclub_*.db 2>/dev/null | head -1)
    if [ -n "$latest" ]; then
        rm -f "$DATA/softclub.db-wal" "$DATA/softclub.db-shm"
        install -m 640 -o "$APP" -g "$APP" "$latest" "$DATA/softclub.db"
        log "база нест шуда буд → аз $latest барқарор шуд"
        restart=1
    fi
fi
# Сейф: нусхаи ҳаррӯза берун аз /var/lib (14-тои охирин)
daily=$(ls -t "$DATA"/backups/softclub_*_daily.db 2>/dev/null | head -1)
if [ -n "$daily" ] && [ ! -e "$VAULT/db/$(basename "$daily")" ]; then
    install -m 640 -o root -g "$APP" "$daily" "$VAULT/db/"
    ls -t "$VAULT"/db/softclub_*_daily.db 2>/dev/null | tail -n +15 | xargs -r rm -f
fi

# 6. хидмат
if ! systemctl is-enabled --quiet "$APP"; then
    systemctl enable "$APP" >/dev/null 2>&1 && log "хидмат disabled буд → enable шуд"
fi
if [ "$restart" = 1 ]; then
    systemctl reset-failed "$APP" >/dev/null 2>&1
    systemctl restart "$APP" && log "пас аз барқароркунӣ → restart"
    rm -f "$FAILS_FILE"
elif ! systemctl is-active --quiet "$APP"; then
    log "хидмат кор намекард ($(systemctl is-active "$APP")) → start"
    systemctl reset-failed "$APP" >/dev/null 2>&1
    systemctl start "$APP"
    rm -f "$FAILS_FILE"
else
    since=$(date -d "$(systemctl show -p ActiveEnterTimestamp --value "$APP")" +%s 2>/dev/null || echo 0)
    if [ $(( $(date +%s) - since )) -gt 120 ]; then          # ба оғози нав вақт медиҳем
        if curl -fsS -m 15 -o /dev/null "$HEALTH_URL"; then
            rm -f "$FAILS_FILE"
        else
            fails=$(( $(cat "$FAILS_FILE" 2>/dev/null || echo 0) + 1 ))
            echo "$fails" > "$FAILS_FILE"
            log "health-check хато ($fails/2)"
            if [ "$fails" -ge 2 ]; then
                log "бот ҷавоб намедиҳад → restart"
                systemctl restart "$APP"
                rm -f "$FAILS_FILE"
            fi
        fi
    fi
fi

# 7. nginx (пас аз reboot ҳатман бояд барояд)
if command -v nginx >/dev/null 2>&1; then
    if ! systemctl is-enabled --quiet nginx; then
        systemctl enable nginx >/dev/null 2>&1 && log "nginx disabled буд → enable шуд"
    fi
    if [ ! -f "$NGX_AVAIL" ] && [ -f "$CODE/deploy/nginx-hrcontrol.conf" ]; then
        install -m 644 "$CODE/deploy/nginx-hrcontrol.conf" "$NGX_AVAIL"
        log "конфиги nginx нест шуда буд → аз код барқарор шуд"
    fi
    if [ -f "$NGX_AVAIL" ] && [ ! -e "$NGX_LINK" ]; then
        ln -s "$NGX_AVAIL" "$NGX_LINK"
        if nginx -t >/dev/null 2>&1; then
            systemctl reload nginx && log "пайванди nginx нест шуда буд → барқарор шуд"
        else
            rm -f "$NGX_LINK"
            log "пайванди nginx нест, вале 'nginx -t' хато медиҳад (конфиги каси дигар) → барқарор накардам"
        fi
    fi
    if ! systemctl is-active --quiet nginx && nginx -t >/dev/null 2>&1; then
        systemctl start nginx && log "nginx истода буд → start"
    fi
fi

exit 0
