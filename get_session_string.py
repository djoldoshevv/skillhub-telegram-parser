import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

# Загружаем настройки из .env
load_dotenv()

api_id = os.getenv("TELEGRAM_API_ID")
api_hash = os.getenv("TELEGRAM_API_HASH")

if not api_id or not api_hash:
    print("❌ Ошибка: Убедитесь, что TELEGRAM_API_ID и TELEGRAM_API_HASH заполнены в файле .env!")
    exit(1)

api_id = int(api_id)

# Инициализируем клиента на основе уже существующей локальной сессии
client = TelegramClient("skillhub_session", api_id, api_hash)

async def main():
    session_str = StringSession.save(client.session)
    print("\n" + "="*80)
    print("🔑 ВАША СТРОКА СЕССИИ (TELEGRAM_SESSION_STRING) ДЛЯ ДЕПЛОЯ:")
    print("="*80)
    print(session_str)
    print("="*80)
    print("\n👉 Скопируйте всю эту длинную строку целиком.")
    print("👉 Добавьте её в настройки Environment Variables на Render как:")
    print("   Key: TELEGRAM_SESSION_STRING")
    print("   Value: [скопированная строка]\n")

with client:
    client.loop.run_until_complete(main())
