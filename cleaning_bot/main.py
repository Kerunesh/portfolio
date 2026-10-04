import asyncio
import logging
from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from database import init_db
from handlers.user_handlers import router # Імпортуємо нашу логіку

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

async def main():
    await init_db()
    
    # Підключаємо роутер з нашими хендлерами до диспетчера
    dp.include_router(router)
    
    logger.info("Starting bot with FSM handlers...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped!")