import asyncio
import logging
from os import getenv

import aiogram.utils.markdown as md
import mysql.connector
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode
from aiogram.utils import executor
from mysql.connector import Error
from telethon import TelegramClient
from config import db_config

API_TOKEN = getenv("API_TOKEN")
if not API_TOKEN:
    exit("Error: API_TOKEN")
api_id = getenv("API_ID")
if not api_id:
    exit("Error: api_id")
api_hash = getenv("API_HASH")
if not api_hash:
    exit("Error: api_hash")

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
client = TelegramClient('session_name', api_id, api_hash)
client.start()


class Form(StatesGroup):
    url = State()
    n = State()


async def create_connection_mysql_db(db_host, user_name, user_password, db_name=None):
    connection_db = None
    try:
        connection_db = mysql.connector.connect(
            host=db_host,
            user=user_name,
            passwd=user_password,
            database=db_name
        )
        # print("Подключение к MySQL успешно выполнено")
    except Error as db_connection_error:
        print("Возникла ошибка: ", db_connection_error)
    return connection_db


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    await Form.url.set()
    await message.answer("Введите ссылку")


@dp.message_handler(commands='list')
async def channel_list_for_user(message: types.Message):
    conn = await create_connection_mysql_db(db_config["mysql"]["host"],
                                            db_config["mysql"]["user"],
                                            db_config["mysql"]["pass"])
    cursor = conn.cursor()

    sql_check_values = """SELECT name, url, num_of_messages_downloaded FROM parse_tg.channel_list_for_user;"""
    cursor.execute(sql_check_values)
    query_result = cursor.fetchall()

    await message.answer(md.text(
        md.text(query_result),
    ))


@dp.message_handler(state=Form.url)
async def process_url(message: types.Message, state: FSMContext):
    conn = await create_connection_mysql_db(db_config["mysql"]["host"],
                                            db_config["mysql"]["user"],
                                            db_config["mysql"]["pass"])
    cursor = conn.cursor()

    async with state.proxy() as data:
        data['url'] = message.text

    try:
        entry = await client.get_entity(data['url'])
    except:
        return await message.reply("Что-то не так с ссылкой")

    sql_check_values = f"""
    SELECT * FROM parse_tg.channel_list_for_user 
    WHERE name = '{entry.title}' and url = '{data["url"]}';
    """
    cursor.execute(sql_check_values)
    query_result = cursor.fetchall()

    if len(query_result) == 0:
        sql_insert = f"""
        INSERT INTO parse_tg.channel_list_for_user (name, url, num_of_messages_downloaded) 
        VALUES ('{entry.title}', '{data["url"]}', 0); 
        """
        cursor.execute(sql_insert)

    conn.commit()
    cursor.close()
    conn.close()

    await Form.next()
    await message.answer("Сколько сообщений?")


@dp.message_handler(lambda message: message.text.isdigit() or message.text == "-1", state=Form.n)
async def process_n(message: types.Message, state: FSMContext):
    conn = await create_connection_mysql_db(db_config["mysql"]["host"],
                                            db_config["mysql"]["user"],
                                            db_config["mysql"]["pass"])
    cursor = conn.cursor()

    await state.update_data(n=int(message.text))

    async with state.proxy() as data:
        await message.answer(
            md.text(
                md.text('Ссылка', data['url']),
                md.text('Кол-во сообщений:', data['n']),
                sep='\n',
            ),
            parse_mode=ParseMode.MARKDOWN,
        )

    entry = await client.get_entity(data['url'])
    limit_mess = 10000 if data['n'] == -1 else data['n']

    for message_from_client in await client.get_messages(data['url'], limit=limit_mess):
        sql_check_values = f"""
        SELECT * FROM parse_tg.data_for_analysis 
        WHERE message_sending_time='{message_from_client.date}' and channel='{entry.title}';
         """

        cursor.execute(sql_check_values)
        query_result = cursor.fetchall()
        if len(query_result) == 0:
            sql_insert = f"""
            INSERT INTO parse_tg.data_for_analysis (message_sending_time, message, channel) 
            VALUES ('{message_from_client.date}', '{message_from_client.message}', '{entry.title}');
            """
            cursor.execute(sql_insert)

    sql_count = f"""
        SELECT COUNT(*) FROM parse_tg.data_for_analysis WHERE channel = '{entry.title}';
        """
    cursor.execute(sql_count)
    query_result = cursor.fetchall()
    sql_update = f"""
        UPDATE parse_tg.channel_list_for_user 
        SET num_of_messages_downloaded = {query_result[0][0]} WHERE name = '{entry.title}';
        """
    cursor.execute(sql_update)

    conn.commit()
    cursor.close()
    conn.close()

    await state.finish()


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        return
    logging.info('Состояние отмены %r', current_state)
    await state.finish()
    await message.reply('Отменено.', reply_markup=types.ReplyKeyboardRemove())


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
