import os
import asyncio
import json
from pathlib import Path
from typing import cast
from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes
)
from telegram.constants import ChatAction
from config.config import settings
from services.llm_service import llm_service
from services.whisper_service import whisper_service
from services.calendar_service import calendar_service
from utils.logger import logger
from functools import wraps


def restricted(func):
    """Декоратор: разрешает доступ только указанным user_id"""

    @wraps(func)
    async def wrapper(self, update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id

        if settings.allowed_users and user_id not in settings.allowed_users:
            logger.warning(f"⚠️ Несанкционированный доступ: user_id={user_id}")
            await update.message.reply_text(
                "❌ Доступ запрещен. Вы не в списке разрешенных пользователей."
            )
            return

        return await func(self, update, context, *args, **kwargs)

    return wrapper


class TelegramHandler:
    def __init__(self):
        self.bot = Bot(token=settings.TELEGRAM_TOKEN)

    @restricted
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """F-40: Команда /start"""
        await update.message.reply_text(
            "👋 Привет! Я AI-ассистент для управления календарём.\n\n"
            "📌 Что я умею:\n"
            "• Создавать встречи голосом или текстом\n"
            "• Проверять занятость времени\n"
            "• Показывать предстоящие события\n\n"
            "Просто напиши или отправь голосовое: "
            "'Создай встречу с Иваном завтра в 14:00'"
        )
        logger.info(f"📱 Новый пользователь: {update.effective_user.id}")

    @restricted
    async def help_cmd(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """F-42: Команда /help"""
        await update.message.reply_text(
            "📋 Примеры команд:\n\n"
            "📝 Текст:\n"
            "'Создай созвон с Петей на завтра в 15:00 на час'\n"
            "'Покажи мои встречи на неделю'\n"
            "'Перенеси встречу с Иваном на пятницу в 16:00'\n\n"
            "🎤 Голос:\n"
            "Просто отправь голосовое сообщение с командой"
        )

    @restricted
    async def handle_voice(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """F-51: Обработка голосовых"""
        await update.message.reply_chat_action(ChatAction.TYPING)

        try:
            # Скачивание в абсолютный путь
            voice_file = await update.message.voice.get_file()
            ogg_path = Path(settings.TEMP_DIR).resolve() / f"voice_{update.update_id}.ogg"
            ogg_path.parent.mkdir(parents=True, exist_ok=True)

            await voice_file.download_to_drive(ogg_path)

            logger.info(f"📥 Скачано: {ogg_path} ({ogg_path.stat().st_size} байт)")

            # Проверка файла
            if not ogg_path.exists():
                raise FileNotFoundError(f"Файл не скачался: {ogg_path}")

            # Транскрибация
            transcription = await asyncio.to_thread(
                whisper_service.transcribe, ogg_path
            )

            # Удаление оригинала
            ogg_path.unlink(missing_ok=True)

            await update.message.reply_text(
                f"🎤 Распознано:\n*{transcription}*",
                parse_mode='Markdown'
            )

            # Обработка как текст
            await self._process_text(update, context, transcription)

        except Exception as e:
            logger.error(f"❌ Ошибка голоса: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка распознавания: {e}")

    @restricted
    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """F-11: Обработка текста"""
        await update.message.reply_chat_action(ChatAction.TYPING)
        text = update.message.text

        # F-12: Очистка
        text = " ".join(text.split())[:2000]

        await self._process_text(update, context, text)

    async def _process_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Общая обработка текста"""
        try:
            logger.info(f"🔍 Обрабатываю текст: '{text}'")

            # Парсинг намерений
            parsed = await asyncio.to_thread(llm_service.parse_intent, text)

            logger.info(f"📊 Результат парсинга: {parsed}")

            if parsed.get("intent") == "create":
                await self._handle_create(update, context, parsed)
            elif parsed.get("intent") == "list":
                await self._handle_list(update, context)
            elif parsed.get("intent") == "question":
                await self._handle_question(update, context, text)
            else:
                logger.warning(f"⚠️ Неизвестный intent: {parsed.get('intent')}")
                await update.message.reply_text("❓ Не понял команду. Используйте /help")

        except Exception as e:
            logger.error(f"❌ Ошибка обработки: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {e}")

    @restricted
    async def _handle_create(self, update: Update, context: ContextTypes.DEFAULT_TYPE, data: dict):
        """F-44: Создание события с подтверждением"""
        import json

        # Сохраняем в контекст
        context_key = f"event_{update.update_id}"
        context.user_data[context_key] = data

        # Формирование сообщения
        msg = f"📅 *{data.get('title', 'Без названия')}*\n"
        if data.get('start_time'):
            msg += f"🕐 {data['start_time']}\n"
        if data.get('duration'):
            msg += f"⏱️ {data['duration']} минут\n"
        if data.get('type'):
            msg += f"📝 Тип: {data['type']}\n"

        keyboard = [
            [InlineKeyboardButton("✅ Подтвердить",
                                  callback_data=f"confirm_create|{context_key}")],
            [InlineKeyboardButton("❌ Отмена", callback_data="cancel")]
        ]

        await update.message.reply_text(
            msg,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )

    @restricted
    async def _handle_list(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """F-30: Показ событий"""
        logger.info("📋 Запрос списка событий")

        events = await asyncio.to_thread(calendar_service.list_events, days=7)

        if not events:
            await update.message.reply_text("📭 На неделе нет событий")
            return

        message = "📋 Предстоящие события:\n\n"
        for event in events[:10]:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'Без названия')
            message += f"• `{summary}` — {start}\n"

        await update.message.reply_text(message, parse_mode='Markdown')

    async def _handle_create_alt(self, update: Update, context: ContextTypes.DEFAULT_TYPE,
                                 start_time: str, title: str):
        """Создание события из альтернативы"""
        data = {
            "title": title,
            "start_time": start_time,
            "duration": 60,
            "type": "meeting"
        }

        result = await asyncio.to_thread(calendar_service.create_event, data)

        if isinstance(result, str):
            await update.callback_query.edit_message_text(
                f"✅ Создано: [Открыть]({result})",
                parse_mode='Markdown'
            )
        else:
            await update.callback_query.edit_message_text("❌ Ошибка создания")

    async def _handle_question(self, update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
        """Ответ на вопрос через LLM"""
        try:
            response = await asyncio.to_thread(
                llm_service.ollama_client.chat,
                model=llm_service.model,
                messages=[{"role": "user", "content": text}],
                options={"temperature": 0.7}
            )
            await update.message.reply_text(response['message']['content'])
        except Exception as e:
            logger.error(f"❌ Ошибка ответа: {e}", exc_info=True)
            await update.message.reply_text("❌ Не удалось получить ответ")

    @restricted
    async def callback_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """F-44..F-45: Обработка кнопок"""
        query = update.callback_query
        await query.answer()

        logger.info(f"🔘 Callback: {query.data}")

        if query.data.startswith("confirm_create|"):
            context_key = query.data.split("|")[1]
            data = context.user_data.get(context_key)

            if not data:
                await query.edit_message_text("❌ Данные устарели. Отправьте команду снова.")
                return

            logger.info(f"📝 Создаю событие: {data}")

            # Создание
            result = await asyncio.to_thread(calendar_service.create_event, data)

            if isinstance(result, str) and result.startswith("http"):
                await query.edit_message_text(
                    f"✅ Событие создано!\n[Открыть в календаре]({result})",
                    parse_mode='Markdown'
                )
                logger.info(f"✅ Событие создано: {result}")
            elif isinstance(result, dict) and result.get("conflict"):
                keyboard = []
                for alt in result["alternatives"]:
                    keyboard.append([InlineKeyboardButton(
                        f"{alt['start'][:16].replace('T', ' ')}",
                        callback_data=f"create_alt|{alt['start']}|{data.get('title', '')}"
                    )])

                await query.edit_message_text(
                    "⚠️ Время занято. Выберите альтернативу:",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await query.edit_message_text(f"❌ Ошибка: {result}")

        elif query.data.startswith("create_alt|"):
            parts = query.data.split("|")
            start_time = parts[1]
            title = parts[2]
            await self._handle_create_alt(update, context, start_time, title)

        elif query.data == "cancel":
            await query.edit_message_text("❌ Создание отменено")

    def run(self):
        """Запуск бота"""
        app = Application.builder().token(settings.TELEGRAM_TOKEN).build()

        # Команды
        app.add_handler(CommandHandler("start", self.start))
        app.add_handler(CommandHandler("help", self.help_cmd))
        app.add_handler(CommandHandler("calendar", self._handle_list))

        # Сообщения
        app.add_handler(MessageHandler(filters.VOICE, self.handle_voice))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text))

        # Callbacks
        app.add_handler(CallbackQueryHandler(self.callback_handler))

        logger.info("🚀 Бот запущен!")
        app.run_polling()


telegram_handler = TelegramHandler()