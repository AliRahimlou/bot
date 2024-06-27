import requests
import json

# Define the URL to hit
url = "https://gmgn.ai/sol/token/6VeSg58mGb8SGuJ8VPq8JcrD8WdfHemCvvUJrfK8pump"
response = requests.get(url)
# Check if the request was successful
if response.status_code == 200:
    # Parse the response text as JSON
    response_text = response.text
    # Find the market_cap value in the response text
    start_index = response_text.find('"market_cap":') + len('"market_cap":')
    end_index = response_text.find(',', start_index)
    market_cap = response_text[start_index:end_index]
    print(f"Market Cap: {market_cap}")
else:
    print(f"Failed to retrieve data: {response.status_code}")
