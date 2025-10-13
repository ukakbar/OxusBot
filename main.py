import os
import asyncio
import logging
import sqlite3
import tempfile
import datetime
import csv

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ------------------ CONFIG ------------------
TOKEN = os.getenv("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0") or 0)
bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
router_export = Router()
# --------------------------------------------


# ------------------ DATABASE ------------------
def init_db():
    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        car TEXT,
        phone TEXT,
        lang TEXT,
        people INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    conn.commit()
    conn.close()

# ------------------------------------------------


# ------------------ REGISTRATION ------------------
@router.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "Добро пожаловать на регистрацию OxusBot!\n\n"
        "Чтобы зарегистрироваться, отправьте данные в формате:\n\n"
        "`Имя, Автомобиль, Телефон, Кол-во человек`\n\n"
        "Пример:\n`Akbar, Jeep Grand, +998901112233, 3`",
        parse_mode="Markdown"
    )

@router.message(F.text.regexp(r"^[A-Za-zА-Яа-яЁё\s]+,\s*.+,\s*\+?\d+,\s*\d+$"))
async def register(message: Message):
    try:
        name, car, phone, people = [x.strip() for x in message.text.split(",")]
        people = int(people)
        conn = sqlite3.connect("bot.db")
        cur = conn.cursor()
        cur.execute("INSERT INTO registrations (name, car, phone, lang, people) VALUES (?, ?, ?, ?, ?)",
                    (name, car, phone, "RU", people))
        conn.commit()
        conn.close()

        reg_id = cur.lastrowid
        await message.answer(f"✅ Регистрация успешна! Ваш ID: {reg_id}\n\n"
                             f"👤 {name}\n🚙 {car}\n📞 {phone}\n👥 Кол-во человек: {people}")

        # уведомление админу
        if ADMIN_CHAT_ID:
            await bot.send_message(
                ADMIN_CHAT_ID,
                f"🆕 Новая регистрация (ID {reg_id}):\n"
                f"👤 {name}\n🚙 {car}\n📞 {phone}\n👥 Людей: {people}"
            )
    except Exception as e:
        await message.answer("Ошибка при регистрации, проверьте формат.")
        print(e)
# ------------------------------------------------


# ------------------ EXPORT TO CSV ------------------
def _detect_people_column(cur) -> str | None:
    candidates = {"people", "persons", "count", "qty", "passengers", "num_people"}
    cur.execute("PRAGMA table_info(registrations)")
    cols = {row[1].lower() for row in cur.fetchall()}
    for c in candidates:
        if c in cols:
            return c
    return None

@router_export.message(Command("export"))
async def export_csv(message: Message):
    if not ADMIN_CHAT_ID or message.from_user.id != ADMIN_CHAT_ID:
        return await message.answer("⛔ У вас нет доступа к этой команде.")

    conn = sqlite3.connect("bot.db")
    cur = conn.cursor()
    people_col = _detect_people_column(cur)

    if people_col:
        cur.execute(f"SELECT id, name, car, phone, lang, {people_col} AS people, created_at FROM registrations ORDER BY id DESC")
        headers = ["id", "name", "car", "phone", "lang", "people", "created_at"]
        rows = cur.fetchall()
    else:
        cur.execute("SELECT id, name, car, phone, lang, created_at FROM registrations ORDER BY id DESC")
        headers = ["id", "name", "car", "phone", "lang", "people", "created_at"]
        rows_raw = cur.fetchall()
        rows = [(r[0], r[1], r[2], r[3], r[4], 1, r[5]) for r in rows_raw]

    conn.close()

    if not rows:
        return await message.answer("📭 Пока нет регистраций.")

    total_people = sum(int(r[5] or 0) for r in rows)
    total_reg = len(rows)

    with tempfile.NamedTemporaryFile("w", newline="", suffix=".csv", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)
        writer.writerow([])
        writer.writerow(["ИТОГО", "", "", "", "", "Всего людей", "Заявок"])
        writer.writerow(["", "", "", "", "", total_people, total_reg])
        tmp_path = f.name

    ts = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M")
    await message.answer_document(
        FSInputFile(tmp_path, filename=f"registrations_{ts}.csv"),
        caption=f"✅ Экспорт выполнен\nВсего заявок: {total_reg}\nВсего людей: {total_people}"
    )
# ------------------------------------------------


# ------------------ MAIN ------------------
async def main():
    logging.basicConfig(level=logging.INFO)
    init_db()
    dp.include_router(router)
    dp.include_router(router_export)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
# ------------------------------------------------
