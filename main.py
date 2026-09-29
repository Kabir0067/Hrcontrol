"""
SoftClub / Hrcontrol — нуқтаи оғоз.

Меъмории устувор:
  • ҳар як зерсистема (polling, ҳалқаи ёдоварӣ, сервери веб) ҷудогона назорат
    мешавад — агар яке афтад, дигарон кор мекунанд ва афтода аз нав мебарояд;
  • log бо ротация (диск пур намешавад);
  • хомӯшшавии осоишта бо SIGTERM (systemd restart).
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import signal
import sys

from telebot.async_telebot import AsyncTeleBot
from telebot.types import BotCommand

import config as cfg
import database as db
from admin_server import start_admin_server
from handlers import (
    housekeeping,
    notify_overdue,
    process_arrival_checks,
    register_handlers,
    send_reminders,
)


# ══════════════════════════════════════════════════════════════════════════
#  Logging
# ══════════════════════════════════════════════════════════════════════════

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
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    return logging.getLogger("SoftClubBot")


log = setup_logging()
bot = AsyncTeleBot(cfg.BOT_TOKEN, parse_mode="HTML")


# ══════════════════════════════════════════════════════════════════════════
#  Зерсистемаҳо
# ══════════════════════════════════════════════════════════════════════════

async def setup_commands() -> None:
    await bot.set_my_commands([
        BotCommand("start", "🚀 Оғоз — интихоби вазъият"),
        BotCommand("holat", "📋 Дархостҳои ман"),
        BotCommand("bekor", "❌ Бекор кардани амали ҷорӣ"),
        BotCommand("help", "ℹ️ Дастурамал"),
        BotCommand("admin", "🔐 Панели маъмурият"),
    ])
    log.info("📋 Менюи фармонҳо навсозӣ шуд")


async def polling_task() -> None:
    log.info("🔄 Polling оғоз шуд")
    await bot.infinity_polling(timeout=30, request_timeout=60, skip_pending=False)


async def scheduler_task() -> None:
    log.info("🔔 Ҳалқаи ёдоварӣ оғоз шуд (ҳар %d сония)", cfg.LOOP_INTERVAL)
    tick = 0
    while True:
        for job in (send_reminders, notify_overdue, process_arrival_checks):
            try:
                await job(bot)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("⚠️ %s: %s", job.__name__, exc)

        tick += 1
        if tick % 60 == 0:                       # тақрибан ҳар 20 дақиқа
            await housekeeping()

        await asyncio.sleep(cfg.LOOP_INTERVAL)


async def web_task() -> None:
    await start_admin_server(bot)


async def supervise(name: str, factory) -> None:
    """Зерсистемаро зинда нигоҳ медорад: афтад — аз нав мебардорад."""
    delay = 5
    while True:
        try:
            await factory()
            log.warning("↩️ «%s» ба анҷом расид — аз нав оғоз мекунем", name)
            delay = 5
        except asyncio.CancelledError:
            log.info("🛑 «%s» боздошта шуд", name)
            raise
        except Exception as exc:
            log.exception("💥 «%s» афтод: %s. Пас аз %d сония аз нав…", name, exc, delay)
        await asyncio.sleep(delay)
        delay = min(delay * 2, 60)               # backoff то 1 дақиқа


# ══════════════════════════════════════════════════════════════════════════
#  main
# ══════════════════════════════════════════════════════════════════════════

async def main() -> None:
    log.info("═" * 62)
    log.info("🚀 %s v%s (build %s)", cfg.APP_NAME, cfg.VERSION, cfg.BUILD)
    log.info("🕒 Минтақаи вақт: %s · ҳозир %s", cfg.TZ_NAME, cfg.now_str())

    db.init_db()

    try:
        me = await bot.get_me()
        log.info("🤖 Бот: @%s (id=%s)", me.username, me.id)
    except Exception as exc:
        log.error("❌ Токени бот кор намекунад: %s", exc)
        raise

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

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
        if sig is None:
            continue
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            pass                                  # Windows — KeyboardInterrupt кор мекунад

    try:
        await stop.wait()
    finally:
        log.info("🛑 Хомӯшшавӣ…")
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        try:
            await bot.close_session()
        except Exception:
            pass
        log.info("👋 Хуш бимонед!")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("🛑 Аз ҷониби корбар боздошта шуд")
    except Exception as exc:
        log.critical("💥 Оғоз номумкин: %s", exc, exc_info=True)
        sys.exit(1)
