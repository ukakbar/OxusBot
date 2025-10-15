
import asyncio
import os
import re
import aiosqlite
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.enums.parse_mode import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton
)

# ================== Config ==================
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # optional

DB_PATH = os.getenv("DB_PATH", "registrations.db")

EVENT_TITLE = "Off-Road Slet Aydarkul 2025"
EVENT_DATES = "25–26 октября 2025"
EVENT_LOCATION = "Озеро Айдаркуль, Узбекистан"
EVENT_SITE = "t.me/CarPro_UZ"

WELCOME_TEXT = f"""
Добро пожаловать на регистрацию OxusBot!

<b>{EVENT_TITLE}</b>
📅 Даты: {EVENT_DATES}
📍 Локация: {EVENT_LOCATION}

Чтобы зарегистрироваться, нажмите <b>«Зарегистрироваться»</b>.
Вы также можете узнать подробности через кнопку «Инфо».

Если хотите, можно прислать все сразу одной строкой:
<i>Имя, Автомобиль, Телефон, Кол-во человек</i>
Пример:
<i>Akbar, Jeep Grand, +998901112233, 3</i>
"""

INFO_TEXT = f"""
<b>{EVENT_TITLE}</b>
📅 {EVENT_DATES}
📍 {EVENT_LOCATION}

Формат: джип-спринт, триал, семейная зона, тест-драйвы.
Оргкоманда: Kay Tourist Services / CarPro_UZ
Связь: {EVENT_SITE}
"""

# ============== Finite State Machine ==============
class RegForm(StatesGroup):
    name = State()
    car = State()
    phone = State()
    people = State()

# ============== Keyboards ==============
def start_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Зарегистрироваться")],
                  [KeyboardButton(text="ℹ️ Инфо")]],
        resize_keyboard=True
    )

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )

# ============== DB helpers ==============
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER,
    name TEXT,
    car TEXT,
    phone TEXT,
    people INTEGER,
    created_at TEXT
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SQL)
        await db.commit()

async def insert_registration(tg_id: int, name: str, car: str, phone: str, people: int) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO registrations (tg_id, name, car, phone, people, created_at) VALUES (?,?,?,?,?,?)",
            (tg_id, name.strip(), car.strip(), phone.strip(), int(people), datetime.utcnow().isoformat())
        )
        await db.commit()
        return cur.lastrowid

# ============== Validation ==============
def parse_inline(text: str):
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        return None
    name, car, phone, people = parts
    if not name or not car:
        return None
    if not re.fullmatch(r"[+0-9)( -]{7,20}", phone):
        return None
    digits = re.sub(r"[^0-9]", "", people or "")
    if not digits:
        return None
    ppl = int(digits)
    if ppl <= 0 or ppl > 50:
        return None
    return name, car, phone, ppl

def phone_valid(phone: str) -> bool:
    return re.fullmatch(r"[+0-9)( -]{7,20}", phone) is not None

def people_valid(p: str):
    digits = re.sub(r"[^0-9]", "", p or "")
    if not digits:
        return None
    n = int(digits)
    return n if 1 <= n <= 50 else None

# ============== Router & Handlers ==============
router = Router()

@router.message(CommandStart())
async def cmd_start(m: types.Message, state: FSMContext):
    await state.clear()
    await m.answer(WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=start_kb())

@router.message(F.text == "ℹ️ Инфо")
async def info(m: types.Message):
    await m.answer(INFO_TEXT, parse_mode=ParseMode.HTML)

@router.message(F.text == "🚀 Зарегистрироваться")
async def reg_begin(m: types.Message, state: FSMContext):
    await state.set_state(RegForm.name)
    await m.answer("Как Вас зовут? (Имя и, при желании, фамилия)", reply_markup=cancel_kb())

@router.message(RegForm.name)
async def reg_name(m: types.Message, state: FSMContext):
    name = m.text.strip()
    if len(name) < 2:
        return await m.answer("Пожалуйста, укажите имя корректно.")
    await state.update_data(name=name)
    await state.set_state(RegForm.car)
    await m.answer("Какой автомобиль? (Марка и модель)")

@router.message(RegForm.car)
async def reg_car(m: types.Message, state: FSMContext):
    car = m.text.strip()
    if len(car) < 2:
        return await m.answer("Пожалуйста, укажите автомобиль корректно.")
    await state.update_data(car=car)
    await state.set_state(RegForm.phone)
    await m.answer("Ваш телефон (например +998901112233):")

@router.message(RegForm.phone)
async def reg_phone(m: types.Message, state: FSMContext):
    phone = m.text.strip()
    if not phone_valid(phone):
        return await m.answer("Похоже, номер некорректен. Пример: +998901112233. Отправьте номер ещё раз.")
    await state.update_data(phone=phone)
    await state.set_state(RegForm.people)
    await m.answer("Сколько человек в экипаже? (число)")

@router.message(RegForm.people)
async def reg_people(m: types.Message, state: FSMContext):
    n = people_valid(m.text)
    if n is None:
        return await m.answer("Укажите, пожалуйста, число от 1 до 50.")
    data = await state.get_data()
    reg_id = await insert_registration(
        tg_id=m.from_user.id,
        name=data["name"],
        car=data["car"],
        phone=data["phone"],
        people=n
    )
    await state.clear()
    text = (
        "✅ <b>Регистрация успешна!</b>\n"
        f"Ваш ID: <b>{reg_id}</b>\n\n"
        f"👤 <b>{data['name']}</b>\n"
        f"🚙 <b>{data['car']}</b>\n"
        f"📞 {data['phone']}\n"
        f"👥 Кол-во человек: <b>{n}</b>"
    )
    await m.answer(text, parse_mode=ParseMode.HTML, reply_markup=start_kb())

# --------- Fallback: inline one-line message ---------
@router.message()
async def fallback_inline(m: types.Message, state: FSMContext):
    parsed = parse_inline(m.text or "")
    if not parsed:
        return await m.answer(
            "Чтобы зарегистрироваться, нажмите «Зарегистрироваться» или отправьте данные одной строкой:\n"
            "<i>Имя, Автомобиль, Телефон, Кол-во человек</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=start_kb()
        )
    name, car, phone, ppl = parsed
    reg_id = await insert_registration(m.from_user.id, name, car, phone, ppl)
    text = (
        "✅ <b>Регистрация успешна!</b>\n"
        f"Ваш ID: <b>{reg_id}</b>\n\n"
        f"👤 <b>{name}</b>\n"
        f"🚙 <b>{car}</b>\n"
        f"📞 {phone}\n"
        f"👥 Кол-во человек: <b>{ppl}</b>"
    )
    await m.answer(text, parse_mode=ParseMode.HTML, reply_markup=start_kb())

# ============== Admin section ==============
admin_router = Router()

def is_admin(user_id: int) -> bool:
    try:
        return ADMIN_CHAT_ID and int(ADMIN_CHAT_ID) == int(user_id)
    except Exception:
        return False

@admin_router.message(Command("export"))
async def cmd_export(m: types.Message):
    if not is_admin(m.from_user.id):
        return await m.answer("У вас нет доступа к этой команде.")
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id","tg_id","name","car","phone","people","created_at"])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id,tg_id,name,car,phone,people,created_at FROM registrations ORDER BY id") as cur:
            async for row in cur:
                writer.writerow(row)
    output.seek(0)
    await m.answer_document(types.BufferedInputFile(
        output.getvalue().encode("utf-8"), filename=f"registrations_{datetime.utcnow().date()}.csv"
    ))

@admin_router.message(Command("count"))
async def cmd_count(m: types.Message):
    if not is_admin(m.from_user.id):
        return await m.answer("У вас нет доступа к этой команде.")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM registrations") as cur:
            row = await cur.fetchone()
    await m.answer(f"Всего регистраций: <b>{row[0]}</b>", parse_mode=ParseMode.HTML)

# ============== App runner ==============
async def main():
    await init_db()
    bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp.include_router(admin_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
