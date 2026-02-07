import asyncio
import os
import yt_dlp
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from concurrent.futures import ThreadPoolExecutor

# ضع توكن البوت هنا أو من متغير بيئي
TOKEN = os.getenv("TOKEN") or "PUT_YOUR_TOKEN_HERE"

bot = Bot(token=TOKEN)
dp = Dispatcher()

# مجلد التحميل المؤقت
DOWNLOAD_PATH = "downloads"
os.makedirs(DOWNLOAD_PATH, exist_ok=True)

# Executor للتحميل في الخلفية (سرعة أعلى)
executor = ThreadPoolExecutor(max_workers=4)

# Cache لتجنب إعادة التحميل
CACHE = {}

# ===== START =====
@dp.message(CommandStart())
async def start(message: types.Message):
    await message.answer(
        "👋 أهلاً بك في بوت التحميل الاحترافي!\n\n"
        "📥 أرسل رابط فيديو من:\n"
        "YouTube - TikTok - Instagram - Twitter\n\n"
        "وسأعرض لك معلومات الفيديو قبل التحميل."
    )

# ===== جلب معلومات الفيديو =====
def get_video_info(url):
    opts = {"quiet": True, "noplaylist": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            "title": info.get("title"),
            "thumbnail": info.get("thumbnail"),
            "id": info.get("id")
        }

# ===== تحميل الفيديو =====
def download_video(url, fmt):
    ydl_opts = {
        "format": fmt,
        "outtmpl": f"{DOWNLOAD_PATH}/%(title)s.%(ext)s",
        "quiet": True,
        "noplaylist": True,
        "merge_output_format": "mp4"
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        file_path = ydl.prepare_filename(info)
        return file_path

# ===== استقبال الرابط =====
@dp.message(F.text)
async def handle_link(message: types.Message):
    url = message.text.strip()

    if "http" not in url:
        await message.answer("❌ أرسل رابط صحيح فقط")
        return

    await message.answer("🔎 جاري جلب معلومات الفيديو...")

    loop = asyncio.get_event_loop()
    try:
        info = await loop.run_in_executor(executor, get_video_info, url)
        title = info["title"]
        thumb = info["thumbnail"]
        video_id = info["id"]
    except Exception:
        await message.answer("❌ لم أستطع قراءة الرابط")
        return

    # أزرار اختيار الجودة
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton("🎬 720p", callback_data=f"{video_id}|720|{url}"),
            InlineKeyboardButton("🎬 480p", callback_data=f"{video_id}|480|{url}")
        ],
        [
            InlineKeyboardButton("🎬 360p", callback_data=f"{video_id}|360|{url}"),
            InlineKeyboardButton("🎧 صوت MP3", callback_data=f"{video_id}|mp3|{url}")
        ]
    ])

    if thumb:
        await message.answer_photo(photo=thumb, caption=f"🎬 {title}\nاختر الجودة:", reply_markup=kb)
    else:
        await message.answer(f"🎬 {title}\nاختر الجودة:", reply_markup=kb)

# ===== التعامل مع الأزرار =====
@dp.callback_query()
async def callbacks(call: types.CallbackQuery):
    try:
        video_id, quality, url = call.data.split("|", 2)
    except ValueError:
        await call.answer("خطأ في البيانات")
        return

    # اختيار صيغة التحميل
    if quality == "720":
        fmt = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        is_audio = False
    elif quality == "480":
        fmt = "bestvideo[height<=480]+bestaudio/best[height<=480]"
        is_audio = False
    elif quality == "360":
        fmt = "bestvideo[height<=360]+bestaudio/best[height<=360]"
        is_audio = False
    else:
        fmt = "bestaudio/best"
        is_audio = True

    # تحقق من الـCache
    if video_id in CACHE:
        file_path = CACHE[video_id]
    else:
        await call.message.answer("⏳ جاري التحميل...")
        loop = asyncio.get_event_loop()
        file_path = await loop.run_in_executor(executor, download_video, url, fmt)
        CACHE[video_id] = file_path

    file_to_send = FSInputFile(file_path)

    # إرسال الفيديو أو الصوت
    try:
        if is_audio:
            await bot.send_audio(call.message.chat.id, file_to_send, caption=os.path.basename(file_path))
        else:
            await bot.send_video(call.message.chat.id, file_to_send, caption=os.path.basename(file_path))
    except Exception as e:
        await bot.send_message(call.message.chat.id, f"❌ حدث خطأ أثناء الإرسال:\n{e}")

    await call.answer()

    # حذف الملفات بعد الإرسال (اختياري)
    # os.remove(file_path)

# ===== تشغيل البوت =====
async def main():
    print("✅ Bot is running...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())