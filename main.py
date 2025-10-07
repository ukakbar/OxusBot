import asyncio, re, csv, tempfile
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from pytz import timezone

from config import (
    BOT_TOKEN, ADMIN_IDS, CARD_NUMBER, TIMEZONE,
    LOCATION_NAME, LOCATION_COORDS, FEE_AMOUNT,
    PRICE_COTTAGE_2, PRICE_COTTAGE_3, PRICE_YURT, ORGANIZER_NICK
)
from locales import RU, UZ
from keyboards import lang_kb, main_menu, people_kb, skip_kb, confirm_kb
import storage


# ------------ Состояния ------------
class RegForm(StatesGroup):
    lang = State()
    name = State()
    car = State()
    plate = State()
    people = State()
    phone = State()
    photo = State()
    confirm = State()
    receipt = State()


# ------------ Настройки ------------
PHONE_RE = re.compile(r"^\+998\s?\d{2}\s?\d{3}\s?\d{2}\s?\d{2}$")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def t_of(lang_code: str):
    return RU if lang_code == "RU" else UZ


def format_amount(num: int) -> str:
    # 300000 -> 300 000
    s = f"{num:,}".replace(",", " ")
    return s

def pay_instructions(lang: str) -> str:
    amt = format_amount(FEE_AMOUNT)
    if lang == "RU":
        return (
            f"💳 *Оплата участия* — {amt} сум с автомобиля\n"
            f"Получатель: *Akbarjon Kulov*\n"
            f"UZCARD: `5614 6806 0888 2326`\n"
            f"VISA:   `4023 0602 2688 2305`\n\n"
            f"После оплаты *пришлите скрин/фото чека* в этот чат.\n"
            f"Связь с организатором: {ORGANIZER_NICK}"
        )
    else:
        return (
            f"💳 *Ishtirok to‘lovi* — {amt} so‘m (har bir avtomobil uchun)\n"
            f"Qabul qiluvchi: *Akbarjon Kulov*\n"
            f"UZCARD: `5614 6806 0888 2326`\n"
            f"VISA:   `4023 0602 2688 2305`\n\n"
            f"To‘lovdan so‘ng *chek skrin/fotosini* shu chatga yuboring.\n"
            f"Aloqa: {ORGANIZER_NICK}"
        )


# ---------------- Старт и выбор языка ----------------
@dp.message(Command("start"))
async def start(m: Message, state: FSMContext):
    await state.clear()
    # (опционально можно отправить баннер, если есть)
    await m.answer(RU["choose_lang"], reply_markup=lang_kb())

@dp.message(F.text.in_(["🇷🇺 Русский", "🇺🇿 O‘zbekcha"]))
async def set_lang(m: Message, state: FSMContext):
    lang = "RU" if "Русский" in m.text else "UZ"
    await state.update_data(lang=lang)
    t = t_of(lang)
    await m.answer(f"*{t['start_title']}*\n\n{t['start_body']}",
                   reply_markup=main_menu(t), parse_mode="Markdown")


# ---------------- Анкета (без шага размещения) ----------------
@dp.message(lambda msg: msg.text in [RU["btn_register"], UZ["btn_register"]])
async def reg_begin(m: Message, state: FSMContext):
    lang = (await state.get_data()).get("lang", "RU")
    t = t_of(lang)
    await m.answer(t["form_name"])
    await state.set_state(RegForm.name)

@dp.message(RegForm.name)
async def reg_name(m: Message, state: FSMContext):
    await state.update_data(name=m.text.strip())
    t = t_of((await state.get_data()).get("lang", "RU"))
    await m.answer(t["form_car"])
    await state.set_state(RegForm.car)

@dp.message(RegForm.car)
async def reg_car(m: Message, state: FSMContext):
    await state.update_data(car=m.text.strip())
    t = t_of((await state.get_data()).get("lang", "RU"))
    await m.answer(t["form_plate"])
    await state.set_state(RegForm.plate)

@dp.message(RegForm.plate)
async def reg_plate(m: Message, state: FSMContext):
    await state.update_data(plate=m.text.strip())
    t = t_of((await state.get_data()).get("lang", "RU"))
    await m.answer(t["form_people"], reply_markup=people_kb(t))
    await state.set_state(RegForm.people)

@dp.message(RegForm.people)
async def reg_people(m: Message, state: FSMContext):
    await state.update_data(people=m.text.strip())
    t = t_of((await state.get_data()).get("lang", "RU"))
    await m.answer(t["form_phone"])
    await state.set_state(RegForm.phone)

@dp.message(RegForm.phone)
async def reg_phone(m: Message, state: FSMContext):
    phone = (m.text or "").strip()
    t = t_of((await state.get_data()).get("lang", "RU"))
    if not PHONE_RE.match(phone):
        await m.answer(t["invalid_phone"])
        return
    await state.update_data(phone=phone)
    await m.answer(t["form_photo"], reply_markup=skip_kb(t))
    await state.set_state(RegForm.photo)

@dp.message(RegForm.photo, F.photo)
async def got_photo(m: Message, state: FSMContext):
    await state.update_data(photo_file_id=m.photo[-1].file_id)
    await show_preview_and_confirm(m, state)

@dp.message(RegForm.photo, F.text)  # Пропуск фото
async def skip_photo(m: Message, state: FSMContext):
    await show_preview_and_confirm(m, state)

async def show_preview_and_confirm(m: Message, state: FSMContext):
    data = await state.get_data()
    t = t_of(data.get("lang", "RU"))
    preview = (
        f"{t['form_preview']}\n\n"
        f"👤 {data.get('name')}\n"
        f"🚙 {data.get('car')} | {data.get('plate')}\n"
        f"👥 {data.get('people')}\n"
        f"📞 {data.get('phone')}\n"
    )
    await m.answer(preview, parse_mode="Markdown")
    await m.answer(t["confirm"], reply_markup=confirm_kb(t))
    await state.set_state(RegForm.confirm)


# ---------------- Подтверждение / Отмена / Назад ----------------
@dp.message(RegForm.confirm)
async def do_confirm(m: Message, state: FSMContext):
    data = await state.get_data()
    t = t_of(data.get("lang", "RU"))
    txt = (m.text or "").strip()
    back_text = t.get("back", "⬅ Orqaga")

    # Отмена анкеты
    if txt == t["cancel"]:
        await state.clear()
        await m.answer(t["menu"], reply_markup=main_menu(t))
        return

    # Назад — вернёмся к фото (последний шаг)
    if txt == back_text:
        await m.answer(t["form_photo"], reply_markup=skip_kb(t))
        await state.set_state(RegForm.photo)
        return

    # Редактировать — начнём с имени
    if txt == t["edit_data_btn"]:
        await m.answer(t["form_name"])
        await state.set_state(RegForm.name)
        return

    # Подтверждение — создаём заявку, отдаём реквизиты и просим чек
    if txt == t["confirm"]:
        reg_id = await storage.insert_reg(
            m.from_user.id,
            data.get("lang", "RU"),
            data["name"], data["car"], data["plate"],
            data["people"], data["phone"],
            None,  # lodging_plan больше не используем
            data.get("photo_file_id")
        )

        # Сообщение админу(ам)
        admin_text = (
            f"🆕 Новая регистрация (ID {reg_id})\n\n"
            f"👤 {data['name']}\n"
            f"🚙 {data['car']} | {data['plate']}\n"
            f"👥 {data['people']}\n"
            f"📞 {data['phone']}\n"
            f"🌐 Lang: {data.get('lang','RU')}"
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, admin_text)
                if data.get("photo_file_id"):
                    await bot.send_photo(admin_id, data["photo_file_id"])
            except Exception:
                pass

        # Инструкция по оплате с двумя картами
        await m.answer(pay_instructions(data.get("lang","RU")), parse_mode="Markdown")
        await m.answer(f"{(UZ if data.get('lang','RU')!='RU' else RU)['file_prompt']} (ID: {reg_id})")
        await state.update_data(reg_id=reg_id)
        await state.set_state(RegForm.receipt)
        return

    # Любой другой текст — повторно показываем кнопки
    await m.answer(t["confirm"], reply_markup=confirm_kb(t))


# ---------------- Приём чека ----------------
@dp.message(RegForm.receipt, F.photo)
async def receipt(m: Message, state: FSMContext):
    data = await state.get_data()
    reg_id = data.get("reg_id")
    if not reg_id:
        await m.answer("No reg id.")
        return

    await storage.set_receipt(reg_id, m.photo[-1].file_id)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"💳 Получен чек по регистрации ID {reg_id}")
            await bot.send_photo(admin_id, m.photo[-1].file_id)
        except Exception:
            pass

    t = t_of(data.get("lang", "RU"))
    await m.answer(t["paid_text"])
    await state.clear()


# ---------------- Инфо и Контакт ----------------
@dp.message(lambda msg: msg.text in [RU["btn_info"], UZ["btn_info"]])
async def info(m: Message, state: FSMContext):
    lang = (await state.get_data()).get("lang", "RU")
    t = t_of(lang)
    msg = t["info_text"].format(
        loc=LOCATION_NAME, coords=LOCATION_COORDS,
        p2=PRICE_COTTAGE_2, p3=PRICE_COTTAGE_3, py=PRICE_YURT
    )
    # пометка про бронирование через организатора
    if lang == "RU":
        msg += f"\n\n⚠️ Бронирование коттеджей/юрты — только через организатора: {ORGANIZER_NICK}"
    else:
        msg += f"\n\n⚠️ Kottej/Yurta broni — faqat tashkilotchi orqali: {ORGANIZER_NICK}"
    await m.answer(msg)

@dp.message(lambda msg: msg.text in [RU["btn_contact"], UZ["btn_contact"]])
async def contact(m: Message, state: FSMContext):
    lang = (await state.get_data()).get("lang", "RU")
    t = t_of(lang)
    await m.answer(t["contact_text"].format(nick=ORGANIZER_NICK))


# ---------------- Админ-команды ----------------
@dp.message(Command("users"))
async def users(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    regs = await storage.all_regs()
    total = len(regs)
    confirmed = sum(1 for r in regs if r[11] == "paid_confirmed")
    await m.answer(f"Всего заявок: {total}\nПодтверждено оплат: {confirmed}")

@dp.message(Command("report"))
async def report(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    regs = await storage.all_regs()
    headers = ["id","user_id","dt_created","lang","name","car","plate","people",
               "phone","lodging_plan","photo_file_id","pay_status","pay_dt","receipt_file_id"]
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".csv")
    with open(tmp.name, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(headers); [w.writerow(r) for r in regs]
    await m.answer_document(FSInputFile(tmp.name), caption="report.csv")

@dp.message(Command("confirm"))
async def confirm(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    parts = (m.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await m.answer("Usage: /confirm <id>")
        return
    await storage.confirm_payment(int(parts[1]))
    await m.answer("OK")

@dp.message(Command("reject"))
async def reject(m: Message):
    if m.from_user.id not in ADMIN_IDS:
        return
    parts = (m.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await m.answer("Usage: /reject <id>")
        return
    await storage.reject_payment(int(parts[1]))
    await m.answer("OK")


# ---------------- Напоминание ----------------
async def weekly_reminder(bot):
    regs = await storage.all_regs()
    targets = {r[1] for r in regs if r[11] in ("submitted", "paid_pending")}
    amt = format_amount(FEE_AMOUNT)
    for uid in targets:
        try:
            await bot.send_message(uid, f"Napominaniye / Eslatma: ishtirok to‘lovi / взнос {amt} so‘m/sum. Iltimos, to‘lovni yakunlang va chekni yuboring.")
        except Exception:
            pass

async def on_startup():
    await storage.init_db()
    sched = AsyncIOScheduler(timezone=timezone(TIMEZONE))
    sched.add_job(lambda: asyncio.create_task(weekly_reminder(bot)),
                  "cron", day_of_week="sun", hour=10, minute=0)
    sched.start()

async def main():
    await on_startup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
