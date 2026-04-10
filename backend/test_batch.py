import requests
import json

payload = {
    "scores": [
        {
            "matchup_id": 1,
            "player_id": 1,
            "hole_number": 1,
            "strokes": 4
        }
    ]
}

res = requests.post('http://127.0.0.1:5000/api/players/scores/batch', json=payload)
print(res.status_code)
print(res.json())
