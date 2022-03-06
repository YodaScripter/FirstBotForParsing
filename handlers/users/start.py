import aiogram.utils.markdown as md
from aiogram import types
from aiogram.dispatcher import FSMContext

from data import config
from loader import client
from loader import dp
from states.form_main_logic import FormMainLogic
from utils.db_api.database import create_connection_mysql_db
from utils.misc.logging import logger


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    logger.info("Запуск команды страт")
    await FormMainLogic.lang.set()
    await message.answer("Введите язык каналов (рус/англ):")


@dp.message_handler(state=FormMainLogic.lang)
async def process_lang(message: types.Message, state: FSMContext):
    logger.info("Провека вводимого языка")
    if message.text.lower() not in ["рус", "англ"]:
        return await message.reply('Можно выбрать только рус/англ (регистр не важен)')

    logger.info('Запись данных в data["lang"]')
    async with state.proxy() as data:
        data["lang"] = message.text.lower()

    await FormMainLogic.next()
    await message.answer("Введите ссылку/и:")


@dp.message_handler(state=FormMainLogic.url)
async def process_url(message: types.Message, state: FSMContext):
    logger.info('Сплит по запятой')
    async with state.proxy() as data:
        data['urls'] = message.text.split(",")

    conn = await create_connection_mysql_db(config.MYSQL_HOST,
                                            config.MYSQL_USER,
                                            config.MYSQL_PASS)
    cursor = conn.cursor()

    logger.info('Проверка корректности ссылки и запись в parse_tg.channel_list_for_user')
    for item in data['urls']:
        try:
            entry = await client.get_entity(item)
        except Exception as err:
            logger.error("Ошибка: ", err)
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
    logger.info('Проверка введенного значение на число')
    if not message.text.isdigit() and message.text != "-1":
        return await message.reply('Нужно число, введите еще раз:')

    conn = await create_connection_mysql_db(config.MYSQL_HOST,
                                            config.MYSQL_USER,
                                            config.MYSQL_PASS)
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

    logger.info('Парсинг сообщений и запись в БД')
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
