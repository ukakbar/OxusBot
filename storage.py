import aiosqlite
from datetime import datetime

DB_PATH = "bot.db"

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS registrations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER,
  dt_created TEXT,
  lang TEXT,
  name TEXT,
  car TEXT,
  plate TEXT,
  people TEXT,
  phone TEXT,
  lodging_plan TEXT,
  photo_file_id TEXT,
  pay_status TEXT,
  pay_dt TEXT,
  receipt_file_id TEXT
);
"""

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SQL)
        await db.commit()

async def insert_reg(user_id, lang, name, car, plate, people, phone, lodging_plan, photo_file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO registrations (user_id, dt_created, lang, name, car, plate, people, phone, lodging_plan, photo_file_id, pay_status) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (user_id, datetime.utcnow().isoformat(), lang, name, car, plate, people, phone, lodging_plan, photo_file_id, "submitted")
        )
        await db.commit()
        cur = await db.execute("SELECT last_insert_rowid()")
        row = await cur.fetchone()
        return row[0]

async def set_receipt(reg_id, file_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE registrations SET receipt_file_id=?, pay_status=? WHERE id=?", (file_id, "paid_pending", reg_id))
        await db.commit()

async def confirm_payment(reg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE registrations SET pay_status=?, pay_dt=? WHERE id=?", ("paid_confirmed", datetime.utcnow().isoformat(), reg_id))
        await db.commit()

async def reject_payment(reg_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE registrations SET pay_status=? WHERE id=?", ("submitted", reg_id))
        await db.commit()

async def get_reg_by_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM registrations WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))
        return await cur.fetchone()

async def all_regs():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT * FROM registrations ORDER BY id DESC")
        return await cur.fetchall()
