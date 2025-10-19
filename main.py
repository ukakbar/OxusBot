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
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# ================== Config ==================
TOKEN = os.getenv("TELEGRAM_TOKEN")
DB_PATH = os.getenv("DB_PATH", "registrations.db")

# Админы по username
ADMINS = ["UkAkbar", "fdimon"]

# ================== Helpers ==================
def is_admin(message: types.Message) -> bool:
    username = (message.from_user.username or "").lower()
    return username in [a.lower() for a in ADMINS]

def normalize_phone(s: str) -> str:
    # убираем пробелы/скобки/дефисы, оставляем + и цифры
    s = (s or "").strip()
    s = re.sub(r"[^\d+]", "", s)
    return s

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
O‘zbekiston, Navoiy viloyati, Aydarkul ko‘li atrofida.

👇 <a href="https://yandex.ru/navi?rtext=41.331143,69.272065~40.800573,66.970008&rtt=auto">Открыть маршрут в Яндекс.Навигаторе</a>
"""

PARTICIPATE_TEXT = """
🏁 <b>Участвуете ли вы в соревнованиях? / Musobaqalarda ishtirok etasizmi?</b>

RU:
• 25 октября — <b>Jeep Sprint</b> — только для подготовленных автомобилей
• 26 октября — <b>Jeep Trial</b> — для всех желающих, на любых полноприводных (4x4) автомобилях

UZ:
• 25 oktabr — <b>Jeep Sprint</b> — faqat tayyorlangan avtomobillar uchun
• 26 oktabr — <b>Jeep Trial</b> — istalgan 4x4 avtomobillar uchun, hamma qatnasha oladi

RU: Выберите «Да» или «Нет».
UZ: «Ha» yoki «Yo‘q» ni tanlang.
"""

# ================== FSM ==================
class RegForm(StatesGroup):
    name = State()
    car = State()
    plate = State()
    race = State()
    race_type = State()
    phone = State()
    payment = State()
    people = State()

# ================== Keyboards ==================
def start_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🚀 Зарегистрироваться / Ro‘yxatdan o‘tish")],
            [KeyboardButton(text="ℹ️ Инфо / Ma’lumot")],
            [KeyboardButton(text="📍 Локация / Manzil")],
        ],
        resize_keyboard=True
    )

def yes_no_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Да / Ha")],
            [KeyboardButton(text="❌ Нет / Yo‘q")],
        ],
        resize_keyboard=True, one_time_keyboard=True
    )

def race_type_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🏁 Jeep Sprint")],
            [KeyboardButton(text="🧗 Jeep Trial")],
        ],
        resize_keyboard=True, one_time_keyboard=True
    )

def payment_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="💰 Я оплатил(а) / To‘lov qildim")],
            [KeyboardButton(text="⏳ Оплачу позже / Keyin to‘layman")],
            [KeyboardButton(text="❌ Отмена / Bekor qilish")],
        ],
        resize_keyboard=True, one_time_keyboard=True
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

# ================== Routers ==================
router = Router()
admin_router = Router()

# ================== Handlers ==================
@router.message(CommandStart())
async def cmd_start(m: types.Message):
    await m.answer(WELCOME_TEXT, parse_mode=ParseMode.HTML, reply_markup=start_kb())

@router.message(F.text == "ℹ️ Инфо / Ma’lumot")
async def info(m: types.Message):
    await m.answer(INFO_TEXT, parse_mode=ParseMode.HTML)

@router.message(F.text == "📍 Локация / Manzil")
async def location(m: types.Message):
    await m.answer(LOCATION_TEXT, parse_mode=ParseMode.HTML, disable_web_page_preview=False)

# ---------- Registration flow ----------
@router.message(F.text == "🚀 Зарегистрироваться / Ro‘yxatdan o‘tish")
async def reg_start(m: types.Message, state: FSMContext):
    await state.set_state(RegForm.name)
    await m.answer("😎 RU: Укажите ваше имя и фамилию.\nUZ: Ism va familiyangizni yozing.")

@router.message(RegForm.name)
async def reg_name(m: types.Message, state: FSMContext):
    name = (m.text or "").strip()
    if len(name) < 2:
        return await m.answer("RU: Введите корректное имя.\nUZ: To‘g‘ri ism kiriting.")
    await state.update_data(name=name)
    await state.set_state(RegForm.car)
    await m.answer("🚙 RU: Напишите марку и модель вашего автомобиля.\nUZ: Avtomobil brendi va modelini yozing.")

@router.message(RegForm.car)
async def reg_car(m: types.Message, state: FSMContext):
    car = (m.text or "").strip()
    if len(car) < 2:
        return await m.answer("RU: Укажите марку и модель корректно.\nUZ: Brend va modelni to‘g‘ri yozing.")
    await state.update_data(car=car)
    await state.set_state(RegForm.plate)
    await m.answer("🔢 RU: Укажите госномер автомобиля (например 01A777AA, KZ 321ABC05).\nUZ: Avtomobil davlat raqamini yozing (misol: 01A777AA, KZ 321ABC05).")

@router.message(RegForm.plate)
async def reg_plate(m: types.Message, state: FSMContext):
    plate = (m.text or "").strip().upper()
    if len(plate) < 4:
        return await m.answer("RU: Введите корректный госномер (минимум 4 символа).\nUZ: To‘g‘ri davlat raqamini kiriting (kamida 4 belgi).")
    await state.update_data(plate=plate)
    await state.set_state(RegForm.race)
    await m.answer(PARTICIPATE_TEXT, parse_mode=ParseMode.HTML, reply_markup=yes_no_kb())

@router.message(RegForm.race)
async def reg_race(m: types.Message, state: FSMContext):
    t = (m.text or "").lower()
    if "да" in t or "ha" in t:
        await state.update_data(race="yes")
        await state.set_state(RegForm.race_type)
        return await m.answer(
            "Tanlang / Выберите:\n"
            "🏁 Jeep Sprint — 25.10 (faqat tayyorlangan avtomobillar uchun / подготовленные авто)\n"
            "🧗 Jeep Trial — 26.10 (istalgan 4x4 uchun / для всех желающих 4x4)",
            reply_markup=race_type_kb()
        )
    elif "нет" in t or "yo‘q" in t or "yoq" in t or "yok" in t:
        await state.update_data(race="no", race_type="-")
        await state.set_state(RegForm.phone)
        return await m.answer("📞 RU: Укажите номер телефона (+код страны...)\nUZ: Telefon raqamingizni yozing (+mamlakat kodi bilan...).")
    else:
        return await m.answer("RU: Нажмите кнопку «Да» или «Нет».\nUZ: «Ha» yoki «Yo‘q» tugmasini bosing.", reply_markup=yes_no_kb())

@router.message(RegForm.race_type)
async def reg_race_type(m: types.Message, state: FSMContext):
    t = (m.text or "").lower()
    if "sprint" in t:
        await state.update_data(race_type="Jeep Sprint")
    elif "trial" in t:
        await state.update_data(race_type="Jeep Trial")
    else:
        return await m.answer("Tanlang / Выберите: «🏁 Jeep Sprint» yoki «🧗 Jeep Trial».", reply_markup=race_type_kb())
    await state.set_state(RegForm.phone)
    await m.answer("📞 RU: Укажите номер телефона (+код страны...)\nUZ: Telefon raqamingizni yozing (+mamlakat kodi bilan...).")

@router.message(RegForm.phone)
async def reg_phone(m: types.Message, state: FSMContext):
    phone = normalize_phone(m.text)
    if not phone.startswith("+") or not (7 <= len(re.sub(r"\D", "", phone)) <= 15):
        return await m.answer("RU: Кажется, номер некорректный. Отправьте ещё раз (+код страны...)\nUZ: Raqam noto‘g‘ri. +mamlakat kodi bilan yuboring.")
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
    t = (m.text or "").lower()
    if "оплачу" in t or "keyin" in t:
        await state.update_data(payment="later")
    elif "оплат" in t or "to‘lov" in t or "tolov" in t:
        await state.update_data(payment="paid")
    elif "отмена" in t or "bekor" in t:
        await state.clear()
        return await m.answer("Bekor qilindi / Отменено.", reply_markup=start_kb())
    else:
        await state.update_data(payment="-")
    await state.set_state(RegForm.people)
    await m.answer("👥 RU: Сколько человек будет в автомобиле (включая водителя)? Только число.\nUZ: Mashinada (haydovchini qo‘shib) nechta odam? Faqat raqam yozing.")

@router.message(RegForm.people)
async def reg_people(m: types.Message, state: FSMContext):
    data = await state.get_data()
    digits = re.sub(r"\D", "", (m.text or ""))
    if not digits:
        return await m.answer("RU: Введите только число.\nUZ: Faqat raqam yozing.")
    people = int(digits)

    ok = await insert_registration(
        tg_id=m.from_user.id,
        name=data["name"],
        car=data["car"],
        plate=data["plate"],
        phone=data["phone"],
        race=data.get("race", "no"),
        race_type=data.get("race_type", "-"),
        payment=data.get("payment", "-"),
        people=people
    )
    if not ok:
        return await m.answer("❗️ Регистрация с таким номером телефона или госномером уже существует.\nAgar ma’lumotni o‘zgartirmoqchi bo‘lsangiz — @UkAkbar bilan bog‘laning.")

    # Итог
    race_line = data["race_type"] if data.get("race") == "yes" else "Нет"
    await m.answer(
        "✅ <b>Регистрация успешна!</b>\n\n"
        f"👤 {data['name']}\n"
        f"🚙 {data['car']}  •  {data['plate']}\n"
        f"📞 {data['phone']}\n"
        f"🏁 Участие: {race_line}\n"
        f"💰 Оплата: {data.get('payment','-')}\n"
        f"👥 Людей: {people}",
        parse_mode=ParseMode.HTML
    )
    # Доп-опция: проживание
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

# ================== Admin: export ==================
@admin_router.message(Command("export"))
async def cmd_export_csv(m: types.Message):
    if not is_admin(m):
        return await m.answer("❌ У вас нет доступа.")
    import csv, io
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID","Имя","Автомобиль","Госномер","Телефон","Кол-во",
        "Участие(Да/Нет)","Дисциплина","Статус оплаты","Дата регистрации (UTC)"
    ])
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id,name,car,plate,phone,people,race,race_type,payment,created_at "
            "FROM registrations ORDER BY id"
        ) as cur:
            async for rid,name,car,plate,phone,people,race,race_type,payment,created_at in cur:
                writer.writerow([
                    rid, name, car, plate, phone, people,
                    ("Да" if str(race).lower().startswith("y") else "Нет"),
                    (race_type or "-"),
                    (payment or "-"),
                    created_at
                ])
    output.seek(0)
    await m.answer_document(
        types.BufferedInputFile(output.getvalue().encode("utf-8"),
                                filename=f"registrations_{datetime.utcnow().date()}.csv")
    )

@admin_router.message(Command("exportxlsx")))
async def cmd_export_xlsx(m: types.Message):
    if not is_admin(m):
        return await m.answer("❌ У вас нет доступа.")
    rows = []
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id,name,car,plate,phone,people,race,race_type,payment,created_at "
            "FROM registrations ORDER BY id"
        ) as cur:
            async for r in cur:
                rows.append(r)

    wb = Workbook()
    ws = wb.active
    ws.title = "Registrations"
    ws.append([
        "ID","Имя","Автомобиль","Госномер","Телефон","Кол-во",
        "Участие(Да/Нет)","Дисциплина","Статус оплаты","Дата регистрации (UTC)"
    ])
    for rid,name,car,plate,phone,people,race,race_type,payment,created_at in rows:
        ws.append([
            rid, name, car, plate, phone, people,
            ("Да" if str(race).lower().startswith("y") else "Нет"),
            (race_type or "-"),
            (payment or "-"),
            created_at
        ])
    for col in ws.columns:
        width = max(len(str(c.value)) if c.value is not None else 0 for c in col)
        ws.column_dimensions[col[0].column_letter].width = min(width + 2, 42)

    buf = BytesIO(); wb.save(buf); buf.seek(0)
    await m.answer_document(
        types.BufferedInputFile(buf.getvalue(),
                                filename=f"registrations_{datetime.utcnow().date()}.xlsx"),
        caption="Экспорт регистраций (Excel)"
    )

@admin_router.message(Command("count"))
async def cmd_count(m: types.Message):
    if not is_admin(m):
        return await m.answer("❌ У вас нет доступа.")
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM registrations") as cur:
            row = await cur.fetchone()
    await m.answer(f"Всего регистраций: <b>{row[0]}</b>", parse_mode=ParseMode.HTML)

# ================== Runner ==================
async def main():
    await init_db()
    bot = Bot(TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp.include_router(admin_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
