#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  SoftClub HR Control — watchdog (ҳар 2 дақиқа аз hrcontrol-watchdog.timer)
#
#  1. Хидмат disabled шуда бошад  → enable (то пас аз reboot худаш биёяд)
#  2. Хидмат кор накунад          → start
#  3. /api/health?strict=1 2 бор пай дар пай хато → restart
#     (раванд зинда, вале polling-и Telegram овезон — ин ҳам «мурда» аст)
#  4. Пайванди nginx (sites-enabled/hrcontrol) нест шуда бошад → барқарор
#
#  Таъмир (ки watchdog халал нарасонад):  touch ~/Hrcontrol/.maintenance
#  Баъди таъмир:                          rm ~/Hrcontrol/.maintenance
# ═══════════════════════════════════════════════════════════════════
set -u

APP=hrcontrol
APP_DIR=/home/kabir0067/Hrcontrol
HEALTH_URL="http://127.0.0.1:8901/api/health?strict=1"
NGX_AVAIL=/etc/nginx/sites-available/hrcontrol
NGX_LINK=/etc/nginx/sites-enabled/hrcontrol
FAILS_FILE=/run/hrcontrol-watchdog.fails

log() { logger -t hrcontrol-watchdog -- "$*"; echo "$*"; }

[ -e "$APP_DIR/.maintenance" ] && exit 0

# 1. autostart
if ! systemctl is-enabled --quiet "$APP"; then
    systemctl enable "$APP" >/dev/null 2>&1 && log "хидмат disabled буд → enable шуд"
fi

# 2–3. раванд ва саломатӣ
if ! systemctl is-active --quiet "$APP"; then
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

# 4. nginx
if [ -f "$NGX_AVAIL" ] && [ ! -e "$NGX_LINK" ]; then
    ln -s "$NGX_AVAIL" "$NGX_LINK"
    if nginx -t >/dev/null 2>&1; then
        systemctl reload nginx && log "пайванди nginx нест шуда буд → барқарор шуд"
    else
        rm -f "$NGX_LINK"
        log "пайванди nginx нест, вале 'nginx -t' хато медиҳад (конфиги каси дигар) → барқарор накардам"
    fi
fi

exit 0
