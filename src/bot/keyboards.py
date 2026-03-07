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


def user_tasks_keyboard(tasks: list[tuple[int, str]]) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    for task_id, title in tasks:
        short_title = title if len(title) <= 32 else title[:29] + "..."
        rows.append([KeyboardButton(text=f"📌 {task_id}. {short_title}")])
    rows.append([KeyboardButton(text="🔙 Orqaga")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def user_task_actions_keyboard(is_joined: bool) -> ReplyKeyboardMarkup:
    join_text = "✅ Siz qatnashyapsiz" if is_joined else "✅ Qatnashish"
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=join_text), KeyboardButton(text="📈 Progressim")],
            [KeyboardButton(text="ℹ️ Qoidalar"), KeyboardButton(text="🎁 Sovg'alar")],
            [KeyboardButton(text="🔙 Orqaga")],
        ],
        resize_keyboard=True,
    )


def user_certificates_keyboard(available_ids: list[int]) -> ReplyKeyboardMarkup:
    rows: list[list[KeyboardButton]] = []
    for cert_id in available_ids[:20]:
        rows.append([KeyboardButton(text=f"🎁 Foydalanish #{cert_id}")])
    rows.append([KeyboardButton(text="🔙 Orqaga")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def user_confirm_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Tasdiqlayman"), KeyboardButton(text="❌ Bekor qilish")],
            [KeyboardButton(text="🔙 Orqaga")],
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
