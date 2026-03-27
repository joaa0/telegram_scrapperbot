"""
main.py - Ponto de entrada do bot de auto-buy.
"""

import asyncio
import logging
import sys
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import config
from telegram_listener import router, start_workers
from crawler import crawler_loop, setup_crawler

LOCK_FILE = "/tmp/autobuy_bot.lock"


def _acquire_lock() -> None:
    if os.path.exists(LOCK_FILE):
        with open(LOCK_FILE) as f:
            old_pid = f.read().strip()
        if old_pid and os.path.exists(f"/proc/{old_pid}"):
            print(f"❌ Bot já está rodando (PID {old_pid}). Encerre-o antes de iniciar outro.")
            sys.exit(1)
    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))


def _release_lock() -> None:
    try:
        os.remove(LOCK_FILE)
    except FileNotFoundError:
        pass


def _setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL, logging.INFO),
        format=config.LOG_FORMAT,
        datefmt=config.LOG_DATE_FORMAT,
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    for noisy in ("httpx", "httpcore", "playwright"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def _validate_config() -> None:
    errors = []
    if not config.BOT_TOKEN or config.BOT_TOKEN == "SEU_TOKEN_AQUI":
        errors.append("BOT_TOKEN não configurado.")
    if config.SOURCE_CHAT_ID == -1001234567890:
        errors.append("SOURCE_CHAT_ID não configurado.")
    if errors:
        for e in errors:
            print(f"❌ ERRO DE CONFIGURAÇÃO: {e}")
        sys.exit(1)


async def main() -> None:
    _setup_logging()
    _validate_config()
    _acquire_lock()

    logger = logging.getLogger(__name__)
    logger.info("🚀 Iniciando bot de auto-buy... (PID %s)", os.getpid())
    logger.info("📡 Monitorando chat ID: %s", config.SOURCE_CHAT_ID)
    logger.info("📋 Regras ativas: %d", len(config.BUY_RULES))
    for rule in config.BUY_RULES:
        logger.info("   • %s | keywords: %s | max: R$ %.2f", rule.name, rule.keywords, rule.max_price)

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN),
    )
    dp = Dispatcher()
    dp.include_router(router)

    # Injeta o bot no crawler para que ele possa postar no grupo
    setup_crawler(bot, config.NOTIFY_CHAT_ID)

    logger.info("✅ Bot + Crawler iniciados. Aguardando mensagens e buscando promoções...")
    try:
        while True:
            try:
                await asyncio.gather(
                    dp.start_polling(bot, drop_pending_updates=True),
                    start_workers(n=3),
                    crawler_loop(),
                )
            except KeyboardInterrupt:
                raise  # deixa o Ctrl+C funcionar normalmente
            except Exception as exc:
                logger.warning("⚠️  Conexão perdida: %s", exc)
                logger.info("🔄 Reconectando em 10s...")
                await asyncio.sleep(10)
    finally:
        await bot.session.close()
        _release_lock()
        logger.info("Lock liberado.")


if __name__ == "__main__":
    asyncio.run(main())
