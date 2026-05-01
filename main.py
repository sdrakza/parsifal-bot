import asyncio
import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
from aiogram.enums import UpdateType
import yt_dlp
import os

TOKEN = os.environ.get("TOKEN")
bot = Bot(token=TOKEN)
dp = Dispatcher()

YDL_OPTS = {
    'format': 'best[ext=mp4]/best',
    'outtmpl': 'video.%(ext)s',
    'http_headers': {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    },
    'extractor_args': {
        'instagram': {'include_ads': False},
    },
}


def is_tiktok(url: str) -> bool:
    return 'tiktok.com' in url or 'vm.tiktok.com' in url or 'vt.tiktok.com' in url


async def download_tiktok(url: str) -> str:
    api_url = f"https://www.tikwm.com/api/?url={url}"
    async with aiohttp.ClientSession() as session:
        async with session.get(api_url) as resp:
            data = await resp.json()

    if data.get('code') != 0:
        raise Exception(f"tikwm API error: {data.get('msg')}")

    video_url = data['data']['play']

    async with aiohttp.ClientSession() as session:
        async with session.get(video_url) as resp:
            filename = 'video.mp4'
            with open(filename, 'wb') as f:
                f.write(await resp.read())

    return filename


async def download_ytdlp(url: str) -> str:
    with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
    return filename


async def download_and_send(url: str, chat_id: int, reply_to_message_id: int = None, business_connection_id: str = None):
    if is_tiktok(url):
        filename = await download_tiktok(url)
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
