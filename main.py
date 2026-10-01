import json
import logging
import sqlite3
import time
import requests

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

# Загрузка конфигурации
def load_config(config_path="config.json"):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.critical(f"Не удалось загрузить config.json: {e}")
        exit(1)

CONFIG = load_config()

# Инициализация базы данных SQLite
def init_db():
    conn = sqlite3.connect("sent_projects.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sent_projects (
            project_id INTEGER PRIMARY KEY
        )
    """)
    conn.commit()
    conn.close()

def is_project_sent(project_id: int) -> bool:
    conn = sqlite3.connect("sent_projects.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM sent_projects WHERE project_id = ?", (project_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def mark_project_as_sent(project_id: int):
    conn = sqlite3.connect("sent_projects.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO sent_projects (project_id) VALUES (?)", (project_id,))
    conn.commit()
    conn.close()

# Получение проектов с Freelancehunt API
def fetch_projects():
    url = "https://api.freelancehunt.com/v2/projects"
    headers = {
        "Authorization": f"Bearer {CONFIG['freelancehunt_token']}",
        "Accept-Language": "uk"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get("data", [])
    except Exception as e:
        logging.error(f"Ошибка при получении данных из Freelancehunt API: {e}")
        return []

# Проверка текста на соответствие фильтрам
def matches_filters(title: str, description: str) -> bool:
    text = f"{title} {description}".lower()
    
    keywords = [kw.lower() for kw in CONFIG.get("keywords", [])]
    stop_words = [sw.lower() for sw in CONFIG.get("stop_words", [])]

    # Проверка на стоп-слова
    for sw in stop_words:
        if sw in text:
            return False

    # Проверка на ключевые слова
    for kw in keywords:
        if kw in text:
            return True

    return False

# Форматирование бюджета
def format_budget(budget_data):
    if not budget_data:
        return "Договорная"
    amount = budget_data.get("amount", "")
    currency = budget_data.get("currency", "")
    return f"{amount} {currency}".strip()

# Отправка сообщения в Telegram
def send_telegram_message(project):
    bot_token = CONFIG["telegram_bot_token"]
    chat_id = CONFIG["telegram_chat_id"]
    
    attr = project.get("attributes", {})
    project_id = project.get("id")
    title = attr.get("name", "Без названия")
    budget = format_budget(attr.get("budget"))
    bids_count = attr.get("bid_count", 0)
    link = project.get("links", {}).get("html", "")

    text = (
        f"🎯 <b>{title}</b>\n\n"
        f"💰 <b>Бюджет:</b> {budget}\n"
        f"📩 <b>Ставок:</b> {bids_count}\n"
        f"🔗 <a href='{link}'>Смотреть проект</a>"
    )

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logging.info(f"Проект #{project_id} успешно отправлен в Telegram.")
        return True
    except Exception as e:
        logging.error(f"Ошибка при отправке в Telegram (ID {project_id}): {e}")
        return False

# Основной цикл проверки
def check_new_projects():
    logging.info("Сканирование новых проектов...")
    projects = fetch_projects()

    for project in reversed(projects):  # Обработка от старых к новым
        project_id = project.get("id")
        if not project_id or is_project_sent(project_id):
            continue

        attr = project.get("attributes", {})
        title = attr.get("name", "")
        description = attr.get("description", "")

        if matches_filters(title, description):
            if send_telegram_message(project):
                mark_project_as_sent(project_id)
            time.sleep(1)

def main():
    init_db()
    logging.info("Бот-монитор Freelancehunt запущен.")
    
    interval = CONFIG.get("check_interval_seconds", 300)
    
    while True:
        try:
            check_new_projects()
        except Exception as e:
            logging.error(f"Непредвиденная ошибка в главном цикле: {e}")
            
        time.sleep(interval)

if __name__ == "__main__":
    main()