import aiogram.utils.markdown as md
from aiogram import types
from aiogram.dispatcher import FSMContext

from data import config
from keyboards.default.ketboards import keyboard_rus_en, keyboard_yes_no
from loader import client
from loader import dp
from loader import exception_dict
from states.form_main_logic import FormMainLogic
from utils.additionally import add_urls_to_list
from utils.db_api.mysql import create_connection_mysql_db
from utils.misc.logging import logger


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    logger.info("Запуск команды страт")
    await FormMainLogic.lang.set()
    await message.answer("Введите язык каналов (русский/английский):", reply_markup=keyboard_rus_en)


@dp.message_handler(state=FormMainLogic.lang)
async def process_lang(message: types.Message, state: FSMContext):
    logger.info(f"Провека вводимого языка - {message.text}")

    if message.text.lower() not in ["русский", "английский"]:
        return await message.reply('Можно выбрать только русский/английский (регистр не важен)')

    logger.info(f'Запись данных в data["lang"] - {message.text.lower()}')
    async with state.proxy() as data:
        data["lang"] = message.text.lower()

    await FormMainLogic.next()
    await message.answer("Нужно записывать media? (да/нет)", reply_markup=keyboard_yes_no)


@dp.message_handler(state=FormMainLogic.media)
async def process_media(message: types.Message, state: FSMContext):
    if message.text.lower() not in ["да", "нет"]:
        return await message.reply('Можно выбрать только да/нет (регистр не важен)')

    logger.info(f'Запись данных в data["media"] - {message.text.lower()}')

    async with state.proxy() as data:
        data["media"] = message.text.lower()

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Спарсить все что есть в list")

    await FormMainLogic.next()
    await message.answer("Введите ссылку/и:", reply_markup=keyboard)


@dp.message_handler(state=FormMainLogic.url)
async def process_url(message: types.Message, state: FSMContext):
    if message.text == "Спарсить все что есть в list":
        conn = await create_connection_mysql_db(config.MYSQL_HOST,
                                                config.MYSQL_USER,
                                                config.MYSQL_PASS)
        cursor = conn.cursor()
        async with state.proxy() as data:
            cursor.execute(f"""
            SELECT url FROM parse_tg.channel_list_for_user
            WHERE language='{data["lang"]}';
            """)

            data['urls'] = [item[0] for item in cursor.fetchall()]

            if len(data['urls']) == 0:
                return await message.answer("в /list пусто")

        cursor.close()
        conn.close()
    else:
        await add_urls_to_list(message, state)

    await FormMainLogic.next()
    await message.answer("Сколько сообщений?")


@dp.message_handler(state=FormMainLogic.n)
async def process_n(message: types.Message, state: FSMContext):
    logger.info(f'Проверка введенного текста на число - {message.text}')

    if not message.text.isdigit() and message.text > 5000 and message.text != "-1":
        return await message.reply('Введите число [-1:5000]:')

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

    logger.info(f"Парсинг сообщений и запись в БД из - {data['urls']}")

    await message.answer("Парсинг начался...")

    for url in data['urls']:
        if url in exception_dict:
            url = exception_dict[url]

        entry = await client.get_entity(url)

        limit_mess = 10000 if data['n'] == -1 else data['n']

        get_mes = await client.get_messages(url, limit=limit_mess)

        for message_from_client in get_mes:

            path = None
            if message_from_client.photo and data['media'] == 'да':
                path = await message_from_client.download_media(file=f"media/{entry.title}/{message_from_client.id}")

            sql_q = f"""
            SELECT * FROM parse_tg.data_for_analysis 
            WHERE message_sending_time='{message_from_client.date}' and channel='{entry.title}';
             """
            cursor.execute(sql_q)
            query_result = cursor.fetchall()

            if len(query_result) == 0:
                sql_q = """
                INSERT INTO parse_tg.data_for_analysis (message_sending_time, message, channel, language, media) 
                VALUES (%s, %s, %s, %s, %s);
                """
                val = (message_from_client.date, message_from_client.message,
                       entry.title, data["lang"], path)
                try:
                    cursor.execute(sql_q, val)
                except Exception as e:
                    logger.error(f"Ошибка вставки запроса: {sql_q} и {val}")
                    return await message.answer("Ошибка обработки запроса")

        cursor.execute(f"""
            SELECT COUNT(*) FROM parse_tg.data_for_analysis WHERE channel = '{entry.title}';
            """)
        query_result = cursor.fetchall()
        cursor.execute(f"""
            UPDATE parse_tg.channel_list_for_user 
            SET num_of_messages_downloaded = {query_result[0][0]} WHERE name = '{entry.title}';
            """)

        conn.commit()
        logger.info(f"Пасинг с ссылки {url} завершен")
        await message.answer(f"Пасинг с ссылки {url} завершен")

    cursor.close()
    conn.close()
    await message.answer("Парсинг завершен")
    await state.finish()
