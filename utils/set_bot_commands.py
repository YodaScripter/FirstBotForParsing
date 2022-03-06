from aiogram import types


async def set_default_commands(dp):
    await dp.bot.set_my_commands(
        [
            types.BotCommand("start", "Запустить бота"),
            types.BotCommand("list", "Список каналов"),
            types.BotCommand("delete", "Удалить канал из БД"),
            types.BotCommand("cancel", "Отменить действие"),
            types.BotCommand("help", "Вывести справку"),
        ]
    )
