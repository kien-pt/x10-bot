from telethon.sync import events

from utils.constants import *
from core.engine.telegram import TelegramBot


class BotTest:
    def __init__(self):
        self.telegram_bot = TelegramBot(
            bot_token=TELEGRAM_BOT_TOKEN,
            api_id=TELETHON_API_ID,
            api_hash=TELETHON_API_HASH)
    
    def run_until_disconnected(self):
        with self.telegram_bot.client:
            print(HELLO_WORLD_TEXT)
            self.telegram_bot.client.run_until_disconnected()


BOT = BotTest()
ADMIN_ID = -895017451


@BOT.telegram_bot.client.on(events.NewMessage(chats=ADMIN_ID, pattern='/ping'))
async def pong_handler(event):
    message = event.message
    if message.text != '/ping': return
    BOT.telegram_bot.send_message(ADMIN_ID, 'pong')


BOT.run_until_disconnected()