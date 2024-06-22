from flask import Flask, request, jsonify
from flask_cors import CORS
from telethon import TelegramClient
from dotenv import load_dotenv
import json
import os
import asyncio
import sqlite3
import concurrent.futures
from threading import Lock

# Load environment variables from .env file
load_dotenv()

# Get API ID, hash, and chat ID from environment variables
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
chat_id = '@paris_trojanbot'  # The chat ID or username of the chat you want to send messages to

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize contract sets and locks
contract_ids = set()
sent_contract_ids = set()
db_lock = Lock()
executor = concurrent.futures.ThreadPoolExecutor()
processing_lock = Lock()

# Initialize Telegram client
client = TelegramClient('session_name', api_id, api_hash)


@app.route('/save_contracts', methods=['POST'])
def save_contracts():
    data = request.get_json()
    contract_key = data.get('contractKey')
    if contract_key and contract_key not in contract_ids:
        contract_ids.add(contract_key)
        with open('contracts.json', 'w') as f:
            json.dump(list(contract_ids), f)
        executor.submit(process_new_contracts)
    return jsonify(success=True)


@app.route('/get_contracts', methods=['GET'])
def get_contracts():
    return jsonify(list(contract_ids))


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


async def send_messages(chat_id, messages):
    async with TelegramClient('session_name', api_id, api_hash) as client:
        try:
            await client.start()
            for message in messages:
                print(f"Sending message: {message}")
                await client.send_message(chat_id, message)
                await asyncio.sleep(1)  # Delay between messages
        except sqlite3.OperationalError as e:
            print(f"SQLite error: {e}")
        except Exception as e:
            print(f"Error sending messages: {e}")


def process_new_contracts():
    with processing_lock:
        asyncio.run(_process_new_contracts())


async def _process_new_contracts():
    global sent_contract_ids

    # Load current contract IDs and previously sent contract IDs
    current_contract_ids = contract_ids
    sent_contract_ids = set(load_json('sent_contracts.json'))

    # Determine new contract IDs to send
    new_contract_ids = current_contract_ids - sent_contract_ids

    if new_contract_ids:
        messages = [f"{contract_id}" for contract_id in new_contract_ids]
        await send_messages(chat_id, messages)

        # Update sent contract IDs
        with db_lock:
            sent_contract_ids.update(new_contract_ids)
            save_json('sent_contracts.json', list(sent_contract_ids))

    print("Finished processing new contracts")


if __name__ == "__main__":
    contract_ids = set(load_json('contracts.json'))
    sent_contract_ids = set(load_json('sent_contracts.json'))
    app.run(debug=False)
