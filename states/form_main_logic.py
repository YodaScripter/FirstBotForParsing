from aiogram.dispatcher.filters.state import State, StatesGroup


class FormMainLogic(StatesGroup):
    lang = State()
    url = State()
    n = State()