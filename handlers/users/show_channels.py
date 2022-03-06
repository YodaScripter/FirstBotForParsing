import aiogram.utils.markdown as md
from aiogram import types

from data import config
from loader import dp
from utils.db_api.database import create_connection_mysql_db
from utils.misc.logging import logger


@dp.message_handler(commands="list")
async def channel_list_for_user(message: types.Message):
    logger.info("Вывод всех каналов")
    conn = await create_connection_mysql_db(config.MYSQL_HOST,
                                            config.MYSQL_USER,
                                            config.MYSQL_PASS)
    cursor = conn.cursor()

    cursor.execute("""SELECT name, url, num_of_messages_downloaded FROM parse_tg.channel_list_for_user;""")
    query_result = cursor.fetchall()
    if len(query_result) == 0:
        await message.answer(md.text(
            md.text("Пока что пусто"),
        ))

    s = ''.join(f"Канал : {i[0]}\nСсылка : {i[1]}\nКоличество скачанных сообщений : {i[2]}\n\n" for i in query_result)
    await message.answer(md.text(
        md.text(s),
    ))
