import logging
import os
from pathlib import Path
from datetime import datetime, timedelta

from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


# ================== ENV ==================
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found. Check your .env file")

# ================== CONFIG ==================
SCOPES = ["https://www.googleapis.com/auth/calendar"]
CLIENT_SECRET_FILE = BASE_DIR / "client_secret.json"
TOKEN_FILE = BASE_DIR / "token.json"
TIMEZONE = "Europe/Oslo"
CALENDAR_ID = "primary"

# ================== LOGGING ==================
logging.basicConfig(level=logging.INFO)

# ================== GOOGLE AUTH ==================
def authorize_google():
    if TOKEN_FILE.exists():
        logging.info("Google already authorized")
        return

    logging.info("Opening browser for Google authorization...")
    flow = InstalledAppFlow.from_client_secrets_file(
        CLIENT_SECRET_FILE, SCOPES
    )
    creds = flow.run_local_server(port=8080)

    TOKEN_FILE.write_text(creds.to_json())
    logging.info("Google authorization completed")


def get_calendar_service():
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    return build("calendar", "v3", credentials=creds)

# ================== BOT ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)

# ================== DATA ==================
AVAILABLE_DATES = [
    "29 Jan", "30 Jan", "31 Jan",
    "01 Feb", "02 Feb", "03 Feb", "04 Feb"
]

AVAILABLE_TIMES = [
    "10:00", "11:00", "12:00", "13:00", "14:00"
]

user_state = {}

# ================== CALENDAR ==================
def create_calendar_event(date_str, time_str):
    service = get_calendar_service()

    start_dt = datetime.strptime(
        f"{date_str} 2026 {time_str}", "%d %b %Y %H:%M"
    )
    end_dt = start_dt + timedelta(hours=1)

    event = {
        "summary": "Barber appointment",
        "description": "Booked via Telegram bot",
        "start": {
            "dateTime": start_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": end_dt.isoformat(),
            "timeZone": TIMEZONE,
        },
    }

    service.events().insert(
        calendarId=CALENDAR_ID,
        body=event
    ).execute()

# ================== KEYBOARDS ==================
def main_menu():
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("✂️ Book / Bestill", callback_data="book"),
        InlineKeyboardButton("💰 Prices / Priser", callback_data="prices"),
        InlineKeyboardButton("📍 Contact / Kontakt", callback_data="contact"),
    )
    return kb


def dates_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for d in AVAILABLE_DATES:
        kb.add(InlineKeyboardButton(d, callback_data=f"date_{d}"))
    return kb


def times_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    for t in AVAILABLE_TIMES:
        kb.add(InlineKeyboardButton(t, callback_data=f"time_{t}"))
    return kb

# ================== HANDLERS ==================
@dp.message_handler(commands=["start"])
async def start(message: types.Message):
    await message.answer(
        "👋 Welcome to Lofoten Barber!\nChoose an option ⬇️",
        reply_markup=main_menu()
    )


@dp.callback_query_handler(lambda c: c.data == "prices")
async def prices(cb: types.CallbackQuery):
    await cb.message.answer(
        "💰 Prices:\n✂️ Haircut — 500 NOK\n🧔 Beard — 300 NOK"
    )
    await cb.answer()


@dp.callback_query_handler(lambda c: c.data == "contact")
async def contact(cb: types.CallbackQuery):
    await cb.message.answer(
        "📍 Lofoten Barber\n📞 +47 XXX XX XXX"
    )
    await cb.answer()


@dp.callback_query_handler(lambda c: c.data == "book")
async def book(cb: types.CallbackQuery):
    await cb.message.answer(
        "📅 Choose a date:",
        reply_markup=dates_keyboard()
    )
    await cb.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("date_"))
async def choose_date(cb: types.CallbackQuery):
    date = cb.data.replace("date_", "")
    user_state[cb.from_user.id] = {"date": date}

    await cb.message.answer(
        f"⏰ Available times for {date}:",
        reply_markup=times_keyboard()
    )
    await cb.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("time_"))
async def choose_time(cb: types.CallbackQuery):
    time = cb.data.replace("time_", "")
    date = user_state.get(cb.from_user.id, {}).get("date")

    if not date:
        await cb.message.answer("⚠️ Please choose a date first.")
        await cb.answer()
        return

    create_calendar_event(date, time)

    await cb.message.answer(
        f"✅ Booking confirmed!\n\n"
        f"📅 Date: {date}\n"
        f"⏰ Time: {time}\n\n"
        f"✂️ See you at Lofoten Barber!"
    )
    await cb.answer()

# ================== START ==================
if __name__ == "__main__":
    authorize_google()
    executor.start_polling(dp, skip_updates=True)
