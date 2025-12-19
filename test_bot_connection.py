"""Test script to verify Discord bot token works."""
import os
import asyncio
import discord

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "your_bot_token_here")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = discord.Client(intents=intents)

@bot.event
async def on_ready():
    print(f"Bot connected successfully!")
    print(f"  Bot name: {bot.user.name}")
    print(f"  Bot ID: {bot.user.id}")
    print(f"  Number of servers: {len(bot.guilds)}")
    print("\nServers the bot is in:")
    for guild in bot.guilds:
        print(f"  - {guild.name}")
        print(f"    Server ID: {guild.id}")
    await bot.close()

@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Error in {event}: {args}")

async def main():
    try:
        print("Attempting to connect to Discord...")
        await bot.start(DISCORD_TOKEN)
    except discord.LoginFailure:
        print("Invalid bot token!")
    except Exception as e:
        print(f"Connection failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
