from aiogram.dispatcher.filters.state import State, StatesGroup


class FormAddUrl(StatesGroup):
    lang = State()
    url = State()
