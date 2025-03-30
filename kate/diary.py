
import json
from datetime import datetime

def add_diary_entry(thought):
    today = datetime.now().strftime('%Y-%m-%d')
    try:
        with open("memory/diary.json", "r") as f:
            diary = json.load(f)
    except:
        diary = {}

    if today not in diary:
        diary[today] = []

    diary[today].append({
        "time": datetime.now().isoformat(),
        "entry": thought
    })

    with open("memory/diary.json", "w") as f:
        json.dump(diary, f, indent=2)
