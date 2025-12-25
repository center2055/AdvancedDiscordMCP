"""Standalone Discord bot runner for Railway deployment."""
import os
import asyncio
import logging
import discord
from discord.ext import commands

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("discord-bot")

# Discord bot setup
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is required")

# Initialize Discord bot with necessary intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Store automation rules (will be loaded from server if needed)
automation_rules = {}

# Event handlers
@bot.event
async def on_ready():
    logger.info(f"Bot logged in as {bot.user.name} (ID: {bot.user.id})")
    logger.info(f"Bot is in {len(bot.guilds)} server(s)")
    for guild in bot.guilds:
        logger.info(f"  - {guild.name} (ID: {guild.id})")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Discord bot error in {event}: {args}, {kwargs}")

@bot.event
async def on_disconnect():
    logger.warning("Discord bot disconnected")

# Copy member join handler
@bot.event
async def on_member_join(member: discord.Member):
    """Handle member join events and execute automation rules."""
    if not bot:
        return
    
    # Check for enabled automation rules with member_join trigger
    for rule_id, rule in server.automation_rules.items():
        if not rule.get("enabled", True):
            continue
        
        if rule.get("trigger_type") != "member_join":
            continue
        
        # Check if rule applies to this server
        server_id = rule.get("server_id")
        if server_id and str(member.guild.id) != str(server_id):
            continue
        
        try:
            action_type = rule.get("action_type")
            action_payload = rule.get("action_payload", {})
            
            if action_type == "send_message":
                channel_id = action_payload.get("channel_id")
                if channel_id:
                    channel = await bot.fetch_channel(int(channel_id))
                    content = action_payload.get("content", "Welcome to the server!")
                    # Replace placeholders
                    content = content.replace("{user}", member.mention)
                    content = content.replace("{username}", member.name)
                    content = content.replace("{server}", member.guild.name)
                    
                    # Send as embed
                    embed = discord.Embed(
                        title="Welcome!",
                        description=content,
                        color=0x5865F2  # Discord blurple
                    )
                    embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
                    await channel.send(embed=embed)
                    logger.info(f"Executed automation rule {rule_id}: sent welcome message")
            
            elif action_type == "assign_role":
                role_id = action_payload.get("role_id")
                if role_id:
                    role = member.guild.get_role(int(role_id))
                    if role and role not in member.roles:
                        await member.add_roles(role, reason=f"Welcome role: {rule.get('name', rule_id)}")
                        logger.info(f"Executed automation rule {rule_id}: assigned role {role.name} to {member.name}")
        
        except Exception as exc:
            logger.error(f"Error executing automation rule {rule_id}: {exc}")

# Copy reaction handlers
@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """Handle reaction add events and execute automation rules for reaction roles."""
    if not bot:
        return
    
    # Ignore bot reactions
    if user.bot:
        return
    
    # Get member from guild
    if not isinstance(reaction.message.channel, discord.TextChannel):
        return
    
    try:
        member = await reaction.message.guild.fetch_member(user.id)
    except:
        return
    
    # Get emoji string (handle both Unicode and custom emojis)
    emoji_str = str(reaction.emoji)
    
    # Check for enabled automation rules with reaction_added trigger
    for rule_id, rule in automation_rules.items():
        if not rule.get("enabled", True):
            continue
        
        if rule.get("trigger_type") != "reaction_added":
            continue
        
        # Check if rule applies to this server
        server_id = rule.get("server_id")
        if server_id and str(reaction.message.guild.id) != str(server_id):
            continue
        
        # Check if emoji matches trigger_value
        trigger_value = rule.get("trigger_value", "")
        if trigger_value and emoji_str != trigger_value:
            continue
        
        # Check if message matches (optional message_id in action_payload)
        action_payload = rule.get("action_payload", {})
        message_id = action_payload.get("message_id")
        if message_id and str(reaction.message.id) != str(message_id):
            continue
        
        try:
            action_type = rule.get("action_type")
            
            if action_type == "assign_role":
                role_id = action_payload.get("role_id")
                if role_id:
                    role = reaction.message.guild.get_role(int(role_id))
                    if role and role not in member.roles:
                        await member.add_roles(role, reason=f"Reaction role: {rule.get('name', rule_id)}")
                        logger.info(f"Executed automation rule {rule_id}: assigned role {role.name} to {member.name}")
            
            elif action_type == "send_message":
                channel_id = action_payload.get("channel_id")
                if channel_id:
                    channel = await bot.fetch_channel(int(channel_id))
                    content = action_payload.get("content", "Reaction received!")
                    content = content.replace("{user}", member.mention)
                    content = content.replace("{username}", member.name)
                    content = content.replace("{emoji}", emoji_str)
                    
                    # Send as embed
                    embed = discord.Embed(
                        title="Reaction Event",
                        description=content,
                        color=0x5865F2  # Discord blurple
                    )
                    embed.set_footer(text=f"Reaction: {emoji_str}")
                    await channel.send(embed=embed)
                    logger.info(f"Executed automation rule {rule_id}: sent message")
            
            elif action_type == "log":
                logger.info(f"Automation rule {rule_id} triggered for reaction {emoji_str} by {member.name} (ID: {member.id})")
        
        except Exception as exc:
            logger.error(f"Error executing automation rule {rule_id}: {exc}")

@bot.event
async def on_reaction_remove(reaction: discord.Reaction, user: discord.User):
    """Handle reaction remove events and execute automation rules (e.g., remove roles)."""
    if not bot:
        return
    
    # Ignore bot reactions
    if user.bot:
        return
    
    # Get member from guild
    if not isinstance(reaction.message.channel, discord.TextChannel):
        return
    
    try:
        member = await reaction.message.guild.fetch_member(user.id)
    except:
        return
    
    # Get emoji string (handle both Unicode and custom emojis)
    emoji_str = str(reaction.emoji)
    
    # Check for enabled automation rules with reaction_added trigger
    for rule_id, rule in automation_rules.items():
        if not rule.get("enabled", True):
            continue
        
        if rule.get("trigger_type") != "reaction_added":
            continue
        
        # Check if rule applies to this server
        server_id = rule.get("server_id")
        if server_id and str(reaction.message.guild.id) != str(server_id):
            continue
        
        # Check if emoji matches trigger_value
        trigger_value = rule.get("trigger_value", "")
        if trigger_value and emoji_str != trigger_value:
            continue
        
        # Check if message matches (optional message_id in action_payload)
        action_payload = rule.get("action_payload", {})
        message_id = action_payload.get("message_id")
        if message_id and str(reaction.message.id) != str(message_id):
            continue
        
        # Check if we should remove role on unreact (default: true for reaction roles)
        remove_on_unreact = action_payload.get("remove_on_unreact", True)
        if not remove_on_unreact:
            continue
        
        try:
            action_type = rule.get("action_type")
            
            if action_type == "assign_role":
                role_id = action_payload.get("role_id")
                if role_id:
                    role = reaction.message.guild.get_role(int(role_id))
                    if role and role in member.roles:
                        await member.remove_roles(role, reason=f"Reaction role removed: {rule.get('name', rule_id)}")
                        logger.info(f"Executed automation rule {rule_id}: removed role {role.name} from {member.name}")
        
        except Exception as exc:
            logger.error(f"Error executing automation rule {rule_id} on reaction remove: {exc}")

# Copy message delete handler
@bot.event
async def on_message_delete(message: discord.Message):
    """Handle message deletion events and log to staff logs."""
    if not bot:
        return
    
    # Ignore DMs
    if not isinstance(message.channel, (discord.TextChannel, discord.Thread)):
        return
    
    # Log to staff logs channel (if it exists)
    try:
        guild = message.guild
        if not guild:
            return
        
        staff_logs_channel = None
        for ch in guild.channels:
            if isinstance(ch, discord.TextChannel) and "staff" in ch.name.lower() and "log" in ch.name.lower():
                staff_logs_channel = ch
                break
        
        if staff_logs_channel:
            message_content = message.content[:500] if message.content else "(No content/embed only)"
            message_author = message.author.mention if message.author else "Unknown"
            message_author_name = message.author.name if message.author else "Unknown"
            
            log_embed = discord.Embed(
                title="🗑️ Message Deleted",
                color=0xe74c3c,
                timestamp=discord.utils.utcnow()
            )
            log_embed.add_field(name="Channel", value=f"#{message.channel.name}", inline=True)
            log_embed.add_field(name="Author", value=f"{message_author} ({message_author_name})", inline=True)
            log_embed.add_field(name="Message ID", value=f"`{message.id}`", inline=True)
            
            if message_content and message_content != "(No content/embed only)":
                log_embed.add_field(
                    name="Content", 
                    value=message_content if len(message_content) <= 1024 else message_content[:1021] + "...", 
                    inline=False
                )
            
            # Try to get jump URL (may not work for deleted messages, but worth trying)
            try:
                jump_url = message.jump_url
                log_embed.add_field(name="Message Link", value=f"[Jump to Message]({jump_url})", inline=False)
            except:
                pass
            
            log_embed.set_footer(text="Deleted via Discord UI or bot command")
            await staff_logs_channel.send(embed=log_embed)
            logger.info(f"Logged message deletion to staff logs: {message.id} in {message.channel.name}")
    except Exception as e:
        logger.warning(f"Failed to log message deletion to staff logs: {e}")

async def main():
    """Main entry point for the bot."""
    try:
        logger.info("Starting Discord bot...")
        await bot.start(DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Shutting down Discord bot...")
        await bot.close()
    except Exception as e:
        logger.error(f"Error running Discord bot: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())

