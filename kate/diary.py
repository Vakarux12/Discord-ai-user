import json
from datetime import datetime

def log_diary(entry):
    try:
        with open("memory/diary.json", "r") as f:
            diary = json.load(f)
    except:
        diary = {}

    today = datetime.now().strftime("%Y-%m-%d")
    if today not in diary:
        diary[today] = []

    diary[today].append({
        "time": datetime.now().isoformat(),
        "entry": entry
    })

    with open("memory/diary.json", "w") as f:
        json.dump(diary, f, indent=2)

def get_recent_entries(days=1):
    try:
        with open("memory/diary.json", "r") as f:
            diary = json.load(f)
        return diary
    except:
        return {}