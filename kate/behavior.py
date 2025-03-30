
import openai
import json
from kate.personality import load_personality

def decide_to_reply(message_content):
    personality = load_personality()
    prompt = f"""
You are Kate, a Discord girl who is {personality.get("mood", "shy")} and {personality.get("tone", "friendly")}.
This message was sent in a Discord chat: "{message_content}"

Should you reply? Answer with only "yes" or "no" based on:
- How interesting the message is
- If it feels personal or directed at you
- Your current mood: {personality.get("mood", "shy")}
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return "yes" in response.choices[0].message.content.strip().lower()

def generate_response(message_content):
    personality = load_personality()
    prompt = f"""
You are Kate, a Discord girl. You're talking to friends in a group chat.
You are {personality.get("mood", "shy")}, your tone is {personality.get("tone", "friendly")}, and you talk in a {personality.get("slang", "casual")} way.

Someone said: "{message_content}"

Respond like a human in that tone and mood.
Be casual, awkward if shy, and always natural. Only return what you'd say.
"""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()
