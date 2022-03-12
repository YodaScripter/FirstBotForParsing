from aiogram import types
from aiogram.dispatcher import FSMContext

from data import config
from loader import client
from loader import exception_dict
from utils.db_api.mysql import create_connection_mysql_db
from utils.misc.logging import logger


async def add_urls_to_list(message: types.Message, state: FSMContext):
    logger.info(f'Сплит по запятой - {message.text.split(", ")}')

    async with state.proxy() as data:
        temp_str = message.text.replace('\n', '')
        data['urls'] = temp_str.split(", ")
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
