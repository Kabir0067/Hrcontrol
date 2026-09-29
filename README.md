# SoftClub HR Control

Боти Telegram барои огоҳ кардани роҳбарият аз вазъияти кории ҳамкорон
(дер мондан, наомадан, ҷавоб пурсидан, барвақт рафтан) + панели веби маъмурият.

**Продакшн:** https://test.softclub.tj/hrcontrol/ · бот `@SoftClubHrControlBot`

---

## Сохтор

| Файл | Вазифа |
|---|---|
| `config.py` | Ҳамаи танзимот (аз `.env` ё муҳити система). Вақт — ҳамеша `Asia/Dushanbe` |
| `database.py` | SQLite: дархостҳо, санҷиши омадан, ҳолати корбар, кормандон, омор |
| `handlers.py` | Мантиқи бот: равандҳо, тугмаҳо, ёдовариҳо |
| `admin_server.py` | aiohttp API + статикаи панел |
| `main.py` | Оғоз, назорати зерсистемаҳо, log |
| `deploy/` | systemd watchdog (`hrcontrol-watchdog.*`) ва `install.sh` |
| `tests/` | Санҷишҳои офлайн: `python tests/test_resilience.py` |
| `admin_panel/` | Панели веб (HTML/CSS/JS, **бе ягон китобхонаи беруна**) |

---

## Оғоз дар компютер

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env        # BOT_TOKEN ва ғайраро гузоред
.venv/bin/python main.py
```

Панел: http://127.0.0.1:8901/

---

## Продакшн (сервери 157.180.29.248)

- **Роҳ:** `/home/kabir0067/Hrcontrol/`
- **Git:** https://github.com/Kabir0067/Hrcontrol (private)
- **Сервис:** `hrcontrol.service` (`enabled` — пас аз reboot худаш меояд;
  `Restart=always` — пас аз ҳар афтиш дар 5 сония бармегардад)
- **Watchdog:** `hrcontrol-watchdog.timer` — ҳар 2 дақиқа (скрипт: `deploy/hrcontrol-watchdog.sh`):
  - хидмат `disabled` шавад → `enable`; истода бошад → `start`;
  - `/api/health?strict=1` ду бор пай дар пай хато (polling-и Telegram овезон) → `restart`;
  - пайванди `sites-enabled/hrcontrol`-и nginx нест шавад → барқарор + `reload`
    (танҳо агар `nginx -t` гузарад).
- **Порт:** `127.0.0.1:8901` (танҳо дохилӣ; аз берун — тавассути nginx)
- **nginx:** `/etc/nginx/sites-available/hrcontrol` → `test.softclub.tj`
- **База:** `softclub.db` — **ҳеҷ гоҳ рӯйнавис накунед**
- **Сирҳо:** танҳо дар `.env` (`BOT_TOKEN`, `ADMIN_PASS`, `SECRET_KEY`) — ба git намеравад.

### Деплойи нав

```bash
# 1. Нусхаи эҳтиётӣ
ssh kabir0067@157.180.29.248 'cd ~/Hrcontrol && B=backup_$(date +%Y%m%d_%H%M%S) \
  && mkdir -p $B && cp -r *.py softclub.db admin_panel hrcontrol.service $B/'

# 2. Файлҳо (БЕ softclub.db ва .env!)
scp config.py database.py handlers.py admin_server.py main.py hrcontrol.service \
    kabir0067@157.180.29.248:~/Hrcontrol/
scp -r admin_panel deploy kabir0067@157.180.29.248:~/Hrcontrol/

# 3. Санҷиш, насби systemd (хидмат + watchdog) ва restart
ssh kabir0067@157.180.29.248 'cd ~/Hrcontrol \
  && .venv/bin/python3 -m py_compile *.py \
  && sudo bash deploy/install.sh \
  && sleep 8 && curl -s "localhost:8901/api/health?strict=1"'
```

Ҳангоми тағйири `admin_panel/` рақами `?v=` -ро дар `index.html` як зина боло баред,
вагарна браузери телефон нусхаи кӯҳнаро нишон медиҳад.

### Таъмир (то watchdog ботро «зинда» накунад)

```bash
touch ~/Hrcontrol/.maintenance && sudo systemctl stop hrcontrol   # оғози таъмир
rm ~/Hrcontrol/.maintenance && sudo systemctl start hrcontrol     # анҷом
```

### Фармонҳои фоиданок

```bash
systemctl status hrcontrol                    # вазъият
journalctl -u hrcontrol -f                    # log-и зинда
grep hrcontrol-watchdog /var/log/syslog | tail   # амалҳои watchdog (ё: journalctl -u hrcontrol-watchdog)
tail -f ~/Hrcontrol/bot.log                   # log-и барнома (ротация: 5 МБ × 3)
curl -s localhost:8901/api/health             # санҷиши тандурустӣ (база)
curl -s "localhost:8901/api/health?strict=1"  # + polling-и Telegram зинда аст?
```

---

## API

| Метод | Роҳ | Авторизатсия |
|---|---|---|
| GET | `/api/health` (`?strict=1` — бо санҷиши polling) | не |
| POST | `/api/login` | не (маҳдудкунӣ: 8 кӯшиш / 5 дақ) |
| GET | `/api/dashboard` | Bearer |
| GET | `/api/requests?type&status&date_from&date_to&q&limit&offset` | Bearer |
| GET | `/api/workers` | Bearer |
| GET | `/api/stats?days=N` | Bearer |
| GET | `/api/export.csv` | Bearer ё `?token=` |
| POST | `/api/requests/{id}/decision` | Bearer |
| POST | `/api/requests/{id}/message` | Bearer |

---

## Чизҳое, ки махсус барои устуворӣ сохта шудаанд

- **Зерсистемаҳои мустақил.** Polling, ҳалқаи ёдоварӣ ва сервери веб ҷудо назорат
  мешаванд. Афтиши яке дигаронро намекушад; афтода бо backoff аз нав мебарояд.
- **Ҳолати корбар дар база.** Restart равандҳои нотамомро вайрон намекунад.
- **Вақти маҳаллӣ.** Сервер бо UTC кор мекунад — `config.now()` ҳамеша
  `Asia/Dushanbe` медиҳад, то мӯҳлатҳо 5 соат хато нашаванд.
- **Муҳофизат аз спами таърихӣ.** Дархостҳое, ки мӯҳлаташон аз `STALE_AFTER`
  (180 дақ) зиёдтар гузаштааст, ёдоварӣ намегиранд.
- **Escape-и HTML.** Матни корбар пеш аз фиристодан escape мешавад — вагарна
  аломати `<` тамоми паёмро вайрон мекард.
- **Бе CDN.** Панел ба ягон сервери беруна вобаста нест (ба ғайр аз SDK-и
  ихтиёрии Telegram, ки набошад ҳам ҳамааш кор мекунад).
- **Бе анимацияи ҳаётан муҳим.** Ҳеҷ элемент ҳолати ибтидоии `opacity: 0` надорад:
  агар анимация иҷро нашавад, интерфейс ҳамон тавр намоён мемонад.
- **Ротацияи log.** 5 МБ × 3 файл — диски сервер пур намешавад.
- **Хомӯшшавии кафолатнок.** telebot `CancelledError`-ро дар `infinity_polling`
  фурӯ мебарад; бе парчами `_stopping` зерсистемаи polling пас аз SIGTERM аз нав
  оғоз мешуд, раванд хомӯш намешуд ва systemd онро бо SIGKILL мекушт (хидмат
  «failed» мемонд). Акнун хомӯшшавӣ ≤10 сония аст.
- **Оғози устувор.** Агар ҳангоми оғоз Telegram/шабака дастрас набошад, бот
  намеафтад — бо backoff интизор мешавад. Токени нодуруст — хатои возеҳ дар log.
- **«Набзи» polling.** Вақти охирин `getUpdates`-и муваффақ дар `/api/health`
  нишон дода мешавад; watchdog боти овезоншударо restart мекунад.
- **IP-и воқеӣ барои маҳдудкунии вуруд.** Ба `X-Forwarded-For` (ки мизоҷ худаш
  менависад) бовар намекунем — `X-Real-IP`-и nginx.
