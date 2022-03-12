from aiogram import types

keyboard_rus_en = types.ReplyKeyboardMarkup(resize_keyboard=True)
buttons = ["Русский", "Английский"]
keyboard_rus_en.add(*buttons)

keyboard_yes_no = types.ReplyKeyboardMarkup(resize_keyboard=True)
buttons = ["Да", "Нет"]
keyboard_yes_no.add(*buttons)
