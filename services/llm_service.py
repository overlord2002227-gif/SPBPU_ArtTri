import ollama
import json
from typing import Dict, Any, Optional
from config.config import settings
from utils.logger import logger


class LLMService:
    def __init__(self):
        self.model = settings.OLLAMA_MODEL
        self.ollama_client = ollama.Client(host=settings.OLLAMA_HOST)

    def check_connection(self) -> bool:
        """F-02: Проверка доступности Ollama"""
        try:
            self.ollama_client.list()
            logger.info("✅ Ollama доступен")
            return True
        except Exception as e:
            logger.error(f"❌ Ollama не доступен: {e}")
            return False

    def parse_intent(self, text: str) -> Dict[str, Any]:
        """F-14..F-21: Парсинг намерений и генерация JSON"""

        # Предобработка: добавляем контекст даты
        from datetime import datetime, timedelta
        today = datetime.now()

        prompt = f"""Ты — AI-ассистент, который ТОЛЬКО преобразует текст в JSON для календаря.

    ### ПРАВИЛА (строго следуй):
    1. "в 13", "в 9", "в 15" → добавляй :00 (13:00, 09:00, 15:00)
    2. "11 декабря в 13" → 2025-12-11T13:00:00+03:00
    3. "завтра в 14" → {(today + timedelta(days=1)).strftime('%Y-%m-%d')}T14:00:00+03:00
    4. "после обеда" → 14:00
    5. "утром" → 09:00, "вечером" → 18:00
    6. "поход в больницу" → title = "поход в больницу"
    7. "напоминание" → type = "reminder"
    8. Если не можешь определить — "intent": "question"

    ### ПРИМЕРЫ (обязательно изучи):

    Вход: "Создай встречу с Иваном на завтра в 15"
    Выход: {{"intent": "create", "title": "Встреча с Иваном", "start_time": "{(today + timedelta(days=1)).strftime('%Y-%m-%d')}T15:00:00+03:00", "duration": 60, "type": "meeting"}}

    Вход: "Напоминание на 11 декабря в 13 поход в больницу"
    Выход: {{"intent": "create", "title": "поход в больницу", "start_time": "2025-12-11T13:00:00+03:00", "duration": 30, "type": "reminder"}}

    Вход: "Покажи встречи на неделю"
    Выход: {{"intent": "list"}}

    Вход: "Не понятный текст"
    Выход: {{"intent": "question"}}

    ### ВАШ ЗАПРОС:
    Текст: "{text}"

    ВЫВЕДИ ТОЛЬКО JSON, без комментариев, без текста до или после.
    """

        try:
            response = self.ollama_client.chat(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                options={"temperature": 0.1, "num_predict": 300}
            )

            result = response['message']['content'].strip()
            logger.info(f"🧠 LLM ответ: {result}")

            # Агрессивная очистка
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0].strip()
            elif "```" in result:
                result = result.split("```")[1].split("```")[0].strip()

            # Проверка на пустой результат
            if not result or result == "{}":
                return {"intent": "question", "text": text}

            # Попытка парсинга
            parsed = json.loads(result)

            # Валидация обязательных полей
            if "intent" not in parsed:
                parsed["intent"] = "question"

            # Добавление дефолтов
            parsed.setdefault("duration", 30 if "напоминание" in text.lower() else 60)
            parsed.setdefault("type", "reminder" if "напоминание" in text.lower() else "meeting")

            return parsed

        except Exception as e:
            logger.error(f"❌ Ошибка парсинга LLM: {e}, ответ: {result}")
            return {"intent": "question", "text": text}


llm_service = LLMService()