import aiosqlite
import logging

# Налаштування логування, щоб бачити помилки в терміналі
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_NAME = "orders.db"

async def init_db():
    """Створює таблицю orders, якщо її ще не існує."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    username TEXT,
                    name TEXT,
                    phone TEXT,
                    cleaning_type TEXT,
                    area INTEGER,
                    extra_services TEXT,
                    total_price REAL,
                    date TEXT,
                    status TEXT DEFAULT 'new'
                )
            ''')
            await db.commit()
            logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

async def add_order(user_id, username, name, phone, cleaning_type, area, extra_services, total_price, date):
    """Додає нове замовлення в базу даних."""
    try:
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute('''
                INSERT INTO orders (user_id, username, name, phone, cleaning_type, area, extra_services, total_price, date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, username, name, phone, cleaning_type, area, extra_services, total_price, date))
            await db.commit()
            logger.info(f"Order for user {user_id} added successfully.")
    except Exception as e:
        logger.error(f"Error adding order: {e}")