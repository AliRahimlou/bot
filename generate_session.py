import os
from telethon import TelegramClient

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')

client = TelegramClient('session_name', API_ID, API_HASH)

async def main():
    await client.start()
    print("Client Created Successfully. Session file is saved.")

with client:
    client.loop.run_until_complete(main())
