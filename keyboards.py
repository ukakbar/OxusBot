from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def lang_kb():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇺🇿 O‘zbekcha")]],
        resize_keyboard=True, one_time_keyboard=True
    )

def main_menu(t):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["btn_register"])],
            [KeyboardButton(text=t["btn_info"]), KeyboardButton(text=t["btn_contact"])]
        ],
        resize_keyboard=True
    )

def people_kb(t):
    row = [KeyboardButton(text=x) for x in t["people_buttons"]]
    return ReplyKeyboardMarkup(keyboard=[row], resize_keyboard=True, one_time_keyboard=True)

def skip_kb(t):
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t["skip"])]],
        resize_keyboard=True, one_time_keyboard=True
    )

def lodging_kb(t):
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["lodging_cottage"]), KeyboardButton(text=t["lodging_yurt"])],
            [KeyboardButton(text=t["lodging_tent"]), KeyboardButton(text=t["lodging_none"])]
        ],
        resize_keyboard=True, one_time_keyboard=True
    )

def confirm_kb(t):
    # Кнопки на экране подтверждения
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["confirm"])],
            [KeyboardButton(text=t["edit_data_btn"])],
            [KeyboardButton(text=t["cancel"]), KeyboardButton(text=t.get("back", "⬅ Orqaga"))]
        ],
        resize_keyboard=True, one_time_keyboard=True
    )
