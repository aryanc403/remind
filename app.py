import os

import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN_REMIND')
GUILD = os.getenv('GUILD_ID')
CHANNEL = int(os.getenv('CHANNEL_ID'))

client = discord.Client()

@client.event
async def on_ready():
    print(type(CHANNEL))
    await client.get_channel(CHANNEL).send("On ready called.")
client.run(TOKEN)