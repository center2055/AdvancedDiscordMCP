"""Script to find bot messages in channels"""
import asyncio
import os
import discord
from discord.ext import commands

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    channels = [
        (1444062669286932512, "info"),
        (1451648849486549199, "welcome"),
        (1451648853286588449, "rules"),
    ]
    
    for channel_id, name in channels:
        channel = await bot.fetch_channel(channel_id)
        print(f"\n=== {name} channel ({channel_id}) ===")
        async for message in channel.history(limit=20):
            if message.author.bot and message.content:
                print(f"ID: {message.id}")
                print(f"Content: {message.content[:100]}...")
                print("---")
    
    await bot.close()

if __name__ == "__main__":
    asyncio.run(bot.start(DISCORD_TOKEN))

