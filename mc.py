# url = 'https://www.geckoterminal.com/solana/pools/GdeytBSJyArGHqFhcVG5E8hNGFYqFTvhQp97gTbSpump'

# headers = {
#     'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
#     'Cache-Control': 'no-cache',
#     'Pragma': 'no-cache',
#     'Connection': 'close'  # Ensure the connection is not reused
# }

# response = requests.get(url, headers=headers)

# if response.status_code == 200:
#     soup = BeautifulSoup(response.text, 'html.parser')

#     # Find the <tr> containing the market cap information
#     market_cap_th = soup.find('th', string='Market Cap')
#     if market_cap_th:
#         market_cap_td = market_cap_th.find_next('td', class_='number-1')
#         if market_cap_td:
#             market_cap_span = market_cap_td.find('span')
#             if market_cap_span:
#                 market_cap_value = market_cap_span.text.strip()
#                 print('Current Mc:' , market_cap_value)
# else:
#     print(f'Request failed with status code: {response.status_code}')



# working server but 25% of called 

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
import requests
from bs4 import BeautifulSoup

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

def parse_market_cap(market_cap_str):
    market_cap_str = market_cap_str.lower()
    if 'k' in market_cap_str:
        return float(market_cap_str.replace('$', '').replace(',', '').replace('k', '')) * 1000
    elif 'm' in market_cap_str:
        return float(market_cap_str.replace('$', '').replace(',', '').replace('m', '')) * 1000000
    else:
        return float(market_cap_str.replace('$', '').replace(',', ''))

def get_current_market_cap(contract_id):
    url = f'https://www.geckoterminal.com/solana/pools/{contract_id}'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36',
        'Cache-Control': 'no-cache',
        'Pragma': 'no-cache',
        'Connection': 'close'  # Ensure the connection is not reused
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        market_cap_th = soup.find('th', string='Market Cap')
        if market_cap_th:
            market_cap_td = market_cap_th.find_next('td', class_='number-1')
            if market_cap_td:
                market_cap_span = market_cap_td.find('span')
                if market_cap_span:
                    market_cap_value = market_cap_span.text.strip()
                    return parse_market_cap(market_cap_value)
    except Exception as e:
        print(f"Error fetching market cap for {contract_id}: {e}")
    return None

@app.route('/save_contracts', methods=['POST'])
def save_contracts():
    data = request.get_json()
    contract_key = data.get('contractKey')
    market_cap_str = data.get('marketCap')
    try:
        called_market_cap = parse_market_cap(market_cap_str)
    except ValueError as e:
        print(f"Error parsing market cap {market_cap_str}: {e}")
        return jsonify(success=False, error=str(e)), 400

    if contract_key and contract_key not in contract_ids:
        contract_ids.add((contract_key, called_market_cap))
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
                data = json.load(f)
                return {tuple(item) for item in data}
        except json.JSONDecodeError:
            return set()
    return set()

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(list(data), f)

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

    current_contracts = contract_ids
    sent_contract_ids = load_json('sent_contracts.json')

    new_contracts = current_contracts - sent_contract_ids

    if new_contracts:
        messages = []
        for contract_key, called_market_cap in new_contracts:
            print(f"Checking contract {contract_key} with called market cap {called_market_cap}")
            current_market_cap = get_current_market_cap(contract_key)
            if current_market_cap is not None:
                print(f"Current market cap for {contract_key} is {current_market_cap}")
                if current_market_cap <= called_market_cap:
                    messages.append(f"{contract_key}")
                else:
                    while current_market_cap > called_market_cap * 0.75:
                        print(f"Waiting for market cap to drop for {contract_key} (Current: {current_market_cap}, Called: {called_market_cap})")
                        await asyncio.sleep(5)  # Wait for 5 sec before rechecking
                        current_market_cap = get_current_market_cap(contract_key)
                    messages.append(f"{contract_key}")

        if messages:
            await send_messages(chat_id, messages)

            with db_lock:
                sent_contract_ids.update(new_contracts)
                save_json('sent_contracts.json', sent_contract_ids)

    print("Finished processing new contracts")

if __name__ == "__main__":
    contract_ids = load_json('contracts.json')
    sent_contract_ids = load_json('sent_contracts.json')
    app.run(debug=False)





# 25% lower than the initial as apposed to the OGcalled

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
import requests
from bs4 import BeautifulSoup

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

def parse_market_cap(market_cap_str):
    market_cap_str = market_cap_str.lower()
    if 'k' in market_cap_str:
        value = float(market_cap_str.replace('$', '').replace(',', '').replace('k', '')) * 1000
    elif 'm' in market_cap_str:
        value = float(market_cap_str.replace('$', '').replace(',', '').replace('m', '')) * 1000000
    else:
        value = float(market_cap_str.replace('$', '').replace(',', ''))
    return round(value, 1)

def get_current_market_cap(contract_id):
    url = f'https://gmgn.ai/sol/token/{contract_id}'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            response_text = response.text
            start_index = response_text.find('"market_cap":') + len('"market_cap":')
            end_index = response_text.find(',', start_index)
            market_cap = response_text[start_index:end_index].strip()
            return parse_market_cap(market_cap)
        else:
            print(f"Failed to retrieve data: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching market cap for {contract_id}: {e}")
        return None

@app.route('/save_contracts', methods=['POST'])
def save_contracts():
    data = request.get_json()
    contract_key = data.get('contractKey')
    market_cap_str = data.get('marketCap')
    try:
        called_market_cap = parse_market_cap(market_cap_str)
    except ValueError as e:
        print(f"Error parsing market cap {market_cap_str}: {e}")
        return jsonify(success=False, error=str(e)), 400

    if contract_key and contract_key not in contract_ids:
        contract_ids.add((contract_key, called_market_cap))
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
                data = json.load(f)
                return {tuple(item) for item in data}
        except json.JSONDecodeError:
            return set()
    return set()

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(list(data), f)

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

    current_contracts = contract_ids
    sent_contract_ids = load_json('sent_contracts.json')

    new_contracts = current_contracts - sent_contract_ids

    if new_contracts:
        messages = []
        for contract_key, called_market_cap in new_contracts:
            print(f"Checking contract {contract_key} with called market cap {called_market_cap}")
            current_market_cap = get_current_market_cap(contract_key)
            if current_market_cap is not None:
                print(f"Current market cap for {contract_key} is {current_market_cap}")
                if current_market_cap <= called_market_cap:
                    messages.append(f"{contract_key}")
                else:
                    initial_market_cap = current_market_cap
                    while current_market_cap > initial_market_cap * 0.75:
                        print(f"Waiting for market cap to drop for {contract_key} (Current: {current_market_cap}, Initial: {initial_market_cap})")
                        await asyncio.sleep(3)  # Wait for a minute before rechecking
                        current_market_cap = get_current_market_cap(contract_key)
                    messages.append(f"{contract_key}")

        if messages:
            await send_messages(chat_id, messages)

            with db_lock:
                sent_contract_ids.update(new_contracts)
                save_json('sent_contracts.json', sent_contract_ids)

    print("Finished processing new contracts")

if __name__ == "__main__":
    contract_ids = load_json('contracts.json')
    sent_contract_ids = load_json('sent_contracts.json')
    app.run(debug=False)
