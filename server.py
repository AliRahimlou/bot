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
import time
from bs4 import BeautifulSoup

# Load environment variables from .env file
load_dotenv()

# Get API ID, hash, and chat ID from environment variables
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
chat_id = '@paris_trojanbot'  # The chat ID or username of the chat you want to send messages to
IP = os.getenv('IP')

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
    market_cap, source = get_market_cap_from_gmgn(contract_id)
    if market_cap is None:
        market_cap, source = get_market_cap_from_geckoterminal(contract_id)
    return market_cap, source

def get_market_cap_from_gmgn(contract_id):
    url = f'https://gmgn.ai/sol/token/{contract_id}'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            response_text = response.text
            start_index = response_text.find('"market_cap":') + len('"market_cap":')
            end_index = response_text.find(',', start_index)
            market_cap = response_text[start_index:end_index].strip()
            return parse_market_cap(market_cap), 'gmgn'
        else:
            print(f"Failed to retrieve data from GMGN: {response.status_code}")
            return None, 'gmgn'
    except Exception as e:
        print(f"Error fetching market cap from GMGN for {contract_id}: {e}")
        return None, 'gmgn'

def get_market_cap_from_geckoterminal(contract_id):
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
                    return parse_market_cap(market_cap_value), 'geckoterminal'
    except Exception as e:
        print(f"Error fetching market cap from GeckoTerminal for {contract_id}: {e}")
    return None, 'geckoterminal'

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
        executor.submit(process_contract, contract_key, called_market_cap)
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

def process_contract(contract_key, called_market_cap):
    asyncio.run(_process_contract(contract_key, called_market_cap))

async def _process_contract(contract_key, called_market_cap):
    global sent_contract_ids

    sent_contract_ids = load_json('sent_contracts.json')

    if (contract_key, called_market_cap) not in sent_contract_ids:
        print(f"Checking contract {contract_key} with called market cap {called_market_cap}")
        current_market_cap, source = get_current_market_cap_with_source(contract_key)
        if current_market_cap is None:
            print(f"Skipping contract {contract_key} due to error fetching market cap")
            with db_lock:
                sent_contract_ids.add((contract_key, called_market_cap))
                save_json('sent_contracts.json', sent_contract_ids)
            return

        print(f"Current market cap for {contract_key} is {current_market_cap}")
        initial_market_cap = current_market_cap
        
        # Instantly send a message
        messages = [f"{contract_key}"]
        await send_messages(chat_id, messages)
        with db_lock:
            sent_contract_ids.add((contract_key, called_market_cap))
            save_json('sent_contracts.json', sent_contract_ids)
        
        # Start watching for market cap drop
        start_time = time.time()
        while True:
            if time.time() - start_time > 10:  # 10 sec for now
                print(f"Contract {contract_key} not satisfied within 5 minutes")
                return

            if current_market_cap <= initial_market_cap * 0.40:
                print(f"Market cap dropped 60% for {contract_key} (Current: {current_market_cap}, Initial: {initial_market_cap})")
                messages = [f"{contract_key}"]
                await send_messages(chat_id, messages)
                with db_lock:
                    sent_contract_ids.add((contract_key, called_market_cap))
                    save_json('sent_contracts.json', sent_contract_ids)
                return

            print(f"Waiting for market cap to drop for {contract_key} (Current: {current_market_cap}, Initial: {initial_market_cap})")
            await asyncio.sleep(2 if source == 'gmgn' else 5)  # Adjust sleep based on source
            current_market_cap, source = get_current_market_cap_with_source(contract_key)
            if current_market_cap is None:
                print(f"Skipping contract {contract_key} due to error fetching market cap during waiting")
                return

def get_current_market_cap_with_source(contract_id):
    market_cap, source = get_market_cap_from_gmgn(contract_id)
    if market_cap is None:
        market_cap, source = get_market_cap_from_geckoterminal(contract_id)
    return market_cap, source

if __name__ == "__main__":
    contract_ids = load_json('contracts.json')
    sent_contract_ids = load_json('sent_contracts.json')
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', 5001)))
