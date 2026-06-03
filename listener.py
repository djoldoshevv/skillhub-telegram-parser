import os
import json
import logging
import requests
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.errors import ChannelPrivateError, InviteHashExpiredError
from config import config


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("parser.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("skillhub_parser")

# Валидируем настройки перед запуском
config.validate()

# Путь к файлу со списком каналов
CHANNELS_FILE = "channels.json"
TEMP_DIR = "temp"

# Создаем папку для временных файлов, если её нет
os.makedirs(TEMP_DIR, exist_ok=True)

def load_tracked_channels():
    """Загружает список отслеживаемых каналов из файла."""
    if not os.path.exists(CHANNELS_FILE):
        # Дефолтный список каналов для примера
        default_channels = ["durov", "telegram"]
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(default_channels, f, ensure_ascii=False, indent=4)
        return default_channels
    try:
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            channels = json.load(f)
            return [str(c).lower().strip().lstrip("@") for c in channels]
    except Exception as e:
        logger.error(f"Ошибка при чтении channels.json: {e}")
        return []

def save_tracked_channels(channels):
    """Сохраняет список отслеживаемых каналов в файл."""
    try:
        # Уникализируем и очищаем список
        cleaned_channels = list(set([str(c).lower().strip().lstrip("@") for c in channels if c]))
        with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
            json.dump(cleaned_channels, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении channels.json: {e}")
        return False

# Инициализируем список отслеживаемых каналов
tracked_channels = load_tracked_channels()
logger.info(f"Загружено {len(tracked_channels)} каналов для мониторинга: {tracked_channels}")

# Создаем клиента Telethon (используем StringSession для Render, если она передана)
session_string = os.getenv("TELEGRAM_SESSION_STRING")
if session_string:
    # Очищаем строку от возможных пробелов и переносов строк при копировании из терминала
    session_string = session_string.strip().replace("\n", "").replace("\r", "").replace(" ", "")
    # Важно: Telethon StringSession начинается с символа версии '1', а остальная часть - это base64.
    # Нам нужно правильно дополнить (pad) именно base64 часть, а не всю строку целиком!
    if session_string.startswith('1'):
        version = '1'
        payload = session_string[1:]
        # Добавляем '=' к base64 payload, чтобы его длина делилась на 4
        missing_padding = len(payload) % 4
        if missing_padding:
            payload += '=' * (4 - missing_padding)
        session_string = version + payload
    else:
        # Если версия не '1', просто пробуем дополнить всю строку на всякий случай
        missing_padding = len(session_string) % 4
        if missing_padding:
            session_string += '=' * (4 - missing_padding)
            
    client = TelegramClient(StringSession(session_string), config.api_id, config.api_hash)
    logger.info("🔑 Инициализация клиента Telethon через StringSession")
else:
    client = TelegramClient(config.session_name, config.api_id, config.api_hash)
    logger.info("📁 Инициализация клиента Telethon через локальный файл сессии")


def send_to_n8n(data, file_path=None, media_type=None):
    """Отправляет данные поста на n8n Webhook."""
    try:
        url = config.n8n_webhook_url
        logger.info(f"Отправка сообщения на n8n Webhook ({url})...")
        
        if file_path and os.path.exists(file_path):
            # Отправка с медиафайлом (Multipart form-data)
            with open(file_path, 'rb') as f:
                files = {
                    'media_file': (os.path.basename(file_path), f, 'application/octet-stream')
                }
                # В multipart/form-data все поля данных должны быть строками
                payload = {
                    'text': data.get('text', ''),
                    'channel_name': str(data.get('channel_name', '')),
                    'channel_id': str(data.get('channel_id', '')),
                    'message_id': str(data.get('message_id', '')),
                    'media_type': str(media_type)
                }
                response = requests.post(url, data=payload, files=files, timeout=30)
        else:
            # Отправка только текста (JSON)
            response = requests.post(url, json=data, timeout=30)
            
        if response.status_code in [200, 201]:
            logger.info(f" успешно отправлено в n8n! Статус: {response.status_code}")
            return True
        else:
            logger.error(f"Ошибка n8n Webhook! Код ответа: {response.status_code}, Текст: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Не удалось связаться с n8n: {e}")
        return False

def clean_channel_input(text):
    """Очищает юзернейм канала от ссылок и символов @."""
    text = text.strip()
    if "t.me/" in text:
        text = text.split("t.me/")[-1]
    text = text.lstrip("@").split("?")[0]
    return text.lower().strip()

@client.on(events.NewMessage)
async def handle_new_message(event):
    global tracked_channels
    
    # 1. ОБРАБОТКА КОМАНД УПРАВЛЕНИЯ (в Избранном / Saved Messages)
    if event.is_private:
        sender = await event.get_sender()
        sender_username = sender.username.lower() if getattr(sender, 'username', None) else ""
        
        # Проверяем, что отправитель — администратор
        is_admin = False
        if config.admin_username and sender_username == config.admin_username:
            is_admin = True
        
        # Также разрешаем отправку самому себе (Saved Messages имеет chat_id == me_id)
        me = await client.get_me()
        if event.chat_id == me.id:
            is_admin = True

        if is_admin and event.text:
            text = event.text.strip()
            
            # Команда /add
            if text.startswith("/add"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    await event.reply("❌ Использование: `/add @channel_username` или `/add t.me/channel`")
                    return
                
                channel_input = clean_channel_input(parts[1])
                if not channel_input:
                    await event.reply("❌ Некорректное имя канала.")
                    return
                
                if channel_input in tracked_channels:
                    await event.reply(f"ℹ️ Канал `@{channel_input}` уже отслеживается.")
                    return
                
                # Пробуем подписаться/проверить доступ к каналу
                try:
                    await client(JoinChannelRequest(channel_input))
                    tracked_channels.append(channel_input)
                    if save_tracked_channels(tracked_channels):
                        await event.reply(f"✅ Успешно добавлен и подписан: `@{channel_input}`")
                        logger.info(f"Добавлен новый канал для мониторинга: @{channel_input}")
                    else:
                        await event.reply("❌ Не удалось сохранить список каналов.")
                except ChannelPrivateError:
                    await event.reply(f"❌ Канал `@{channel_input}` приватный, и у юзербота нет туда доступа.")
                except Exception as e:
                    await event.reply(f"❌ Ошибка при попытке войти в `@{channel_input}`: {e}")
                return
            
            # Команда /remove
            elif text.startswith("/remove") or text.startswith("/del"):
                parts = text.split(maxsplit=1)
                if len(parts) < 2:
                    await event.reply("❌ Использование: `/remove @channel_username` или `/remove t.me/channel`")
                    return
                
                channel_input = clean_channel_input(parts[1])
                if channel_input not in tracked_channels:
                    await event.reply(f"ℹ️ Канал `@{channel_input}` не найден в списке отслеживаемых.")
                    return
                
                # Удаляем из списка
                tracked_channels.remove(channel_input)
                if save_tracked_channels(tracked_channels):
                    try:
                        # Попробуем выйти из канала, чтобы не захламлять подписки
                        await client(LeaveChannelRequest(channel_input))
                        await event.reply(f"✅ Успешно удален и покинут: `@{channel_input}`")
                    except Exception:
                        await event.reply(f"✅ Успешно удален из списка (не удалось автоматически выйти): `@{channel_input}`")
                    logger.info(f"Удален канал из мониторинга: @{channel_input}")
                else:
                    await event.reply("❌ Не удалось сохранить список каналов.")
                return
            
            # Команда /list
            elif text == "/list":
                if not tracked_channels:
                    await event.reply("📭 Список отслеживаемых каналов пуст.")
                    return
                
                channels_str = "\n".join([f"{i+1}. @{c}" for i, c in enumerate(tracked_channels)])
                await event.reply(f"📋 **Список отслеживаемых каналов ({len(tracked_channels)}):**\n\n{channels_str}")
                return

    # 2. ПАРСИНГ ПУБЛИКАЦИЙ В КАНАЛАХ
    if event.is_channel:
        chat = await event.get_chat()
        chat_username = chat.username.lower() if getattr(chat, 'username', None) else None
        chat_id = chat.id
        
        # Проверяем, входит ли этот канал в наш список отслеживаемых
        is_tracked = False
        if chat_username and chat_username in tracked_channels:
            is_tracked = True
        elif str(chat_id) in tracked_channels:
            is_tracked = True
            
        if not is_tracked:
            return
            
        # Игнорируем сервисные сообщения
        if event.action:
            return
            
        logger.info(f"📢 Обнаружен новый пост в канале @{chat_username or chat_id} (ID сообщения: {event.id})")
        
        # Собираем данные сообщения
        post_data = {
            'text': event.text or '',
            'channel_name': chat_username or chat.title,
            'channel_id': chat_id,
            'message_id': event.id
        }
        
        # Проверяем наличие медиафайлов
        file_path = None
        media_type = None
        
        if event.media:
            # Определяем тип медиа
            if event.photo:
                media_type = "photo"
            elif event.video:
                media_type = "video"
            elif event.document:
                media_type = "document"
            else:
                media_type = "other"
                
            logger.info(f"⏳ Скачивание медиа ({media_type}) для сообщения {event.id}...")
            try:
                # Скачиваем файл во временную директорию
                file_path = await event.download_media(file=TEMP_DIR)
                if file_path:
                    logger.info(f"✅ Медиа успешно скачано: {file_path}")
            except Exception as e:
                logger.error(f"❌ Ошибка скачивания медиа: {e}")
                file_path = None
                media_type = None
                
        # Отправляем на n8n Webhook
        success = send_to_n8n(post_data, file_path, media_type)
        
        # Удаляем временный файл, если он был скачан
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"🧹 Временный файл удален: {file_path}")
            except Exception as e:
                logger.error(f"🧹 Не удалось удалить временный файл {file_path}: {e}")

def run_health_check_server():
    import threading
    from http.server import SimpleHTTPRequestHandler, HTTPServer
    
    port = int(os.getenv("PORT", 8080))
    class HealthCheckHandler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health" or self.path == "/":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"OK")
            else:
                self.send_response(404)
                self.end_headers()
                
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"🩺 Фоновый веб-сервер проверки жизнеспособности запущен на порту {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"❌ Не удалось запустить веб-сервер проверки жизнеспособности: {e}")

async def main():
    logger.info("🚀 Инициализация сессии юзербота Telegram...")
    # Запускаем клиента (если запускается в первый раз, в терминале появится запрос телефона и кода)
    await client.start()
    me = await client.get_me()
    logger.info(f"✨ Успешная авторизация от лица аккаунта: {me.first_name} (@{me.username})")
    logger.info(f"💡 Команды управления работают в вашем чате 'Saved Messages' (Избранное).")
    
    # Запускаем бесконечное прослушивание
    logger.info("📡 Слушатель каналов успешно запущен в фоновом режиме.")
    await client.run_until_disconnected()

if __name__ == "__main__":
    import asyncio
    import threading
    
    # Запускаем фоновый веб-сервер, если задан порт (для Render)
    if os.getenv("PORT"):
        threading.Thread(target=run_health_check_server, daemon=True).start()
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⏹️ Скрипт остановлен пользователем.")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка при работе скрипта: {e}")

