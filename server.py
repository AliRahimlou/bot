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
import numpy as np
import datetime

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
    if market_cap_str is None:
        raise ValueError("Market cap string is None")
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

def get_contract_creation_timestamp(contract_id):
    creation_date_time, source = get_creation_timestamp_from_gmgn(contract_id)
    if creation_date_time is None:
        creation_date_time, source = get_creation_timestamp_from_geckoterminal(contract_id)
    return creation_date_time, source

def get_creation_timestamp_from_gmgn(contract_id):
    url = f'https://gmgn.ai/sol/token/{contract_id}'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            script_data = soup.find('script', id='__NEXT_DATA__').string
            data = json.loads(script_data)
            creation_timestamp = data['props']['pageProps']['tokenInfo']['creation_timestamp']
            creation_date_time = datetime.datetime.fromtimestamp(creation_timestamp)
            return creation_date_time, 'gmgn'
        else:
            print(f"Failed to retrieve data from GMGN: {response.status_code}")
            return None, 'gmgn'
    except Exception as e:
        print(f"Error fetching creation timestamp from GMGN for {contract_id}: {e}")
        return None, 'gmgn'

def get_creation_timestamp_from_geckoterminal(contract_id):
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

        age_th = soup.find('span', string='Age')
        if age_th:
            age_td = age_th.find_parent('th').find_next_sibling('td')
            if age_td:
                age_span = age_td.find('span')
                if age_span:
                    age_value = age_span.text.strip()
                    creation_date_time = convert_age_to_datetime(age_value)
                    return creation_date_time, 'geckoterminal'
    except Exception as e:
        print(f"Error fetching age from GeckoTerminal for {contract_id}: {e}")
    return None, 'geckoterminal'

def convert_age_to_datetime(age_value):
    now = datetime.datetime.now()
    if "minute" in age_value:
        minutes = int(age_value.split()[0])
        return now - datetime.timedelta(minutes=minutes)
    if "hour" in age_value:
        hours = int(age_value.split()[0])
        return now - datetime.timedelta(hours=hours)
    if "day" in age_value:
        days = int(age_value.split()[0])
        return now - datetime.timedelta(days=days)
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
                await asyncio.sleep(1.5)  # Delay between messages
        except sqlite3.OperationalError as e:
            print(f"SQLite error: {e}")
        except Exception as e:
            print(f"Error sending messages: {e}")

def process_contract(contract_key, called_market_cap):
    asyncio.run(_process_contract(contract_key, called_market_cap))

def is_trending_upward(market_caps):
    """Return True if market caps are generally increasing, otherwise False."""
    if len(market_caps) < 2:
        return False
    valid_caps = filter_invalid_market_caps(market_caps)
    return np.polyfit(range(len(valid_caps)), valid_caps, 1)[0] > 0

def is_trending_downward(market_caps):
    """Return True if market caps are generally decreasing, otherwise False."""
    if len(market_caps) < 2:
        return False
    valid_caps = filter_invalid_market_caps(market_caps)
    return np.polyfit(range(len(valid_caps)), valid_caps, 1)[0] < 0

def filter_invalid_market_caps(market_caps):
    return [cap for cap in market_caps if np.isfinite(cap)]

async def _process_contract(contract_key, called_market_cap):
    global sent_contract_ids

    sent_contract_ids = load_json('sent_contracts.json')

    if (contract_key, called_market_cap) not in sent_contract_ids:
        # Check contract creation time
        creation_date_time, source = get_contract_creation_timestamp(contract_key)
        if creation_date_time is None or (datetime.datetime.now() - creation_date_time).total_seconds() > 86400:
            print(f"Skipping contract {contract_key} because it is older than 24 hours")
            with db_lock:
                sent_contract_ids.add((contract_key, called_market_cap))
                save_json('sent_contracts.json', sent_contract_ids)
            return

        print(f"Checking contract {contract_key} with called market cap {called_market_cap} at {creation_date_time}")
        current_market_cap, source = get_current_market_cap_with_source(contract_key)
        if current_market_cap is None:
            print(f"Skipping contract {contract_key} due to error fetching market cap")
            with db_lock:
                sent_contract_ids.add((contract_key, called_market_cap))
                save_json('sent_contracts.json', sent_contract_ids)
            return

        print(f"Current market cap for {contract_key} is {current_market_cap}")
        initial_market_cap = current_market_cap

        # Scan for 5 minutes to observe dips
        start_time = time.time()
        market_caps = []
        while time.time() - start_time < 300:  # 300 seconds = 5 minutes
            market_cap, source = get_current_market_cap_with_source(contract_key)
            if market_cap is not None:
                market_caps.append(market_cap)
                print(f"Current market cap for {contract_key} during 5-minute scan: {market_cap} Initial: {initial_market_cap}")
            time.sleep(2 if source == 'gmgn' else 5)

        # Identify significant dips
        dips = [(initial_market_cap - cap) / initial_market_cap * 100 for cap in market_caps if cap < initial_market_cap]
        if not dips:
            print(f"No significant dips found for {contract_key}")
            with db_lock:
                sent_contract_ids.add((contract_key, called_market_cap))
                save_json('sent_contracts.json', sent_contract_ids)
            return

        # Calculate the average of significant dips
        average_dip_percentage = sum(dips) / len(dips)
        average_dip_percentage = round(average_dip_percentage, 1)  # Rounding to one decimal place
        if average_dip_percentage < 5:
            print(f"Skipping contract {contract_key} because the average significant dip percentage is below 5%")
            with db_lock:
                sent_contract_ids.add((contract_key, called_market_cap))
                save_json('sent_contracts.json', sent_contract_ids)
            return

        target_market_cap = initial_market_cap * (1 - average_dip_percentage / 100 * 1.02)  # Adding 2% buffer

        print(f"Average significant dip percentage: {average_dip_percentage}%, Target market cap: {target_market_cap}")

        # Calculate the range for target market cap with ±5% buffer
        lower_bound = round(target_market_cap * 0.90, 1)
        upper_bound = round(target_market_cap * 1.10, 1)

        # Start a 2-minute timer to see if the target market cap is hit
        start_time = time.time()
        while time.time() - start_time < 120:
            market_cap, source = get_current_market_cap_with_source(contract_key)
            if market_cap is not None:
                print(f"Current market cap for {contract_key} during additional 2-minute wait: {market_cap} Target: {target_market_cap}")
            if lower_bound <= market_cap <= upper_bound:
                print(f"Market cap is within the target range for {contract_key} (Current: {market_cap}, Target range: {lower_bound} - {upper_bound})")
                messages = [f"{contract_key}"]
                await send_messages(chat_id, messages)
                with db_lock:
                    sent_contract_ids.add((contract_key, called_market_cap))
                    save_json('sent_contracts.json', sent_contract_ids)
                return
            time.sleep(2 if source == 'gmgn' else 5)

        print(f"Contract {contract_key} did not hit the target within 2 minutes")
        with db_lock:
            sent_contract_ids.add((contract_key, called_market_cap))
            save_json('sent_contracts.json', sent_contract_ids)

# Additional functions remain the same

def get_current_market_cap_with_source(contract_id):
    market_cap, source = get_market_cap_from_gmgn(contract_id)
    if market_cap is None:
        market_cap, source = get_market_cap_from_geckoterminal(contract_id)
    return market_cap, source

if __name__ == "__main__":
    contract_ids = load_json('contracts.json')
    sent_contract_ids = load_json('sent_contracts.json')
    app.run(host='127.0.0.1', port=5001, debug=False)
