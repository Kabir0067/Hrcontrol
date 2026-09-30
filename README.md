# SoftClub HR Control

Боти Telegram ва панели веб барои **давомоти кормандон** ва дархостҳо ба роҳбарият
(дер мемонам, намеоям, ҷавоб мепурсам, барвақт меравам).

**Продакшн:** https://test.softclub.tj/hrcontrol/ · бот `@SoftClubHrControlBot` · фармони `/admin`

---

## Имкониятҳо

### Бот
- **Давомот.** Ҳар рӯзи корӣ дар вақти муқарраршуда бот аз ҳар корманд мепурсад: «Ба кор омадед?»
  - **✅ Омадам** — вақти омадан сабт мешавад (сари вақт ё чанд дақиқа дер);
  - **❌ Наомадам** — сабаб (тугма ё матн) → кай меояд (тугма ё матн) → роҳбарият дар гурӯҳ огоҳ мешавад;
    баъдтар тугмаи **«Ман омадам»** вақти воқеии омаданро сабт мекунад;
  - агар 30 дақиқа ҷавоб надиҳад — як ёдоварӣ;
  - як соат пас аз оғози кор — **ҳисоботи рӯз** ба гурӯҳи роҳбарият (кӣ дер кард, кӣ наомад, кӣ ҷавоб надод);
  - якшанбе ва рӯзҳои истироҳат (идҳо) савол намеравад;
  - касе, ки субҳ «Имрӯз намеоям / Дер мекунам» фиристодааст, савол намегирад — сабаб аз дархост гирифта мешавад.
- **Дархостҳо** ба гурӯҳи роҳбарият бо тугмаҳои «Иҷозат / Рад», ёдовариҳо ва санҷиши «расидед?».

### Панели веб (Telegram Mini App + браузер; телефон, планшет, компютер; мавзӯи равшан/торик)
| Бахш | Чӣ ҳаст |
|---|---|
| **Асосӣ** | Давомоти имрӯз (ҳалқа), кӣ ҳанӯз дар кор нест ва чаро, дархостҳои интизор бо «Иҷозат / Рад», графикҳои 7 рӯз |
| **Давомот** | Вақти корӣ (муқаррар / иваз / хомӯш), **рӯз** (рӯйхат бо филтр) ва **моҳи корӣ 5 → 4** (ҷадвали корманд × рӯз), ислоҳи дастӣ (омад / наомад / рухсатӣ), рӯзи ид, Excel (CSV) |
| **Дархостҳо** | Ҷустуҷӯ, филтрҳо (давра, навъ, ҳолат, корманд), нест кардан **бо як пахш** ва «Бозгардондан» (5 сония), интихоби якчанд, CSV |
| **Кормандон** | Рӯйхат, профил бо тақвими моҳ, иваз кардани ном, хомӯш кардани савол (масалан, барои роҳбарон), нест кардан |
| **Омор** | Давомот: %, сари вақт, миёнаи омадан, дерӣ, вақти омадан, рӯзҳои ҳафта, рейтинг (тартиб бо пахши сутун). Дархостҳо: навъҳо, қарорҳо, сабабҳо, соатҳо, кормандон |
| **Танзимот** | Вақти корӣ, логин + рамз (танҳо логини нав ва рамзи нав × 2), нусхаи база, CSV, тозакунӣ |

- Админҳои гурӯҳи роҳбарият дар дохили Telegram **бе рамз** ворид мешаванд (initData + `getChatMember`).
- Нест кардан рамз намепурсад; пеш аз ҳар нест кардани оммавӣ нусхаи эҳтиётӣ худкор сохта мешавад.
- Моҳи корӣ аз **5-ум то 4-уми** моҳи дигар ҳисоб мешавад (ҳам дар ҷадвал, ҳам дар омор).

---

## Сохтор

| Файл | Вазифа |
|---|---|
| `config.py` | Ҳамаи танзимот (аз `.env` ё муҳити система). Вақт — ҳамеша `Asia/Dushanbe` |
| `database.py` | SQLite: дархостҳо, давомот, кормандон, рӯзҳои истироҳат, омор, нусхаҳо |
| `handlers.py` | Бот: равандҳо, тугмаҳо, саволи давомот, ёдовариҳо, ҳисоботи рӯз |
| `admin_server.py` | aiohttp API + статикаи панел |
| `main.py` | Оғоз, назорати зерсистемаҳо, log |
| `admin_panel/` | Панели веб (HTML/CSS/JS, **бе ягон китобхонаи беруна**) |
| `deploy/` | systemd, watchdog, nginx, `deploy.sh` |
| `tests/` | `test_resilience.py`, `test_attendance.py`, `test_admin_api.py` (бе Telegram, бо базаи муваққатӣ) |

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
for t in test_resilience test_attendance test_admin_api; do .venv/bin/python tests/$t.py; done
.venv/bin/python tests/test_admin_api.py --serve     # панел бо маълумоти намунавӣ: http://127.0.0.1:18901/__dev_login
```

> ⚠️ Ботро бо **ҳамон** `BOT_TOKEN`-и продакшн дар компютер оғоз накунед — Telegram ду нусхаро
> ҳамзамон иҷозат намедиҳад (409 Conflict) ва боти сервер «худ аз худ» кор намекунад.
> Ин ҳолат дар log ва дар «Танзимот → Система» нишон дода мешавад.

---

## Продакшн (сервери 157.180.29.248)

Лоиҳа ба папкаи хонаи ягон корбар вобаста **нест** (сервер муштарак аст):

| Роҳ | Чӣ | Соҳиб |
|---|---|---|
| `/opt/hrcontrol` | код (git) + `.venv` | root (барои хидмат — танҳо хондан) |
| `/var/lib/hrcontrol` | `softclub.db`, `backups/`, `bot.log` | `hrcontrol` (корбари системавӣ) |
| `/etc/hrcontrol/hrcontrol.env` | сирҳо: `BOT_TOKEN`, `ADMIN_PASS`, `SECRET_KEY` | root:hrcontrol 640 |
| `/var/backups/hrcontrol` | **сейф**: `repo.git`, нусхаҳои база (14 рӯз), нусхаи env | root |

- **Хидмат** `hrcontrol.service`: `enabled` (пас аз reboot худаш меояд), `Restart=always`,
  корбари ҷудо, `ProtectSystem=strict`, `MemoryMax=512M`.
- **Watchdog** `hrcontrol-watchdog.timer` (ҳар 2 дақиқа, 90 сония пас аз boot) — ҳар чизи нестшударо барқарор мекунад:
  код (аз `repo.git`), venv, сирҳо, файлҳои systemd, база (аз навтарин нусха), хидмат (enable/start,
  health-check → restart), nginx (enable/start, конфиг, пайванд).
- Худи бот ҳам ҳангоми оғоз, агар база нест бошад, онро аз нусха барқарор мекунад.
- Нусхаи ҳаррӯзаи база худкор; ихтиёрӣ — ба чати Telegram (`BACKUP_CHAT_ID`).

### Деплой (аз git)

```bash
# Аз компютер: bundle-и ҳамон commit-е, ки дар GitHub аст
git bundle create hr.bundle HEAD main
scp hr.bundle kabir0067@157.180.29.248:/tmp/
ssh kabir0067@157.180.29.248 'sudo hrcontrol-deploy /tmp/hr.bundle'

# Ё мустақиман аз GitHub (агар deploy key-и /etc/hrcontrol/deploy_key.pub ба репо илова шуда бошад):
ssh kabir0067@157.180.29.248 'sudo hrcontrol-deploy'
```

`hrcontrol-deploy`: git → код → venv (агар `requirements.txt` иваз шуда бошад) → **ҳамаи санҷишҳо** →
нусхаи база → systemd/nginx → restart → health-check. Агар санҷиш ё оғоз хато шавад — **версияи қаблӣ
худкор бармегардад**.

### Фармонҳои фоиданок

```bash
systemctl status hrcontrol                        # вазъият
journalctl -u hrcontrol -f                        # log-и зинда
journalctl -t hrcontrol-watchdog -t hrcontrol-deploy --since today   # амалҳои watchdog ва деплой
curl -s "localhost:8901/api/health?strict=1"      # саломатӣ (база + polling-и Telegram)
sudo touch /etc/hrcontrol/maintenance             # таъмир: watchdog дахолат намекунад
sudo rm /etc/hrcontrol/maintenance                # анҷоми таъмир
```

Агар рамзи панел фаромӯш шавад:

```bash
sudo -u hrcontrol /opt/hrcontrol/.venv/bin/python3 -c "import sqlite3; c=sqlite3.connect('/var/lib/hrcontrol/softclub.db'); c.execute(\"DELETE FROM settings WHERE key IN ('admin_login','admin_pass_hash')\"); c.commit()"
# Акнун боз ADMIN_LOGIN / ADMIN_PASS аз /etc/hrcontrol/hrcontrol.env кор мекунанд
```

---

## API

| Метод | Роҳ | Авторизатсия |
|---|---|---|
| GET | `/api/health` (`?strict=1` — бо санҷиши polling) | не |
| POST | `/api/login`, `/api/login/telegram` (`{init_data}`) | не (маҳдуд: 8 кӯшиш / 5 дақ) |
| GET / POST | `/api/account` — `{new_login, new_password, new_password_confirm}` | Bearer |
| GET | `/api/overview`, `/api/dashboard`, `/api/analytics?date_from&date_to` | Bearer |
| GET / POST | `/api/work-schedule` — `{time, days, grace, report}` | Bearer |
| GET | `/api/attendance/day?date`, `/api/attendance/month?period=YYYY-MM&user_id`, `/api/attendance/stats` | Bearer |
| POST / DELETE | `/api/attendance` — `{user_id, date, status: present\|absent\|leave, time, reason, eta}`, `/api/attendance/{id}` | Bearer |
| POST | `/api/days-off` — `{date, off, title}` | Bearer |
| GET / POST | `/api/employees`, `/api/employees/{id}` — `{alias, active}` | Bearer |
| GET | `/api/requests?type&status&date_from&date_to&q&user_id&sort&limit&offset` | Bearer |
| GET / DELETE | `/api/requests/{id}` | Bearer |
| POST | `/api/requests/delete` — `{ids}` ё `{filters}`; `/api/requests/{id}/decision`, `/api/requests/{id}/message` | Bearer |
| GET / POST | `/api/workers?…`, `/api/workers/{id}`, `/api/workers/{id}/delete` | Bearer |
| POST | `/api/wipe` — `{scope: requests\|all, before?}` | Bearer |
| GET | `/api/backups`, `/api/backup.db`, `/api/export.csv?…`, `/api/attendance.csv?period` | Bearer ё `?token=` |

---

## Чизҳое, ки махсус барои устуворӣ сохта шудаанд

- **Худбарқароркунӣ.** Код, база, сирҳо, systemd ва nginx — ҳар кадом нест шавад, watchdog дар ≤2 дақиқа
  барқарор мекунад (ҳатто агар папкаи хона пурра нест карда шавад).
- **Reboot / қатъ шудани сервер.** Хидмат, watchdog ва nginx `enabled`; бот то пайдо шудани шабака интизор
  мешавад; саволи давомот танҳо дар 4 соати аввали рӯзи корӣ меравад (пас аз хомӯшии дароз спам нест).
- **Деплой бо rollback.** Санҷишҳо пеш аз оғоз; хато → версияи қаблӣ.
- **Зерсистемаҳои мустақил.** Polling, ҳалқаи фонӣ ва веб ҷудо назорат мешаванд; афтода бо backoff бармегардад.
- **Ҳолати корбар дар база.** Restart равандҳои нотамомро вайрон намекунад.
- **Бе такрор.** Давомот: `UNIQUE(user_id, work_date)`; сабт пеш аз фиристодан — ҳеҷ кас ду савол намегирад.
- **Вақти маҳаллӣ.** Сервер бо UTC — `config.now()` ҳамеша `Asia/Dushanbe`.
- **409 Conflict** (ду нусхаи бот) ошкор ва дар log/панел нишон дода мешавад.
- **Бе CDN.** Панел ба ягон сервери беруна вобаста нест (ба ғайр аз SDK-и ихтиёрии Telegram).
- **Ротацияи log.** 5 МБ × 3 файл; версияҳои китобхонаҳо маҳкам (`requirements.txt`).
