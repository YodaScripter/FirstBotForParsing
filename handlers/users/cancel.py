from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text

from loader import dp
from utils.misc.logging import logger


@dp.message_handler(state='*', commands='cancel')
@dp.message_handler(Text(equals='cancel', ignore_case=True), state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    logger.info("Действие отменено")
    current_state = await state.get_state()
    if current_state is None:
        return
    await state.finish()
    await message.reply('Действие отменено', reply_markup=types.ReplyKeyboardRemove())
