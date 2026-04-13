import asyncio
from config.config import settings
from services.llm_service import llm_service
from services.calendar_service import calendar_service
from handlers.telegram_handler import telegram_handler
from utils.logger import logger


async def startup_checks():
    """F-02, F-03: Проверки при старте"""
    logger.info("🔍 Проверка сервисов...")

    # Проверка разрешённых пользователей
    if not settings.allowed_users:
        logger.warning("⚠️ ALLOWED_USER_IDS не установлен! Бот будет доступен всем!")
    else:
        logger.info(f"✅ Доступ разрешён для: {settings.allowed_users}")

    # Проверка Ollama
    if not llm_service.check_connection():
        logger.error("❌ Ollama не доступен. Запустите 'ollama serve'")
        return False

    # Проверка Google Calendar
    try:
        # Проверим, что service создан
        _ = calendar_service.service
    except Exception as e:
        logger.error(f"❌ Google Calendar не доступен: {e}")
        return False

    logger.info("✅ Все сервисы готовы!")
    return True


def main():
    """Запуск приложения"""
    logger.info("🚀 Запуск AI-ассистента...")

    # Синхронные проверки
    if not asyncio.run(startup_checks()):
        return

    # Запуск Telegram бота
    telegram_handler.run()


if __name__ == "__main__":
    main()