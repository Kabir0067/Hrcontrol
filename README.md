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
- **Сервис:** `hrcontrol.service` (`enabled` — пас аз reboot худаш меояд;
  `Restart=always` — пас аз ҳар афтиш дар 5 сония бармегардад)
- **Порт:** `127.0.0.1:8901` (танҳо дохилӣ; аз берун — тавассути nginx)
- **nginx:** `/etc/nginx/sites-available/hrcontrol` → `test.softclub.tj`
- **База:** `softclub.db` — **ҳеҷ гоҳ рӯйнавис накунед**

### Деплойи нав

```bash
# 1. Нусхаи эҳтиётӣ
ssh kabir0067@157.180.29.248 'cd ~/Hrcontrol && mkdir -p backup_$(date +%F_%H%M) \
  && cp *.py softclub.db backup_$(date +%F_%H%M)/'

# 2. Файлҳо (БЕ softclub.db!)
scp config.py database.py handlers.py admin_server.py main.py \
    kabir0067@157.180.29.248:~/Hrcontrol/
scp admin_panel/* kabir0067@157.180.29.248:~/Hrcontrol/admin_panel/

# 3. Санҷиш ва оғоз
ssh kabir0067@157.180.29.248 'cd ~/Hrcontrol \
  && .venv/bin/python3 -m py_compile *.py \
  && sudo systemctl restart hrcontrol.service \
  && sleep 8 && curl -s localhost:8901/api/health'
```

Ҳангоми тағйири `admin_panel/` рақами `?v=` -ро дар `index.html` як зина боло баред,
вагарна браузери телефон нусхаи кӯҳнаро нишон медиҳад.

### Фармонҳои фоиданок

```bash
systemctl status hrcontrol            # вазъият
journalctl -u hrcontrol -f            # log-и зинда
tail -f ~/Hrcontrol/bot.log           # log-и барнома (ротация: 5 МБ × 3)
curl -s localhost:8901/api/health     # санҷиши тандурустӣ
```

---

## API

| Метод | Роҳ | Авторизатсия |
|---|---|---|
| GET | `/api/health` | не |
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
