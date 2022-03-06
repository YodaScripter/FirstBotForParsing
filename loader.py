from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from telethon import TelegramClient
from utils.misc.logging import logger
from data import config

logger.info("Подключение к боту")
bot = Bot(token=config.API_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

logger.info("Подключение к клиенту")
client = TelegramClient(config.SESSION_NAME, config.API_ID, config.API_HASH)
client.start()
