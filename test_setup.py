import ollama
from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

print("🔍 Проверка установки...\n")

# 1. Проверка Ollama
try:
    model = os.getenv("OLLAMA_MODEL")
    response = ollama.chat(
        model=model,
        messages=[{"role": "user", "content": "Сколько будет 2+2? Ответь на русском."}]
    )
    print("✅ Ollama + Qwen работает")
    print(f"   Модель: {model}")
except Exception as e:
    print(f"❌ Ollama ошибка: {e}\n   Запустили ли вы 'ollama serve'?\n")

# 2. Проверка Whisper
whisper_exe = Path(os.getenv("WHISPER_EXE_PATH"))
whisper_model = Path(os.getenv("WHISPER_MODEL_PATH"))

if whisper_exe.exists() and whisper_model.exists():
    print("✅ Whisper установлен")
    print(f"   EXE: {whisper_exe}")
    print(f"   Model: {whisper_model}")
else:
    print("❌ Whisper файлы не найдены")
    if not whisper_exe.exists():
        print(f"   Не найден: {whisper_exe}")
    if not whisper_model.exists():
        print(f"   Не найден: {whisper_model}")
    print("   Скачайте whisper.exe из https://github.com/ggerganov/whisper.cpp/releases")

# 3. Проверка .env
if Path(".env").exists():
    print("\n✅ .env файл найден")
else:
    print("\n❌ .env отсутствует")

# 4. Проверка Google credentials
creds = Path(os.getenv("GOOGLE_CREDENTIALS_PATH"))
if creds.exists():
    print("✅ Google credentials.json найден")
else:
    print("❌ Google credentials.json не найден")

print("\nПроверка завершена!")