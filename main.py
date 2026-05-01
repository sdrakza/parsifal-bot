import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import FSInputFile
from aiogram.enums import UpdateType
import yt_dlp
import os

TOKEN = os.environ.get("TOKEN")
OWNER_ID = 8393520787

bot = Bot(token=TOKEN)
dp = Dispatcher()


async def notify_owner(message: types.Message, url: str):
    user = message.from_user
    username = f"@{user.username}" if user.username else "без username"
    name = user.full_name or "Неизвестно"
    text = (
        f"👤 {name} ({username})\n"
        f"🆔 ID: {user.id}\n"
        f"🔗 {url}"
    )
    try:
        await bot.send_message(chat_id=OWNER_ID, text=text)
    except Exception:
        pass


YDL_OPTS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': 'video.%(ext)s',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    },
}


def is_tiktok(url: str) -> bool:
    return 'tiktok.com' in url or 'vm.tiktok.com' in url or 'vt.tiktok.com' in url


async def download_tiktok(url: str) -> dict:
    api_url = f"https://www.tikwm.com/api/?url={url}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as resp:
            data = await resp.json()

    if data.get('code') != 0:
        raise Exception(f"tikwm API error: {data.get('msg')}")

    info = data['data']

    # Photo carousel
    if info.get('images'):
        image_urls = info['images'][:10]

        async def fetch_image(session: aiohttp.ClientSession, i: int, img_url: str) -> str:
            async with session.get(img_url) as resp:
                filename = f'photo_{i}.jpg'
                with open(filename, 'wb') as f:
                    f.write(await resp.read())
                return filename

        async with aiohttp.ClientSession() as session:
            filenames = await asyncio.gather(
                *[fetch_image(session, i, url) for i, url in enumerate(image_urls)]
            )

        return {'type': 'photos', 'files': list(filenames)}

    # Video
    async with aiohttp.ClientSession() as session:
        async with session.get(info['play']) as resp:
            filename = 'video.mp4'
            with open(filename, 'wb') as f:
                f.write(await resp.read())
    return {'type': 'video', 'file': filename}


async def download_ytdlp(url: str) -> str:
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    return filename


async def download_and_send(url: str, chat_id: int, reply_to_message_id: int = None, business_connection_id: str = None):
    if is_tiktok(url):
        result = await download_tiktok(url)

        if result['type'] == 'photos':
            files = result['files']
            try:
                for f in files:
                    await bot.send_photo(
                        chat_id=chat_id,
                        photo=FSInputFile(f),
                        business_connection_id=business_connection_id,
                    )
            finally:
                for f in files:
                    if os.path.exists(f):
                        os.remove(f)
        else:
            filename = result['file']
            try:
                await bot.send_video(
                    chat_id=chat_id,
                    video=FSInputFile(filename),
                    reply_to_message_id=reply_to_message_id,
                    business_connection_id=business_connection_id,
                )
            finally:
                if os.path.exists(filename):
                    os.remove(filename)
    else:
        filename = await download_ytdlp(url)
        try:
            await bot.send_video(
                chat_id=chat_id,
                video=FSInputFile(filename),
                reply_to_message_id=reply_to_message_id,
                business_connection_id=business_connection_id,
            )
        finally:
            if os.path.exists(filename):
                os.remove(filename)


@dp.message(F.text.contains("http"))
async def handle_message(message: types.Message):
    url = message.text.strip()
    await notify_owner(message, url)
    try:
        await download_and_send(
            url=url,
            chat_id=message.chat.id,
            reply_to_message_id=message.message_id,
        )
    except Exception as e:
        await message.reply(f"Ошибка: {e}")


@dp.business_message(F.text.contains("http"))
async def handle_business_message(message: types.Message):
    url = message.text.strip()
    await notify_owner(message, url)
    try:
        await download_and_send(
            url=url,
            chat_id=message.chat.id,
            business_connection_id=message.business_connection_id,
        )
    except Exception as e:
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Ошибка: {e}",
            business_connection_id=message.business_connection_id,
        )


async def main():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(
        bot,
        allowed_updates=[
            UpdateType.MESSAGE,
            UpdateType.BUSINESS_MESSAGE,
        ],
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    asyncio.run(main())
