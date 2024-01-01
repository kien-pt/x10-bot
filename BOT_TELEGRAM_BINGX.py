import asyncio

from telethon.sync import events

from utils.constants import *
from core.engine.telegram import TelegramEngine


class BotTelegramBingX:
    def __init__(self, bot_token, api_id, api_hash, admin_id, bingx_client):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.admin_id = admin_id
        self.tele_engine = TelegramEngine(bot_token, api_id, api_hash, self.loop)
        self.tele_client = self.tele_engine.client
        self.bingx_client = bingx_client

    async def async_run_events(self):
        await self.tele_client.run_until_disconnected()
        
    def run_until_disconnected(self):
        @self.tele_client.on(events.NewMessage(chats=self.admin_id, pattern='/ping', from_users=1283551985))
        async def pong_handler(event):
            message = event.message
            if message.text != '/ping': return
            self.tele_engine.send_message(self.admin_id, 'pong')

        self.loop.run_until_complete(self.async_run_events())


