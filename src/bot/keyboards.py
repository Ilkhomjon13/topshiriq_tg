from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def user_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Topshiriqlar"), KeyboardButton(text="📊 Mening natijam")],
            [KeyboardButton(text="🏆 Mening sovg'alarim"), KeyboardButton(text="👤 Profilim")],
            [KeyboardButton(text="ℹ️ Qoidalar"), KeyboardButton(text="📞 Yordam")],
        ],
        resize_keyboard=True,
    )


def admin_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📋 Topshiriqlar"), KeyboardButton(text="➕ Topshiriq qo'shish")],
            [KeyboardButton(text="🎁 Sovg'alar"), KeyboardButton(text="👥 Foydalanuvchilar")],
            [KeyboardButton(text="⏳ So'rovlar"), KeyboardButton(text="📊 Statistika")],
            [KeyboardButton(text="📢 Xabarnoma"), KeyboardButton(text="⚙️ Sozlamalar")],
            [KeyboardButton(text="🧾 Loglar")],
        ],
        resize_keyboard=True,
    )
