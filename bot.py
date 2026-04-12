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
    {"id": -1002040788383, "name": "Bolalar tashkiloti ⎸Qashqadaryo", "url": "https://t.me/Bolalar_Qashqadaryo"},
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

# ================= KANALNI TEKSHIRISH =================
async def is_subscribed(user_id):
    for channel in REQUIRED_CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                return False
        except:
            return False
    return True

# ================= KANALNI TARK ETISH VA QAYTA KIRISH =================
@dp.chat_member()
async def on_chat_member_update(event: ChatMemberUpdated):
    channel_ids = [ch['id'] for ch in REQUIRED_CHANNELS]
    if event.chat.id not in channel_ids:
        return

    user_id = event.from_user.id
    full_name = event.from_user.full_name

    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT score, ref_by FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        if not row: return
        
        current_score, ref_by = row

        # CHIQIB KETSA: Ball ayirish
        if event.new_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
            await db.execute("UPDATE users SET score = max(0, score - 1) WHERE user_id=?", (user_id,))
            if ref_by:
                await db.execute("UPDATE users SET score = max(0, score - 1) WHERE user_id=?", (ref_by,))
                try:
                    await bot.send_message(ref_by, f"⚠️ <b>{full_name}</b> kanaldan chiqib ketgani sababli sizdan <b>1 ball</b> ayirildi!")
                except: pass

        # QAYTA QO'SHILSA: Ballni qaytarish
        elif event.new_chat_member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            # Faqat avvalgi status "left" yoki "kicked" bo'lsa ball qo'shiladi
            if event.old_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
                await db.execute("UPDATE users SET score = score + 1 WHERE user_id=?", (user_id,))
                if ref_by:
                    await db.execute("UPDATE users SET score = score + 1 WHERE user_id=?", (ref_by,))
                    try:
                        await bot.send_message(ref_by, f"✅ <b>{full_name}</b> kanalga qayta qo'shildi! <b>1 ball</b> qaytarildi.")
                        # 3 ball bo'lganini tekshirish
                        cur = await db.execute("SELECT score FROM users WHERE user_id=?", (ref_by,))
                        new_score = (await cur.fetchone())[0]
                        if new_score == 3:
                            invite = await bot.create_chat_invite_link(PRIVATE_CHANNEL_ID, member_limit=1)
                            await bot.send_message(ref_by, f"🎉 Tabriklaymiz! Ballaringiz 3 taga yetdi.\nMaxfiy kanal havolasi: {invite.invite_link}")
                    except: pass
        
        await db.commit()

# ================= START =================
@dp.message(CommandStart())
async def start_cmd(msg: Message):
    user_id = msg.from_user.id
    name = msg.from_user.full_name
    username = msg.from_user.username
    
    args = msg.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = await cur.fetchone()

        if not user:
            await db.execute("INSERT INTO users (user_id, name, username, ref_by, score) VALUES(?,?,?,?,?)", 
                             (user_id, name, username, ref_id, 0))
            if ref_id and ref_id != user_id:
                await db.execute("UPDATE users SET score = score + 1 WHERE user_id=?", (ref_id,))
                try:
                    cur = await db.execute("SELECT score FROM users WHERE user_id=?", (ref_id,))
                    ref_score = (await cur.fetchone())[0]
                    await bot.send_message(ref_id, f"🔔 Yangi do'st qo'shildi! Sizga <b>+1 ball</b> berildi.")
                    
                    if ref_score == 3:
                        invite = await bot.create_chat_invite_link(PRIVATE_CHANNEL_ID, member_limit=1)
                        await bot.send_message(ref_id, f"🎉 Tabriklaymiz! 3 ta do'stingizni taklif qildingiz.\nYopiq kanal havolasi: {invite.invite_link}")
                except: pass
            await db.commit()
        else:
            await db.execute("UPDATE users SET name = ?, username = ? WHERE user_id = ?", (name, username, user_id))
            await db.commit()

    buttons = [[InlineKeyboardButton(text=f"📢 {ch['name']}", url=ch['url'])] for ch in REQUIRED_CHANNELS]
    buttons.append([InlineKeyboardButton(text="✅ Men qo‘shildim", callback_data="check_subs")])
    
    start_text = f"Assalomu alaykum! Botimizga xush kelibsiz, <b>{name}</b>!\n\n⚡️ <b>SAT Matematika Olimpiadasiga xush kelibsiz!</b> 🏆\n\nIshtirok etish uchun quyidagi kanallarimizga qo‘shiling."
    await msg.answer(start_text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

# ================= CALLBACKS =================
@dp.callback_query(F.data == "check_subs")
async def check_callback(call: CallbackQuery):
    subbed = await is_subscribed(call.from_user.id)
    if not subbed:
        await call.answer("❌ Obuna to'liq emas! Avval hamma kanallarga a'zo bo'ling.", show_alert=True)
        return

    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT score FROM users WHERE user_id=?", (call.from_user.id,))
        score = (await cur.fetchone())[0]

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔗 Referal havola", callback_data="get_ref"), 
         InlineKeyboardButton(text="📊 Ballarim", callback_data="my_score")],
        [InlineKeyboardButton(text="🏆 Top-10", callback_data="show_top")]
    ])

    if score >= 3:
        status_text = f"🎉 Siz allaqachon <b>{score} ball</b> to‘pladingiz! Quyidagi tugma orqali <b>yopiq kanal havolasini</b> oling."
    else:
        status_text = f"Har bir muvaffaqiyatli taklif uchun siz <b>+1 ball</b> olasiz. <b>3 ball</b> to‘plagan qatnashchilar loyiha ichiga qabul qilinadi.\n\n📊 Sizning hozirgi ballaringiz: <b>{score}</b>"

    menu_text = f"""Do‘stlaringizni <b>“🏆 SAT MATH OLYMPIAD”</b> ga bepul qatnashishga taklif qiling.

Sizga <b>shaxsiy referral havola</b> berildi. Do‘stlaringiz shu havola orqali kirib, barcha talablarni bajarganidan so‘ng, bot sizga <b>yopiq kanal havolasini</b> avtomatik yuboradi.

{status_text}

<b>Sovrin yutish usullari:</b>
1. SAT MATH OLYMPIAD da g‘olib bo‘lish
2. Eng ko‘p do‘st taklif qilib <b>Top-3</b> o‘rinni olish

<b>Referral havolangizni olish uchun pastdagi tugmani bosing👇</b>"""

    await call.message.answer(menu_text, reply_markup=kb)
    await call.answer()

@dp.callback_query(F.data == "get_ref")
async def get_ref(call: CallbackQuery):
    link = f"https://t.me/{BOT_USERNAME}?start={call.from_user.id}"
    text = f"""🏆 <b>SAT MATH OLYMPIAD</b>
Qanday qatnashish mumkin:

1. Botni ishga tushiring
2. 3 ta do‘stingizni taklif qiling
3. Olimpiyada o‘tkaziladigan yopiq kanaliga kirish huquqini oling

<b>Sovrinlar:</b>
• Masalalarni yechish yoki ko‘proq odam taklif qilish orqali g‘olib bo‘lish mumkin
• Eng yaxshi qatnashchilar uchun haqiqiy va qimmatbaho sovrinlar

<b>Referral reyting:</b>
• Eng ko‘p do‘st taklif qilganlar leaderboard ga kiradi va qo‘shimcha mukofotlar oladi
• Agar taklif qilgan do‘stlaringiz kanaldan chiqib ketsa, ballaringiz kamayadi

Jiddiy tayyorlaning va hozirdan boshlang!

<b>Referal link:</b>
<code>{link}</code>"""
    await call.message.answer(text)
    await call.answer()

@dp.callback_query(F.data == "my_score")
async def my_score(call: CallbackQuery):
    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT score FROM users WHERE user_id=?", (call.from_user.id,))
        score = (await cur.fetchone())[0]

    if score >= 3:
        try:
            invite = await bot.create_chat_invite_link(PRIVATE_CHANNEL_ID, member_limit=1)
            await call.message.answer(f"✅ Ballaringiz yetarli ({score}/3).\nMaxfiy kanal havolasi: {invite.invite_link}")
        except:
            await call.message.answer("⚠️ Texnik xatolik (Bot admin emas).")
    else:
        await call.message.answer(f"📊 Sizning ballaringiz: <b>{score}/3</b>\nKirish uchun yana {3-score} ta do'st kerak.")
    await call.answer()

@dp.callback_query(F.data == "show_top")
async def show_top(call: CallbackQuery):
    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT name, score FROM users ORDER BY score DESC LIMIT 10")
        users = await cur.fetchall()
    text = "<b>TOP 10 FOYDALANUVCHILAR:</b>\n\n"
    for i, u in enumerate(users, 1):
        text += f"{i}. {u[0]} — <b>{u[1]}</b> ball\n"
    await call.message.answer(text)
    await call.answer()

# ================= ADMIN VA BOSHQA FUNKSIYALAR (ESKI KODDAGI KABI) =================
@dp.message(Command("admin"), F.from_user.id == ADMIN_ID)
async def admin_panel(msg: Message):
    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        total = (await cur.fetchone())[0]
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE score >= 3")
        completed = (await cur.fetchone())[0]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Reklama yuborish", callback_data="send_ad")],
        [InlineKeyboardButton(text="📊 Excel Hisobot", callback_data="get_report")]
    ])
    await msg.answer(f"🛡 <b>ADMIN PANEL</b>\n\nJami: {total}\nShartni bajargan: {completed}", reply_markup=kb)

@dp.callback_query(F.data == "get_report", F.from_user.id == ADMIN_ID)
async def get_report(call: CallbackQuery):
    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT user_id, name, score FROM users")
        rows = await cur.fetchall()
    output = "ID | Ism | Ball\n" + "-"*30 + "\n"
    for r in rows: output += f"{r[0]} | {r[1]} | {r[2]}\n"
    await call.message.answer_document(BufferedInputFile(output.encode(), filename="report.txt"))

@dp.callback_query(F.data == "send_ad", F.from_user.id == ADMIN_ID)
async def start_ad(call: CallbackQuery, state: FSMContext):
    await call.message.answer("Reklama xabarini yuboring:")
    await state.set_state(AdminStates.waiting_for_ad)

@dp.message(AdminStates.waiting_for_ad, F.from_user.id == ADMIN_ID)
async def broadcast_ad(msg: Message, state: FSMContext):
    async with aiosqlite.connect("db.sqlite3") as db:
        cur = await db.execute("SELECT user_id FROM users")
        users = await cur.fetchall()
    for user in users:
        try:
            await bot.copy_message(user[0], msg.chat.id, msg.message_id)
            await asyncio.sleep(0.05)
        except: pass
    await msg.answer("✅ Yuborildi.")
    await state.clear()

async def main():
    await create_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
