import requests
API_KEY = "sk-prod-abc123secretkey-live"

def call_api():
    return requests.get("https://api.example.com", headers={"Authorization": API_KEY})
