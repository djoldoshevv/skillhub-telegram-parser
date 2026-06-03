import os
import sys
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

class Config:
    def __init__(self):
        self.api_id = os.getenv("TELEGRAM_API_ID")
        self.api_hash = os.getenv("TELEGRAM_API_HASH")
        self.session_name = os.getenv("TELEGRAM_SESSION_NAME", "skillhub_session")
        self.n8n_webhook_url = os.getenv("N8N_WEBHOOK_URL")
        self.admin_username = os.getenv("ADMIN_USERNAME")

        if self.admin_username:
            # Убираем @, если пользователь случайно ввел её
            self.admin_username = self.admin_username.lstrip("@").lower()

    def validate(self):
        """Проверяет корректность заполнения конфигурационного файла."""
        errors = []
        if not self.api_id:
            errors.append("TELEGRAM_API_ID не указан в файле .env")
        else:
            try:
                self.api_id = int(self.api_id)
            except ValueError:
                errors.append("TELEGRAM_API_ID должен быть числом")

        if not self.api_hash:
            errors.append("TELEGRAM_API_HASH не указан в файле .env")

        if not self.n8n_webhook_url:
            errors.append("N8N_WEBHOOK_URL не указан в файле .env")

        if errors:
            print("\n❌ Ошибка конфигурации! Пожалуйста, исправьте файл .env:")
            for err in errors:
                print(f"  - {err}")
            print("\nПодробности в README.md. Скрипт остановлен.")
            sys.exit(1)

        print("✅ Конфигурация успешно загружена и проверена.")

config = Config()
