
# -*- coding: utf-8 -*-
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
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# ================== Config ==================
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID")  # optional
DB_PATH = os.getenv("DB_PATH", "registrations.db")

# === Helpers to avoid Unicode-quote issues ===
QUOTES = " '\"`“”„‟‹›«»"

def clean_car(text: str) -> str:
    # strip spaces + ASCII quotes + common Unicode quotes
    return (text or "").strip().strip(QUOTES)

# === Bilingual Welcome Text (RU + UZ) ===
WELCOME_TEXT = """
🌍 <b>Слёт Джиперов 2025 / Jeepchilar Slyoti 2025</b>
📍 <b>Озеро Айдаркуль / Aydarkul ko‘li</b>
📅 <b>25–26 октября 2025 / 25–26 oktabr 2025</b>

Добро пожаловать на участие в <b>оффроуд-фестивале года!</b>
Xush kelibsiz, bu yilgi eng katta <b>off-road festivali!</b> 🚙🔥

🌄 <b>Вас ждёт настоящий праздник для всех любителей внедорожников!</b>
Bu barcha off-road ixlosmandlari uchun haqiqiy bayram!
Deyarli butun mamlakatdan klub va ishtirokchilar yig‘iladi —
birgalikda tabiat bag‘rida ikki kunlik sarguzasht kutmoqda!

🎯 <b>Программа фестиваля / Festival dasturi:</b>
🏁 Джип-триал / Jip-trial — ochiq musobaqa, har kim qatnasha oladi
🚘 Джип-спринт / Jip-sprint — faqat tayyorlangan avtomobillar uchun
🚗 <b>Официальная презентация:</b> Toyota Land Cruiser 300 Hybrid
🚙 Ko‘rgazma: turli kompaniyalarning yangi avtomobillari
🎵 Musiqa, 🍢 taomlar, ☕ ichimliklar, 🏕 dam olish zonasi
🎁 Sovg‘alar va test-drayvlar!

Это место, где встречаются энтузиасты,
делятся опытом, заводят новых друзей
и просто отлично проводят выходные у Айдаркуля! 💪🌅

Ro‘yxatdan o‘tish uchun — <b>«🚀 Зарегистрироваться / Ro‘yxatdan o‘tish»</b>
Batafsil ma’lumot — <b>«ℹ️ Инфо / Ma’lumot»</b>
"""

INFO_TEXT = """
🔥 <b>Off-Road Festival "Слёт Джиперов 2025"</b>

📅 25–26 октября 2025
📍 Озеро Айдаркуль, Узбекистан

Это масштабное off-road событие, где встречаются клубы и энтузиасты со всей страны!
Вас ждут:
🏁 Джип-триал — для всех желающих
🚘 Джип-спринт — для подготовленных машин
🚗 Презентация нового Toyota Land Cruiser 300 Hybrid
🎵 Музыка, еда, напитки, подарки, отдых, тест-драйвы!

Оргкоманда: CarPro_UZ
Связь: @UkAkbar
"""

LOCATION_TEXT = """
📍 <b>Локация фестиваля / Festival joyi</b>

Оффроуд «Слёт Джиперов 2025» пройдёт у живописного озера Айдаркуль
Hudud: O‘zbekiston, Navoiy viloyati, Aydarkul ko‘li atrofida.

👇 Нажмите, чтобы проложить маршрут в Яндекс.Картах:
👉 <a href="https://yandex.ru/navi?rtext=41.331143,69.272065~40.800573,66.970008&rtt=auto">Открыть маршрут в Яндекс.Навигаторе</a>
"""

# ============== Finite State Machine ==============
class RegForm(StatesGroup):
    name = State()
    car = State()
    phone = State()
    people = State()

class EditForm(StatesGroup):
    name = State()
    car = State()
    phone = State()
    people = State()

# ============== Keyboards ==============
def start_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🚀 Зарегистрироваться / Ro‘yxatdan o‘tish")],
                  [KeyboardButton(text="ℹ️ Инфо / Ma’lumot")],
                  [KeyboardButton(text="📍 Локация / Manzil")]],
        resize_keyboard=True
    )

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Отмена / Bekor qilish")]],
        resize_keyboard=True
    )

def skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="➡️ Пропустить / Skip")],
                  [KeyboardButton(text="❌ Отмена / Bekor qilish")]],
        resize_keyboard=True
    )

# ============== DB helpers ==============
CREATE_SQL = """
CREATE TABLE IF NOT EXISTS registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_id INTEGER UNIQUE,
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
            "INSERT OR REPLACE INTO registrations (id, tg_id, name, car, phone, people, created_at) "
            "VALUES ((SELECT id FROM registrations WHERE tg_id=?),?,?,?,?,?,?)",
            (tg_id, tg_id, name.strip(), car.strip(), phone.strip(), int(people), datetime.utcnow().isoformat())
        )
        await db.commit()
        return cur.lastrowid

async def get_registration(tg_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id,tg_id,name,car,phone,people,created_at FROM registrations WHERE tg_id=?", (tg_id,)) as cur:
            return await cur.fetchone()

async def update_registration(tg_id: int, name: str = None, car: str = None, phone: str = None, people: int = None):
    async with aiosqlite.connect(DB_PATH) as db:
        fields, params = [], []
        if name is not None:
            fields.append("name=?"); params.append(name.strip())
        if car is not None:
            fields.append("car=?"); params.append(car.strip())
        if phone is not None:
            fields.append("phone=?"); params.append(phone.strip())
        if people is not None:
            fields.append("people=?"); params.append(int(people))
        if not fields:
            return
        params.append(tg_id)
        await db.execute(f"UPDATE registrations SET {', '.join(fields)} WHERE tg_id=?", params)
        await db.commit()

# ============== Validation ==============
def parse_inline(text: str):
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != 4:
        return None
    name, car, phone, people = parts
    if not name or not car:
        return None
    if not re.fullmatch(r"[+0-9)( -]{7,20}", phone or ""):
        return None
    digits = re.sub(r"[^0-9]", "", people or "")
    if not digits:
        return None
    ppl = int(digits)
    if not (1 <= ppl <= 50):
        return None
    car = clean_car(car)
    return name, car, phone, ppl

def phone_valid(phone: str) -> bool:
    return re.fullmatch(r"[+0-9)( -]{7,20}", phone or "") is not None

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

@router.message(F.text == "ℹ️ Инфо / Ma’lumot")
async def info(m: types.Message):
    await m.answer(INFO_TEXT, parse_mode=ParseMode.HTML)

@router.message(F.text == "📍 Локация / Manzil")
async def location(m: types.Message):
    await m.answer(LOCATION_TEXT, parse_mode=ParseMode.HTML, disable_web_page_preview=False)

@router.message(F.text == "🚀 Зарегистрироваться / Ro‘yxatdan o‘tish")
async def reg_begin(m: types.Message, state: FSMContext):
    await state.set_state(RegForm.name)
    await m.answer(
        "😎 Начнём регистрацию!\n"
        "RU: Укажите, пожалуйста, ваше имя и фамилию.\n"
        "UZ: Iltimos, ism va familiyangizni yozing.",
        reply_markup=cancel_kb()
    )

@router.message(RegForm.name)
async def reg_name(m: types.Message, state: FSMContext):
    name = (m.text or "").strip()
    if len(name) < 2:
        return await m.answer("RU: Пожалуйста, введите корректное имя.\nUZ: Iltimos, ismingizni to‘g‘ri kiriting.")
    await state.update_data(name=name)
    await state.set_state(RegForm.car)
    await m.answer(
        "👍 Отлично, {0}!\n"
        "RU: Теперь напишите, какой у вас автомобиль (марка и модель).\n"
        "UZ: Endi avtomobilingizni yozing (brend va model).".format(name)
    )

@router.message(RegForm.car)
async def reg_car(m: types.Message, state: FSMContext):
    car = clean_car(m.text)
    if len(car) < 2:
        return await m.answer('RU: Укажите корректно марку и модель.\nUZ: Brend va modelni to‘g‘ri yozing.')
    await state.update_data(car=car)
    await state.set_state(RegForm.phone)
    await m.answer(
        "📱 Отлично!\n"
        "RU: Укажите ваш номер телефона (формат: +998...).\n"
        "UZ: Telefon raqamingizni yozing (+998 bilan)."
    )

@router.message(RegForm.phone)
async def reg_phone(m: types.Message, state: FSMContext):
    phone = (m.text or "").strip()
    if not phone_valid(phone):
        return await m.answer("RU: Кажется, номер некорректный. Отправьте ещё раз.\nUZ: Raqam noto‘g‘ri ko‘rinadi. Qayta yuboring.")
    await state.update_data(phone=phone)
    await state.set_state(RegForm.people)
    await m.answer(
        "👥 Принято!\n"
        "RU: Сколько человек будет в вашем автомобиле (включая водителя)? Напишите только число.\n"
        "UZ: Ekipajda (haydovchini qo‘shib) nechta odam? Faqat raqam yozing."
    )

@router.message(RegForm.people)
async def reg_people(m: types.Message, state: FSMContext):
    n = people_valid(m.text or "")
    if n is None:
        return await m.answer("RU: Укажите число от 1 до 50.\nUZ: 1 dan 50 gacha bo‘lgan son kiriting.")
    data = await state.get_data()
    reg_id = await insert_registration(
        tg_id=m.from_user.id,
        name=data["name"],
        car=data["car"],
        phone=data["phone"],
        people=n
    )
    text = (
        "✅ <b>Регистрация успешна! / Ro‘yxatdan o‘tish muvaffaqiyatli!</b>\n"
        f"ID: <b>{reg_id}</b>\n\n"
        f"👤 {data['name']}\n"
        f"🚙 {data['car']}\n"
        f"📞 {data['phone']}\n"
        f"👥 {n}"
    )
    await m.answer(text, parse_mode=ParseMode.HTML, reply_markup=start_kb())
    accom = (
        "\n\n<b>🏡 Проживание / Turar joy (ixtiyoriy):</b>\n"
        "🏠 Коттедж 2-местный — 1 500 000 сум\n"
        "🏡 Коттедж 3-местный — 2 000 000 сум\n"
        "⛺ Юрта (3+ человек) — 800 000 сум\n"
        "Bron qilish / Бронь: shaxsiy xabar — <b>@UkAkbar</b>"
    )
    await m.answer(accom, parse_mode=ParseMode.HTML)
    await state.clear()

# --------- /mydata and editing ---------
@router.message(Command("mydata"))
async def cmd_mydata(m: types.Message):
    row = await get_registration(m.from_user.id)
    if not row:
        return await m.answer("У вас пока нет регистрации. Нажмите «🚀 Зарегистрироваться / Ro‘yxatdan o‘tish».", reply_markup=start_kb())
    _id, tg_id, name, car, phone, people, created_at = row
    text = (
        "🗂 <b>Ваши данные / Ma'lumotlaringiz</b>\n\n"
        f"👤 {name}\n"
        f"🚙 {car}\n"
        f"📞 {phone}\n"
        f"👥 {people}\n"
        f"🕒 {created_at} UTC"
    )
    await m.answer(text, parse_mode=ParseMode.HTML, reply_markup=start_kb())
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="✏️ Изменить / Tahrirlash", callback_data="edit_start")]])
    await m.answer("Если нужно — можно обновить данные.", reply_markup=kb)

@router.message(Command("edit"))
async def cmd_edit(m: types.Message, state: FSMContext):
    row = await get_registration(m.from_user.id)
    if not row:
        return await m.answer("Регистрация не найдена. Сначала нажмите «🚀 Зарегистрироваться / Ro‘yxatdan o‘tish».", reply_markup=start_kb())
    _id, tg_id, name, car, phone, people, created_at = row
    await state.update_data(name=name, car=car, phone=phone, people=people)
    await state.set_state(EditForm.name)
    await m.answer(
        f"✏️ Обновим данные.\n"
        f"Текущее имя: <b>{name}</b>\n"
        "RU: Отправьте новое имя и фамилию или нажмите «➡️ Пропустить / Skip».\n"
        "UZ: Yangi ism-familyani yuboring yoki «➡️ Пропустить / Skip» tugmasini bosing.",
        parse_mode=ParseMode.HTML,
        reply_markup=skip_kb()
    )

@router.callback_query(F.data == "edit_start")
async def cb_edit_start(c: types.CallbackQuery, state: FSMContext):
    row = await get_registration(c.from_user.id)
    if not row:
        return await c.message.answer("Регистрация не найдена. Сначала нажмите «🚀 Зарегистрироваться / Ro‘yxatdan o‘tish».", reply_markup=start_kb())
    _id, tg_id, name, car, phone, people, created_at = row
    await state.update_data(name=name, car=car, phone=phone, people=people)
    await state.set_state(EditForm.name)
    await c.message.answer(
        f"✏️ Обновим данные.\n"
        f"Текущее имя: <b>{name}</b>\n"
        "RU: Отправьте новое имя и фамилию или нажмите «➡️ Пропустить / Skip».\n"
        "UZ: Yangi ism-familyani yuboring yoki «➡️ Пропустить / Skip» tugmasini bosing.",
        parse_mode=ParseMode.HTML,
        reply_markup=skip_kb()
    )
    await c.answer()

@router.message(EditForm.name)
async def edit_name(m: types.Message, state: FSMContext):
    txt = (m.text or "").strip().lower()
    if txt.startswith(("➡️", "пропустить", "skip")):
        pass
    else:
        if len(txt) < 2:
            return await m.answer("RU: Пожалуйста, введите корректное имя.\nUZ: Iltimos, ismingizni to‘g‘ri kiriting.")
        await state.update_data(name=m.text.strip())
    data = await state.get_data()
    await state.set_state(EditForm.car)
    await m.answer(
        f"Текущий автомобиль: <b>{data['car']}</b>\n"
        "RU: Отправьте новую марку и модель или «➡️ Пропустить / Skip».\n"
        "UZ: Yangi brend va modelni yuboring yoki «➡️ Пропустить / Skip».",
        parse_mode=ParseMode.HTML,
        reply_markup=skip_kb()
    )

@router.message(EditForm.car)
async def edit_car(m: types.Message, state: FSMContext):
    txt = (m.text or "").strip()
    if txt.lower().startswith(("➡️", "пропустить", "skip")):
        pass
    else:
        car = clean_car(txt)
        if len(car) < 2:
            return await m.answer('RU: Укажите корректно марку и модель.\nUZ: Brend va modelni to‘g‘ri yozing.')
        await state.update_data(car=car)
    data = await state.get_data()
    await state.set_state(EditForm.phone)
    await m.answer(
        f"Текущий телефон: <b>{data['phone']}</b>\n"
        "RU: Отправьте новый номер телефона или «➡️ Пропустить / Skip».\n"
        "UZ: Yangi telefon raqamini yuboring yoki «➡️ Пропустить / Skip».",
        parse_mode=ParseMode.HTML,
        reply_markup=skip_kb()
    )

@router.message(EditForm.phone)
async def edit_phone(m: types.Message, state: FSMContext):
    txt = (m.text or "").strip()
    if txt.lower().startswith(("➡️", "пропустить", "skip")):
        pass
    else:
        if not phone_valid(txt):
            return await m.answer("RU: Кажется, номер некорректный. Отправьте ещё раз.\nUZ: Raqam noto‘g‘ri ko‘rinadi. Qayta yuboring.")
        await state.update_data(phone=txt)
    data = await state.get_data()
    await state.set_state(EditForm.people)
    await m.answer(
        f"Текущее кол-во: <b>{data['people']}</b>\n"
        "RU: Отправьте новое число (1–50) или «➡️ Пропустить / Skip».\n"
        "UZ: Yangi sonni yuboring (1–50) yoki «➡️ Пропустить / Skip».",
        parse_mode=ParseMode.HTML,
        reply_markup=skip_kb()
    )

@router.message(EditForm.people)
async def edit_people(m: types.Message, state: FSMContext):
    txt = (m.text or "").strip()
    if txt.lower().startswith(("➡️", "пропустить", "skip")):
        pass
    else:
        n = people_valid(txt)
        if n is None:
            return await m.answer("RU: Укажите число от 1 до 50.\nUZ: 1 dan 50 gacha bo‘lgan son kiriting.")
        await state.update_data(people=n)
    data = await state.get_data()
    await update_registration(
        tg_id=m.from_user.id,
        name=data.get("name"),
        car=data.get("car"),
        phone=data.get("phone"),
        people=data.get("people")
    )
    await state.clear()
    text = (
        "✅ Данные обновлены! / Ma'lumotlar yangilandi!\n\n"
        f"👤 {data['name']}\n"
        f"🚙 {data['car']}\n"
        f"📞 {data['phone']}\n"
        f"👥 {data['people']}"
    )
    await m.answer(text, parse_mode=ParseMode.HTML, reply_markup=start_kb())

# ============== Admin section (export/count) ==============
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
