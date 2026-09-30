"""
SoftClub / Hrcontrol — нуқтаи оғоз.

Меъмории устувор:
  • ҳар як зерсистема (polling, ҳалқаи ёдоварӣ, сервери веб) ҷудогона назорат
    мешавад — агар яке афтад, дигарон кор мекунанд ва афтода аз нав мебарояд;
  • log бо ротация (диск пур намешавад);
  • хомӯшшавии осоишта бо SIGTERM (systemd restart) — ҳатман дар ≤10 сония;
  • «набзи» polling (вақти охирин getUpdates-и муваффақ) — /api/health?strict=1
    онро месанҷад ва watchdog боти овезоншударо restart мекунад.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import os
import signal
import sys
import time

from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException
from telebot.types import BotCommand

import config as cfg
import database as db
from admin_server import start_admin_server
from handlers import (
    daily_backup,
    housekeeping,
    notify_overdue,
    process_arrival_checks,
    process_work_attendance,
    register_handlers,
    remind_attendance,
    send_daily_report,
    send_reminders,
)


# ══════════════════════════════════════════════════════════════════════════
#  Logging
# ══════════════════════════════════════════════════════════════════════════

_SHUTDOWN_NOISE = ("Polling is stopped", "polling exited", "Break infinity polling")


def _quiet_shutdown_filter(record: logging.LogRecord) -> bool:
    """
    telebot ҳангоми хомӯшшавии муқаррарӣ сатрҳои ERROR менависад
    («Break infinity polling» ва ғ.) — онҳо хато нестанд ва log-ро гумроҳ мекунанд.
    Танҳо вақти хомӯшшавии қасдан пинҳон мекунем; дар ҳолати дигар намоён мемонанд.
    """
    stopping = globals().get("_stopping", False)
    return not (stopping and any(n in record.getMessage() for n in _SHUTDOWN_NOISE))


def setup_logging() -> logging.Logger:
    root = logging.getLogger()
    root.setLevel(getattr(logging, cfg.LOG_LEVEL, logging.INFO))
    root.handlers.clear()

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%d.%m.%Y %H:%M:%S",
    )

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            cfg.LOG_PATH, maxBytes=cfg.LOG_MAX_BYTES,
            backupCount=cfg.LOG_BACKUPS, encoding="utf-8",
        )
        file_handler.setFormatter(fmt)
        root.addHandler(file_handler)
    except OSError as exc:
        print(f"⚠️ Файли log кушода нашуд ({exc}) — танҳо ба консол менависем")

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    root.addHandler(stream)

    # Китобхонаҳои беруна набояд log-ро пур кунанд
    logging.getLogger("TeleBot").setLevel(logging.WARNING)
    logging.getLogger("TeleBot").addFilter(_quiet_shutdown_filter)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    return logging.getLogger("SoftClubBot")


class HRBot(AsyncTeleBot):
    """AsyncTeleBot + «набзи» polling.

    `last_poll_ok` — вақти охирин ҷавоби муваффақи getUpdates. Агар polling
    овезон шавад (раванд зинда, вале паёмҳо намеоянд), /api/health?strict=1
    503 медиҳад ва watchdog хидматро restart мекунад.
    """

    last_poll_ok: float = 0.0
    conflict_at: float = 0.0          # охирин 409: ҳамин токен дар ҷои дигар ҳам кор мекунад

    async def get_updates(self, *args, **kwargs):
        try:
            updates = await super().get_updates(*args, **kwargs)
        except ApiTelegramException as exc:
            if exc.error_code == 409:
                if time.time() - self.conflict_at > 600:   # ҳар 10 дақ. як бор, на спам
                    logging.getLogger("SoftClubBot").error(
                        "⚠️ 409 Conflict: ҳамин бот (ҳамин BOT_TOKEN) дар ҷои дигар низ оғоз шудааст "
                        "(масалан, дар компютер). Ду нусха ҳамзамон кор карда наметавонанд — "
                        "нусхаи дигарро хомӯш кунед.")
                self.conflict_at = time.time()
            raise
        self.last_poll_ok = time.time()
        return updates


log = setup_logging()

if not cfg.BOT_TOKEN:
    log.critical("❌ BOT_TOKEN дар .env гузошта нашудааст — бот оғоз шуда наметавонад")
    sys.exit(1)

bot = HRBot(cfg.BOT_TOKEN, parse_mode="HTML")

# Ҳангоми хомӯшшавӣ True мешавад. Лозим аст, чунки telebot CancelledError-ро
# дар дохили infinity_polling «фурӯ мебарад» ва polling оддӣ ба анҷом мерасад —
# бе ин парчам supervise() онро аз нав мебардошт ва раванд ҳеҷ гоҳ хомӯш
# намешуд (systemd пас аз TimeoutStopSec SIGKILL мекард → «failed»).
_stopping = False


# ══════════════════════════════════════════════════════════════════════════
#  Зерсистемаҳо
# ══════════════════════════════════════════════════════════════════════════

async def setup_commands() -> None:
    await bot.set_my_commands([
        BotCommand("start", "🚀 Оғоз — дархости нав"),
        BotCommand("holat", "📋 Дархостҳои ман"),
        BotCommand("bekor", "❌ Бекор кардани амали ҷорӣ"),
        BotCommand("help", "ℹ️ Бот чӣ кор мекунад"),
        BotCommand("admin", "🔐 Панели идоракунӣ"),
    ])
    log.info("📋 Менюи фармонҳо навсозӣ шуд")


async def polling_task() -> None:
    log.info("🔄 Polling оғоз шуд")
    await bot.infinity_polling(timeout=30, request_timeout=60, skip_pending=False)


async def scheduler_task() -> None:
    log.info("🔔 Ҳалқаи ёдоварӣ оғоз шуд (ҳар %d сония)", cfg.LOOP_INTERVAL)
    tick = 0
    while True:
        for job in (send_reminders, notify_overdue, process_arrival_checks,
                    process_work_attendance, remind_attendance, send_daily_report, daily_backup):
            try:
                await job(bot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("⚠️ %s: %s", job.__name__, exc)

        tick += 1
        if tick % 60 == 0:                       # тақрибан ҳар 20 дақиқа
            await housekeeping()
        if tick % 180 == 0:                      # тақрибан ҳар соат — «зиндаам»
            age = int(time.time() - bot.last_poll_ok) if bot.last_poll_ok else -1
            log.info("💓 Кор мекунад · охирин getUpdates %s сония пеш", age)

        await asyncio.sleep(cfg.LOOP_INTERVAL)


async def web_task() -> None:
    await start_admin_server(bot)


def _is_stopping() -> bool:
    if _stopping:
        return True
    task = asyncio.current_task()
    # Python 3.11+: бекоркунӣ дархост шудааст, ҳатто агар китобхона онро фурӯ бурда бошад
    cancelling = getattr(task, "cancelling", None)
    return bool(cancelling and cancelling())


async def supervise(name: str, factory) -> None:
    """Зерсистемаро зинда нигоҳ медорад: афтад — аз нав мебардорад."""
    delay = 5
    while not _is_stopping():
        started = time.monotonic()
        try:
            await factory()
            if _is_stopping():
                break
            log.warning("↩️ «%s» ба анҷом расид — аз нав оғоз мекунем", name)
            delay = 5
        except asyncio.CancelledError:
            log.info("🛑 «%s» боздошта шуд", name)
            raise
        except Exception as exc:
            if _is_stopping():
                break
            if time.monotonic() - started > 300:  # муддати дароз кор кард — backoff аз нав
                delay = 5
            log.exception("💥 «%s» афтод: %s. Пас аз %d сония аз нав…", name, exc, delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)               # backoff то 1 дақиқа
    log.info("🛑 «%s» боздошта шуд", name)


def _loop_exception_handler(loop, context) -> None:
    """Хатоҳои task-ҳои «гумшуда» ба log мераванд, на ба stderr-и нонамоён."""
    exc = context.get("exception")
    log.error("⚠️ asyncio: %s", context.get("message", "хатои номаълум"),
              exc_info=exc if isinstance(exc, BaseException) else None)


async def connect_telegram(stop: asyncio.Event) -> bool:
    """
    Бо Telegram пайваст мешавад. Агар шабака ё Telegram дастрас набошад —
    намеафтад, балки бо backoff интизор мешавад (масалан, пас аз reboot).
    Токени нодуруст (401/404) — хатои ислоҳнашаванда: False.
    """
    delay = 5
    while not stop.is_set():
        try:
            me = await bot.get_me()
            log.info("🤖 Бот: @%s (id=%s)", me.username, me.id)
            return True
        except ApiTelegramException as exc:
            if exc.error_code in (401, 404):
                log.critical("❌ Токени бот нодуруст аст (%s). .env-ро санҷед.", exc.error_code)
                return False
            log.error("⚠️ Telegram: %s. Пас аз %d сония аз нав…", exc, delay)
        except Exception as exc:
            log.error("🌐 Telegram дастрас нест (%s). Пас аз %d сония аз нав…", exc, delay)
        try:
            await asyncio.wait_for(stop.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
        delay = min(delay * 2, 60)
    return False


# ══════════════════════════════════════════════════════════════════════════
#  main
# ══════════════════════════════════════════════════════════════════════════

async def main() -> int:
    global _stopping

    log.info("═" * 62)
    log.info("🚀 %s v%s (build %s)", cfg.APP_NAME, cfg.VERSION, cfg.BUILD)
    log.info("🕒 Минтақаи вақт: %s · ҳозир %s", cfg.TZ_NAME, cfg.now_str())

    loop = asyncio.get_running_loop()
    loop.set_exception_handler(_loop_exception_handler)

    # Сигналҳо аввал — то SIGTERM ҳатто ҳангоми интизори шабака осоишта кор кунад
    stop = asyncio.Event()
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass                                  # Windows — KeyboardInterrupt кор мекунад

    try:
        db.restore_if_missing()
    except Exception as exc:                    # барқароркунӣ набояд оғозро боздорад
        log.error("♻️ Барқароркунии база нашуд: %s", exc)
    db.init_db()

    if not await connect_telegram(stop):
        await _close_session()
        return 0 if stop.is_set() else 1

    register_handlers(bot)
    try:
        await setup_commands()
    except Exception as exc:
        log.warning("⚠️ Менюи фармонҳо гузошта нашуд: %s", exc)

    log.info("🌐 Панел: %s", cfg.WEBAPP_URL)
    log.info("👥 Гурӯҳи корӣ: %s", cfg.GROUP_ID)
    log.info("═" * 62)

    tasks = [
        asyncio.create_task(supervise("polling", polling_task), name="polling"),
        asyncio.create_task(supervise("scheduler", scheduler_task), name="scheduler"),
        asyncio.create_task(supervise("web", web_task), name="web"),
    ]

    try:
        await stop.wait()
    finally:
        _stopping = True
        log.info("🛑 Хомӯшшавӣ…")
        for task in tasks:
            task.cancel()
        _, pending = await asyncio.wait(tasks, timeout=10)
        await _close_session()
        if pending:
            # Набояд рӯй диҳад, вале агар рӯй диҳад — овезон намемонем,
            # вагарна systemd SIGKILL мекунад ва хидмат «failed» мешавад.
            log.error("⚠️ %d зерсистема дар 10 сония хомӯш нашуд — хуруҷи маҷбурӣ",
                      len(pending))
            logging.shutdown()
            os._exit(0)
        log.info("👋 Хуш бимонед!")
    return 0


async def _close_session() -> None:
    try:
        await bot.close_session()
    except Exception:
        pass


if __name__ == "__main__":
    code = 0
    try:
        code = asyncio.run(main())
    except KeyboardInterrupt:
        log.info("🛑 Аз ҷониби корбар боздошта шуд")
    except Exception as exc:
        log.critical("💥 Оғоз номумкин: %s", exc, exc_info=True)
        code = 1
    sys.exit(code)
