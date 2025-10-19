# -*- coding: utf-8 -*-
import asyncio
import os
import re
import aiosqlite
from datetime import datetime
from io import BytesIO
from openpyxl import Workbook

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ================== Config ==================
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")
DB_PATH = os.getenv("DB_PATH", "registrations.db")

# ================== Texts ==================
WELCOME_TEXT = """
🌍 <b>Off-Road Festival Aydarkul 2025</b>
📍 <b>Озеро Айдаркуль / Aydarkul ko‘li</b>
📅 <b>25–26 октября 2025 / 25–26 oktabr 2025</b>

Добро пожаловать на участие в <b>оффроуд-фестивале года!</b>
Xush kelibsiz, bu yilgi eng katta <b>off-road festivaliga!</b> 🚙🔥

🌄 <b>Вас ждёт настоящий праздник для всех любителей внедорожников!</b>
Bu barcha off-road ixlosmandlari uchun haqiqiy bayram!
Deyarli butun mamlakatdan klub va ishtirokchilar yig‘iladi —
birgalikda tabiat bag‘rida ikki kunlik sarguzasht kutmoqda!

🎯 <b>Программа фестиваля / Festival dasturi:</b>
🏁 Джип-триал / Jip-trial — ochiq musobaqa, har kim qatnasha oladi
🚘 Джип-спринт / Jip-sprint — faqat tayyorlangan avtomobillar uchun
🚗 Официальная презентация: Toyota Land Cruiser 300 Hybrid
🚙 Festivalda: turli kompaniyalarning yangi avtomobillari
🎵 Musiqa, 🍢 taomlar, ☕ ichimliklar, 🏕 dam olish zonasi
🎁 Sovg‘alar va test-drayvlar kutmoqda!

Это место, где встречаются энтузиасты,
делятся опытом, заводят новых друзей
и просто отлично проводят выходные у Айдаркуля! 💪🌅

💳 <b>Входной взнос / Kirish to‘lovi:</b>
200 000 so‘m mashina boshiga / <b>за автомобиль</b>
(tashkiliy xarajatlar uchun / <b>на организационные расходы</b>)

Ro‘yxatdan o‘tish uchun — <b>«🚀 Зарегистрироваться / Ro‘yxatdan o‘tish»</b>
Batafsil ma’lumot — <b>«ℹ️ Инфо / Ma’lumot»</b>
"""

INFO_TEXT = """
🔥 <b>Off-Road Festival Aydarkul 2025</b>
📅 25–26 октября 2025
📍 Озеро Айдаркуль, Узбекистан

🏁 Jeep Sprint — 25 октября (для подготовленных автомобилей)
🧗 Jeep Trial — 26 октября (для всех желающих 4x4)
🎵 Музыка, еда, напитки, подарки, отдых, тест-драйвы!

Оргкоманда: CarPro_UZ
Связь: @UkAkbar
"""

LOCATION_TEXT = """
📍 <b>Локация фестиваля / Festival joyi</b>
Оффроуд «Festival Aydarkul 2025» пройдёт у живописного озера Айдаркуль.
Hudud: O‘zbekiston, Navoiy viloyati, Aydarkul ko‘li atrofida.

👇 <a href="https://yandex.ru/navi?rtext=41.331143,69.272065~40.800573,66.970008&rtt=auto">Открыть маршрут в Яндекс.Навигаторе</a>
"""

# ================== FSM ==================
class RegForm(StatesGroup):
    name = State()
    car = State()
    plate = State()
    phone = State()
    race = State()
    race_type = State()
    payment = State()
    people = State()

# ================== Keyboards ==================
def start_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Зарегистрироваться / Ro‘yxatdan o‘tish")],
            [KeyboardButton(text="ℹ️ Инфо / Ma’lumot")],
            [KeyboardButton(text="📍 Локация / Manzil")]
        ],
        resize_keyboard=True
    )

def yes_no_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да / Ha")],
            [KeyboardButton(text="❌ Нет / Yo‘q")]
        ],
        resize_keyboard=True
    )

def race_type_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏁 Jeep Sprint")],
            [KeyboardButton(text="🧗 Jeep Trial")]
        ],
        resize_keyboard=True
    )

def payment_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Я оплатил(а) / To‘lov qildim")],
            [KeyboardButton(text="⏳ Оплачу позже / Keyin to‘layman")],
            [KeyboardButton(text="❌ Отмена / Bekor qilish")]
        ],
        resize_keyboard=True
    )

def confirm_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Завершить / Tugatish")],
            [KeyboardButton(text="✏️ Исправить / Tahrirlash")]
        ],
        resize_keyboard=True
    )

# ================== Database ==================
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE,
    name TEXT,
    car TEXT,
    plate TEXT UNIQUE,
    phone TEXT UNIQUE,
    race TEXT,
    race_type TEXT,
    payment TEXT,
    people INTEGER,
    created_at TEXT
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SQL)
        await db.commit()

async def insert_registration(tg_id, name, car, plate, phone, race, race_type, payment, people):
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO registrations (tg_id, name, car, plate, phone, race, race_type, payment, people, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (tg_id, name, car, plate, phone, race, race_type, payment, people, datetime.utcnow().isoformat()))
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

# ================== Router ==================
router = Router()

@router.message(CommandStart())
async def start(m: types.Message):
    await m.answer(WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=start_kb())

@router.message(F.text == "ℹ️ Инфо / Ma’lumot")
async def info(m: types.Message):
    await m.answer(INFO_TEXT, parse_mode=ParseMode.HTML)

@router.message(F.text == "📍 Локация / Manzil")
async def location(m: types.Message):
    await m.answer(LOCATION_TEXT, parse_mode=ParseMode.HTML, disable_web_page_preview=False)

# ================== Registration ==================
@router.message(F.text == "🚀 Зарегистрироваться / Ro‘yxatdan o‘tish")
async def reg_start(m: types.Message, state: FSMContext):
    await state.set_state(RegForm.name)
    await m.answer("😎 RU: Укажите ваше имя и фамилию.\nUZ: Ism va familiyangizni yozing.")

@router.message(RegForm.name)
async def reg_name(m: types.Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    await state.set_state(RegForm.car)
    await m.answer("🚙 RU: Напишите марку и модель вашего автомобиля.\nUZ: Avtomobil brendi va modelini yozing.")

@router.message(RegForm.car)
async def reg_car(m: types.Message, state: FSMContext):
    await state.update_data(car=m.text.strip())
    await state.set_state(RegForm.plate)
    await m.answer("🔢 RU: Укажите госномер автомобиля (например 01A777AA).\nUZ: Avtomobil davlat raqamini yozing (misol: 01A777AA).")

@router.message(RegForm.plate)
async def reg_plate(m: types.Message, state: FSMContext):
    await state.update_data(plate=m.text.strip().upper())
    await state.set_state(RegForm.race)
    await m.answer(
        "🏁 RU: Участвуете ли вы в соревнованиях?\n"
        "UZ: Musobaqalarda ishtirok etasizmi?\n\n"
        "📋 Jeep Sprint — 25 октября (подготовленные авто)\n"
        "📋 Jeep Trial — 26 октября (все желающие 4x4)",
        reply_markup=yes_no_kb()
    )

@router.message(RegForm.race)
async def reg_race(m: types.Message, state: FSMContext):
    text = m.text.lower()
    if "да" in text or "ha" in text:
        await state.update_data(race="yes")
        await state.set_state(RegForm.race_type)
        await m.answer("Tanlang / Выберите дисциплину:", reply_markup=race_type_kb())
    else:
        await state.update_data(race="no", race_type="-")
        await state.set_state(RegForm.phone)
        await m.answer("📞 RU: Укажите номер телефона (+998...)\nUZ: Telefon raqamingizni yozing (+998... bilan).")

@router.message(RegForm.race_type)
async def reg_race_type(m: types.Message, state: FSMContext):
    await state.update_data(race_type=m.text.strip())
    await state.set_state(RegForm.phone)
    await m.answer("📞 RU: Укажите номер телефона (+998...)\nUZ: Telefon raqamingizni yozing (+998... bilan).")

@router.message(RegForm.phone)
async def reg_phone(m: types.Message, state: FSMContext):
    phone = re.sub(r"\s+", "", m.text)
    await state.update_data(phone=phone)
    await state.set_state(RegForm.payment)
    await m.answer(
        "💳 Kirish to‘lovi / Входной взнос — 200 000 so‘m mashina boshiga / за автомобиль\n"
        "(tashkiliy xarajatlar uchun / на организационные расходы)\n\n"
        "To‘lov uchun / Для оплаты:\n"
        "UZCARD: 5614 6806 0888 2326 — Akbarjon Kulov\n"
        "VISA: 4023 0602 2688 2305 — Akbarjon Kulov",
        reply_markup=payment_kb()
    )

@router.message(RegForm.payment)
async def reg_payment(m: types.Message, state: FSMContext):
    text = m.text.lower()
    if "оплачу" in text or "keyin" in text:
        await state.update_data(payment="later")
    elif "оплат" in text or "to‘lov" in text:
        await state.update_data(payment="paid")
    else:
        await state.update_data(payment="-")
    await state.set_state(RegForm.people)
    await m.answer("👥 RU: Сколько человек будет в автомобиле (включая водителя)?\nUZ: Mashinada (haydovchini qo‘shib) nechta odam bo‘ladi?")

@router.message(RegForm.people)
async def reg_people(m: types.Message, state: FSMContext):
    data = await state.get_data()
    people = re.sub(r"\D", "", m.text)
    if not people:
        return await m.answer("❗️RU: Введите только число.\nUZ: Faqat raqam yozing.")
    ok = await insert_registration(
        tg_id=m.from_user.id,
        name=data["name"], car=data["car"], plate=data["plate"], phone=data["phone"],
        race=data["race"], race_type=data.get("race_type", "-"), payment=data["payment"],
        people=int(people)
    )
    if not ok:
        return await m.answer("❗️ Регистрация с таким номером телефона или госномером уже существует.\n"
                              "Agar ma’lumotni o‘zgartirmoqchi bo‘lsangiz — @UkAkbar bilan bog‘laning.")
    await m.answer(
        f"✅ <b>Регистрация успешна!</b>\n\n"
        f"👤 {data['name']}\n🚙 {data['car']}\n🔢 {data['plate']}\n📞 {data['phone']}\n"
        f"🏁 Участие: {data['race_type'] if data['race']=='yes' else 'Нет'}\n💰 Оплата: {data['payment']}\n"
        f"👥 Людей: {people}",
        parse_mode=ParseMode.HTML
    )
    await m.answer(
        "🏡 <b>Проживание / Turar joy (ixtiyoriy):</b>\n"
        "🏠 Коттедж 2-местный — 1 500 000 сум\n"
        "🏡 Коттедж 3-местный — 2 000 000 сум\n"
        "⛺️ Юрта (3+ человек) — 800 000 сум\n"
        "Bron qilish / Бронь: shaxsiy xabar — @UkAkbar",
        parse_mode=ParseMode.HTML,
        reply_markup=start_kb()
    )
    await state.clear()

# ================== Runner ==================
async def main():
    await init_db()
    bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
