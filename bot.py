import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from scraper import scrape_movie_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "8573110391:AAHtya3zYRpFQYJcmr1pLfDOPdF1SI-wUfI")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://movieextractbot.vercel.app")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def get_start_keyboard():
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🌐 Open Web App",
        web_app=WebAppInfo(url=WEBAPP_URL)
    ))
    return builder.as_markup()

def get_result_keyboard(data: dict):
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(
        text="🌐 Open Web App",
        web_app=WebAppInfo(url=WEBAPP_URL)
    ))
    builder.row(
        InlineKeyboardButton(text="📋 Copy Name", callback_data=f"copy_name"),
        InlineKeyboardButton(text="⭐ Copy IMDb", callback_data=f"copy_imdb")
    )
    builder.row(
        InlineKeyboardButton(text="🎭 Copy Genre", callback_data=f"copy_genre"),
        InlineKeyboardButton(text="🌍 Copy Language", callback_data=f"copy_lang")
    )
    builder.row(
        InlineKeyboardButton(text="📺 Copy Quality", callback_data=f"copy_quality")
    )
    if data.get("thumbnail"):
        builder.row(
            InlineKeyboardButton(text="🖼 Download Thumbnail", callback_data="dl_thumb")
        )
    if data.get("screenshots"):
        builder.row(
            InlineKeyboardButton(text="🖼 Download Screenshots", callback_data="dl_screens")
        )
    builder.row(
        InlineKeyboardButton(text="📤 Create Post", callback_data="create_post")
    )
    return builder.as_markup()

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    await message.answer(
        "👋 <b>Hello!</b>\n\n"
        "Send me any movie/series URL\nor click the button below to open Web App.\n\n"
        "✅ Extract movie/series details\n"
        "✅ Get thumbnail\n"
        "✅ Get all screenshots & merge\n"
        "✅ Create post for channel",
        parse_mode="HTML",
        reply_markup=get_start_keyboard()
    )

@dp.message(F.text.startswith("http"))
async def url_handler(message: types.Message):
    url = message.text.strip()
    processing_msg = await message.answer("⏳ <b>Fetching data...</b>\nPlease wait...", parse_mode="HTML")

    try:
        data = await asyncio.get_event_loop().run_in_executor(None, scrape_movie_data, url)

        if not data or "error" in data:
            await processing_msg.edit_text(
                f"❌ <b>Error:</b> Could not extract data from this URL.\n\n"
                f"Make sure it's a valid HDHub4u movie/series page.",
                parse_mode="HTML"
            )
            return

        # Store data in bot context for callbacks
        user_id = message.from_user.id
        dp["user_data"] = dp.get("user_data", {})
        dp["user_data"][user_id] = data

        text = format_movie_text(data)

        # Send thumbnail if available
        if data.get("thumbnail"):
            try:
                await message.answer_photo(
                    photo=data["thumbnail"],
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=get_result_keyboard(data)
                )
                await processing_msg.delete()
            except Exception:
                await processing_msg.edit_text(
                    text,
                    parse_mode="HTML",
                    reply_markup=get_result_keyboard(data)
                )
        else:
            await processing_msg.edit_text(
                text,
                parse_mode="HTML",
                reply_markup=get_result_keyboard(data)
            )

    except Exception as e:
        logger.error(f"Error processing URL: {e}")
        await processing_msg.edit_text(
            "❌ <b>Something went wrong.</b> Please try again.",
            parse_mode="HTML"
        )

def format_movie_text(data: dict) -> str:
    name = data.get("name", "N/A")
    imdb = data.get("imdb", "N/A")
    genre = data.get("genre", "N/A")
    language = data.get("language", "N/A")
    quality = data.get("quality", "N/A")
    stars = data.get("stars", "N/A")
    episodes = data.get("episodes", "")
    storyline = data.get("storyline", "")

    text = (
        f"🎬 <b>Name:</b> {name}\n"
        f"⭐ <b>IMDb:</b> {imdb}\n"
        f"🎭 <b>Genre:</b> {genre}\n"
        f"🌍 <b>Language:</b> {language}\n"
        f"📺 <b>Quality:</b> {quality}\n"
    )
    if stars and stars != "N/A":
        text += f"👥 <b>Stars:</b> {stars}\n"
    if episodes:
        text += f"📁 <b>Episodes:</b> {episodes}\n"
    if storyline:
        short_story = storyline[:200] + "..." if len(storyline) > 200 else storyline
        text += f"\n📖 <b>Storyline:</b> {short_story}"

    return text

@dp.callback_query(F.data.startswith("copy_"))
async def copy_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = dp.get("user_data", {}).get(user_id, {})

    field_map = {
        "copy_name": ("name", "🎬 Name"),
        "copy_imdb": ("imdb", "⭐ IMDb"),
        "copy_genre": ("genre", "🎭 Genre"),
        "copy_lang": ("language", "🌍 Language"),
        "copy_quality": ("quality", "📺 Quality"),
    }

    key, label = field_map.get(callback.data, ("name", "Name"))
    value = user_data.get(key, "N/A")

    await callback.answer(f"Copied!", show_alert=False)
    await callback.message.answer(
        f"{label}:\n<code>{value}</code>\n\n<i>Tap to copy ☝️</i>",
        parse_mode="HTML"
    )

@dp.callback_query(F.data == "dl_thumb")
async def dl_thumb_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = dp.get("user_data", {}).get(user_id, {})
    thumbnail = user_data.get("thumbnail")

    if thumbnail:
        await callback.answer("Sending thumbnail...")
        await callback.message.answer_document(
            document=thumbnail,
            caption="🖼 Thumbnail"
        )
    else:
        await callback.answer("No thumbnail found!", show_alert=True)

@dp.callback_query(F.data == "dl_screens")
async def dl_screens_handler(callback: types.CallbackQuery):
    from image_processor import merge_screenshots
    import io

    user_id = callback.from_user.id
    user_data = dp.get("user_data", {}).get(user_id, {})
    screenshots = user_data.get("screenshots", [])

    if not screenshots:
        await callback.answer("No screenshots found!", show_alert=True)
        return

    await callback.answer("Processing screenshots...")
    processing = await callback.message.answer("⏳ Merging screenshots...")

    try:
        merged = await asyncio.get_event_loop().run_in_executor(
            None, merge_screenshots, screenshots
        )
        if merged:
            await callback.message.answer_document(
                document=types.BufferedInputFile(merged.read(), filename="screenshots_merged.jpg"),
                caption="🖼 Screenshots (Merged)"
            )
        await processing.delete()
    except Exception as e:
        logger.error(f"Screenshot merge error: {e}")
        await processing.edit_text("❌ Could not merge screenshots.")

@dp.callback_query(F.data == "create_post")
async def create_post_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    user_data = dp.get("user_data", {}).get(user_id, {})

    if not user_data:
        await callback.answer("No data found!", show_alert=True)
        return

    name = user_data.get("name", "N/A")
    imdb = user_data.get("imdb", "N/A")
    genre = user_data.get("genre", "N/A")
    language = user_data.get("language", "N/A")
    quality = user_data.get("quality", "N/A")
    stars = user_data.get("stars", "N/A")
    storyline = user_data.get("storyline", "")

    post = (
        f"🎬 <b>{name}</b>\n\n"
        f"⭐ <b>IMDb:</b> {imdb}\n"
        f"🎭 <b>Genre:</b> {genre}\n"
        f"🌍 <b>Language:</b> {language}\n"
        f"📺 <b>Quality:</b> {quality}\n"
        f"👥 <b>Stars:</b> {stars}\n\n"
    )
    if storyline:
        short = storyline[:300] + "..." if len(storyline) > 300 else storyline
        post += f"📖 <b>Plot:</b>\n{short}\n\n"

    post += (
        f"📥 <b>Download Now:</b> [Your Link Here]\n"
        f"📢 <b>Join Channel:</b> @yourchannel\n\n"
        f"#{name.replace(' ', '').replace('(', '').replace(')', '')[:15]} "
        f"#Hollywood #Hindi"
    )

    await callback.answer()
    await callback.message.answer(
        f"📤 <b>Your Post:</b>\n\n{post}",
        parse_mode="HTML"
    )

async def main():
    logger.info("Bot starting...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
