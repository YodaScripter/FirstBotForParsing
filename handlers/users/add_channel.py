from aiogram import types
from aiogram.dispatcher import FSMContext

from keyboards.default.ketboards import keyboard_rus_en
from loader import dp
from states.form_add_url import FormAddUrl
from utils.additionally import add_urls_to_list
from utils.misc.logging import logger


@dp.message_handler(commands="add")
async def cmd_add_channel(message: types.Message):
    await FormAddUrl.lang.set()

    await message.answer("Введите язык каналов (русский/английский):", reply_markup=keyboard_rus_en)


@dp.message_handler(state=FormAddUrl.lang)
async def process_lang(message: types.Message, state: FSMContext):
    logger.info(f"Провека вводимого языка - {message.text}")

    if message.text.lower() not in ["русский", "английский"]:
        return await message.reply('Можно выбрать только русский/английский (регистр не важен)')

    logger.info(f'Запись данных в data["lang"] - {message.text.lower()}')
    async with state.proxy() as data:
        data["lang"] = message.text.lower()

    await FormAddUrl.next()

    await message.answer("Введите ссылку/и на канал, который нужно добавить в список /list:")


@dp.message_handler(state=FormAddUrl.url)
async def process_url(message: types.Message, state: FSMContext):
    await add_urls_to_list(message, state)
    await state.finish()
