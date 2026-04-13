import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from config.config import settings
from utils.logger import logger


class CalendarService:
    def __init__(self):
        self.creds = None
        self.service = None
        self._authenticate()

    def _authenticate(self):
        """F-26: OAuth2 авторизация"""
        try:
            if settings.GOOGLE_TOKEN_PATH.exists():
                try:
                    self.creds = Credentials.from_authorized_user_file(
                        str(settings.GOOGLE_TOKEN_PATH),
                        ['https://www.googleapis.com/auth/calendar']
                    )
                except ValueError as e:
                    if "refresh_token" in str(e):
                        logger.error("❌ token.json без refresh_token. Удалите его и запустите google_auth.py")
                        raise RuntimeError(
                            "Отсутствует refresh_token. "
                            "Удалите config/token.json и запустите 'python config/google_auth.py'"
                        )
                    raise

            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    raise FileNotFoundError("token.json не найден или недействителен. Запустите google_auth.py")

            self.service = build('calendar', 'v3', credentials=self.creds)
            logger.info("✅ Google Calendar API подключен")

        except Exception as e:
            logger.error(f"❌ Ошибка подключения Google: {e}")
            raise

    def create_event(self, event_data: Dict) -> Optional[Union[str, Dict]]:
        """F-27: Создание события"""
        try:
            # ВАЖНО: LLM возвращает start_time, а не start!
            start_time = event_data.get('start_time') or event_data.get('start')
            if not start_time:
                raise ValueError("Отсутствует start_time или start")

            # Вычисляем end_time на основе duration
            duration = event_data.get('duration', 60)
            from datetime import datetime, timedelta

            # Парсим start_time
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = start_dt + timedelta(minutes=duration)

            # Формируем тело события
            event = {
                'summary': event_data.get('title', 'Без названия'),
                'description': event_data.get('description', ''),
                'location': event_data.get('location', ''),
                'start': {
                    'dateTime': start_dt.isoformat(),
                    'timeZone': 'Europe/Moscow'
                },
                'end': {
                    'dateTime': end_dt.isoformat(),
                    'timeZone': 'Europe/Moscow'
                },
                'reminders': {'useDefault': True},
                'colorId': self._get_color_id(event_data.get('type', 'meeting'))
            }

            # Добавление участников (если есть)
            if event_data.get('participants'):
                event['attendees'] = [{'email': email} for email in event_data['participants']]

            logger.info(f"📝 Создание события: {event}")

            # Создание в Google
            created = self.service.events().insert(
                calendarId='primary',
                body=event
            ).execute()

            logger.info(f"✅ Событие создано: {created.get('htmlLink')}")
            return created.get('htmlLink')

        except HttpError as e:
            if e.resp.status == 409:
                logger.warning("⚠️ Событие уже существует (409)")
                return {"error": "already_exists"}
            logger.error(f"❌ HTTP ошибка: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка создания события: {e}", exc_info=True)
            return None

    def _check_conflicts(self, start: str, end: str) -> List[Dict]:
        """F-22: Проверка пересечений в календаре"""
        try:
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            return events_result.get('items', [])
        except Exception as e:
            logger.error(f"❌ Ошибка проверки конфликтов: {e}")
            return []

    def _generate_alternatives(self, event_data: Dict) -> Dict:
        """F-23: Генерация 3 альтернативных слотов"""
        try:
            start = datetime.fromisoformat(event_data['start'].replace('Z', '+00:00'))
            duration = event_data.get('duration', 60)
            alternatives = []

            for i in range(1, 7):  # Проверяем 6 часов вперёд
                new_start = start + timedelta(hours=i)
                new_end = new_start + timedelta(minutes=duration)

                conflicts = self._check_conflicts(new_start.isoformat(), new_end.isoformat())
                if not conflicts:
                    alternatives.append({
                        'start': new_start.isoformat(),
                        'end': new_end.isoformat(),
                        'summary': event_data.get('title', 'Событие')
                    })

                if len(alternatives) >= 3:
                    break

            return {
                "conflict": True,
                "message": "Время занято. Предлагаю альтернативы:",
                "alternatives": alternatives
            }
        except Exception as e:
            logger.error(f"❌ Ошибка генерации альтернатив: {e}")
            return {"conflict": False}

    def list_events(self, days: int = 7) -> List[Dict]:
        """F-30: Получение событий с учётом часового пояса"""
        try:
            from datetime import datetime, timezone

            # Используем UTC для Google API
            now = datetime.now(timezone.utc)
            future = now + timedelta(days=days)

            logger.info(f"🔍 Запрашиваю события с {now.isoformat()} до {future.isoformat()}")

            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=now.isoformat(),
                timeMax=future.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            logger.info(f"✅ Найдено {len(events)} событий")

            # Для отладки: выводим первое событие
            if events:
                logger.info(f"Пример события: {events[0]}")

            return events

        except HttpError as e:
            logger.error(f"❌ Ошибка получения событий: {e}")
            return []

    def _get_color_id(self, event_type: str) -> str:
        """F-35: Определение цвета события"""
        colors = {
            'meeting': '5',  # Синий
            'call': '3',  # Фиолетовый
            'deadline': '11',  # Красный
            'reminder': '2',  # Зелёный
            'default': '5'
        }
        return colors.get(event_type, colors['default'])

    def delete_event(self, event_id: str) -> bool:
        """F-29: Удаление события"""
        try:
            self.service.events().delete(
                calendarId='primary',
                eventId=event_id
            ).execute()
            logger.info(f"✅ Событие {event_id} удалено")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка удаления: {e}")
            return False


# Создаём глобальный экземпляр
calendar_service = CalendarService()