from aiogram.dispatcher.filters.state import State, StatesGroup


class FormDeleteLogic(StatesGroup):
    name_ch = State()
