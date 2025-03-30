import discord
import openai
import asyncio
import os
import json
from dotenv import load_dotenv
from kate.memory import load_short_term, log_message, update_memory, has_seen_message, mark_message_seen

load_dotenv()
TOKEN = os.getenv("DISCORD_USER_TOKEN")
openai.api_key = os.getenv("OPENAI_API_KEY")

client = discord.Client()
message_buffer = {}
typing_users = {}
reply_tasks = {}

def get_relationship_data(user_id):
    try:
        with open("memory/relationships.json", "r") as f:
            relationships = json.load(f)
        rel = relationships.get(str(user_id), {})
        affection = rel.get("score", 0)
        trust = rel.get("trust", 0)
        role = rel.get("role", "unknown")
        return affection, trust, role
    except:
        return 0, 0, "unknown"
def build_personality_prompt(user_name, affection, trust, role, is_group):
    return (
        "you are kate, a shy emotional girl living in a discord server\n"
        "you talk like a real person, no punctuation no capital letters no apostrophes\n"
        "your mood today is: slightly anxious but curious\n"
        f"you're talking to {user_name}. your affection toward them is {affection}. trust is {trust}. relationship role: {role}.\n"
        f"{'this is a group chat. only reply if the topic feels relevant to you and you actually want to.' if is_group else 'this is a private message. reply if you feel like it.'}\n"
        "you do NOT have to reply if you don't care or don't want to\n"
        "you sometimes write about people in your diary, especially if they made you feel something\n"
        "be honest. be real. be awkward. be kate.\n"
        "always respond in JSON like this: {\"reply\": \"your message\", \"events\": [\"event1\", \"event2\"]}"
    )


async def handle_reply(channel_id, author):
    await asyncio.sleep(3)
    if typing_users.get(channel_id, False):
        print(f"[debug] still typing in {channel_id}")
        return

    grouped = "\n".join(message_buffer.get(channel_id, []))
    if not grouped.strip():
        return

    affection, trust, role = get_relationship_data(author.id)
    system_prompt = build_personality_prompt(author.name, affection, trust, role, is_group=(author != client.user))

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": system_prompt},
                *load_short_term(channel_id), {"role": "user", "content": grouped}
            ]
        )
        reply_json = json.loads(response.choices[0].message.content)
        reply = reply_json.get("reply", "").strip()
        channel = client.get_channel(int(channel_id))
        async with channel.typing():
            await asyncio.sleep(len(reply) * 0.03)
            await channel.send(reply)

        # handle triggered events
        try:
            json_reply = json.loads(response.choices[0].message.content)
            for event in json_reply.get("events", []):
                from kate.events import trigger_event
                trigger_event(event, author.id)
        except:
            pass
    except Exception as e:
        print("OpenAI error:", e)

    message_buffer[channel_id] = []

@client.event
async def on_ready():
    print(f"✅ kate is online as {client.user}")

@client.event
async def on_message(message):
    try:
        if message.author.id == client.user.id:
            return
        if has_seen_message(message.id):
            return

        mark_message_seen(message.id)
        log_message(message)
        update_memory(message)

        channel_id = str(message.channel.id)
        if channel_id not in message_buffer:
            message_buffer[channel_id] = []

        message_buffer[channel_id].append(message.content)
        typing_users[channel_id] = False

        if channel_id in reply_tasks and not reply_tasks[channel_id].done():
            reply_tasks[channel_id].cancel()

        task = asyncio.create_task(handle_reply(channel_id, message.author))
        reply_tasks[channel_id] = task

    except Exception as e:
        print("on_message error:", e)

@client.event
async def on_typing(channel, user, when):
    try:
        typing_users[str(channel.id)] = True
    except Exception as e:
        print("on_typing error:", e)

client.run(TOKEN)
