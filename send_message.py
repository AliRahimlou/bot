import asyncio
import os
import json
import requests
from telethon import TelegramClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get API ID, hash, IP, and port from environment variables
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
ip = os.getenv('IP', 'localhost')  # Default to 'localhost' if IP is not set
port = os.getenv('PORT', 5000)  # Default to 5000 if PORT is not set

# Create a new Telegram client instance
client = TelegramClient('session_name', api_id, api_hash)

async def send_messages(chat_id, messages, delay=1):
    """
    Send multiple messages to a chat with a specified delay between each message.
    
    Args:
    chat_id (str): The ID or username of the chat.
    messages (list): A list of messages to send.
    delay (int): The delay between messages in seconds.
    """
    for message in messages:
        await client.send_message(chat_id, message)
        await asyncio.sleep(delay)

def load_json(file_path):
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f)

async def main():
    # Connect to the client
    await client.start()

    # The chat ID or username of the chat you want to send messages to
    chat_id = '@paris_trojanbot'

    # Fetch contract IDs from the server
    server_url = f'http://{ip}:{port}/get_contracts'
    try:
        response = requests.get(server_url)
        contract_ids = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching contract IDs: {e}")
        contract_ids = []

    # Load sent contract IDs
    sent_contract_ids = load_json('sent_contracts.json')

    # Determine new contract IDs to send
    new_contract_ids = [id for id in contract_ids if id not in sent_contract_ids]

    if new_contract_ids:
        # Prepare messages
        messages = ['/buy'] + new_contract_ids
        



        # Send messages with a delay of 1 second between each
        await send_messages(chat_id, messages, delay=1.3)

        # Update sent contract IDs
        sent_contract_ids.extend(new_contract_ids)
        save_json('sent_contracts.json', sent_contract_ids)

    # Disconnect the client
    await client.disconnect()

# Run the client
with client:
    client.loop.run_until_complete(main())
