import os
import sys
import hashlib
import subprocess
from pathlib import Path

# Глобальные пути к FFmpeg
FFMPEG_DIR = Path(r"C:\AI_Assistant\whisper").resolve()
FFMPEG_PATH = FFMPEG_DIR / "ffmpeg.exe"
FFPROBE_PATH = FFMPEG_DIR / "ffprobe.exe"

# Принудительно устанавливаем переменные среды
os.environ["PATH"] = str(FFMPEG_DIR) + os.pathsep + os.environ.get("PATH", "")
os.environ["FFMPEG_BINARY"] = str(FFMPEG_PATH)
os.environ["FFPROBE_BINARY"] = str(FFPROBE_PATH)

# ТЕПЕРЬ импортируем pydub
from pydub import AudioSegment
from config.config import settings
from utils.logger import logger

# Проверка файлов при импорте
if not FFMPEG_PATH.exists():
    raise FileNotFoundError(f"❌ ffmpeg.exe не найден: {FFMPEG_PATH}")
if not FFPROBE_PATH.exists():
    raise FileNotFoundError(f"❌ ffprobe.exe не найден: {FFPROBE_PATH}")

print(f"✅ FFmpeg настроен: {FFMPEG_PATH}")
print(f"✅ FFprobe настроен: {FFPROBE_PATH}")


class WhisperService:
    def __init__(self):
        self.model_path = settings.WHISPER_MODEL_PATH
        self.exe_path = settings.WHISPER_EXE_PATH
        self.temp_dir = Path(settings.TEMP_DIR).resolve()  # <-- АБСОЛЮТНЫЙ ПУТЬ
        self.cache = {}

    def transcribe(self, audio_path: Path, language: str = "ru") -> str:
        """F-07: Вызов whisper-cli.exe с абсолютными путями"""
        try:
            # Абсолютные пути
            exe_path = self.exe_path.resolve()
            model_path = self.model_path.resolve()
            audio_path = Path(audio_path).resolve()

            # АБСОЛЮТНЫЙ путь для WAV (критично!)
            wav_path = self.temp_dir / f"temp_{audio_path.stem}.wav"
            wav_path = wav_path.resolve()  # <-- Делаем абсолютным

            # Создаем директорию temp, если не существует
            wav_path.parent.mkdir(parents=True, exist_ok=True)

            logger.info(f"📄 Создаю WAV: {wav_path}")

            # Конвертация в WAV
            audio = AudioSegment.from_file(str(audio_path))
            audio = audio.set_channels(1).set_frame_rate(16000)
            audio.export(wav_path, format="wav")

            # Проверяем, что файл создан
            if not wav_path.exists():
                raise FileNotFoundError(f"❌ WAV файл не создан: {wav_path}")

            logger.info(f"✅ WAV создан: {wav_path} ({wav_path.stat().st_size} байт)")

            # Команда whisper с АБСОЛЮТНЫМ путем к файлу
            cmd = [
                str(exe_path),
                "-m", str(model_path),
                "-l", language,
                "-f", str(wav_path),  # <-- АБСОЛЮТНЫЙ ПУТЬ
                "--no-timestamps"
            ]

            work_dir = exe_path.parent

            logger.info(f"🎤 Запуск Whisper: {' '.join(cmd)}")
            logger.info(f"    Рабочая директория: {work_dir}")
            logger.info(f"    Входной файл: {wav_path}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                check=True,
                cwd=str(work_dir)
            )

            # Удаление временных файлов
            wav_path.unlink(missing_ok=True)
            audio_path.unlink(missing_ok=True)

            transcription = result.stdout.strip()
            logger.info(f"✅ Распознано: {transcription[:100]}...")
            return transcription

        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Whisper ошибка: returncode={e.returncode}")
            logger.error(f"STDERR: {e.stderr}")
            logger.error(f"STDOUT: {e.stdout}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка транскрибации: {e}", exc_info=True)
            raise


whisper_service = WhisperService()