import logging
from os import getenv

import aiogram.utils.markdown as md
import mysql.connector
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor
from mysql.connector import Error
from telethon import TelegramClient

from config import db_config

# Окружение
API_TOKEN = getenv("API_TOKEN")
api_id = getenv("API_ID")
api_hash = getenv("API_HASH")
session_name = getenv("SESSION_NAME")
if not api_hash or not API_TOKEN or not api_id:
    exit("Error: getenv")

# Бот
dp = Dispatcher(Bot(token=API_TOKEN), storage=MemoryStorage())
client = TelegramClient('session_name', api_id, api_hash)
client.start()


async def set_default_commands(dp):
    await dp.bot.set_my_commands([
        types.BotCommand("start", "Запустить бота"),
        types.BotCommand("list", "Список каналов"),
        types.BotCommand("delete", "Удалить канал из БД"),
        types.BotCommand("cancel", "Отменить действие"),
    ])


class FormMainLogic(StatesGroup):
    lang = State()
    url = State()
    n = State()


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    logging.info('Состояние отмены %r', current_state)
    await state.finish()
    await message.reply('Отменено.', reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    await FormMainLogic.lang.set()
    await message.answer("Введите язык каналов (рус/англ):")


@dp.message_handler(state=FormMainLogic.lang)
async def process_lang(message: types.Message, state: FSMContext):
    if message.text.lower() not in ["рус", "англ"]:
        return await message.reply('Можно выбрать только рус/англ (регистр не важен)')

    async with state.proxy() as data:
        data["lang"] = message.text.lower()

    await FormMainLogic.next()
    await message.answer("Введите ссылку/и:")


@dp.message_handler(state=FormMainLogic.url)
async def process_url(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['urls'] = message.text.split(",")

    conn = await create_connection_mysql_db(db_config["mysql"]["host"],
                                            db_config["mysql"]["user"],
                                            db_config["mysql"]["pass"])
    cursor = conn.cursor()

    for item in data['urls']:
        try:
            entry = await client.get_entity(item)
        except:
            return await message.reply(f"Что-то не так с ссылкой {item}")

        # Добавление в таблицу каналов
        cursor.execute(f"""
        SELECT * FROM parse_tg.channel_list_for_user 
        WHERE name = '{entry.title}' and url = '{item}';
        """)
        query_result = cursor.fetchall()

        if len(query_result) == 0:
            cursor.execute(f"""
            INSERT INTO parse_tg.channel_list_for_user (name, url, num_of_messages_downloaded, language) 
            VALUES ('{entry.title}', '{item}', 0, '{data["lang"]}'); 
            """)

    conn.commit()
    cursor.close()
    conn.close()

    await FormMainLogic.next()
    await message.answer("Сколько сообщений?")


@dp.message_handler(state=FormMainLogic.n)
async def process_n(message: types.Message, state: FSMContext):
    if not message.text.isdigit() and message.text != "-1":
        return await message.reply('Нужно число, введите еще раз:')

    conn = await create_connection_mysql_db(db_config["mysql"]["host"],
                                            db_config["mysql"]["user"],
                                            db_config["mysql"]["pass"])
    cursor = conn.cursor()
    await state.update_data(n=int(message.text))

    async with state.proxy() as data:
        await message.answer(
            md.text(
                md.text('Ссылка/и: ', *data['urls']),
                md.text('Кол-во сообщений: ', data['n']),
                md.text('Язык: ', data['lang']),
                sep='\n',
            )
        )

    for item in data['urls']:
        entry = await client.get_entity(item)
        limit_mess = 10000 if data['n'] == -1 else data['n']

        for message_from_client in await client.get_messages(item, limit=limit_mess):
            cursor.execute(f"""
            SELECT * FROM parse_tg.data_for_analysis 
            WHERE message_sending_time='{message_from_client.date}' and channel='{entry.title}';
             """)
            query_result = cursor.fetchall()
            if len(query_result) == 0:
                cursor.execute(f"""
                INSERT INTO parse_tg.data_for_analysis (message_sending_time, message, channel, language) 
                VALUES ('{message_from_client.date}', '{message_from_client.message}', '{entry.title}', '{data["lang"]}');
                """)

        cursor.execute(f"""
            SELECT COUNT(*) FROM parse_tg.data_for_analysis WHERE channel = '{entry.title}';
            """)
        query_result = cursor.fetchall()
        cursor.execute(f"""
            UPDATE parse_tg.channel_list_for_user 
            SET num_of_messages_downloaded = {query_result[0][0]} WHERE name = '{entry.title}';
            """)

    conn.commit()
    cursor.close()
    conn.close()

    await state.finish()


@dp.message_handler(commands='list')
async def channel_list_for_user(message: types.Message):
    conn = await create_connection_mysql_db(db_config["mysql"]["host"],
                                            db_config["mysql"]["user"],
                                            db_config["mysql"]["pass"])
    cursor = conn.cursor()

    cursor.execute("""SELECT name, url, num_of_messages_downloaded FROM parse_tg.channel_list_for_user;""")
    query_result = cursor.fetchall()

    s = ''.join(f"Канал : {i[0]}\nСсылка : {i[1]}\nКоличество скачанных сообщений : {i[2]}\n\n" for i in query_result)
    await message.answer(md.text(
        md.text(s),
    ))


class FormDeleteLogic(StatesGroup):
    name_ch = State()


@dp.message_handler(commands='delete')
async def cmd_start(message: types.Message):
    await FormDeleteLogic.name_ch.set()
    await message.answer("Введите название канала, который хотите удалить:")


@dp.message_handler(state=FormDeleteLogic.name_ch)
async def delete_channel(message: types.Message):
    conn = await create_connection_mysql_db(db_config["mysql"]["host"],
                                            db_config["mysql"]["user"],
                                            db_config["mysql"]["pass"])
    cursor = conn.cursor()

    cursor.execute(f"""
            SELECT * FROM parse_tg.channel_list_for_user 
            WHERE name = '{message.text}';
            """)
    query_result = cursor.fetchall()
    if len(query_result) == 0:
        return await message.reply("Канал не найден")

    cursor.execute(f"""
                    DELETE FROM parse_tg.channel_list_for_user 
                    WHERE name = '{message.text}';
                    """)

    cursor.execute(f"""
                    DELETE FROM parse_tg.data_for_analysis 
                    WHERE channel = '{message.text}';
                    """)

    conn.commit()
    cursor.close()
    conn.close()

    await message.answer("Канал и данные с ним удалены")


async def create_connection_mysql_db(db_host, user_name, user_password, db_name=None):
    connection_db = None
    try:
        connection_db = mysql.connector.connect(
            host=db_host,
            user=user_name,
            passwd=user_password,
            database=db_name
        )
    except Error as db_connection_error:
        print("Возникла ошибка: ", db_connection_error)
    return connection_db


async def on_startup(dp):
    await set_default_commands(dp)


if __name__ == '__main__':
    executor.start_polling(dp, on_startup=on_startup)
