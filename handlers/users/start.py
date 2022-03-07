import aiogram.utils.markdown as md
from aiogram import types
from aiogram.dispatcher import FSMContext

from data import config
from loader import client
from loader import dp
from loader import exception_dict
from states.form_main_logic import FormMainLogic
from utils.db_api.mysql import create_connection_mysql_db
from utils.misc.logging import logger


@dp.message_handler(commands='start')
async def cmd_start(message: types.Message):
    logger.info("Запуск команды страт")
    await FormMainLogic.lang.set()

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ["Русский", "Английский"]
    keyboard.add(*buttons)

    await message.answer("Введите язык каналов (русский/английский):", reply_markup=keyboard)


@dp.message_handler(state=FormMainLogic.lang)
async def process_lang(message: types.Message, state: FSMContext):

    logger.info(f"Провека вводимого языка - {message.text}")

    if message.text.lower() not in ["русский", "английский"]:
        return await message.reply('Можно выбрать только русский/английский (регистр не важен)')

    logger.info(f'Запись данных в data["lang"] - {message.text.lower()}')
    async with state.proxy() as data:
        data["lang"] = message.text.lower()

    await FormMainLogic.next()

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    buttons = ["Да", "Нет"]
    keyboard.add(*buttons)

    await message.answer("Нужно записывать media? (да/нет)", reply_markup=keyboard)


@dp.message_handler(state=FormMainLogic.media)
async def process_media(message: types.Message, state: FSMContext):

    if message.text.lower() not in ["да", "нет"]:
        return await message.reply('Можно выбрать только да/нет (регистр не важен)')

    logger.info(f'Запись данных в data["media"] - {message.text.lower()}')

    async with state.proxy() as data:
        data["media"] = message.text.lower()

    await FormMainLogic.next()
    await message.answer("Введите ссылку/и:", reply_markup=types.ReplyKeyboardRemove())


@dp.message_handler(state=FormMainLogic.url)
async def process_url(message: types.Message, state: FSMContext):

    logger.info(f'Сплит по запятой - {message.text.split(", ")}')

    async with state.proxy() as data:
        data['urls'] = message.text.split(", ")

    conn = await create_connection_mysql_db(config.MYSQL_HOST,
                                            config.MYSQL_USER,
                                            config.MYSQL_PASS)
    cursor = conn.cursor()

    logger.info(f"Проверка корректности ссылок из {data['urls']} и запись в БД")
    for url in data['urls']:
        if url in exception_dict:
            url = exception_dict[url]

        try:
            entry = await client.get_entity(url)
        except Exception as err:
            logger.error(f"Ошибка входа по ссылке - {url}, err - {err}")
            await message.reply(f"Что-то не так с ссылкой - {url}, она будет пропущена")

            async with state.proxy() as data:
                data['urls'].remove(url)

            continue

        # Добавление в таблицу каналов
        cursor.execute(f"""
        SELECT * FROM parse_tg.channel_list_for_user 
        WHERE name = '{entry.title}' and url = '{url}';
        """)
        query_result = cursor.fetchall()

        if len(query_result) == 0:
            cursor.execute(f"""
            INSERT INTO parse_tg.channel_list_for_user (name, url, num_of_messages_downloaded, language) 
            VALUES ('{entry.title}', '{url}', 0, '{data["lang"]}'); 
            """)

    conn.commit()
    cursor.close()
    conn.close()

    await FormMainLogic.next()
    await message.answer("Сколько сообщений?")


@dp.message_handler(state=FormMainLogic.n)
async def process_n(message: types.Message, state: FSMContext):
    logger.info(f'Проверка введенного текста на число - {message.text}')

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

    logger.info(f"Парсинг сообщений и запись в БД из - {data['urls']}")

    for url in data['urls']:
        if url in exception_dict:
            url = exception_dict[url]

        entry = await client.get_entity(url)

        limit_mess = 10000 if data['n'] == -1 else data['n']

        for message_from_client in await client.get_messages(url, limit=limit_mess):
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
