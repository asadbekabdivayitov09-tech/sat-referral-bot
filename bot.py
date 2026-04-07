import asyncio
import aiosqlite
import logging
import io
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, BufferedInputFile, ChatMemberUpdated
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# --- KONFIGURATSIYA ---
TOKEN = "8247343198:AAHVdKBLrev7hP-M2RyBSWBB3k6PqABNYlM"
ADMIN_ID = 7871908619 
BOT_USERNAME = "DigitalSAT_bot" 
PRIVATE_CHANNEL_ID = -1003887821245

REQUIRED_CHANNELS = [
    {"id": -1003596418374, "name": "SAT Prep | The Duo SAT Hub", "url": "https://t.me/DigitalSAT_Math"},
    {"id": -1001232048732, "name": "Mirfayzbek Abdullayev", "url": "https://t.me/Mirfayzbek_blog"},
    {"id": -1002040788383, "name": "Bolalar tashkiloti ⎸Qashqadaryo", "url": "https://t.me/Bolalar_Qashqadaryo"}, # Vergul to'g'irlandi
    {"id": -1003334879516, "name": "M&A SAT prep (cooking SAT in may )", "url": "https://t.me/MASATiseasy"}
]

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

class AdminStates(StatesGroup):
    waiting_for_ad = State()

# ================= DATABASE =================
async def create_db():
    async with aiosqlite.connect("db.sqlite3") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users(
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            username TEXT,
            ref_by INTEGER,
            score INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        await db.commit()

# ================= KANALNI TEKSHIRISH FUNKSIYASI =================
async def check_and_update_score(user_id, full_name):
    unsubscribed_count = 0 
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                unsubscribed_count += 1
        except:
            unsubscribed_count += 1

    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT score FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        current_score = row[0] if row else 0
            
    is_all_subbed = (unsubscribed_count == 0)
    return is_all_subbed, current_score

# ================= KANALNI TARK ETGANLARNI NAZORAT QILISH =================
@dp.chat_member()
async def on_chat_member_update(event: ChatMemberUpdated):
    channel_ids = [ch['id'] for ch in REQUIRED_CHANNELS]
    if event.chat.id not in channel_ids:
        return

    # Agar foydalanuvchi kanaldan chiqib ketsa
    if event.new_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
        user_id = event.from_user.id
        full_name = event.from_user.full_name

        async with aiosqlite.connect("db.sqlite3") as db:
            cur = await db.execute("SELECT score, ref_by FROM users WHERE user_id=?", (user_id,))
            row = await cur.fetchone()
            
            if row:
                current_score, ref_by = row
                # Foydalanuvchini o'zini jazolash
                await db.execute("UPDATE users SET score = max(0, score - 1) WHERE user_id=?", (user_id,))
                
                # Taklif qilgan odamdan ball ayirish
                if ref_by:
                    await db.execute("UPDATE users SET score = max(0, score - 1) WHERE user_id=?", (ref_by,))
                    try:
                        await bot.send_message(
                            ref_by, 
                            f"⚠️ <b>{full_name}</b> kanaldan chiqib ketgani sababli sizdan <b>1 ball</b> ayirildi!"
                        )
                    except:
                        pass
                await db.commit()

# ================= START =================
@dp.message(CommandStart())
async def start_cmd(msg: Message):
    user_id = msg.from_user.id
    name = msg.from_user.full_name
    username = msg.from_user.username
    
    args = msg.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    # Obunani tekshirish
    unsub_count = 0
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(channel["id"], user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                unsub_count += 1
        except:
            unsub_count += 1

    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = await cur.fetchone()

        if not user:
            await db.execute("INSERT INTO users (user_id, name, username, ref_by, score) VALUES(?,?,?,?,?)", 
                             (user_id, name, username, ref_id, 0))
            if ref_id and ref_id != user_id:
                await db.execute("UPDATE users SET score = score + 1 WHERE user_id=?", (ref_id,))
                try:
                    await bot.send_message(ref_id, f"🔔 Yangi do'st qo'shildi! Sizga <b>+1 ball</b> berildi.")
                except: pass
            await db.commit()
        else:
            await db.execute("UPDATE users SET name = ?, username = ? WHERE user_id = ?", (name, username, user_id))
            await db.commit()

    buttons = [[InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch['url'])] for ch in REQUIRED_CHANNELS]
    buttons.append([InlineKeyboardButton(text="✅ Men qo‘shildim", callback_data="check_subs")])
    
    status_msg = ""
    if unsub_count > 0:
        status_msg = "<b>Avval Kanallarga to`liq qo`shiling❌</b>\n\n"

    start_text = f"""{status_msg}Assalomu alaykum! Botimizga xush kelibsiz, <b>{name}</b>!

⚡️ <b>SAT Matematika Olimpiadasiga xush kelibsiz!</b> 🏆

Ishtirok etish uchun quyidagi kanallarimizga qo‘shiling.
Shundan so‘ng "✅ Men qo‘shildim" tugmasini bosing."""

    await msg.answer(start_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ================= CALLBACKS =================
@dp.callback_query(F.data == "check_subs")
async def check_callback(call: CallbackQuery):
    is_sub, score = await check_and_update_score(call.from_user.id, call.from_user.full_name)
    if not is_sub:
        await call.answer(f"❌ Obuna to'liq emas! Avval Kanallarga to`liq qo`shiling❌", show_alert=True)
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Referal havola", callback_data="get_ref"), 
         InlineKeyboardButton(text="📊 Ballarim", callback_data="my_score")],
        [InlineKeyboardButton(text="🏆 Top-10", callback_data="show_top")]
    ])

    menu_text = f"""✅ Barcha kanallarga a'zo ekansiz! 👏

Har bir muvaffaqiyatli taklif uchun sizga <b>+1 ball</b> beriladi. <b>3 ball</b> to‘plagan ishtirokchilar olimpiadaga qabul qilinadi.

📊 <b>Sizning hozirgi ballaringiz:</b> <b>{score}</b>"""

    await call.message.answer(menu_text, reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "get_ref")
async def get_ref(call: CallbackQuery):
    link = f"https://t.me/{BOT_USERNAME}?start={call.from_user.id}"
    await call.message.answer(f"Sizning referal havolangiz:\n<code>{link}</code>\n\nUni do'stlaringizga tarqating!")
    await call.answer()

@dp.callback_query(F.data == "my_score")
async def my_score(call: CallbackQuery):
    is_sub, score = await check_and_update_score(call.from_user.id, call.from_user.full_name)
    if not is_sub:
         await call.answer(f"❌ Obuna to'liq emas!", show_alert=True)
         return

    if score >= 3:
        try:
            invite = await bot.create_chat_invite_link(PRIVATE_CHANNEL_ID, member_limit=1)
            await call.message.answer(f"Tabriklaymiz! Ballaringiz yetarli.\nMaxfiy kanal havolasi: {invite.invite_link}")
        except:
            await call.message.answer("⚠️ Bot yopiq kanalda admin emas yoki texnik xato.")
    else:
        await call.message.answer(f"📊 Sizning ballaringiz: <b>{score}/3</b>\nLinkni olish uchun yana {3-score} ta do'stingizni taklif qiling.")
    await call.answer()

@dp.callback_query(F.data == "show_top")
async def show_top(call: CallbackQuery):
    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT name, username, score FROM users ORDER BY score DESC LIMIT 10")
        users = await cur.fetchall()
    
    text = "<b>TOP 10 FOYDALANUVCHILAR:</b>\n\n"
    for i, u in enumerate(users, 1):
        uname = f" (@{u[1]})" if u[1] else ""
        text += f"{i}. {u[0]}{uname} — <b>{u[2]}</b> ball\n"
    
    await call.message.answer(text)
    await call.answer()

# ================= ADMIN PANEL =================
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(msg: Message):
    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE score >= 3")
        completed = (await cur.fetchone())[0]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="send_ad")],
        [InlineKeyboardButton(text="📊 Batafsil Excel/Hujjat", callback_data="get_report")]
    ])
    
    text = (
        f"🛡 <b>ADMIN PANEL</b>\n\n"
        f"👤 Jami foydalanuvchilar: <b>{total}</b>\n"
        f"✅ Shartni bajarganlar (3+ ball): <b>{completed}</b>"
    )
    await msg.answer(text, reply_markup=kb)

@dp.callback_query(F.data == "get_report", F.from_user.id == ADMIN_ID)
async def get_report(call: CallbackQuery):
    await call.answer("Hisobot tayyorlanmoqda...")
    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT user_id, name, username, score, ref_by FROM users")
        rows = await cur.fetchall()

    output = "ID | Ism | Username | Ball | Kim taklif qilgan (ID)\n"
    output += "-" * 50 + "\n"
    for r in rows:
        output += f"{r[0]} | {r[1]} | @{r[2] if r[2] else 'yoq'} | {r[3]} | {r[4] if r[4] else 'Direct'}\n"

    file_content = io.BytesIO(output.encode())
    await call.message.answer_document(
        BufferedInputFile(file_content.getvalue(), filename="users_report.txt"),
        caption="📊 Barcha foydalanuvchilar va takliflar hisoboti."
    )

@dp.callback_query(F.data == "send_ad", F.from_user.id == ADMIN_ID)
async def start_ad(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Reklama xabarini yuboring (rasm, matn yoki video):")
    await state.set_state(AdminStates.waiting_for_ad)
    await call.answer()

@dp.message(AdminStates.waiting_for_ad, F.from_user.id == ADMIN_ID)
async def broadcast_ad(msg: Message, state: FSMContext):
    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT user_id FROM users")
        users = await cur.fetchall()
    
    count = 0
    status_msg = await msg.answer("Yuborish boshlandi...")
    for user in users:
        try:
            await bot.copy_message(chat_id=user[0], from_chat_id=msg.chat.id, message_id=msg.message_id)
            count += 1
            await asyncio.sleep(0.05)
        except: pass
    
    await status_msg.edit_text(f"✅ Xabar {count} kishiga muvaffaqiyatli yuborildi.")
    await state.clear()

# ================= RUN =================
async def main():
    await create_db()
    await bot.delete_webhook(drop_pending_updates=True)
    print("Bot muvaffaqiyatli ishga tushdi... 🚀")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "chat_member"])

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
