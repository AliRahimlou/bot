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

def get_market_data_from_gmgn(contract_id):
    url = f'https://gmgn.ai/sol/token/{contract_id}'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            script_tag = soup.find('script', {'id': '__NEXT_DATA__'})
            if not script_tag:
                raise Exception("Couldn't find the script tag with id __NEXT_DATA__")
            json_data = json.loads(script_tag.string)
            token_info = json_data['props']['pageProps']['tokenInfo']
            market_cap = token_info.get('market_cap', 'N/A')
            volume = token_info.get('volume_5m', 'N/A')
            holders = token_info.get('holder_count', 'N/A')
            if market_cap != 'N/A':
                market_cap = round(float(market_cap), 1)
            if volume != 'N/A':
                volume = round(float(volume), 1)
            return {
                'market_cap': market_cap,
                'volume': volume,
                'holders': holders,
            }
        else:
            print(f"Failed to retrieve data from GMGN: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching market data from GMGN for {contract_id}: {e}")
        return None

def get_contract_creation_timestamp(contract_id):
    url = f'https://gmgn.ai/sol/token/{contract_id}'
    try:
        response = requests.get(url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            script_data = soup.find('script', id='__NEXT_DATA__').string
            data = json.loads(script_data)
            creation_timestamp = data['props']['pageProps']['tokenInfo']['creation_timestamp']
            creation_date_time = datetime.datetime.fromtimestamp(creation_timestamp)
            return creation_date_time
        else:
            print(f"Failed to retrieve data from GMGN: {response.status_code}")
            return None
    except Exception as e:
        print(f"Error fetching creation timestamp from GMGN for {contract_id}: {e}")
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

def is_trending_upward(data):
    """Return True if data is generally increasing, otherwise False."""
    if len(data) < 2:
        return False
    valid_data = [d for d in data if np.isfinite(d)]
    return np.polyfit(range(len(valid_data)), valid_data, 1)[0] > 0

def is_trending_downward(data):
    """Return True if data is generally decreasing, otherwise False."""
    if len(data) < 2:
        return False
    valid_data = [d for d in data if np.isfinite(d)]
    return np.polyfit(range(len(valid_data)), valid_data, 1)[0] < 0

def filter_invalid_data(data):
    return [d for d in data if np.isfinite(d)]

async def _process_contract(contract_key, called_market_cap):
    global sent_contract_ids

    sent_contract_ids = load_json('sent_contracts.json')

    if (contract_key, called_market_cap) not in sent_contract_ids:
        # Check contract creation time
        creation_date_time = get_contract_creation_timestamp(contract_key)
        if creation_date_time is None or (datetime.datetime.now() - creation_date_time).total_seconds() > 86400:
            print(f"Skipping contract {contract_key} because it is older than 24 hours")
            with db_lock:
                sent_contract_ids.add((contract_key, called_market_cap))
                save_json('sent_contracts.json', sent_contract_ids)
            return

        print(f"Checking contract {contract_key} with called market cap {called_market_cap} at {creation_date_time}")
        current_market_data = get_market_data_from_gmgn(contract_key)
        if current_market_data is None:
            print(f"Skipping contract {contract_key} due to error fetching market data")
            with db_lock:
                sent_contract_ids.add((contract_key, called_market_cap))
                save_json('sent_contracts.json', sent_contract_ids)
            return

        print(f"Current market data for {contract_key}: Market Cap: {current_market_data['market_cap']}, Volume: {current_market_data['volume']}, Holders: {current_market_data['holders']}")
        initial_market_cap = current_market_data['market_cap']
        initial_volume = current_market_data['volume']
        initial_holders = current_market_data['holders']

        # Scan for 3 minutes to observe dips and trends
        start_time = time.time()
        market_caps = []
        volumes = []
        holders = []
        while time.time() - start_time < 180:  # 180 seconds = 3 minutes
            market_data = get_market_data_from_gmgn(contract_key)
            if market_data is not None:
                market_caps.append(market_data['market_cap'])
                volumes.append(market_data['volume'])
                holders.append(market_data['holders'])
                if time.time() - start_time < 30:
                    print(f"Current market data for {contract_key} during 30-sec scan: Market Cap: {market_data['market_cap']}, Volume: {market_data['volume']}, Holders: {market_data['holders']} Initial Market Cap: {initial_market_cap}")
                else:
                    print(f"Current market data for {contract_key} during 3-minute scan: Market Cap: {market_data['market_cap']}, Volume: {market_data['volume']}, Holders: {market_data['holders']} Initial Market Cap: {initial_market_cap}")
            else:
                print(f"Error fetching market data during 3-minute scan for {contract_key}. Continuing scan...")
            time.sleep(2)

            # Check for upward trend during the first 30 seconds
            if time.time() - start_time >= 30 and time.time() - start_time < 32:
                # if is_trending_upward(market_caps) and is_trending_upward(volumes) and is_trending_upward(holders) and market_data['volume'] >= 35000:
                if is_trending_upward(volumes) and is_trending_upward(holders) and market_data['volume'] >= 35000:
                    print(f"Market cap, volume, and holders are trending upwards for {contract_key} within the first 30 seconds and volume is no lower than 35000")
                    messages = [f"{contract_key}"]
                    await send_messages(chat_id, messages)
                    with db_lock:
                        sent_contract_ids.add((contract_key, called_market_cap))
                        save_json('sent_contracts.json', sent_contract_ids)
                    return

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
        if average_dip_percentage < 12.5:
            print(f"Skipping contract {contract_key} because the average significant dip percentage is below 15%")
            with db_lock:
                sent_contract_ids.add((contract_key, called_market_cap))
                save_json('sent_contracts.json', sent_contract_ids)
            return

        target_market_cap = round(initial_market_cap * (1 - average_dip_percentage / 100 * 1.02), 1)  # Adding 2% buffer

        print(f"Average significant dip percentage: {average_dip_percentage}%, Target market cap: {target_market_cap}")

        # Calculate the range for target market cap with ±5% buffer
        lower_bound = round(target_market_cap * 0.90, 1)
        upper_bound = round(target_market_cap * 1.05, 1)
        
        # Start a 2-minute timer to see if the target market cap is hit
        start_time = time.time()
        while time.time() - start_time < 120:
            market_data = get_market_data_from_gmgn(contract_key)
            if market_data is not None:
                market_caps.append(market_data['market_cap'])
                volumes.append(market_data['volume'])
                holders.append(market_data['holders'])
                print(f"Current market data for {contract_key} during additional 2-minute wait: Market Cap: {market_data['market_cap']}, Volume: {market_data['volume']}, Holders: {market_data['holders']} Target Market Cap: {target_market_cap}")
                if time.time() - start_time < 15 and is_trending_upward(market_caps) and not is_trending_downward(volumes) and market_data['volume'] >= 35000 and not is_trending_downward(holders):
                    print(f"Market cap, volume, and holders are trending upwards for {contract_key} within the first 15 seconds and volume is no lower than 35000")
                    messages = [f"{contract_key}"]
                    await send_messages(chat_id, messages)
                    with db_lock:
                        sent_contract_ids.add((contract_key, called_market_cap))
                        save_json('sent_contracts.json', sent_contract_ids)
                    return
                if lower_bound <= market_data['market_cap'] <= upper_bound and not is_trending_downward(holders) and not is_trending_downward(volumes) and market_data['volume'] >= 40000:
                    print(f"Market cap is within the target range for {contract_key} (Current: {market_data['market_cap']}, Target range: {lower_bound} - {upper_bound}), holders and volumes are not trending downward, and volume is at least 40000")
                    messages = [f"{contract_key}"]
                    await send_messages(chat_id, messages)
                    with db_lock:
                        sent_contract_ids.add((contract_key, called_market_cap))
                        save_json('sent_contracts.json', sent_contract_ids)
                    return

            else:
                print(f"Error fetching market data during additional 2-minute wait for {contract_key}. Continuing wait...")
            time.sleep(2)

        print(f"Contract {contract_key} did not hit the target within 2 minutes")
        with db_lock:
            sent_contract_ids.add((contract_key, called_market_cap))
            save_json('sent_contracts.json', sent_contract_ids)


if __name__ == "__main__":
    contract_ids = load_json('contracts.json')
    sent_contract_ids = load_json('sent_contracts.json')
    app.run(host=IP, port=int(os.getenv('PORT', 5001)), debug=False)
