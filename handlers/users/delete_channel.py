from aiogram import types

from data import config
from loader import dp
from states.form_delete_logic import FormDeleteLogic
from utils.db_api.database import create_connection_mysql_db


@dp.message_handler(commands='delete')
async def cmd_start(message: types.Message):
    await FormDeleteLogic.name_ch.set()
    await message.answer("Введите название канала, который хотите удалить:")


@dp.message_handler(state=FormDeleteLogic.name_ch)
async def delete_channel(message: types.Message):
    conn = await create_connection_mysql_db(config.MYSQL_HOST,
                                            config.MYSQL_USER,
                                            config.MYSQL_PASS)
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
