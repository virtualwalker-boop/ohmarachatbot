import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

PAGE_ACCESS_TOKEN = os.getenv("META_PAGE_ACCESS_TOKEN")

if not PAGE_ACCESS_TOKEN or "YOUR_PAGE_ACCESS_TOKEN" in PAGE_ACCESS_TOKEN:
    print("Error: Please set your actual META_PAGE_ACCESS_TOKEN in the .env file first.")
    exit(1)

url = "https://graph.facebook.com/v21.0/me/messenger_profile"
params = {"access_token": PAGE_ACCESS_TOKEN}
payload = {
    "get_started": {
        "payload": "GET_STARTED" # Clicking 'Get Started' will send this postback event
    }
}

print("Sending request to Meta's Messenger Profile API...")
response = requests.post(url, json=payload, params=params)

if response.status_code == 200:
    print("Success! 'Get Started' button has been registered on your Facebook Page.")
    print("Response:", response.json())
else:
    print(f"Failed (Status Code {response.status_code}):")
    print(response.text)
