
import json
from datetime import datetime, timedelta

seen_messages = set()

def has_seen_message(message_id):
    return message_id in seen_messages

def mark_message_seen(message_id):
    seen_messages.add(message_id)

def update_memory(message):
    try:
        with open("memory/short_term.json", "r") as f:
            memory = json.load(f)
    except:
        memory = {}

    channel_id = str(message.channel.id)
    now = datetime.now().isoformat()

    if channel_id not in memory:
        memory[channel_id] = []

    memory[channel_id].append({
        "author": message.author.name,
        "user_id": str(message.author.id),
        "content": message.content,
        "timestamp": now
    })

    with open("memory/short_term.json", "w") as f:
        json.dump(memory, f, indent=2)

def load_short_term(channel_id):
    try:
        with open("memory/short_term.json", "r") as f:
            memory = json.load(f)
    except:
        return []

    now = datetime.now()
    result = []
    channel_msgs = memory.get(str(channel_id), [])
    for entry in channel_msgs:
        try:
            msg_time = datetime.fromisoformat(entry["timestamp"])
            if now - msg_time <= timedelta(minutes=15):
                role = "user" if entry["user_id"] != "kate" else "assistant"
                result.append({"role": role, "content": entry["content"]})
        except:
            continue
    return result
def log_message(message):
    with open("logs/debug_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] {message.author.name}: {message.content}\\n")

