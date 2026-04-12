import requests
import os

PORT = int(os.environ.get("PORT", 8080))
URL = f"http://127.0.0.1:{PORT}/api/auth"

try:
    resp = requests.post(URL, json={"password": "hotdog"})
    print(f"Status: {resp.status_code}")
    print(f"Body: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
