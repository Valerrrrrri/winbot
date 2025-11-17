# -*- coding: utf-8 -*-
# Файл: winbot.py
# Запуск:
#   python winbot.py

import os
import random
import asyncio
import sqlite3
from datetime import date
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile

# ================== КОНФІГ (твои данные) ==================
BOT_TOKEN   = "8113214724:AAGEnVY3gSSlNuypmpmVjJD5DJCivfhLEr4"
CHANNEL_ID  = -1001800748026                         # numeric id канала (надежно)
CHANNEL_URL = "https://t.me/ezovinua"  # если есть публичная ссылка/инвайт — добавь сюда (например, https://t.me/your_channel)

# Абсолютные пути — чтобы не было проблем с рабочей директорией
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PHOTO_FOLDER = os.path.join(BASE_DIR, "photos")
DB_PATH      = os.path.join(BASE_DIR, "bot.db")
TZ           = ZoneInfo("Europe/Kyiv")

# Тексты для подписи под фото (можно добавить сколько угодно)
CAPTIONS = [
    "Зараз ти отримаєш те, що варто почути. Поміркуй, чому саме це з’явилось сьогодні 🌿",
    "Подумай, що саме ця картинка хоче тобі підказати сьогодні 🌬️",
    "Прийми це послання з довірою. Відчуй, де воно відгукується в тобі ✨",
]
# ===========================================================

bot = Bot(BOT_TOKEN)
dp  = Dispatcher()

# ---------------- БАЗА (ліміт 1/день) ----------------
def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            last_sent DATE
        )
    """)
    con.commit()
    con.close()

def can_send_today(user_id: int) -> bool:
    today = date.today()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("SELECT last_sent FROM users WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    con.close()
    if not row:
        return True
    try:
        last = date.fromisoformat(row[0])
    except Exception:
        return True
    return last < today

def mark_sent_today(user_id: int):
    today = date.today().isoformat()
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO users(user_id, last_sent) VALUES(?, ?)
        ON CONFLICT(user_id) DO UPDATE SET last_sent=excluded.last_sent
    """, (user_id, today))
    con.commit()
    con.close()

# ---------------- КНОПКИ ----------------
def kb_go():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Поїхали", callback_data="go")]
    ])

def kb_subscribe():
    rows = [[InlineKeyboardButton(text="🔁 Перевірити підписку", callback_data="check_sub")]]
    if CHANNEL_URL:
        rows.append([InlineKeyboardButton(text="📣 Відкрити канал", url=CHANNEL_URL)])
    return InlineKeyboardMarkup(inline_keyboard=rows)

def kb_get_message():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔮 Отримати послання", callback_data="get_msg")]
    ])

def kb_come_tomorrow():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🕊 Отримати ще (завтра)", callback_data="get_msg")]
    ])

# ---------------- ХЕНДЛЕРЫ ----------------
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    text = (
        "Привіт! Це бот, де ти отримаєш послання саме для себе ✨\n"
        "Готова/готовий розпочати?"
    )
    await message.answer(text, reply_markup=kb_go())

@dp.callback_query(F.data == "go")
async def on_go(callback: types.CallbackQuery):
    text = (
        "Щоб скористатися ботом — перевір свою підписку на канал.\n\n"
        "Натисни кнопку нижче, підпишись і повернись сюди натиснути «Перевірити підписку»."
        + ("\n\n(Кнопка «Відкрити канал» з’явиться, якщо додати посилання в CHANNEL_URL)" if not CHANNEL_URL else "")
    )
    await callback.message.answer(text, reply_markup=kb_subscribe())
    await callback.answer()

@dp.callback_query(F.data == "check_sub")
async def on_check_sub(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        status = getattr(member, "status", None)
        if status in ("member", "administrator", "creator"):
            await callback.message.answer(
                "Дякую за підписку! Можеш отримати своє послання 🫶",
                reply_markup=kb_get_message()
            )
        else:
            await callback.message.answer(
                "Схоже, підписки ще немає. Підпишись і спробуй ще раз 😊",
                reply_markup=kb_subscribe()
            )
    except Exception as e:
        await callback.message.answer(
            "Не вдалося перевірити підписку. Переконайся, що бот доданий у канал і має права адміністратора.\n"
            f"Помилка: {e}"
        )
    await callback.answer()

@dp.callback_query(F.data == "get_msg")
async def on_get_msg(callback: types.CallbackQuery):
    user_id = callback.from_user.id

    # Лимит: 1 раз в день
    if not can_send_today(user_id):
        await callback.message.answer(
            "Ти вже отримувала/отримував послання сьогодні 🌞\n"
            "Повернись завтра — я чекатиму 🕊",
            reply_markup=kb_come_tomorrow()
        )
        await callback.answer()
        return

    # Подводка
    await callback.message.answer(
        "Зараз ти отримаєш те, що тобі варто почути… 💫\n"
        "Подумай, чому саме ця картинка тобі потрапила сьогодні."
    )

    # Список фото (только jpg/jpeg/png)
    try:
        files = [f for f in os.listdir(PHOTO_FOLDER) if f.lower().endswith((".jpg", ".jpeg", ".png"))]
    except FileNotFoundError:
        files = []

    if not files:
        await callback.message.answer("😅 Фото не знайдено. Додай файл(и) у папку 'photos'.")
        await callback.answer()
        return

    filename = random.choice(files)
    path = os.path.join(PHOTO_FOLDER, filename)

    try:
        photo = FSInputFile(path)
        await callback.message.answer_photo(photo, caption=random.choice(CAPTIONS))
        mark_sent_today(user_id)
    except Exception as e:
        await callback.message.answer(f"❌ Не вдалося надіслати фото. Помилка: {e}")

    await callback.answer()

# ---------------- ЗАПУСК ----------------
async def main():
    init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    print(f"Бот запущено ✅ | Фото папка: {PHOTO_FOLDER}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
