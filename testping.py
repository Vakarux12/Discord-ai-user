import discord
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_USER_TOKEN")

client = discord.Client()

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

client.run(TOKEN)
