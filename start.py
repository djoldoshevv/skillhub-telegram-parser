import os
import sys
import subprocess

def run_command(command):
    """Выполняет команду в консоли."""
    try:
        subprocess.check_call(command, shell=True)
        return True
    except subprocess.CalledProcessError:
        return False

def setup_and_run():
    print("====================================================================")
    print("⚡ Добро пожаловать в Skillhub Telegram Parser Setup Launcher! ⚡")
    print("====================================================================")

    # 1. Проверяем наличие файла .env
    if not os.path.exists(".env"):
        print("❌ Файл .env не найден! Создаем его на основе .env.example...")
        if os.path.exists(".env.example"):
            with open(".env.example", "r", encoding="utf-8") as source:
                with open(".env", "w", encoding="utf-8") as target:
                    target.write(source.read())
            print("⚠️ Файл .env создан. Заполните его перед запуском проекта!")
            print("Отредактируйте .env и впишите туда ваши API_ID, API_HASH и URL вебхука n8n.")
            sys.exit(0)
        else:
            print("❌ Ошибка: .env.example также отсутствует. Пересоздайте проект.")
            sys.exit(1)

    # 2. Проверяем заполненность файла .env
    with open(".env", "r", encoding="utf-8") as f:
        env_content = f.read()
    
    placeholders = ["TELEGRAM_API_ID=", "TELEGRAM_API_HASH=", "N8N_WEBHOOK_URL="]
    missing = []
    for p in placeholders:
        for line in env_content.splitlines():
            if line.strip().startswith(p) and len(line.split("=", 1)[-1].strip()) == 0:
                missing.append(p.rstrip("="))
    
    if missing:
        print(f"❌ Файл .env заполнен не до конца. Пропущены переменные: {', '.join(missing)}")
        print("Пожалуйста, откройте .env, заполните эти поля и запустите снова.")
        sys.exit(1)

    # 3. Установка зависимостей
    print("📦 Проверка и установка зависимостей из requirements.txt...")
    # Пробуем установить с флагом --break-system-packages (для macOS PEP 668)
    success = run_command("python3 -m pip install -r requirements.txt --break-system-packages")
    if not success:
        # Пробуем обычный способ (для старых версий pip)
        success = run_command("python3 -m pip install -r requirements.txt")

    if success:
      print("✅ Зависимости успешно установлены/обновлены.")
    else:
      print("⚠️ Не удалось установить зависимости.")
      sys.exit(1)

    # 4. Запуск основного скрипта
    print("\n🚀 Запуск юзербота listener.py...")
    print("--------------------------------------------------------------------")
    try:
      # Запускаем listener.py
      run_command("python3 listener.py")
    except KeyboardInterrupt:
        print("\n⏹️ Работа скрипта успешно остановлена пользователем.")
    except Exception as e:
        print(f"\n💥 Возникла ошибка при работе скрипта: {e}")

if __name__ == "__main__":
    setup_and_run()
