
import json
import re

def load_personality():
    try:
        with open("config/personality.json") as f:
            return json.load(f)
    except:
        return {}

def apply_personality(text):
    personality = load_personality()
    text = text.lower()
    if personality.get("break_grammar", True):
        text = re.sub(r"[.?!]", "", text)
        text = re.sub(r"['’]", "", text)
    return text
