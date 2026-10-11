import logging
import os

from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiohttp import web

# ============ НАСТРОЙКИ ============
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = 464498182
CHANNEL_ID = "@arenda_by"
COLIVING_URL = "https://t.me/colivingbymatch_bot/app"
SELF_URL = "https://t.me/arenda_poster_bot"
WEBHOOK_PATH = "/webhook"
PORT = int(os.environ.get("PORT", 8080))
RENDER_URL = os.environ.get("RENDER_EXTERNAL_URL", "")

logging.basicConfig(level=logging.INFO)

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN, 
default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


# ============ КЛАВИАТУРА ============
def get_post_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 СОЗДАТЬ ОБЪЯВЛЕНИЕ БЕСПЛАТНО",
                    url=SELF_URL,
                )
            ],
            [
                InlineKeyboardButton(
                    text="🏠 Найти соседа — Coliving by Match",
                    url=COLIVING_URL,
                )
            ],
        ]
    )


# ============ СТАРТ ============
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer(
            "👋 <b>Админ-панель</b>\n\n"
            "Отвечай на <b>пересланное объявление</b> командой:\n"
            "• /publish — опубликовать\n"
            "• /reject — отклонить\n"
            "• /edit &lt;новый_текст&gt; — опубликовать с правкой"
        )
        return

    await message.answer(
        "👋 <b>Здравствуйте!</b>\n\n"
        "Пришлите ваше объявление по образцу:\n\n"
        "<code>#Сниму / #Сдам / #Ищу\n"
        "Текст объявления (что, район, цена)\n"
        "Контакт (телефон / @username)\n"
        "#хэштеги</code>\n\n"
        "📸 Можно прикрепить фото.\n\n"
        "После отправки — проверим и опубликуем."
    )


# ============ АДМИН-КОМАНДЫ ============
@dp.message(Command("publish"))
async def cmd_publish(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        await message.answer("⚠️ Ответь на сообщение командой /publish")
        return
    await handle_admin_reply(message)


@dp.message(Command("reject"))
async def cmd_reject(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        await message.answer("⚠️ Ответь на сообщение командой /reject")
        return
    await handle_admin_reply(message)


@dp.message(Command("edit"))
async def cmd_edit(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.reply_to_message:
        await message.answer("⚠️ Ответь на сообщение командой /edit 
<текст>")
        return
    await handle_admin_reply(message)


# ============ ПРИЁМ ОБЪЯВЛЕНИЙ ============
@dp.message(F.chat.type == "private")
async def handle_ad(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        return
    if message.text and message.text.startswith("/"):
        return

    user = message.from_user

    await bot.forward_message(
        chat_id=ADMIN_ID,
        from_chat_id=message.chat.id,
        message_id=message.message_id,
    )

    await bot.send_message(
        ADMIN_ID,
        f"☝️ Объявление от:\n"
        f"Имя: {user.full_name}\n"
        f"ID: <code>{user.id}</code>\n"
        f"Username: @{user.username if user.username else '—'}\n\n"
        f"Отвечай на <b>это</b> сообщение: /publish, /reject, /edit.",
    )

    await message.answer(
        "✅ <b>Спасибо!</b>\n\n"
        "Ваше объявление отправлено на модерацию.\n"
        "Подписывайтесь на @arenda_by."
    )


# ============ ОБРАБОТКА АДМИНА ============
async def handle_admin_reply(message: types.Message):
    original = message.reply_to_message
    text = message.text or ""

    if text.startswith("/publish"):
        try:
            await bot.copy_message(
                chat_id=CHANNEL_ID,
                from_chat_id=original.chat.id,
                message_id=original.message_id,
                reply_markup=get_post_keyboard(),
            )
            await message.answer("✅ Опубликовано.")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
        return

    if text.startswith("/reject"):
        await message.answer("❌ Отклонено.")
        return

    if text.startswith("/edit"):
        new_text = text.replace("/edit", "", 1).strip()
        if not new_text:
            await message.answer("⚠️ /edit Новый текст")
            return
        try:
            if original.photo:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=original.photo[-1].file_id,
                    caption=new_text,
                    reply_markup=get_post_keyboard(),
                )
            else:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=new_text,
                    reply_markup=get_post_keyboard(),
                )
            await message.answer("✅ Опубликовано (отредактировано).")
        except Exception as e:
            await message.answer(f"❌ Ошибка: {e}")
        return


# ============ WEBHOOK ============
async def handle_webhook(request: web.Request):
    try:
        data = await request.json()
        update = types.Update.model_validate(data, context={"bot": bot})
        await dp.feed_update(bot, update)
    except Exception as e:
        logging.error(f"Webhook error: {e}")
    return web.Response(status=200)


async def on_startup(app: web.Application):
    if RENDER_URL:
        webhook_url = f"{RENDER_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(webhook_url)
        logging.info(f"Webhook set: {webhook_url}")
    else:
        msg = "RENDER_EXTERNAL_URL not set, webhook not configured"
        logging.warning(msg)


async def on_shutdown(app: web.Application):
    await bot.delete_webhook()


# ============ ЗАПУСК ============
def main():
    app = web.Application()
    app.router.add_post(WEBHOOK_PATH, handle_webhook)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)
    web.run_app(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    main()
