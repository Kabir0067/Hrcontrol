#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════
#  SoftClub HR Control — насб ва навсозӣ аз git (бо санҷиш ва rollback)
#
#    sudo hrcontrol-deploy                   # аз GitHub (агар deploy key бошад)
#    sudo hrcontrol-deploy /tmp/hr.bundle    # аз git bundle
#
#  Сохтор дар сервер:
#    /opt/hrcontrol                 — код (git), барои хидмат танҳо хондан
#    /var/lib/hrcontrol             — база, нусхаҳо, log (StateDirectory)
#    /etc/hrcontrol/hrcontrol.env   — сирҳо (root:hrcontrol 640)
#    /var/backups/hrcontrol         — сейф: repo.git, нусхаҳои база, нусхаи env
#
#  Тартиб: git → код → venv → санҷишҳо → нусхаи база → systemd/nginx →
#          restart → health-check. Агар чизе хато шавад — версияи қаблӣ бармегардад.
# ═══════════════════════════════════════════════════════════════════
set -euo pipefail

APP=hrcontrol
CODE=/opt/hrcontrol
DATA=/var/lib/hrcontrol
ETC=/etc/hrcontrol
VAULT=/var/backups/hrcontrol
REPO=$VAULT/repo.git
BRANCH=main
GITHUB=git@github.com:Kabir0067/Hrcontrol.git
KEY=$ETC/deploy_key
HEALTH_URL="http://127.0.0.1:8901/api/health?strict=1"
BUNDLE=${1:-}

log() { echo "▶ $*"; logger -t hrcontrol-deploy -- "$*" 2>/dev/null || true; }
die() { echo "✖ $*" >&2; logger -t hrcontrol-deploy -- "ХАТО: $*" 2>/dev/null || true; exit 1; }
[ "$(id -u)" = 0 ] || die "бо sudo иҷро кунед: sudo hrcontrol-deploy"
export PYTHONDONTWRITEBYTECODE=1

# watchdog дар вақти деплой халал нарасонад
install -d -m 750 "$ETC"
touch "$ETC/maintenance"
trap 'rm -f "$ETC/maintenance"' EXIT

# ── 1. корбар ва папкаҳо ───────────────────────────────────────────
id -u "$APP" >/dev/null 2>&1 || useradd --system --home-dir "$DATA" --no-create-home --shell /usr/sbin/nologin "$APP"
chgrp "$APP" "$ETC"
install -d -m 755 "$VAULT"
install -d -m 750 -o root -g "$APP" "$VAULT/db"
install -d -m 750 -o "$APP" -g "$APP" "$DATA" "$DATA/backups"
[ -s "$ETC/hrcontrol.env" ] || die "$ETC/hrcontrol.env нест. Аз deploy/hrcontrol.env.example созед."
chown root:"$APP" "$ETC/hrcontrol.env" && chmod 640 "$ETC/hrcontrol.env"
install -m 600 "$ETC/hrcontrol.env" "$VAULT/hrcontrol.env"

# ── 2. git-mirror дар сейф ─────────────────────────────────────────
export GIT_SSH_COMMAND="ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o BatchMode=yes -o ConnectTimeout=15"
if [ ! -d "$REPO" ]; then
    if [ -n "$BUNDLE" ]; then git clone -q --bare "$BUNDLE" "$REPO"
    else git clone -q --bare "$GITHUB" "$REPO" || die "GitHub дастрас нест ва bundle дода нашуд"
    fi
fi
if [ -n "$BUNDLE" ]; then
    git -C "$REPO" fetch -q "$BUNDLE" "+refs/heads/*:refs/heads/*"
    log "манбаъ: bundle ($BUNDLE)"
elif [ -f "$KEY" ] && git -C "$REPO" fetch -q "$GITHUB" "+refs/heads/*:refs/heads/*"; then
    log "манбаъ: GitHub"
else
    log "GitHub дастрас нест — версияи охирини сейф истифода мешавад"
fi
NEW=$(git -C "$REPO" rev-parse "$BRANCH")

# ── 3. код ─────────────────────────────────────────────────────────
OLD=""
if [ -d "$CODE/.git" ]; then
    OLD=$(git -C "$CODE" rev-parse HEAD)
    git -C "$CODE" fetch -q "$REPO" "$BRANCH"
    git -C "$CODE" reset -q --hard FETCH_HEAD
else
    rm -rf "$CODE.new"
    git clone -q -b "$BRANCH" "$REPO" "$CODE.new"
    [ -e "$CODE" ] && mv "$CODE" "$CODE.old.$(date +%s)"
    mv "$CODE.new" "$CODE"
fi
git -C "$CODE" clean -qfdx -e .venv
log "код: ${OLD:0:8} → ${NEW:0:8} ($(git -C "$CODE" log -1 --format=%s))"

rollback() {
    [ -n "$OLD" ] || return 0
    log "ROLLBACK → ${OLD:0:8}"
    git -C "$CODE" reset -q --hard "$OLD"
    systemctl restart "$APP" || true
}

# ── 4. venv (танҳо агар requirements иваз шуда бошад) ───────────────
REQ_HASH=$(sha256sum "$CODE/requirements.txt" | cut -c1-16)
if [ ! -x "$CODE/.venv/bin/python3" ] || [ "$(cat "$CODE/.venv/.req" 2>/dev/null)" != "$REQ_HASH" ]; then
    log "насби китобхонаҳо…"
    python3 -m venv "$CODE/.venv"
    "$CODE/.venv/bin/pip" install -q --upgrade pip
    "$CODE/.venv/bin/pip" install -q -r "$CODE/requirements.txt" || { rollback; die "pip install нашуд"; }
    echo "$REQ_HASH" > "$CODE/.venv/.req"
fi

# ── 5. санҷишҳо (бо базаи муваққатӣ; ба базаи корӣ дахл надоранд) ───
log "санҷишҳо…"
for t in test_resilience test_attendance test_admin_api; do
    if ! (cd "$CODE" && timeout 300 "$CODE/.venv/bin/python3" "tests/$t.py" > "/tmp/hrcontrol-$t.log" 2>&1); then
        tail -20 "/tmp/hrcontrol-$t.log" >&2
        rollback
        die "санҷиши $t нагузашт — версияи қаблӣ монд"
    fi
    log "  $t: $(grep -E 'passed' "/tmp/hrcontrol-$t.log" | tail -1)"
done

# ── 6. нусхаи база пеш аз restart ──────────────────────────────────
if [ -s "$DATA/softclub.db" ]; then
    SNAP="$DATA/backups/softclub_$(date +%Y%m%d_%H%M%S)_deploy.db"
    "$CODE/.venv/bin/python3" -c "import sqlite3,sys; s=sqlite3.connect(sys.argv[1]); d=sqlite3.connect(sys.argv[2]); s.backup(d); d.close(); s.close()" \
        "$DATA/softclub.db" "$SNAP"
    chown "$APP:$APP" "$SNAP" && chmod 640 "$SNAP"
    install -m 640 -o root -g "$APP" "$SNAP" "$VAULT/db/"
    ls -t "$VAULT"/db/softclub_*_deploy.db 2>/dev/null | tail -n +11 | xargs -r rm -f
    log "нусхаи база: $SNAP"
fi

# ── 7. systemd, watchdog, nginx ────────────────────────────────────
install -m 644 "$CODE/deploy/hrcontrol.service"            /etc/systemd/system/hrcontrol.service
install -m 644 "$CODE/deploy/hrcontrol-watchdog.service"   /etc/systemd/system/hrcontrol-watchdog.service
install -m 644 "$CODE/deploy/hrcontrol-watchdog.timer"     /etc/systemd/system/hrcontrol-watchdog.timer
install -m 755 "$CODE/deploy/hrcontrol-watchdog.sh"        /usr/local/sbin/hrcontrol-watchdog
install -m 755 "$CODE/deploy/deploy.sh"                    /usr/local/sbin/hrcontrol-deploy

if command -v nginx >/dev/null 2>&1; then
    [ -f /etc/nginx/sites-available/hrcontrol ] || install -m 644 "$CODE/deploy/nginx-hrcontrol.conf" /etc/nginx/sites-available/hrcontrol
    [ -e /etc/nginx/sites-enabled/hrcontrol ] || ln -s /etc/nginx/sites-available/hrcontrol /etc/nginx/sites-enabled/hrcontrol
    systemctl enable nginx >/dev/null 2>&1 || true
    if nginx -t >/dev/null 2>&1; then systemctl reload nginx || systemctl start nginx; else log "огоҳӣ: 'nginx -t' хато медиҳад"; fi
fi

systemctl daemon-reload
systemctl enable "$APP" hrcontrol-watchdog.timer >/dev/null 2>&1
systemctl reset-failed "$APP" >/dev/null 2>&1 || true
systemctl restart "$APP"
systemctl restart hrcontrol-watchdog.timer

# ── 8. саломатӣ ────────────────────────────────────────────────────
ok=""
for _ in $(seq 1 45); do
    if curl -fsS -m 5 -o /dev/null "$HEALTH_URL"; then ok=1; break; fi
    sleep 2
done
if [ -z "$ok" ]; then
    journalctl -u "$APP" -n 30 --no-pager >&2 || true
    rollback
    die "бот пас аз 90 сония ҷавоб надод — версияи қаблӣ баргардонида шуд"
fi

git -C "$REPO" update-ref refs/deployed "$NEW"
log "✅ Тайёр: $(curl -fsS -m 5 "$HEALTH_URL" | head -c 300)"
