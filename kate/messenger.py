
import json
from datetime import datetime
import asyncio

def queue_message_request(from_id, to_id, question, context=""):
    try:
        with open("memory/message_queue.json", "r") as f:
            queue = json.load(f)
    except:
        queue = []

    queue.append({
        "from": str(from_id),
        "to": str(to_id),
        "question": question,
        "context": context,
        "status": "pending",
        "asked_at": datetime.now().isoformat()
    })

    with open("memory/message_queue.json", "w") as f:
        json.dump(queue, f, indent=2)

def fetch_pending_for_user(user_id):
    try:
        with open("memory/message_queue.json", "r") as f:
            queue = json.load(f)
    except:
        return []
    return [q for q in queue if q["to"] == str(user_id) and q["status"] == "pending"]

def reply_to_message_request(to_id, from_id, answer, approve=True):
    try:
        with open("memory/message_queue.json", "r") as f:
            queue = json.load(f)
    except:
        queue = []

    for q in queue:
        if q["to"] == str(to_id) and q["from"] == str(from_id) and q["status"] == "pending":
            q["status"] = "approved" if approve else "denied"
            q["answer"] = answer
            q["answered_at"] = datetime.now().isoformat()
            break

    with open("memory/message_queue.json", "w") as f:
        json.dump(queue, f, indent=2)

def get_approved_responses(for_user_id):
    try:
        with open("memory/message_queue.json", "r") as f:
            queue = json.load(f)
    except:
        return []

    results = []
    new_queue = []
    for q in queue:
        if q["from"] == str(for_user_id) and q["status"] in ["approved", "denied"]:
            results.append(q)
        else:
            new_queue.append(q)

    with open("memory/message_queue.json", "w") as f:
        json.dump(new_queue, f, indent=2)

    return results
