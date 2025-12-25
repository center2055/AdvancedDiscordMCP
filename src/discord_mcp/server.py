import os
import io
import re
import json
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional
from functools import wraps
from collections import Counter

import aiohttp
import discord
from discord.ext import commands
from mcp.server import Server
from mcp.types import Tool, TextContent, EmptyResult
from mcp.server.stdio import stdio_server
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("discord-mcp-server")

# Discord bot setup
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable is required")

# Initialize Discord bot with necessary intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize MCP server
app = Server("discord-server")

# Store Discord client reference
discord_client = None
scheduled_tasks: Dict[str, Dict[str, Any]] = {}
scheduled_task_counter = 0
message_templates: Dict[str, str] = {}
role_templates: Dict[str, Dict[str, Any]] = {}
automation_rules: Dict[str, Dict[str, Any]] = {}
automation_rule_counter = 0
metrics_store: Dict[str, List[Dict[str, Any]]] = {}

@bot.event
async def on_ready():
    global discord_client
    discord_client = bot
    logger.info(f"Logged in as {bot.user.name}")

@bot.event
async def on_error(event, *args, **kwargs):
    logger.error(f"Discord bot error in {event}: {args}, {kwargs}")

@bot.event
async def on_disconnect():
    global discord_client
    discord_client = None
    logger.warning("Discord bot disconnected")

@bot.event
async def on_member_join(member: discord.Member):
    """Handle member join events and execute automation rules."""
    if not discord_client:
        return
    
    # Check for enabled automation rules with member_join trigger
    for rule_id, rule in automation_rules.items():
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
                    channel = await discord_client.fetch_channel(int(channel_id))
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
                    if role:
                        await member.add_roles(role, reason=f"Automation rule: {rule.get('name', rule_id)}")
                        logger.info(f"Executed automation rule {rule_id}: assigned role")
            
            elif action_type == "log":
                logger.info(f"Automation rule {rule_id} triggered for member {member.name} (ID: {member.id})")
        
        except Exception as exc:
            logger.error(f"Error executing automation rule {rule_id}: {exc}")

@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """Handle reaction add events and execute automation rules for reaction roles."""
    if not discord_client:
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
                    channel = await discord_client.fetch_channel(int(channel_id))
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
    if not discord_client:
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
    # Note: We use the same trigger_type but check action_payload for remove_on_unreact
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

@bot.event
async def on_message_delete(message: discord.Message):
    """Handle message deletion events and log to staff logs."""
    if not discord_client:
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

# Helper function to ensure Discord client is ready
def require_discord_client(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        if not discord_client:
            raise RuntimeError("Discord client not ready")
        return await func(*args, **kwargs)
    return wrapper


async def fetch_avatar_bytes(avatar_url: Optional[str]) -> Optional[bytes]:
    if not avatar_url:
        return None

    async with aiohttp.ClientSession() as session:
        async with session.get(avatar_url) as response:
            if response.status != 200:
                raise ValueError(f"Failed to fetch avatar URL (status {response.status})")
            return await response.read()


def parse_timestamp(value: Optional[Any]) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)

    if isinstance(value, str) and value.strip().isdigit():
        return datetime.fromtimestamp(int(value), tz=timezone.utc)

    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        parsed = datetime.fromisoformat(cleaned)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    raise ValueError("Invalid timestamp format")


def next_scheduled_task_id() -> str:
    global scheduled_task_counter
    scheduled_task_counter += 1
    return str(scheduled_task_counter)


def next_automation_rule_id() -> str:
    global automation_rule_counter
    automation_rule_counter += 1
    return str(automation_rule_counter)


async def run_scheduled_task(
    task_id: str,
    run_at: datetime,
    task_callable: Callable[[], Awaitable[Any]]
) -> None:
    now = datetime.now(timezone.utc)
    delay = max(0, (run_at - now).total_seconds())
    if delay:
        await asyncio.sleep(delay)

    task_entry = scheduled_tasks.get(task_id)
    if not task_entry:
        return

    task_entry["status"] = "running"
    try:
        result = await task_callable()
        task_entry["status"] = "completed"
        if result:
            if isinstance(result, list) and hasattr(result[0], "text"):
                task_entry["result"] = result[0].text
            else:
                task_entry["result"] = str(result)
    except Exception as exc:
        task_entry["status"] = "failed"
        task_entry["error"] = str(exc)
        logger.exception("Scheduled task failed: %s", task_id)

def parse_verification_level(value: Optional[str]) -> Optional[discord.VerificationLevel]:
    if value is None:
        return None
    if isinstance(value, int) or (isinstance(value, str) and value.isdigit()):
        return discord.VerificationLevel(int(value))

    normalized = value.strip().lower()
    mapping = {
        "none": discord.VerificationLevel.none,
        "low": discord.VerificationLevel.low,
        "medium": discord.VerificationLevel.medium,
        "high": discord.VerificationLevel.high,
        "very_high": discord.VerificationLevel.highest,
        "highest": discord.VerificationLevel.highest
    }
    if normalized in mapping:
        return mapping[normalized]
    raise ValueError(f"Unknown verification level: {value}")


def parse_notification_level(value: Optional[str]) -> Optional[discord.NotificationLevel]:
    if value is None:
        return None

    normalized = value.strip().lower()
    mapping = {
        "all_messages": discord.NotificationLevel.all_messages,
        "only_mentions": discord.NotificationLevel.only_mentions,
        "mentions_only": discord.NotificationLevel.only_mentions
    }
    if normalized in mapping:
        return mapping[normalized]
    raise ValueError(f"Unknown default notification level: {value}")


def parse_content_filter(value: Optional[str]) -> Optional[discord.ContentFilter]:
    if value is None:
        return None

    normalized = value.strip().lower()
    mapping = {
        "disabled": discord.ContentFilter.disabled,
        "no_role": discord.ContentFilter.no_role,
        "members_without_roles": discord.ContentFilter.no_role,
        "all_members": discord.ContentFilter.all_members
    }
    if normalized in mapping:
        return mapping[normalized]
    raise ValueError(f"Unknown explicit content filter: {value}")


def parse_locale(value: Optional[str]) -> Optional[discord.Locale]:
    if value is None:
        return None

    normalized = value.strip().lower()
    for locale in discord.Locale:
        if locale.name.lower() == normalized or locale.value.lower() == normalized:
            return locale
    raise ValueError(f"Unknown preferred locale: {value}")


def parse_automod_trigger_type(value: str) -> discord.AutoModRuleTriggerType:
    normalized = value.strip().lower()
    mapping = {
        "keyword": discord.AutoModRuleTriggerType.keyword,
        "keyword_preset": discord.AutoModRuleTriggerType.keyword_preset,
        "mention_spam": discord.AutoModRuleTriggerType.mention_spam,
        "spam": discord.AutoModRuleTriggerType.spam
    }
    if normalized in mapping:
        return mapping[normalized]
    raise ValueError(f"Unknown automod trigger type: {value}")


def parse_automod_presets(values: Optional[List[str]]) -> Optional[discord.AutoModPresets]:
    if not values:
        return None

    presets = discord.AutoModPresets.none
    for value in values:
        key = value.strip().lower()
        if key == "profanity":
            presets |= discord.AutoModPresets.profanity
        elif key == "sexual_content":
            presets |= discord.AutoModPresets.sexual_content
        elif key == "slurs":
            presets |= discord.AutoModPresets.slurs
        else:
            raise ValueError(f"Unknown automod preset: {value}")
    return presets


async def build_automod_actions(
    alert_channel_id: Optional[str],
    timeout_minutes: Optional[int]
) -> List[discord.AutoModAction]:
    actions = [discord.AutoModAction(type=discord.AutoModActionType.block_message)]

    if alert_channel_id:
        channel = await discord_client.fetch_channel(int(alert_channel_id))
        metadata = discord.AutoModActionMetadata(channel=channel)
        actions.append(
            discord.AutoModAction(
                type=discord.AutoModActionType.send_alert_message,
                metadata=metadata
            )
        )

    if timeout_minutes and timeout_minutes > 0:
        metadata = discord.AutoModActionMetadata(
            duration=timedelta(minutes=timeout_minutes)
        )
        actions.append(
            discord.AutoModAction(
                type=discord.AutoModActionType.timeout,
                metadata=metadata
            )
        )

    return actions

@app.list_tools()
async def list_tools() -> List[Tool]:
    """List available Discord tools."""
    return [
        # Server Information Tools
        Tool(
            name="list_servers",
            description="List all Discord servers (guilds) the bot is a member of",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="get_server_info",
            description="Get information about a Discord server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server (guild) ID"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="list_members",
            description="Get a list of members in a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server (guild) ID"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of members to fetch",
                        "minimum": 1,
                        "maximum": 1000
                    }
                },
                "required": ["server_id"]
            }
        ),

        # Server Settings Management
        Tool(
            name="get_server_settings",
            description="Retrieve current server configuration settings",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server (guild) ID"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="modify_server_settings",
            description="Modify server settings like name, description, icon, and verification",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server (guild) ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "New server name"
                    },
                    "description": {
                        "type": "string",
                        "description": "New server description"
                    },
                    "icon_url": {
                        "type": "string",
                        "description": "Icon URL"
                    },
                    "banner_url": {
                        "type": "string",
                        "description": "Banner URL"
                    },
                    "verification_level": {
                        "type": "string",
                        "description": "Verification level (none, low, medium, high, very_high)"
                    },
                    "default_notification_level": {
                        "type": "string",
                        "description": "Default notifications (all_messages, only_mentions)"
                    },
                    "afk_timeout": {
                        "type": "number",
                        "description": "AFK timeout in seconds"
                    },
                    "afk_channel_id": {
                        "type": "string",
                        "description": "AFK channel ID"
                    },
                    "system_channel_id": {
                        "type": "string",
                        "description": "System channel ID"
                    },
                    "explicit_content_filter": {
                        "type": "string",
                        "description": "Explicit content filter (disabled, no_role, all_members)"
                    },
                    "preferred_locale": {
                        "type": "string",
                        "description": "Preferred locale (e.g., en-US)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the change"
                    }
                },
                "required": ["server_id"]
            }
        ),

        # Invite Management
        Tool(
            name="create_invite",
            description="Create a channel invite",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to create invite for"
                    },
                    "max_uses": {
                        "type": "number",
                        "description": "Maximum uses for the invite (0 for unlimited)"
                    },
                    "max_age_seconds": {
                        "type": "number",
                        "description": "Invite expiration time in seconds (0 for never)"
                    },
                    "temporary": {
                        "type": "boolean",
                        "description": "Grant temporary membership"
                    },
                    "unique": {
                        "type": "boolean",
                        "description": "Force a unique invite code"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the invite"
                    }
                },
                "required": ["channel_id"]
            }
        ),
        Tool(
            name="list_invites",
            description="List all active invites in a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server (guild) ID"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="delete_invite",
            description="Delete an invite by code",
            inputSchema={
                "type": "object",
                "properties": {
                    "invite_code": {
                        "type": "string",
                        "description": "Invite code to revoke"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for deletion"
                    }
                },
                "required": ["invite_code"]
            }
        ),
        Tool(
            name="get_invite_info",
            description="Get details about an invite",
            inputSchema={
                "type": "object",
                "properties": {
                    "invite_code": {
                        "type": "string",
                        "description": "Invite code to fetch"
                    }
                },
                "required": ["invite_code"]
            }
        ),

        # Auto-Moderation & Rules
        Tool(
            name="create_automod_rule",
            description="Create an auto-moderation rule",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server (guild) ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Rule name"
                    },
                    "trigger_type": {
                        "type": "string",
                        "description": "Trigger type (keyword, keyword_preset, mention_spam, spam)"
                    },
                    "keyword_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keyword filter list"
                    },
                    "regex_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Regex patterns"
                    },
                    "allow_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Allow list for keywords"
                    },
                    "presets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keyword presets (profanity, sexual_content, slurs)"
                    },
                    "mention_total_limit": {
                        "type": "number",
                        "description": "Mention limit for mention_spam"
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable the rule"
                    },
                    "alert_channel_id": {
                        "type": "string",
                        "description": "Channel ID for alert messages"
                    },
                    "timeout_minutes": {
                        "type": "number",
                        "description": "Timeout duration in minutes"
                    },
                    "exempt_role_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Role IDs exempt from the rule"
                    },
                    "exempt_channel_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Channel IDs exempt from the rule"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for rule creation"
                    }
                },
                "required": ["server_id", "name", "trigger_type"]
            }
        ),
        Tool(
            name="list_automod_rules",
            description="List all auto-moderation rules in a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server (guild) ID"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="modify_automod_rule",
            description="Modify an existing auto-moderation rule",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server (guild) ID"
                    },
                    "rule_id": {
                        "type": "string",
                        "description": "Auto-mod rule ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Rule name"
                    },
                    "trigger_type": {
                        "type": "string",
                        "description": "Trigger type (keyword, keyword_preset, mention_spam, spam)"
                    },
                    "keyword_filter": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keyword filter list"
                    },
                    "regex_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Regex patterns"
                    },
                    "allow_list": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Allow list for keywords"
                    },
                    "presets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Keyword presets (profanity, sexual_content, slurs)"
                    },
                    "mention_total_limit": {
                        "type": "number",
                        "description": "Mention limit for mention_spam"
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Enable the rule"
                    },
                    "alert_channel_id": {
                        "type": "string",
                        "description": "Channel ID for alert messages"
                    },
                    "timeout_minutes": {
                        "type": "number",
                        "description": "Timeout duration in minutes"
                    },
                    "exempt_role_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Role IDs exempt from the rule"
                    },
                    "exempt_channel_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Channel IDs exempt from the rule"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for rule modification"
                    }
                },
                "required": ["server_id", "rule_id"]
            }
        ),
        Tool(
            name="delete_automod_rule",
            description="Delete an auto-moderation rule",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server (guild) ID"
                    },
                    "rule_id": {
                        "type": "string",
                        "description": "Auto-mod rule ID"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for deletion"
                    }
                },
                "required": ["server_id", "rule_id"]
            }
        ),

        # Thread Management
        Tool(
            name="create_thread",
            description="Create a thread in a channel or from a message",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to create thread in"
                    },
                    "name": {
                        "type": "string",
                        "description": "Thread name"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Optional message ID to create a thread from"
                    },
                    "auto_archive_duration": {
                        "type": "number",
                        "description": "Auto-archive duration in minutes"
                    },
                    "thread_type": {
                        "type": "string",
                        "description": "Thread type (public or private)"
                    },
                    "invitable": {
                        "type": "boolean",
                        "description": "Allow non-moderators to invite users (private threads)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for creation"
                    }
                },
                "required": ["channel_id", "name"]
            }
        ),
        Tool(
            name="list_threads",
            description="List active or archived threads in a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to list threads from"
                    },
                    "archived": {
                        "type": "boolean",
                        "description": "List archived threads instead of active"
                    },
                    "include_private": {
                        "type": "boolean",
                        "description": "Include private archived threads"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Maximum number of threads to fetch"
                    }
                },
                "required": ["channel_id"]
            }
        ),
        Tool(
            name="archive_thread",
            description="Archive a thread",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {
                        "type": "string",
                        "description": "Thread ID to archive"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for archiving"
                    }
                },
                "required": ["thread_id"]
            }
        ),
        Tool(
            name="unarchive_thread",
            description="Unarchive a thread",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {
                        "type": "string",
                        "description": "Thread ID to unarchive"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for unarchiving"
                    }
                },
                "required": ["thread_id"]
            }
        ),
        Tool(
            name="delete_thread",
            description="Delete a thread",
            inputSchema={
                "type": "object",
                "properties": {
                    "thread_id": {
                        "type": "string",
                        "description": "Thread ID to delete"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for deletion"
                    }
                },
                "required": ["thread_id"]
            }
        ),

        # Category Management
        Tool(
            name="create_category",
            description="Create a channel category",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Category name"
                    },
                    "position": {
                        "type": "number",
                        "description": "Category position"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for creation"
                    }
                },
                "required": ["server_id", "name"]
            }
        ),
        Tool(
            name="modify_category",
            description="Modify a category name, position, or permissions",
            inputSchema={
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "string",
                        "description": "Category ID to modify"
                    },
                    "name": {
                        "type": "string",
                        "description": "New category name"
                    },
                    "position": {
                        "type": "number",
                        "description": "New category position"
                    },
                    "target_type": {
                        "type": "string",
                        "enum": ["role", "member"],
                        "description": "Permission target type"
                    },
                    "target_id": {
                        "type": "string",
                        "description": "Role or member ID for permission update"
                    },
                    "allow_permissions": {
                        "type": "string",
                        "description": "Comma-separated permissions to allow"
                    },
                    "deny_permissions": {
                        "type": "string",
                        "description": "Comma-separated permissions to deny"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for modification"
                    }
                },
                "required": ["category_id"]
            }
        ),
        Tool(
            name="delete_category",
            description="Delete a category, optionally moving channels",
            inputSchema={
                "type": "object",
                "properties": {
                    "category_id": {
                        "type": "string",
                        "description": "Category ID to delete"
                    },
                    "move_channels_to": {
                        "type": "string",
                        "description": "Optional category ID to move channels into"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for deletion"
                    }
                },
                "required": ["category_id"]
            }
        ),

        # Emoji & Sticker Management
        Tool(
            name="create_emoji",
            description="Create a custom emoji in a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Emoji name"
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Image URL for the emoji"
                    },
                    "roles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Role IDs allowed to use the emoji"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for creation"
                    }
                },
                "required": ["server_id", "name", "image_url"]
            }
        ),
        Tool(
            name="list_emojis",
            description="List all custom emojis in a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="delete_emoji",
            description="Delete a custom emoji",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "emoji_id": {
                        "type": "string",
                        "description": "Emoji ID to delete"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for deletion"
                    }
                },
                "required": ["server_id", "emoji_id"]
            }
        ),
        Tool(
            name="create_sticker",
            description="Create a custom sticker in a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Sticker name"
                    },
                    "description": {
                        "type": "string",
                        "description": "Sticker description"
                    },
                    "emoji": {
                        "type": "string",
                        "description": "Emoji associated with the sticker"
                    },
                    "image_url": {
                        "type": "string",
                        "description": "Image URL for the sticker"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for creation"
                    }
                },
                "required": ["server_id", "name", "description", "emoji", "image_url"]
            }
        ),
        Tool(
            name="list_stickers",
            description="List all custom stickers in a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="delete_sticker",
            description="Delete a custom sticker",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "sticker_id": {
                        "type": "string",
                        "description": "Sticker ID to delete"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for deletion"
                    }
                },
                "required": ["server_id", "sticker_id"]
            }
        ),

        # Role Management Tools
        Tool(
            name="add_role",
            description="Add a role to a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User to add role to"
                    },
                    "role_id": {
                        "type": "string",
                        "description": "Role ID to add"
                    }
                },
                "required": ["server_id", "user_id", "role_id"]
            }
        ),
        Tool(
            name="remove_role",
            description="Remove a role from a user",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User to remove role from"
                    },
                    "role_id": {
                        "type": "string",
                        "description": "Role ID to remove"
                    }
                },
                "required": ["server_id", "user_id", "role_id"]
            }
        ),

        # Channel Management Tools
        Tool(
            name="create_text_channel",
            description="Create a new text channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Channel name"
                    },
                    "category_id": {
                        "type": "string",
                        "description": "Optional category ID to place channel in"
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional channel topic"
                    }
                },
                "required": ["server_id", "name"]
            }
        ),
        Tool(
            name="delete_channel",
            description="Delete a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "ID of channel to delete"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for deletion"
                    }
                },
                "required": ["channel_id"]
            }
        ),

        # Message Reaction Tools
        Tool(
            name="add_reaction",
            description="Add a reaction to a message",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel containing the message"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Message to react to"
                    },
                    "emoji": {
                        "type": "string",
                        "description": "Emoji to react with (Unicode or custom emoji ID)"
                    }
                },
                "required": ["channel_id", "message_id", "emoji"]
            }
        ),
        Tool(
            name="add_multiple_reactions",
            description="Add multiple reactions to a message",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel containing the message"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Message to react to"
                    },
                    "emojis": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "description": "Emoji to react with (Unicode or custom emoji ID)"
                        },
                        "description": "List of emojis to add as reactions"
                    }
                },
                "required": ["channel_id", "message_id", "emojis"]
            }
        ),
        Tool(
            name="remove_reaction",
            description="Remove a reaction from a message",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel containing the message"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Message to remove reaction from"
                    },
                    "emoji": {
                        "type": "string",
                        "description": "Emoji to remove (Unicode or custom emoji ID)"
                    }
                },
                "required": ["channel_id", "message_id", "emoji"]
            }
        ),
        Tool(
            name="send_message",
            description="Send a message to a specific channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Discord channel ID"
                    },
                    "content": {
                        "type": "string",
                        "description": "Message content"
                    },
                    "use_embed": {
                        "type": "boolean",
                        "description": "Send message as embed (default: false)"
                    },
                    "embed_title": {
                        "type": "string",
                        "description": "Embed title (required if use_embed is true)"
                    },
                    "embed_color": {
                        "type": "string",
                        "description": "Embed color in hex format (e.g., 0x5865F2)"
                    }
                },
                "required": ["channel_id", "content"]
            }
        ),
        Tool(
            name="read_messages",
            description="Read recent messages from a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Discord channel ID"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Number of messages to fetch (max 100)",
                        "minimum": 1,
                        "maximum": 100
                    }
                },
                "required": ["channel_id"]
            }
        ),
        Tool(
            name="get_user_info",
            description="Get information about a Discord user",
            inputSchema={
                "type": "object",
                "properties": {
                    "user_id": {
                        "type": "string",
                        "description": "Discord user ID"
                    }
                },
                "required": ["user_id"]
            }
        ),
        Tool(
            name="moderate_message",
            description="Delete a message and optionally timeout the user",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID containing the message"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "ID of message to moderate"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for moderation"
                    },
                    "timeout_minutes": {
                        "type": "number",
                        "description": "Optional timeout duration in minutes",
                        "minimum": 0,
                        "maximum": 40320  # Max 4 weeks
                    }
                },
                "required": ["channel_id", "message_id", "reason"]
            }
        ),

        # Permission Management Tools
        Tool(
            name="check_bot_permissions",
            description="Check what permissions the bot has in a channel or server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "channel_id": {
                        "type": "string",
                        "description": "Optional channel ID to check channel-specific permissions"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="check_member_permissions",
            description="Check what permissions a member has in a channel or server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID to check permissions for"
                    },
                    "channel_id": {
                        "type": "string",
                        "description": "Optional channel ID to check channel-specific permissions"
                    }
                },
                "required": ["server_id", "user_id"]
            }
        ),
        Tool(
            name="configure_channel_permissions",
            description="Configure permissions for a role or member in a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to configure permissions for"
                    },
                    "target_type": {
                        "type": "string",
                        "enum": ["role", "member"],
                        "description": "Whether to configure permissions for a role or member"
                    },
                    "target_id": {
                        "type": "string",
                        "description": "Role ID or member ID"
                    },
                    "allow_permissions": {
                        "type": "string",
                        "description": "Comma-separated list of permissions to allow (e.g., 'send_messages,read_messages')"
                    },
                    "deny_permissions": {
                        "type": "string",
                        "description": "Comma-separated list of permissions to deny"
                    }
                },
                "required": ["channel_id", "target_type", "target_id"]
            }
        ),
        Tool(
            name="list_discord_permissions",
            description="List all available Discord permissions with descriptions",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),

        # Webhook Management Tools
        Tool(
            name="create_webhook",
            description="Create a new webhook in a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to create webhook in"
                    },
                    "name": {
                        "type": "string",
                        "description": "Webhook name"
                    },
                    "avatar_url": {
                        "type": "string",
                        "description": "Optional avatar URL for the webhook"
                    }
                },
                "required": ["channel_id", "name"]
            }
        ),
        Tool(
            name="list_webhooks",
            description="List all webhooks in a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to list webhooks from"
                    }
                },
                "required": ["channel_id"]
            }
        ),
        Tool(
            name="send_webhook_message",
            description="Send a message via webhook",
            inputSchema={
                "type": "object",
                "properties": {
                    "webhook_url": {
                        "type": "string",
                        "description": "Webhook URL"
                    },
                    "content": {
                        "type": "string",
                        "description": "Message content"
                    },
                    "username": {
                        "type": "string",
                        "description": "Optional username override"
                    },
                    "avatar_url": {
                        "type": "string",
                        "description": "Optional avatar URL override"
                    }
                },
                "required": ["webhook_url", "content"]
            }
        ),
        Tool(
            name="modify_webhook",
            description="Modify an existing webhook",
            inputSchema={
                "type": "object",
                "properties": {
                    "webhook_id": {
                        "type": "string",
                        "description": "Webhook ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "New webhook name"
                    },
                    "avatar_url": {
                        "type": "string",
                        "description": "New avatar URL"
                    },
                    "channel_id": {
                        "type": "string",
                        "description": "New channel ID to move webhook to"
                    }
                },
                "required": ["webhook_id"]
            }
        ),
        Tool(
            name="delete_webhook",
            description="Delete a webhook",
            inputSchema={
                "type": "object",
                "properties": {
                    "webhook_id": {
                        "type": "string",
                        "description": "Webhook ID to delete"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for deletion"
                    }
                },
                "required": ["webhook_id"]
            }
        ),

        # Advanced Role Management
        Tool(
            name="create_role",
            description="Create a new role in a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Role name"
                    },
                    "permissions": {
                        "type": "string",
                        "description": "Comma-separated list of permissions to grant"
                    },
                    "color": {
                        "type": "string",
                        "description": "Hex color code (e.g., '#FF0000')"
                    },
                    "hoist": {
                        "type": "boolean",
                        "description": "Whether to display role members separately"
                    },
                    "mentionable": {
                        "type": "boolean",
                        "description": "Whether the role is mentionable"
                    }
                },
                "required": ["server_id", "name"]
            }
        ),
        Tool(
            name="delete_role",
            description="Delete a role from a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "role_id": {
                        "type": "string",
                        "description": "Role ID to delete"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for deletion"
                    }
                },
                "required": ["server_id", "role_id"]
            }
        ),
        Tool(
            name="modify_role",
            description="Modify role properties (name, color, permissions, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "role_id": {
                        "type": "string",
                        "description": "Role ID to modify"
                    },
                    "name": {
                        "type": "string",
                        "description": "New role name"
                    },
                    "permissions": {
                        "type": "string",
                        "description": "Comma-separated list of permissions"
                    },
                    "color": {
                        "type": "string",
                        "description": "Hex color code"
                    },
                    "hoist": {
                        "type": "boolean",
                        "description": "Whether to display role members separately"
                    },
                    "mentionable": {
                        "type": "boolean",
                        "description": "Whether the role is mentionable"
                    },
                    "position": {
                        "type": "number",
                        "description": "Role position (higher = higher in hierarchy, 0 = lowest)"
                    }
                },
                "required": ["server_id", "role_id"]
            }
        ),
        Tool(
            name="list_roles",
            description="List all roles in a server with details",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="get_role_info",
            description="Get detailed information about a specific role",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "role_id": {
                        "type": "string",
                        "description": "Role ID"
                    }
                },
                "required": ["server_id", "role_id"]
            }
        ),
        Tool(
            name="set_role_hierarchy",
            description="Set the role hierarchy by specifying role order (from highest to lowest). Higher positions = higher in hierarchy. You can provide either role IDs or role names.",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "role_ids": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Array of role IDs in desired order (first = highest, last = lowest). Only include roles you want to reorder."
                    },
                    "role_names": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        },
                        "description": "Array of role names in desired order (first = highest, last = lowest). Only include roles you want to reorder. If provided, role_ids will be ignored."
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for hierarchy change"
                    }
                },
                "required": ["server_id"]
            }
        ),

        # Advanced Channel Management
        Tool(
            name="list_channels",
            description="List all channels in a server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "channel_type": {
                        "type": "string",
                        "enum": ["text", "voice", "category", "all"],
                        "description": "Filter by channel type"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="get_channel_info",
            description="Get detailed information about a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID"
                    }
                },
                "required": ["channel_id"]
            }
        ),
        Tool(
            name="modify_channel",
            description="Modify channel properties (name, topic, permissions, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to modify"
                    },
                    "name": {
                        "type": "string",
                        "description": "New channel name"
                    },
                    "topic": {
                        "type": "string",
                        "description": "New channel topic"
                    },
                    "nsfw": {
                        "type": "boolean",
                        "description": "Whether channel is NSFW"
                    },
                    "slowmode_delay": {
                        "type": "number",
                        "description": "Slowmode delay in seconds (0-21600)",
                        "minimum": 0,
                        "maximum": 21600
                    },
                    "category_id": {
                        "type": "string",
                        "description": "Category ID to move channel into (or null to remove from category)"
                    },
                    "position": {
                        "type": "number",
                        "description": "Channel position (0 = top, higher numbers = lower)"
                    }
                },
                "required": ["channel_id"]
            }
        ),
        Tool(
            name="create_voice_channel",
            description="Create a new voice channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "name": {
                        "type": "string",
                        "description": "Channel name"
                    },
                    "category_id": {
                        "type": "string",
                        "description": "Optional category ID"
                    },
                    "bitrate": {
                        "type": "number",
                        "description": "Bitrate in bits per second (8000-96000)"
                    },
                    "user_limit": {
                        "type": "number",
                        "description": "Maximum number of users (0 for unlimited)"
                    }
                },
                "required": ["server_id", "name"]
            }
        ),

        # Advanced Message Features
        Tool(
            name="edit_message",
            description="Edit an existing message",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID containing the message"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Message ID to edit"
                    },
                    "content": {
                        "type": "string",
                        "description": "New message content"
                    }
                },
                "required": ["channel_id", "message_id", "content"]
            }
        ),
        Tool(
            name="pin_message",
            description="Pin a message in a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Message ID to pin"
                    }
                },
                "required": ["channel_id", "message_id"]
            }
        ),
        Tool(
            name="unpin_message",
            description="Unpin a message from a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Message ID to unpin"
                    }
                },
                "required": ["channel_id", "message_id"]
            }
        ),
        Tool(
            name="get_message",
            description="Get a specific message by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID"
                    },
                    "message_id": {
                        "type": "string",
                        "description": "Message ID"
                    }
                },
                "required": ["channel_id", "message_id"]
            }
        ),
        Tool(
            name="bulk_delete_messages",
            description="Delete multiple messages at once (2-100 messages)",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID"
                    },
                    "message_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of message IDs to delete (2-100 messages)",
                        "minItems": 2,
                        "maxItems": 100
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for bulk deletion"
                    }
                },
                "required": ["channel_id", "message_ids"]
            }
        ),

        # User Management Tools
        Tool(
            name="ban_user",
            description="Ban a user from the server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID to ban"
                    },
                    "delete_message_days": {
                        "type": "number",
                        "description": "Number of days of messages to delete (0-7)",
                        "minimum": 0,
                        "maximum": 7
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for ban"
                    }
                },
                "required": ["server_id", "user_id"]
            }
        ),
        Tool(
            name="unban_user",
            description="Unban a user from the server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID to unban"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for unban"
                    }
                },
                "required": ["server_id", "user_id"]
            }
        ),
        Tool(
            name="kick_user",
            description="Kick a user from the server",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID to kick"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for kick"
                    }
                },
                "required": ["server_id", "user_id"]
            }
        ),
        Tool(
            name="modify_member",
            description="Modify member properties (nickname, timeout, etc.)",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID"
                    },
                    "nickname": {
                        "type": "string",
                        "description": "New nickname (or empty string to remove)"
                    },
                    "timeout_minutes": {
                        "type": "number",
                        "description": "Timeout duration in minutes (0 to remove timeout)",
                        "minimum": 0,
                        "maximum": 40320
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for modification"
                    }
                },
                "required": ["server_id", "user_id"]
            }
        ),
        Tool(
            name="get_member_info",
            description="Get detailed information about a server member",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "user_id": {
                        "type": "string",
                        "description": "User ID"
                    }
                },
                "required": ["server_id", "user_id"]
            }
        ),

        # Bulk Operations
        Tool(
            name="bulk_add_roles",
            description="Add a role to multiple users",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "role_id": {
                        "type": "string",
                        "description": "Role ID to add"
                    },
                    "user_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "User IDs to receive the role"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the bulk role assignment"
                    }
                },
                "required": ["server_id", "role_id", "user_ids"]
            }
        ),
        Tool(
            name="bulk_modify_members",
            description="Modify multiple members (nickname, timeout) in one call",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "updates": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "user_id": {
                                    "type": "string",
                                    "description": "User ID"
                                },
                                "nickname": {
                                    "type": "string",
                                    "description": "New nickname (empty to clear)"
                                },
                                "timeout_minutes": {
                                    "type": "number",
                                    "description": "Timeout duration in minutes (0 to remove timeout)"
                                }
                            },
                            "required": ["user_id"]
                        },
                        "description": "List of member updates"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Reason for the updates"
                    }
                },
                "required": ["server_id", "updates"]
            }
        ),

        # Smart Search & Filtering
        Tool(
            name="search_messages",
            description="Search messages by content, author, or date range within channels",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to search"
                    },
                    "channel_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Multiple channel IDs to search"
                    },
                    "contains": {
                        "type": "string",
                        "description": "Content substring to search for"
                    },
                    "author_id": {
                        "type": "string",
                        "description": "Author user ID"
                    },
                    "after": {
                        "type": "string",
                        "description": "ISO timestamp or epoch seconds for lower bound"
                    },
                    "before": {
                        "type": "string",
                        "description": "ISO timestamp or epoch seconds for upper bound"
                    },
                    "has_reactions": {
                        "type": "boolean",
                        "description": "Only return messages with reactions"
                    },
                    "limit_per_channel": {
                        "type": "number",
                        "description": "Max messages to scan per channel"
                    },
                    "max_results": {
                        "type": "number",
                        "description": "Max total results to return"
                    }
                }
            }
        ),
        Tool(
            name="find_members_by_criteria",
            description="Find members by role, join date, name, or bot status",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "role_ids_any": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Match members with any of these roles"
                    },
                    "role_ids_all": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Match members with all of these roles"
                    },
                    "joined_after": {
                        "type": "string",
                        "description": "Joined after ISO timestamp or epoch seconds"
                    },
                    "joined_before": {
                        "type": "string",
                        "description": "Joined before ISO timestamp or epoch seconds"
                    },
                    "nickname_contains": {
                        "type": "string",
                        "description": "Nickname contains substring"
                    },
                    "name_contains": {
                        "type": "string",
                        "description": "Username contains substring"
                    },
                    "is_bot": {
                        "type": "boolean",
                        "description": "Filter by bot status"
                    },
                    "scan_limit": {
                        "type": "number",
                        "description": "Max members to scan"
                    },
                    "max_results": {
                        "type": "number",
                        "description": "Max members to return"
                    }
                },
                "required": ["server_id"]
            }
        ),

        # Scheduled Tasks
        Tool(
            name="schedule_task",
            description="Schedule a supported task to run later",
            inputSchema={
                "type": "object",
                "properties": {
                    "task_type": {
                        "type": "string",
                        "description": "Task type (send_message, bulk_add_roles, bulk_modify_members)"
                    },
                    "task_payload": {
                        "type": "object",
                        "description": "Arguments for the task type"
                    },
                    "run_at": {
                        "type": "string",
                        "description": "ISO timestamp or epoch seconds"
                    },
                    "delay_seconds": {
                        "type": "number",
                        "description": "Delay in seconds"
                    }
                },
                "required": ["task_type", "task_payload"]
            }
        ),
        Tool(
            name="send_scheduled_message",
            description="Schedule a message to be sent later",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID"
                    },
                    "content": {
                        "type": "string",
                        "description": "Message content"
                    },
                    "run_at": {
                        "type": "string",
                        "description": "ISO timestamp or epoch seconds"
                    },
                    "delay_seconds": {
                        "type": "number",
                        "description": "Delay in seconds"
                    }
                },
                "required": ["channel_id", "content"]
            }
        ),

        # Analytics
        Tool(
            name="generate_server_analytics",
            description="Generate basic server analytics",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "member_sample_limit": {
                        "type": "number",
                        "description": "Members to sample for bot/human counts"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="generate_channel_analytics",
            description="Generate basic analytics for a channel",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Messages to scan"
                    },
                    "after": {
                        "type": "string",
                        "description": "ISO timestamp or epoch seconds"
                    },
                    "before": {
                        "type": "string",
                        "description": "ISO timestamp or epoch seconds"
                    }
                },
                "required": ["channel_id"]
            }
        ),

        # Automation Rules
        Tool(
            name="create_automation_rule",
            description="Create an automation rule definition",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID (optional)"
                    },
                    "name": {
                        "type": "string",
                        "description": "Rule name"
                    },
                    "trigger_type": {
                        "type": "string",
                        "description": "Trigger type (member_join, message_contains, reaction_added)"
                    },
                    "trigger_value": {
                        "type": "string",
                        "description": "Trigger value (e.g., keyword, emoji)"
                    },
                    "action_type": {
                        "type": "string",
                        "description": "Action type (assign_role, send_message, log)"
                    },
                    "action_payload": {
                        "type": "object",
                        "description": "Action payload details"
                    },
                    "enabled": {
                        "type": "boolean",
                        "description": "Whether the rule is enabled"
                    }
                },
                "required": ["name", "trigger_type", "action_type"]
            }
        ),

        # Templates
        Tool(
            name="create_message_template",
            description="Create a reusable message template",
            inputSchema={
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "description": "Template name"
                    },
                    "content": {
                        "type": "string",
                        "description": "Message template content"
                    }
                },
                "required": ["template_name", "content"]
            }
        ),
        Tool(
            name="create_role_template",
            description="Create a reusable role template",
            inputSchema={
                "type": "object",
                "properties": {
                    "template_name": {
                        "type": "string",
                        "description": "Template name"
                    },
                    "permissions": {
                        "type": "string",
                        "description": "Comma-separated permissions to grant"
                    },
                    "color": {
                        "type": "string",
                        "description": "Hex color code"
                    },
                    "hoist": {
                        "type": "boolean",
                        "description": "Whether to display role members separately"
                    },
                    "mentionable": {
                        "type": "boolean",
                        "description": "Whether the role is mentionable"
                    }
                },
                "required": ["template_name"]
            }
        ),

        # Smart Moderation & Analysis
        Tool(
            name="analyze_message_patterns",
            description="Analyze message patterns for spam indicators",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to analyze"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Messages to analyze"
                    },
                    "after": {
                        "type": "string",
                        "description": "ISO timestamp or epoch seconds"
                    },
                    "before": {
                        "type": "string",
                        "description": "ISO timestamp or epoch seconds"
                    }
                },
                "required": ["channel_id"]
            }
        ),
        Tool(
            name="auto_moderate_by_pattern",
            description="Auto-moderate messages based on simple spam patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "channel_id": {
                        "type": "string",
                        "description": "Channel ID to scan"
                    },
                    "pattern_type": {
                        "type": "string",
                        "description": "Pattern type (repeated_message, link_spam, mention_spam, caps_spam)"
                    },
                    "repeat_threshold": {
                        "type": "number",
                        "description": "Repeat count threshold for repeated_message"
                    },
                    "link_threshold": {
                        "type": "number",
                        "description": "Link count threshold for link_spam"
                    },
                    "mention_threshold": {
                        "type": "number",
                        "description": "Mention count threshold for mention_spam"
                    },
                    "caps_ratio_threshold": {
                        "type": "number",
                        "description": "Caps ratio threshold (0-1)"
                    },
                    "min_length": {
                        "type": "number",
                        "description": "Minimum message length for caps_spam"
                    },
                    "action": {
                        "type": "string",
                        "description": "Action (delete, timeout, report)"
                    },
                    "timeout_minutes": {
                        "type": "number",
                        "description": "Timeout duration for action=timeout"
                    },
                    "limit": {
                        "type": "number",
                        "description": "Messages to scan"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, only report matches"
                    }
                },
                "required": ["channel_id", "pattern_type"]
            }
        ),

        # Advanced Analytics
        Tool(
            name="track_metrics",
            description="Track custom metrics over time",
            inputSchema={
                "type": "object",
                "properties": {
                    "metric_name": {
                        "type": "string",
                        "description": "Metric name"
                    },
                    "value": {
                        "type": "number",
                        "description": "Metric value"
                    },
                    "timestamp": {
                        "type": "string",
                        "description": "ISO timestamp or epoch seconds"
                    },
                    "tags": {
                        "type": "object",
                        "description": "Optional metric tags"
                    }
                },
                "required": ["metric_name", "value"]
            }
        ),
        Tool(
            name="export_data",
            description="Export stored data (metrics, templates, automation rules)",
            inputSchema={
                "type": "object",
                "properties": {
                    "data_type": {
                        "type": "string",
                        "description": "Data type (metrics, templates, automation_rules)"
                    }
                },
                "required": ["data_type"]
            }
        ),

        # Channel Organization
        Tool(
            name="auto_organize_channels",
            description="Move inactive channels into a target category",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "target_category_id": {
                        "type": "string",
                        "description": "Category ID to move channels into"
                    },
                    "create_category_name": {
                        "type": "string",
                        "description": "Create a category with this name if target not provided"
                    },
                    "inactivity_days": {
                        "type": "number",
                        "description": "Move channels with last message older than N days"
                    },
                    "limit_per_channel": {
                        "type": "number",
                        "description": "Messages to scan per channel"
                    },
                    "dry_run": {
                        "type": "boolean",
                        "description": "If true, only report planned moves"
                    }
                },
                "required": ["server_id"]
            }
        ),
        Tool(
            name="create_channel_structure",
            description="Create channel structure from a template",
            inputSchema={
                "type": "object",
                "properties": {
                    "server_id": {
                        "type": "string",
                        "description": "Discord server ID"
                    },
                    "categories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "channels": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "name": {"type": "string"},
                                            "type": {"type": "string"},
                                            "topic": {"type": "string"}
                                        },
                                        "required": ["name"]
                                    }
                                }
                            },
                            "required": ["name"]
                        },
                        "description": "Categories with child channels"
                    },
                    "channels": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "type": {"type": "string"},
                                "topic": {"type": "string"}
                            },
                            "required": ["name"]
                        },
                        "description": "Channels to create at root level"
                    }
                },
                "required": ["server_id"]
            }
        )
    ]

@app.call_tool()
@require_discord_client
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle Discord tool calls."""
    def resolve_run_at(args: Dict[str, Any]) -> datetime:
        if "run_at" in args and args["run_at"]:
            run_at = parse_timestamp(args["run_at"])
        elif "delay_seconds" in args:
            run_at = datetime.now(timezone.utc) + timedelta(seconds=float(args["delay_seconds"]))
        else:
            raise ValueError("run_at or delay_seconds is required")

        if run_at is None:
            raise ValueError("Invalid run_at value")
        return run_at

    if name == "send_message":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        use_embed = arguments.get("use_embed", True)  # Default to True for embeds
        
        if use_embed:
            embed_title = arguments.get("embed_title", "Message")
            embed_color = arguments.get("embed_color", "0x5865F2")
            # Parse color
            try:
                color_int = int(embed_color, 16) if embed_color.startswith("0x") else int(embed_color)
            except ValueError:
                color_int = 0x5865F2  # Default Discord blurple
            
            embed = discord.Embed(
                title=embed_title,
                description=arguments["content"],
                color=color_int
            )
            message = await channel.send(embed=embed)
        else:
            message = await channel.send(arguments["content"])
        
        return [TextContent(
            type="text",
            text=f"Message sent successfully. Message ID: {message.id}"
        )]

    elif name == "read_messages":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        limit = min(int(arguments.get("limit", 10)), 100)
        fetch_users = arguments.get("fetch_reaction_users", False)  # Only fetch users if explicitly requested
        messages = []
        async for message in channel.history(limit=limit):
            reaction_data = []
            for reaction in message.reactions:
                emoji_str = str(reaction.emoji.name) if hasattr(reaction.emoji, 'name') and reaction.emoji.name else str(reaction.emoji.id) if hasattr(reaction.emoji, 'id') else str(reaction.emoji)
                reaction_info = {
                    "emoji": emoji_str,
                    "count": reaction.count
                }
                logger.error(f"Emoji: {emoji_str}")
                reaction_data.append(reaction_info)
            messages.append({
                "id": str(message.id),
                "author": str(message.author),
                "content": message.content,
                "timestamp": message.created_at.isoformat(),
                "reactions": reaction_data  # Add reactions to message dict
            })
        return [TextContent(
            type="text",
            text=f"Retrieved {len(messages)} messages:\n\n" + 
                 "\n".join([
                     f"{m['author']} ({m['timestamp']}): {m['content']}\n" +
                     f"Reactions: {', '.join([f'{r['emoji']}({r['count']})' for r in m['reactions']]) if m['reactions'] else 'No reactions'}"
                     for m in messages
                 ])
        )]

    elif name == "get_user_info":
        user = await discord_client.fetch_user(int(arguments["user_id"]))
        user_info = {
            "id": str(user.id),
            "name": user.name,
            "discriminator": user.discriminator,
            "bot": user.bot,
            "created_at": user.created_at.isoformat()
        }
        return [TextContent(
            type="text",
            text=f"User information:\n" + 
                 f"Name: {user_info['name']}#{user_info['discriminator']}\n" +
                 f"ID: {user_info['id']}\n" +
                 f"Bot: {user_info['bot']}\n" +
                 f"Created: {user_info['created_at']}"
        )]

    elif name == "moderate_message":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        message = await channel.fetch_message(int(arguments["message_id"]))
        reason = arguments.get("reason", "No reason provided")
        
        # Store message info before deletion
        message_author = message.author
        message_content = message.content[:500] if message.content else "(No content)"
        message_channel = channel.name
        message_url = message.jump_url
        
        # Delete the message (reason is logged but not passed to delete())
        await message.delete()
        
        # Log to staff logs channel (if it exists)
        try:
            # Try to find staff logs channel by name
            guild = message.guild
            staff_logs_channel = None
            for ch in guild.channels:
                if isinstance(ch, discord.TextChannel) and "staff" in ch.name.lower() and "log" in ch.name.lower():
                    staff_logs_channel = ch
                    break
            
            if staff_logs_channel:
                log_embed = discord.Embed(
                    title="🗑️ Message Deleted",
                    color=0xe74c3c,
                    timestamp=discord.utils.utcnow()
                )
                log_embed.add_field(name="Channel", value=f"#{message_channel}", inline=True)
                log_embed.add_field(name="Author", value=f"{message_author.mention} ({message_author.name})", inline=True)
                log_embed.add_field(name="Message ID", value=f"`{message.id}`", inline=True)
                log_embed.add_field(name="Content", value=message_content if len(message_content) <= 1024 else message_content[:1021] + "...", inline=False)
                log_embed.add_field(name="Reason", value=reason, inline=False)
                log_embed.add_field(name="Message Link", value=f"[Jump to Message]({message_url})", inline=False)
                await staff_logs_channel.send(embed=log_embed)
        except Exception as e:
            logger.warning(f"Failed to log to staff logs: {e}")
        
        # Handle timeout if specified
        if "timeout_minutes" in arguments and arguments["timeout_minutes"] > 0:
            if isinstance(message.author, discord.Member):
                duration = discord.utils.utcnow() + timedelta(
                    minutes=arguments["timeout_minutes"]
                )
                await message.author.timeout(
                    duration,
                    reason=reason
                )
                return [TextContent(
                    type="text",
                    text=f"Message deleted and user timed out for {arguments['timeout_minutes']} minutes."
                )]
        
        return [TextContent(
            type="text",
            text="Message deleted successfully."
        )]

    # Server Information Tools
    elif name == "list_servers":
        servers = []
        for guild in discord_client.guilds:
            servers.append({
                "id": str(guild.id),
                "name": guild.name,
                "member_count": guild.member_count,
                "owner_id": str(guild.owner_id) if guild.owner_id else None,
                "created_at": guild.created_at.isoformat() if guild.created_at else None
            })
        
        if not servers:
            return [TextContent(type="text", text="Bot is not a member of any servers.")]
        
        server_list = "\n".join(
            f"{s['name']} (ID: {s['id']}, Members: {s['member_count']}, Owner: {s['owner_id']})"
            for s in servers
        )
        return [TextContent(
            type="text",
            text=f"Servers the bot is in ({len(servers)}):\n{server_list}"
        )]

    elif name == "get_server_info":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        info = {
            "name": guild.name,
            "id": str(guild.id),
            "owner_id": str(guild.owner_id),
            "member_count": guild.member_count,
            "created_at": guild.created_at.isoformat(),
            "description": guild.description,
            "premium_tier": guild.premium_tier,
            "explicit_content_filter": str(guild.explicit_content_filter)
        }
        return [TextContent(
            type="text",
            text=f"Server Information:\n" + "\n".join(f"{k}: {v}" for k, v in info.items())
        )]

    elif name == "list_members":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        limit = min(int(arguments.get("limit", 100)), 1000)
        
        members = []
        async for member in guild.fetch_members(limit=limit):
            members.append({
                "id": str(member.id),
                "name": member.name,
                "nick": member.nick,
                "joined_at": member.joined_at.isoformat() if member.joined_at else None,
                "roles": [str(role.id) for role in member.roles[1:]]  # Skip @everyone
            })
        
        return [TextContent(
            type="text",
            text=f"Server Members ({len(members)}):\n" + 
                 "\n".join(f"{m['name']} (ID: {m['id']}, Roles: {', '.join(m['roles'])})" for m in members)
        )]

    # Server Settings Management
    elif name == "get_server_settings":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        info = {
            "name": guild.name,
            "description": guild.description,
            "icon": guild.icon.url if guild.icon else None,
            "banner": guild.banner.url if guild.banner else None,
            "verification_level": str(guild.verification_level),
            "default_notifications": str(guild.default_notifications),
            "afk_timeout": guild.afk_timeout,
            "afk_channel_id": str(guild.afk_channel.id) if guild.afk_channel else None,
            "system_channel_id": str(guild.system_channel.id) if guild.system_channel else None,
            "explicit_content_filter": str(guild.explicit_content_filter),
            "preferred_locale": str(guild.preferred_locale)
        }
        return [TextContent(
            type="text",
            text="Server Settings:\n" + "\n".join(
                f"{k}: {v}" for k, v in info.items() if v is not None
            )
        )]

    elif name == "modify_server_settings":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        kwargs = {"reason": arguments.get("reason", "Server settings updated via MCP")}

        if "name" in arguments:
            kwargs["name"] = arguments["name"]
        if "description" in arguments:
            kwargs["description"] = arguments["description"] or None
        if "icon_url" in arguments:
            kwargs["icon"] = await fetch_avatar_bytes(arguments["icon_url"]) if arguments["icon_url"] else None
        if "banner_url" in arguments:
            kwargs["banner"] = await fetch_avatar_bytes(arguments["banner_url"]) if arguments["banner_url"] else None
        if "verification_level" in arguments:
            kwargs["verification_level"] = parse_verification_level(arguments["verification_level"])
        if "default_notification_level" in arguments:
            kwargs["default_notifications"] = parse_notification_level(arguments["default_notification_level"])
        if "afk_timeout" in arguments:
            kwargs["afk_timeout"] = int(arguments["afk_timeout"])
        if "afk_channel_id" in arguments:
            kwargs["afk_channel"] = await discord_client.fetch_channel(int(arguments["afk_channel_id"])) if arguments["afk_channel_id"] else None
        if "system_channel_id" in arguments:
            kwargs["system_channel"] = await discord_client.fetch_channel(int(arguments["system_channel_id"])) if arguments["system_channel_id"] else None
        if "explicit_content_filter" in arguments:
            kwargs["explicit_content_filter"] = parse_content_filter(arguments["explicit_content_filter"])
        if "preferred_locale" in arguments:
            kwargs["preferred_locale"] = parse_locale(arguments["preferred_locale"])

        await guild.edit(**kwargs)
        return [TextContent(type="text", text=f"Updated server settings for {guild.name}")]

    # Invite Management
    elif name == "create_invite":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        kwargs = {}
        if "max_uses" in arguments:
            kwargs["max_uses"] = int(arguments["max_uses"])
        if "max_age_seconds" in arguments:
            kwargs["max_age"] = int(arguments["max_age_seconds"])
        if "temporary" in arguments:
            kwargs["temporary"] = arguments["temporary"]
        if "unique" in arguments:
            kwargs["unique"] = arguments["unique"]
        if "reason" in arguments:
            kwargs["reason"] = arguments["reason"]

        invite = await channel.create_invite(**kwargs)
        info = {
            "code": invite.code,
            "url": invite.url,
            "uses": invite.uses,
            "max_uses": invite.max_uses,
            "max_age": invite.max_age,
            "temporary": invite.temporary,
            "expires_at": invite.expires_at.isoformat() if invite.expires_at else None
        }
        return [TextContent(
            type="text",
            text="Invite created:\n" + "\n".join(f"{k}: {v}" for k, v in info.items() if v is not None)
        )]

    elif name == "list_invites":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        invites = await guild.invites()
        invite_lines = []
        for invite in invites:
            invite_lines.append(
                f"{invite.code} (Channel: {invite.channel.name if invite.channel else 'Unknown'}, "
                f"Uses: {invite.uses}/{invite.max_uses or 'unlimited'}, "
                f"Expires: {invite.expires_at.isoformat() if invite.expires_at else 'never'})"
            )
        return [TextContent(
            type="text",
            text=f"Invites ({len(invite_lines)}):\n" + "\n".join(invite_lines) if invite_lines else "No active invites found"
        )]

    elif name == "delete_invite":
        invite = await discord_client.fetch_invite(arguments["invite_code"])
        await invite.delete(reason=arguments.get("reason", "Invite deleted via MCP"))
        return [TextContent(type="text", text=f"Deleted invite: {arguments['invite_code']}")]

    elif name == "get_invite_info":
        invite = await discord_client.fetch_invite(
            arguments["invite_code"],
            with_counts=True,
            with_expiration=True
        )
        info = {
            "code": invite.code,
            "guild": invite.guild.name if invite.guild else None,
            "channel": invite.channel.name if invite.channel else None,
            "inviter": str(invite.inviter) if invite.inviter else None,
            "uses": invite.uses,
            "max_uses": invite.max_uses,
            "max_age": invite.max_age,
            "temporary": invite.temporary,
            "created_at": invite.created_at.isoformat() if invite.created_at else None,
            "expires_at": invite.expires_at.isoformat() if invite.expires_at else None
        }
        return [TextContent(
            type="text",
            text="Invite information:\n" + "\n".join(f"{k}: {v}" for k, v in info.items() if v is not None)
        )]

    # Auto-Moderation & Rules
    elif name == "create_automod_rule":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        trigger_type = parse_automod_trigger_type(arguments["trigger_type"])
        trigger_kwargs = {"type": trigger_type}

        if trigger_type == discord.AutoModRuleTriggerType.keyword:
            trigger_kwargs["keyword_filter"] = arguments.get("keyword_filter", [])
            trigger_kwargs["regex_patterns"] = arguments.get("regex_patterns", [])
            trigger_kwargs["allow_list"] = arguments.get("allow_list", [])
        elif trigger_type == discord.AutoModRuleTriggerType.keyword_preset:
            trigger_kwargs["presets"] = parse_automod_presets(arguments.get("presets", [])) or []
            if "allow_list" in arguments:
                trigger_kwargs["allow_list"] = arguments.get("allow_list", [])
        elif trigger_type == discord.AutoModRuleTriggerType.mention_spam:
            if "mention_total_limit" in arguments:
                trigger_kwargs["mention_total_limit"] = int(arguments["mention_total_limit"])

        trigger = discord.AutoModTrigger(**trigger_kwargs)
        actions = await build_automod_actions(
            arguments.get("alert_channel_id"),
            arguments.get("timeout_minutes")
        )

        kwargs = {
            "name": arguments["name"],
            "event_type": discord.AutoModEventType.message_send,
            "trigger": trigger,
            "actions": actions,
            "enabled": arguments.get("enabled", True),
            "reason": arguments.get("reason", "Auto-mod rule created via MCP")
        }

        if "exempt_role_ids" in arguments:
            kwargs["exempt_roles"] = [
                role for role_id in arguments["exempt_role_ids"]
                if (role := guild.get_role(int(role_id))) is not None
            ]
        if "exempt_channel_ids" in arguments:
            exempt_channels = []
            for channel_id in arguments["exempt_channel_ids"]:
                channel = guild.get_channel(int(channel_id)) or await discord_client.fetch_channel(int(channel_id))
                if channel:
                    exempt_channels.append(channel)
            kwargs["exempt_channels"] = exempt_channels

        rule = await guild.create_automod_rule(**kwargs)
        return [TextContent(type="text", text=f"Created auto-mod rule: {rule.name} (ID: {rule.id})")]

    elif name == "list_automod_rules":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        rules = await guild.fetch_automod_rules()
        rule_lines = [
            f"{rule.name} (ID: {rule.id}, Enabled: {rule.enabled}, Trigger: {rule.trigger.type})"
            for rule in rules
        ]
        return [TextContent(
            type="text",
            text=f"Auto-mod rules ({len(rule_lines)}):\n" + "\n".join(rule_lines) if rule_lines else "No auto-mod rules found"
        )]

    elif name == "modify_automod_rule":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        rules = await guild.fetch_automod_rules()
        rule = next((r for r in rules if r.id == int(arguments["rule_id"])), None)
        if not rule:
            raise ValueError("Auto-mod rule not found")

        kwargs = {"reason": arguments.get("reason", "Auto-mod rule modified via MCP")}

        if "name" in arguments:
            kwargs["name"] = arguments["name"]
        if "enabled" in arguments:
            kwargs["enabled"] = arguments["enabled"]
        if "trigger_type" in arguments:
            trigger_type = parse_automod_trigger_type(arguments["trigger_type"])
            trigger_kwargs = {"type": trigger_type}

            if trigger_type == discord.AutoModTriggerType.keyword:
                trigger_kwargs["keyword_filter"] = arguments.get("keyword_filter", [])
                trigger_kwargs["regex_patterns"] = arguments.get("regex_patterns", [])
                trigger_kwargs["allow_list"] = arguments.get("allow_list", [])
            elif trigger_type == discord.AutoModTriggerType.keyword_preset:
                trigger_kwargs["presets"] = parse_automod_presets(arguments.get("presets", [])) or []
                if "allow_list" in arguments:
                    trigger_kwargs["allow_list"] = arguments.get("allow_list", [])
            elif trigger_type == discord.AutoModTriggerType.mention_spam:
                if "mention_total_limit" in arguments:
                    trigger_kwargs["mention_total_limit"] = int(arguments["mention_total_limit"])

            kwargs["trigger"] = discord.AutoModTrigger(**trigger_kwargs)

        if "alert_channel_id" in arguments or "timeout_minutes" in arguments:
            kwargs["actions"] = await build_automod_actions(
                arguments.get("alert_channel_id"),
                arguments.get("timeout_minutes")
            )

        if "exempt_role_ids" in arguments:
            kwargs["exempt_roles"] = [
                role for role_id in arguments["exempt_role_ids"]
                if (role := guild.get_role(int(role_id))) is not None
            ]
        if "exempt_channel_ids" in arguments:
            exempt_channels = []
            for channel_id in arguments["exempt_channel_ids"]:
                channel = guild.get_channel(int(channel_id)) or await discord_client.fetch_channel(int(channel_id))
                if channel:
                    exempt_channels.append(channel)
            kwargs["exempt_channels"] = exempt_channels

        await rule.edit(**kwargs)
        return [TextContent(type="text", text=f"Modified auto-mod rule: {rule.name}")]

    elif name == "delete_automod_rule":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        rules = await guild.fetch_automod_rules()
        rule = next((r for r in rules if r.id == int(arguments["rule_id"])), None)
        if not rule:
            raise ValueError("Auto-mod rule not found")
        await rule.delete(reason=arguments.get("reason", "Auto-mod rule deleted via MCP"))
        return [TextContent(type="text", text=f"Deleted auto-mod rule: {rule.name}")]

    # Thread Management
    elif name == "create_thread":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        kwargs = {
            "name": arguments["name"],
            "reason": arguments.get("reason", "Thread created via MCP")
        }
        if "auto_archive_duration" in arguments:
            kwargs["auto_archive_duration"] = int(arguments["auto_archive_duration"])

        if "message_id" in arguments:
            message = await channel.fetch_message(int(arguments["message_id"]))
            thread = await message.create_thread(**kwargs)
        else:
            thread_type = arguments.get("thread_type", "public").lower()
            kwargs["type"] = (
                discord.ChannelType.private_thread
                if thread_type == "private"
                else discord.ChannelType.public_thread
            )
            if "invitable" in arguments:
                kwargs["invitable"] = arguments["invitable"]
            thread = await channel.create_thread(**kwargs)

        return [TextContent(type="text", text=f"Created thread: {thread.name} (ID: {thread.id})")]

    elif name == "list_threads":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        archived = arguments.get("archived", False)
        limit = arguments.get("limit")

        threads = []
        if archived:
            include_private = arguments.get("include_private", False)
            kwargs = {"private": include_private}
            if limit is not None:
                kwargs["limit"] = int(limit)
            async for thread in channel.archived_threads(**kwargs):
                threads.append(thread)
        else:
            threads = list(channel.threads)

        thread_lines = [
            f"{thread.name} (ID: {thread.id}, Archived: {thread.archived})"
            for thread in threads
        ]
        return [TextContent(
            type="text",
            text=f"Threads ({len(thread_lines)}):\n" + "\n".join(thread_lines) if thread_lines else "No threads found"
        )]

    elif name == "archive_thread":
        thread = await discord_client.fetch_channel(int(arguments["thread_id"]))
        await thread.edit(archived=True, reason=arguments.get("reason", "Thread archived via MCP"))
        return [TextContent(type="text", text=f"Archived thread: {thread.name}")]

    elif name == "unarchive_thread":
        thread = await discord_client.fetch_channel(int(arguments["thread_id"]))
        await thread.edit(archived=False, reason=arguments.get("reason", "Thread unarchived via MCP"))
        return [TextContent(type="text", text=f"Unarchived thread: {thread.name}")]

    elif name == "delete_thread":
        thread = await discord_client.fetch_channel(int(arguments["thread_id"]))
        await thread.delete(reason=arguments.get("reason", "Thread deleted via MCP"))
        return [TextContent(type="text", text=f"Deleted thread: {thread.name}")]

    # Category Management
    elif name == "create_category":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        kwargs = {
            "name": arguments["name"],
            "reason": arguments.get("reason", "Category created via MCP")
        }
        if "position" in arguments:
            kwargs["position"] = int(arguments["position"])

        category = await guild.create_category(**kwargs)
        return [TextContent(type="text", text=f"Created category: {category.name} (ID: {category.id})")]

    elif name == "modify_category":
        category = await discord_client.fetch_channel(int(arguments["category_id"]))
        kwargs = {"reason": arguments.get("reason", "Category modified via MCP")}

        if "name" in arguments:
            kwargs["name"] = arguments["name"]
        if "position" in arguments:
            kwargs["position"] = int(arguments["position"])

        if len(kwargs) > 1:
            await category.edit(**kwargs)

        if "target_type" in arguments and "target_id" in arguments:
            overwrite = discord.PermissionOverwrite()

            if "allow_permissions" in arguments and arguments["allow_permissions"]:
                for perm_name in arguments["allow_permissions"].split(","):
                    perm_name = perm_name.strip()
                    perm_value = getattr(discord.Permissions, perm_name, None)
                    if perm_value is not None:
                        setattr(overwrite, perm_name, True)

            if "deny_permissions" in arguments and arguments["deny_permissions"]:
                for perm_name in arguments["deny_permissions"].split(","):
                    perm_name = perm_name.strip()
                    perm_value = getattr(discord.Permissions, perm_name, None)
                    if perm_value is not None:
                        setattr(overwrite, perm_name, False)

            if arguments["target_type"] == "role":
                target = category.guild.get_role(int(arguments["target_id"]))
            else:
                target = await category.guild.fetch_member(int(arguments["target_id"]))

            await category.set_permissions(
                target,
                overwrite=overwrite,
                reason=arguments.get("reason", "Category permissions modified via MCP")
            )

        return [TextContent(type="text", text=f"Modified category: {category.name}")]

    elif name == "delete_category":
        category = await discord_client.fetch_channel(int(arguments["category_id"]))
        reason = arguments.get("reason", "Category deleted via MCP")
        if "move_channels_to" in arguments and arguments["move_channels_to"]:
            target_category = await discord_client.fetch_channel(int(arguments["move_channels_to"]))
            for channel in category.channels:
                await channel.edit(category=target_category, reason=reason)

        await category.delete(reason=reason)
        return [TextContent(type="text", text=f"Deleted category: {category.name}")]

    # Emoji & Sticker Management
    elif name == "create_emoji":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        image_bytes = await fetch_avatar_bytes(arguments["image_url"])
        kwargs = {
            "name": arguments["name"],
            "image": image_bytes,
            "reason": arguments.get("reason", "Emoji created via MCP")
        }
        if "roles" in arguments:
            kwargs["roles"] = [
                role for role_id in arguments["roles"]
                if (role := guild.get_role(int(role_id))) is not None
            ]
        emoji = await guild.create_custom_emoji(**kwargs)
        return [TextContent(type="text", text=f"Created emoji: {emoji.name} (ID: {emoji.id})")]

    elif name == "list_emojis":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        try:
            emojis = await guild.fetch_emojis()
        except AttributeError:
            emojis = guild.emojis
        emoji_lines = [f"{emoji.name} (ID: {emoji.id})" for emoji in emojis]
        return [TextContent(
            type="text",
            text=f"Emojis ({len(emoji_lines)}):\n" + "\n".join(emoji_lines) if emoji_lines else "No custom emojis found"
        )]

    elif name == "delete_emoji":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        try:
            emojis = await guild.fetch_emojis()
        except AttributeError:
            emojis = guild.emojis
        emoji = next((e for e in emojis if e.id == int(arguments["emoji_id"])), None)
        if not emoji:
            raise ValueError("Emoji not found")
        await emoji.delete(reason=arguments.get("reason", "Emoji deleted via MCP"))
        return [TextContent(type="text", text=f"Deleted emoji: {emoji.name}")]

    elif name == "create_sticker":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        image_bytes = await fetch_avatar_bytes(arguments["image_url"])
        sticker_file = discord.File(io.BytesIO(image_bytes), filename="sticker.png")
        sticker = await guild.create_sticker(
            name=arguments["name"],
            description=arguments["description"],
            emoji=arguments["emoji"],
            file=sticker_file,
            reason=arguments.get("reason", "Sticker created via MCP")
        )
        return [TextContent(type="text", text=f"Created sticker: {sticker.name} (ID: {sticker.id})")]

    elif name == "list_stickers":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        stickers = await guild.fetch_stickers()
        sticker_lines = [f"{sticker.name} (ID: {sticker.id})" for sticker in stickers]
        return [TextContent(
            type="text",
            text=f"Stickers ({len(sticker_lines)}):\n" + "\n".join(sticker_lines) if sticker_lines else "No custom stickers found"
        )]

    elif name == "delete_sticker":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        stickers = await guild.fetch_stickers()
        sticker = next((s for s in stickers if s.id == int(arguments["sticker_id"])), None)
        if not sticker:
            raise ValueError("Sticker not found")
        await sticker.delete(reason=arguments.get("reason", "Sticker deleted via MCP"))
        return [TextContent(type="text", text=f"Deleted sticker: {sticker.name}")]

    # Bulk Operations
    elif name == "bulk_add_roles":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        role = guild.get_role(int(arguments["role_id"]))
        if not role:
            raise ValueError("Role not found")

        reason = arguments.get("reason", "Bulk role assignment via MCP")
        success_ids = []
        failed = []

        for user_id in arguments["user_ids"]:
            try:
                member = await guild.fetch_member(int(user_id))
                await member.add_roles(role, reason=reason)
                success_ids.append(str(member.id))
            except Exception as exc:
                failed.append(f"{user_id}: {exc}")

        summary = f"Bulk add roles complete. Success: {len(success_ids)}, Failed: {len(failed)}"
        if failed:
            summary += "\nFailed:\n" + "\n".join(failed)

        return [TextContent(type="text", text=summary)]

    elif name == "bulk_modify_members":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        reason = arguments.get("reason", "Bulk member update via MCP")
        success_ids = []
        failed = []

        for update in arguments["updates"]:
            user_id = update["user_id"]
            try:
                member = await guild.fetch_member(int(user_id))
                kwargs = {"reason": reason}
                has_changes = False

                if "nickname" in update:
                    kwargs["nick"] = update["nickname"] if update["nickname"] else None
                    has_changes = True

                if "timeout_minutes" in update:
                    if update["timeout_minutes"] > 0:
                        timeout_until = discord.utils.utcnow() + timedelta(
                            minutes=update["timeout_minutes"]
                        )
                        kwargs["timed_out_until"] = timeout_until
                    else:
                        kwargs["timed_out_until"] = None
                    has_changes = True

                if not has_changes:
                    failed.append(f"{user_id}: no changes provided")
                    continue

                await member.edit(**kwargs)
                success_ids.append(str(member.id))
            except Exception as exc:
                failed.append(f"{user_id}: {exc}")

        summary = f"Bulk modify members complete. Success: {len(success_ids)}, Failed: {len(failed)}"
        if failed:
            summary += "\nFailed:\n" + "\n".join(failed)

        return [TextContent(type="text", text=summary)]

    # Smart Search & Filtering
    elif name == "search_messages":
        channel_ids = []
        if "channel_id" in arguments and arguments["channel_id"]:
            channel_ids.append(arguments["channel_id"])
        if "channel_ids" in arguments and arguments["channel_ids"]:
            channel_ids.extend(arguments["channel_ids"])

        if not channel_ids:
            raise ValueError("channel_id or channel_ids is required")

        contains = arguments.get("contains")
        contains_lower = contains.lower() if contains else None
        author_id = arguments.get("author_id")
        after = parse_timestamp(arguments.get("after"))
        before = parse_timestamp(arguments.get("before"))
        has_reactions = arguments.get("has_reactions", False)
        limit_per_channel = min(int(arguments.get("limit_per_channel", 50)), 200)
        max_results = min(int(arguments.get("max_results", 100)), 500)

        results = []
        for channel_id in channel_ids:
            channel = await discord_client.fetch_channel(int(channel_id))
            if not hasattr(channel, "history"):
                continue

            async for message in channel.history(limit=limit_per_channel, after=after, before=before):
                content = message.content or ""
                if contains_lower and contains_lower not in content.lower():
                    continue
                if author_id and str(message.author.id) != str(author_id):
                    continue
                if has_reactions and not message.reactions:
                    continue

                preview = content
                if len(preview) > 200:
                    preview = preview[:200] + "..."

                results.append(
                    f"{message.id} | {message.author} | {channel.name} | {message.created_at.isoformat()} | {preview}"
                )
                if len(results) >= max_results:
                    break
            if len(results) >= max_results:
                break

        return [TextContent(
            type="text",
            text=f"Search results ({len(results)}):\n" + "\n".join(results) if results else "No matching messages found"
        )]

    elif name == "find_members_by_criteria":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        role_ids_any = {int(rid) for rid in arguments.get("role_ids_any", [])}
        role_ids_all = {int(rid) for rid in arguments.get("role_ids_all", [])}
        joined_after = parse_timestamp(arguments.get("joined_after"))
        joined_before = parse_timestamp(arguments.get("joined_before"))
        nickname_contains = arguments.get("nickname_contains")
        name_contains = arguments.get("name_contains")
        is_bot = arguments.get("is_bot")
        scan_limit = min(int(arguments.get("scan_limit", 1000)), 5000)
        max_results = min(int(arguments.get("max_results", 200)), 500)

        if nickname_contains:
            nickname_contains = nickname_contains.lower()
        if name_contains:
            name_contains = name_contains.lower()

        matches = []
        async for member in guild.fetch_members(limit=scan_limit):
            if is_bot is not None and member.bot != is_bot:
                continue
            if joined_after and (member.joined_at is None or member.joined_at < joined_after):
                continue
            if joined_before and (member.joined_at is None or member.joined_at > joined_before):
                continue

            member_role_ids = {role.id for role in member.roles}
            if role_ids_any and not (member_role_ids & role_ids_any):
                continue
            if role_ids_all and not role_ids_all.issubset(member_role_ids):
                continue

            nick_value = member.nick or ""
            if nickname_contains and nickname_contains not in nick_value.lower():
                continue
            if name_contains and name_contains not in member.name.lower():
                continue

            joined_at = member.joined_at.isoformat() if member.joined_at else None
            matches.append(
                f"{member.name} (ID: {member.id}, Nick: {member.nick}, Joined: {joined_at})"
            )
            if len(matches) >= max_results:
                break

        return [TextContent(
            type="text",
            text=f"Member matches ({len(matches)}):\n" + "\n".join(matches) if matches else "No members matched"
        )]

    # Scheduled Tasks
    elif name == "schedule_task":
        task_type = arguments["task_type"]
        payload = arguments.get("task_payload", {})
        allowed = {"send_message", "bulk_add_roles", "bulk_modify_members"}
        if task_type not in allowed:
            raise ValueError("Unsupported task_type")

        run_at = resolve_run_at(arguments)
        task_id = next_scheduled_task_id()
        scheduled_tasks[task_id] = {
            "id": task_id,
            "task_type": task_type,
            "run_at": run_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "scheduled",
            "payload": payload
        }

        async def task_callable() -> Any:
            return await call_tool(task_type, payload)

        asyncio.create_task(run_scheduled_task(task_id, run_at, task_callable))
        return [TextContent(
            type="text",
            text=f"Scheduled task {task_id} ({task_type}) for {run_at.isoformat()}"
        )]

    elif name == "send_scheduled_message":
        run_at = resolve_run_at(arguments)
        payload = {
            "channel_id": arguments["channel_id"],
            "content": arguments["content"]
        }

        task_id = next_scheduled_task_id()
        scheduled_tasks[task_id] = {
            "id": task_id,
            "task_type": "send_message",
            "run_at": run_at.isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "scheduled",
            "payload": payload
        }

        async def task_callable() -> Any:
            return await call_tool("send_message", payload)

        asyncio.create_task(run_scheduled_task(task_id, run_at, task_callable))
        return [TextContent(
            type="text",
            text=f"Scheduled message {task_id} for {run_at.isoformat()}"
        )]

    # Analytics
    elif name == "generate_server_analytics":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        member_sample_limit = min(int(arguments.get("member_sample_limit", 200)), 2000)

        bot_count = 0
        human_count = 0
        async for member in guild.fetch_members(limit=member_sample_limit):
            if member.bot:
                bot_count += 1
            else:
                human_count += 1

        channel_counts = Counter()
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                channel_counts["text"] += 1
            elif isinstance(channel, discord.VoiceChannel):
                channel_counts["voice"] += 1
            elif isinstance(channel, discord.CategoryChannel):
                channel_counts["category"] += 1
            elif isinstance(channel, discord.ForumChannel):
                channel_counts["forum"] += 1
            elif isinstance(channel, discord.StageChannel):
                channel_counts["stage"] += 1
            elif isinstance(channel, discord.NewsChannel):
                channel_counts["announcement"] += 1
            else:
                channel_counts["other"] += 1

        info = {
            "name": guild.name,
            "member_count": guild.member_count,
            "roles": len(guild.roles),
            "channels_total": len(guild.channels),
            "channels_text": channel_counts.get("text", 0),
            "channels_voice": channel_counts.get("voice", 0),
            "channels_category": channel_counts.get("category", 0),
            "channels_forum": channel_counts.get("forum", 0),
            "channels_stage": channel_counts.get("stage", 0),
            "channels_announcement": channel_counts.get("announcement", 0),
            "channels_other": channel_counts.get("other", 0),
            "emojis": len(guild.emojis),
            "stickers": len(guild.stickers),
            "sampled_members": bot_count + human_count,
            "sampled_bots": bot_count,
            "sampled_humans": human_count
        }

        return [TextContent(
            type="text",
            text="Server analytics:\n" + "\n".join(f"{k}: {v}" for k, v in info.items())
        )]

    elif name == "generate_channel_analytics":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        if not hasattr(channel, "history"):
            return [TextContent(type="text", text="Channel does not support message history.")]

        limit = min(int(arguments.get("limit", 200)), 1000)
        after = parse_timestamp(arguments.get("after"))
        before = parse_timestamp(arguments.get("before"))

        message_count = 0
        attachment_count = 0
        reaction_count = 0
        author_counts = Counter()
        author_names: Dict[int, str] = {}
        first_message_at = None
        last_message_at = None

        async for message in channel.history(
            limit=limit,
            after=after,
            before=before,
            oldest_first=True
        ):
            message_count += 1
            attachment_count += len(message.attachments)
            reaction_count += sum(reaction.count for reaction in message.reactions)
            author_counts[message.author.id] += 1
            author_names[message.author.id] = str(message.author)

            if first_message_at is None:
                first_message_at = message.created_at
            last_message_at = message.created_at

        top_authors = [
            f"{author_names.get(author_id, author_id)} ({count})"
            for author_id, count in author_counts.most_common(5)
        ]

        info = {
            "channel": getattr(channel, "name", str(channel.id)),
            "message_count_scanned": message_count,
            "unique_authors": len(author_counts),
            "attachments": attachment_count,
            "reactions": reaction_count,
            "first_message_at": first_message_at.isoformat() if first_message_at else None,
            "last_message_at": last_message_at.isoformat() if last_message_at else None,
            "top_authors": ", ".join(top_authors) if top_authors else None
        }

        return [TextContent(
            type="text",
            text="Channel analytics:\n" + "\n".join(
                f"{k}: {v}" for k, v in info.items() if v is not None
            )
        )]

    # Automation Rules
    elif name == "create_automation_rule":
        rule_id = next_automation_rule_id()
        rule = {
            "id": rule_id,
            "server_id": arguments.get("server_id"),
            "name": arguments["name"],
            "trigger_type": arguments["trigger_type"],
            "trigger_value": arguments.get("trigger_value"),
            "action_type": arguments["action_type"],
            "action_payload": arguments.get("action_payload", {}),
            "enabled": arguments.get("enabled", True),
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        automation_rules[rule_id] = rule
        return [TextContent(type="text", text=f"Created automation rule {rule_id}: {rule['name']}")]

    # Templates
    elif name == "create_message_template":
        message_templates[arguments["template_name"]] = arguments["content"]
        return [TextContent(
            type="text",
            text=f"Saved message template: {arguments['template_name']}"
        )]

    elif name == "create_role_template":
        template = {}
        if "permissions" in arguments:
            template["permissions"] = [
                perm.strip() for perm in arguments["permissions"].split(",") if perm.strip()
            ]
        if "color" in arguments:
            template["color"] = arguments["color"]
        if "hoist" in arguments:
            template["hoist"] = arguments["hoist"]
        if "mentionable" in arguments:
            template["mentionable"] = arguments["mentionable"]

        role_templates[arguments["template_name"]] = template
        return [TextContent(
            type="text",
            text=f"Saved role template: {arguments['template_name']}"
        )]

    # Smart Moderation & Analysis
    elif name == "analyze_message_patterns":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        if not hasattr(channel, "history"):
            return [TextContent(type="text", text="Channel does not support message history.")]

        limit = min(int(arguments.get("limit", 200)), 1000)
        after = parse_timestamp(arguments.get("after"))
        before = parse_timestamp(arguments.get("before"))

        content_counts = Counter()
        author_counts = Counter()
        total_links = 0
        total_mentions = 0
        caps_spam = 0
        total_messages = 0

        async for message in channel.history(limit=limit, after=after, before=before):
            total_messages += 1
            content = (message.content or "").strip()
            if content:
                normalized = content.lower()
                content_counts[normalized] += 1
            author_counts[message.author.id] += 1

            total_links += len(re.findall(r"https?://", content))
            total_mentions += len(message.mentions) + len(message.role_mentions)

            letters = [ch for ch in content if ch.isalpha()]
            if letters:
                ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
                if ratio >= 0.7 and len(content) >= 15:
                    caps_spam += 1

        top_repeated = [
            f"{text[:80]} ({count})"
            for text, count in content_counts.most_common(5)
            if count > 1
        ]
        top_authors = [
            f"{author_id} ({count})" for author_id, count in author_counts.most_common(5)
        ]

        info = {
            "messages_scanned": total_messages,
            "unique_authors": len(author_counts),
            "total_links": total_links,
            "total_mentions": total_mentions,
            "caps_spam_signals": caps_spam,
            "top_repeated_messages": "; ".join(top_repeated) if top_repeated else None,
            "top_authors": "; ".join(top_authors) if top_authors else None
        }
        return [TextContent(
            type="text",
            text="Message pattern analysis:\n" + "\n".join(
                f"{k}: {v}" for k, v in info.items() if v is not None
            )
        )]

    elif name == "auto_moderate_by_pattern":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        if not hasattr(channel, "history"):
            return [TextContent(type="text", text="Channel does not support message history.")]

        pattern_type = arguments["pattern_type"].strip().lower()
        limit = min(int(arguments.get("limit", 200)), 1000)
        action = arguments.get("action", "report").strip().lower()
        dry_run = arguments.get("dry_run", True)

        messages = [msg async for msg in channel.history(limit=limit)]
        matches = []

        if pattern_type == "repeated_message":
            repeat_threshold = int(arguments.get("repeat_threshold", 3))
            counts = Counter()
            for msg in messages:
                content = (msg.content or "").strip().lower()
                if content:
                    counts[(msg.author.id, content)] += 1
            for msg in messages:
                content = (msg.content or "").strip().lower()
                if content and counts[(msg.author.id, content)] >= repeat_threshold:
                    matches.append(msg)

        elif pattern_type == "link_spam":
            link_threshold = int(arguments.get("link_threshold", 3))
            for msg in messages:
                content = msg.content or ""
                if len(re.findall(r"https?://", content)) >= link_threshold:
                    matches.append(msg)

        elif pattern_type == "mention_spam":
            mention_threshold = int(arguments.get("mention_threshold", 5))
            for msg in messages:
                mention_count = len(msg.mentions) + len(msg.role_mentions)
                if mention_count >= mention_threshold:
                    matches.append(msg)

        elif pattern_type == "caps_spam":
            caps_ratio = float(arguments.get("caps_ratio_threshold", 0.7))
            min_length = int(arguments.get("min_length", 15))
            for msg in messages:
                content = msg.content or ""
                letters = [ch for ch in content if ch.isalpha()]
                if not letters:
                    continue
                ratio = sum(1 for ch in letters if ch.isupper()) / len(letters)
                if ratio >= caps_ratio and len(content) >= min_length:
                    matches.append(msg)
        else:
            raise ValueError("Unknown pattern_type")

        applied = 0
        errors = []
        timed_out = set()

        if action not in {"delete", "timeout", "report"}:
            raise ValueError("Invalid action")

        if action != "report" and not dry_run:
            for msg in matches:
                try:
                    if action == "delete":
                        await msg.delete(reason="Auto-moderated via MCP")
                        applied += 1
                    elif action == "timeout":
                        if "timeout_minutes" not in arguments:
                            raise ValueError("timeout_minutes required for timeout action")
                        if isinstance(msg.author, discord.Member) and msg.author.id not in timed_out:
                            duration = discord.utils.utcnow() + timedelta(
                                minutes=arguments["timeout_minutes"]
                            )
                            await msg.author.timeout(duration, reason="Auto-moderated via MCP")
                            timed_out.add(msg.author.id)
                            applied += 1
                except Exception as exc:
                    errors.append(f"{msg.id}: {exc}")

        result_lines = [
            f"Matched messages: {len(matches)}",
            f"Action: {action}",
            f"Dry run: {dry_run}",
            f"Applied: {applied}"
        ]
        if matches:
            sample = ", ".join(str(msg.id) for msg in matches[:10])
            result_lines.append(f"Sample IDs: {sample}")
        if errors:
            result_lines.append("Errors:\n" + "\n".join(errors))

        return [TextContent(type="text", text="\n".join(result_lines))]

    # Advanced Analytics
    elif name == "track_metrics":
        metric_name = arguments["metric_name"]
        timestamp = parse_timestamp(arguments.get("timestamp")) or datetime.now(timezone.utc)
        entry = {
            "timestamp": timestamp.isoformat(),
            "value": arguments["value"],
            "tags": arguments.get("tags", {})
        }
        metrics_store.setdefault(metric_name, []).append(entry)
        return [TextContent(
            type="text",
            text=f"Tracked metric {metric_name} at {entry['timestamp']}"
        )]

    elif name == "export_data":
        data_type = arguments["data_type"]
        if data_type == "metrics":
            export_payload = {"metrics": metrics_store}
        elif data_type == "templates":
            export_payload = {
                "message_templates": message_templates,
                "role_templates": role_templates
            }
        elif data_type == "automation_rules":
            export_payload = {"automation_rules": automation_rules}
        else:
            raise ValueError("Unsupported data_type")

        return [TextContent(
            type="text",
            text=json.dumps(export_payload, indent=2, sort_keys=True)
        )]

    # Channel Organization
    elif name == "auto_organize_channels":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        target_category = None
        if "target_category_id" in arguments and arguments["target_category_id"]:
            target_category = await discord_client.fetch_channel(int(arguments["target_category_id"]))
        elif "create_category_name" in arguments and arguments["create_category_name"]:
            target_category = await guild.create_category(
                arguments["create_category_name"],
                reason="Auto-organize channels via MCP"
            )
        else:
            raise ValueError("target_category_id or create_category_name is required")

        inactivity_days = int(arguments.get("inactivity_days", 30))
        limit_per_channel = min(int(arguments.get("limit_per_channel", 1)), 10)
        dry_run = arguments.get("dry_run", True)
        cutoff = datetime.now(timezone.utc) - timedelta(days=inactivity_days)

        moved = []
        skipped = []

        for channel in guild.text_channels:
            if channel.category_id == target_category.id:
                continue
            try:
                last_message = None
                async for message in channel.history(limit=limit_per_channel):
                    last_message = message
                    break
                last_time = last_message.created_at if last_message else None
                if last_time is None or last_time < cutoff:
                    if not dry_run:
                        await channel.edit(
                            category=target_category,
                            reason="Auto-organize inactive channels via MCP"
                        )
                    moved.append(f"{channel.name} (last: {last_time.isoformat() if last_time else 'none'})")
            except Exception as exc:
                skipped.append(f"{channel.name}: {exc}")

        summary = [
            f"Target category: {target_category.name} ({target_category.id})",
            f"Dry run: {dry_run}",
            f"Moved: {len(moved)}",
            f"Skipped: {len(skipped)}"
        ]
        if moved:
            summary.append("Channels:\n" + "\n".join(moved))
        if skipped:
            summary.append("Skipped:\n" + "\n".join(skipped))

        return [TextContent(type="text", text="\n".join(summary))]

    elif name == "create_channel_structure":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        created_categories = []
        created_channels = []
        errors = []

        async def create_channel(channel_spec: Dict[str, Any], category: Optional[discord.CategoryChannel]) -> None:
            channel_type = (channel_spec.get("type") or "text").lower()
            name = channel_spec["name"]
            topic = channel_spec.get("topic")
            try:
                if channel_type == "voice":
                    channel = await guild.create_voice_channel(
                        name,
                        category=category,
                        reason="Channel structure created via MCP"
                    )
                elif channel_type == "text":
                    channel = await guild.create_text_channel(
                        name,
                        category=category,
                        topic=topic,
                        reason="Channel structure created via MCP"
                    )
                else:
                    raise ValueError(f"Unsupported channel type: {channel_type}")
                created_channels.append(f"{channel.name} ({channel.id})")
            except Exception as exc:
                errors.append(f"{name}: {exc}")

        for category_spec in arguments.get("categories", []):
            try:
                category = await guild.create_category(
                    category_spec["name"],
                    reason="Channel structure created via MCP"
                )
                created_categories.append(f"{category.name} ({category.id})")
                for channel_spec in category_spec.get("channels", []):
                    await create_channel(channel_spec, category)
            except Exception as exc:
                errors.append(f"{category_spec.get('name', 'category')}: {exc}")

        for channel_spec in arguments.get("channels", []):
            await create_channel(channel_spec, None)

        summary = [
            f"Categories created: {len(created_categories)}",
            f"Channels created: {len(created_channels)}"
        ]
        if created_categories:
            summary.append("Categories:\n" + "\n".join(created_categories))
        if created_channels:
            summary.append("Channels:\n" + "\n".join(created_channels))
        if errors:
            summary.append("Errors:\n" + "\n".join(errors))

        return [TextContent(type="text", text="\n".join(summary))]

    # Role Management Tools
    elif name == "add_role":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        member = await guild.fetch_member(int(arguments["user_id"]))
        role = guild.get_role(int(arguments["role_id"]))
        
        await member.add_roles(role, reason="Role added via MCP")
        return [TextContent(
            type="text",
            text=f"Added role {role.name} to user {member.name}"
        )]

    elif name == "remove_role":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        member = await guild.fetch_member(int(arguments["user_id"]))
        role = guild.get_role(int(arguments["role_id"]))
        
        await member.remove_roles(role, reason="Role removed via MCP")
        return [TextContent(
            type="text",
            text=f"Removed role {role.name} from user {member.name}"
        )]

    # Channel Management Tools
    elif name == "create_text_channel":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        category = None
        if "category_id" in arguments:
            category = guild.get_channel(int(arguments["category_id"]))
        
        channel = await guild.create_text_channel(
            name=arguments["name"],
            category=category,
            topic=arguments.get("topic"),
            reason="Channel created via MCP"
        )
        
        return [TextContent(
            type="text",
            text=f"Created text channel #{channel.name} (ID: {channel.id})"
        )]

    elif name == "delete_channel":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        await channel.delete(reason=arguments.get("reason", "Channel deleted via MCP"))
        return [TextContent(
            type="text",
            text=f"Deleted channel successfully"
        )]

    # Message Reaction Tools
    elif name == "add_reaction":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        message = await channel.fetch_message(int(arguments["message_id"]))
        await message.add_reaction(arguments["emoji"])
        return [TextContent(
            type="text",
            text=f"Added reaction {arguments['emoji']} to message"
        )]

    elif name == "add_multiple_reactions":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        message = await channel.fetch_message(int(arguments["message_id"]))
        for emoji in arguments["emojis"]:
            await message.add_reaction(emoji)
        return [TextContent(
            type="text",
            text=f"Added reactions: {', '.join(arguments['emojis'])} to message"
        )]

    elif name == "remove_reaction":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        message = await channel.fetch_message(int(arguments["message_id"]))
        await message.remove_reaction(arguments["emoji"], discord_client.user)
        return [TextContent(
            type="text",
            text=f"Removed reaction {arguments['emoji']} from message"
        )]

    # Permission Management Tools
    elif name == "check_bot_permissions":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        bot_member = await guild.fetch_member(discord_client.user.id)
        
        if "channel_id" in arguments:
            channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
            permissions = channel.permissions_for(bot_member)
        else:
            permissions = bot_member.guild_permissions
        
        perm_list = [name for name, value in permissions if value]
        return [TextContent(
            type="text",
            text=f"Bot permissions: {', '.join(perm_list) if perm_list else 'No permissions'}"
        )]

    elif name == "check_member_permissions":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        member = await guild.fetch_member(int(arguments["user_id"]))
        
        if "channel_id" in arguments:
            channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
            permissions = channel.permissions_for(member)
        else:
            permissions = member.guild_permissions
        
        perm_list = [name for name, value in permissions if value]
        return [TextContent(
            type="text",
            text=f"Member {member.name} permissions: {', '.join(perm_list) if perm_list else 'No permissions'}"
        )]

    elif name == "configure_channel_permissions":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        guild = channel.guild
        
        # Parse permissions
        overwrite = discord.PermissionOverwrite()
        
        if "allow_permissions" in arguments and arguments["allow_permissions"]:
            for perm_name in arguments["allow_permissions"].split(","):
                perm_name = perm_name.strip()
                perm_value = getattr(discord.Permissions, perm_name, None)
                if perm_value is not None:
                    setattr(overwrite, perm_name, True)
        
        if "deny_permissions" in arguments and arguments["deny_permissions"]:
            for perm_name in arguments["deny_permissions"].split(","):
                perm_name = perm_name.strip()
                perm_value = getattr(discord.Permissions, perm_name, None)
                if perm_value is not None:
                    setattr(overwrite, perm_name, False)
        
        if arguments["target_type"] == "role":
            target = guild.get_role(int(arguments["target_id"]))
        else:
            target = await guild.fetch_member(int(arguments["target_id"]))
        
        await channel.set_permissions(target, overwrite=overwrite, reason="Permissions configured via MCP")
        return [TextContent(
            type="text",
            text=f"Configured permissions for {target.name if hasattr(target, 'name') else str(target)}"
        )]

    elif name == "list_discord_permissions":
        perms = [attr for attr in dir(discord.Permissions) if not attr.startswith("_") and isinstance(getattr(discord.Permissions, attr), property)]
        return [TextContent(
            type="text",
            text=f"Available Discord permissions:\n" + "\n".join(f"- {perm}" for perm in sorted(perms))
        )]

    # Webhook Management Tools
    elif name == "create_webhook":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        avatar_bytes = await fetch_avatar_bytes(arguments.get("avatar_url"))
        kwargs = {"name": arguments["name"]}
        if avatar_bytes is not None:
            kwargs["avatar"] = avatar_bytes
        webhook = await channel.create_webhook(**kwargs)
        return [TextContent(
            type="text",
            text=f"Created webhook: {webhook.name} (ID: {webhook.id}, URL: {webhook.url})"
        )]

    elif name == "list_webhooks":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        webhooks = await channel.webhooks()
        webhook_list = [f"{w.name} (ID: {w.id})" for w in webhooks]
        return [TextContent(
            type="text",
            text=f"Webhooks in channel ({len(webhooks)}):\n" + "\n".join(webhook_list) if webhook_list else "No webhooks found"
        )]

    elif name == "send_webhook_message":
        webhook = discord.Webhook.from_url(arguments["webhook_url"], client=discord_client)
        kwargs = {}
        if "username" in arguments:
            kwargs["username"] = arguments["username"]
        if "avatar_url" in arguments:
            kwargs["avatar_url"] = arguments["avatar_url"]
        
        await webhook.send(arguments["content"], **kwargs)
        return [TextContent(type="text", text="Webhook message sent successfully")]

    elif name == "modify_webhook":
        webhook = await discord_client.fetch_webhook(int(arguments["webhook_id"]))
        kwargs = {}
        if "name" in arguments:
            kwargs["name"] = arguments["name"]
        if "avatar_url" in arguments:
            avatar_bytes = await fetch_avatar_bytes(arguments["avatar_url"])
            kwargs["avatar"] = avatar_bytes
        if "channel_id" in arguments:
            kwargs["channel"] = await discord_client.fetch_channel(int(arguments["channel_id"]))
        
        await webhook.edit(**kwargs)
        return [TextContent(type="text", text=f"Modified webhook: {webhook.name}")]

    elif name == "delete_webhook":
        webhook = await discord_client.fetch_webhook(int(arguments["webhook_id"]))
        await webhook.delete(reason=arguments.get("reason", "Deleted via MCP"))
        return [TextContent(type="text", text="Webhook deleted successfully")]

    # Advanced Role Management
    elif name == "create_role":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        
        kwargs = {"name": arguments["name"], "reason": "Role created via MCP"}
        
        if "permissions" in arguments:
            perms = discord.Permissions()
            for perm_name in arguments["permissions"].split(","):
                perm_name = perm_name.strip()
                perm_value = getattr(discord.Permissions, perm_name, None)
                if perm_value is not None:
                    perms.update(**{perm_name: True})
            kwargs["permissions"] = perms
        
        if "color" in arguments:
            kwargs["color"] = discord.Color.from_str(arguments["color"])
        
        if "hoist" in arguments:
            kwargs["hoist"] = arguments["hoist"]
        
        if "mentionable" in arguments:
            kwargs["mentionable"] = arguments["mentionable"]
        
        role = await guild.create_role(**kwargs)
        return [TextContent(
            type="text",
            text=f"Created role: {role.name} (ID: {role.id})"
        )]

    elif name == "delete_role":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        role = guild.get_role(int(arguments["role_id"]))
        await role.delete(reason=arguments.get("reason", "Role deleted via MCP"))
        return [TextContent(type="text", text=f"Deleted role: {role.name}")]

    elif name == "modify_role":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        role = guild.get_role(int(arguments["role_id"]))
        
        kwargs = {"reason": "Role modified via MCP"}
        
        if "name" in arguments:
            kwargs["name"] = arguments["name"]
        
        if "permissions" in arguments:
            perms = discord.Permissions()
            for perm_name in arguments["permissions"].split(","):
                perm_name = perm_name.strip()
                perm_value = getattr(discord.Permissions, perm_name, None)
                if perm_value is not None:
                    perms.update(**{perm_name: True})
            kwargs["permissions"] = perms
        
        if "color" in arguments:
            kwargs["color"] = discord.Color.from_str(arguments["color"])
        
        if "hoist" in arguments:
            kwargs["hoist"] = arguments["hoist"]
        
        if "mentionable" in arguments:
            kwargs["mentionable"] = arguments["mentionable"]
        
        if "position" in arguments:
            kwargs["position"] = int(arguments["position"])
        
        await role.edit(**kwargs)
        return [TextContent(type="text", text=f"Modified role: {role.name}")]

    elif name == "list_roles":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        # Sort roles by position (highest first) to show hierarchy
        sorted_roles = sorted([r for r in guild.roles if not r.is_default()], key=lambda r: r.position, reverse=True)
        roles = []
        for i, r in enumerate(sorted_roles, 1):
            role_info = f"{i}. {r.name} (ID: {r.id}, Position: {r.position}, Members: {len(r.members)})"
            if r.color.value != 0:
                role_info += f", Color: {r.color}"
            roles.append(role_info)
        return [TextContent(
            type="text",
            text=f"Server roles ({len(sorted_roles)} total, excluding @everyone):\n" + "\n".join(roles)
        )]

    elif name == "get_role_info":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        role = guild.get_role(int(arguments["role_id"]))
        info = {
            "name": role.name,
            "id": str(role.id),
            "color": str(role.color),
            "hoist": role.hoist,
            "mentionable": role.mentionable,
            "position": role.position,
            "members": len(role.members),
            "permissions": [name for name, value in role.permissions if value]
        }
        return [TextContent(
            type="text",
            text=f"Role information:\n" + "\n".join(f"{k}: {v}" for k, v in info.items())
        )]

    elif name == "set_role_hierarchy":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        reason = arguments.get("reason", "Role hierarchy updated via MCP")
        
        # Determine if we're using role names or IDs
        if "role_names" in arguments and arguments["role_names"]:
            # Look up roles by name (case-insensitive)
            role_names = arguments["role_names"]
            roles_to_reorder = []
            not_found = []
            
            for role_name in role_names:
                # Try exact match first
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    # Try case-insensitive match
                    for r in guild.roles:
                        if r.name.lower() == role_name.lower():
                            role = r
                            break
                
                if not role:
                    not_found.append(role_name)
                elif role.is_default():
                    raise ValueError(f"Cannot reorder @everyone role")
                else:
                    roles_to_reorder.append(role)
            
            if not_found:
                raise ValueError(f"Roles not found: {', '.join(not_found)}")
            
            role_ids = [r.id for r in roles_to_reorder]
        elif "role_ids" in arguments and arguments["role_ids"]:
            # Use role IDs as before
            role_ids = [int(rid) for rid in arguments["role_ids"]]
            roles_to_reorder = []
            for role_id in role_ids:
                role = guild.get_role(role_id)
                if not role:
                    raise ValueError(f"Role with ID {role_id} not found")
                if role.is_default():
                    raise ValueError("Cannot reorder @everyone role")
                roles_to_reorder.append(role)
        else:
            raise ValueError("Either 'role_ids' or 'role_names' must be provided")
        
        # Get bot's role to exclude it from reordering (bots can't edit their own role position)
        bot_member = await guild.fetch_member(discord_client.user.id)
        bot_role = bot_member.top_role if bot_member else None
        bot_role_id = bot_role.id if bot_role else None
        
        # Filter out bot's own role from roles to reorder
        original_count = len(roles_to_reorder)
        roles_to_reorder = [r for r in roles_to_reorder if r.id != bot_role_id]
        skipped_bot_role = original_count > len(roles_to_reorder)
        
        if not roles_to_reorder:
            return [TextContent(
                type="text",
                text="No roles to reorder. Note: The bot's own role cannot be reordered by the bot itself."
            )]
        
        # Refresh guild to get latest role positions
        await guild.chunk()
        
        # Get all roles and their current positions
        all_roles = sorted([r for r in guild.roles if not r.is_default()], key=lambda r: r.position, reverse=True)
        
        # Get bot's role position - we can only manage roles below this
        bot_role_position = bot_role.position if bot_role else 999
        
        # Get roles not being reordered and find their max position
        role_ids_to_reorder = [r.id for r in roles_to_reorder]
        other_roles = [r for r in all_roles if r.id not in role_ids_to_reorder and r.id != bot_role_id]
        other_max_position = max((r.position for r in other_roles), default=0) if other_roles else 0
        
        # Calculate new positions
        # First role in list = highest position, last = lowest
        # Ensure all positions are below bot's role position
        # The highest position we can assign is bot_role_position - 1
        # Start from the highest available position
        new_positions = {}
        
        # Calculate start position: bot's position - 1, but ensure we have room for all roles
        # If there are other roles, we need to place our roles above them
        if other_roles:
            # Place reordered roles above other roles
            start_position = min(bot_role_position - 1, other_max_position + len(roles_to_reorder))
        else:
            # No other roles, start from bot's position - 1
            start_position = bot_role_position - 1
        
        # Ensure start_position is at least 1
        start_position = max(1, start_position)
        
        # Assign positions: first role gets highest position
        for i, role in enumerate(roles_to_reorder):
            new_positions[role.id] = start_position - i
        
        # Update roles from lowest to highest position to avoid conflicts
        updated_roles = []
        errors = []
        
        # Sort by new position (ascending - lowest first)
        roles_by_new_pos = sorted(roles_to_reorder, key=lambda r: new_positions[r.id])
        
        for role in roles_by_new_pos:
            try:
                await role.edit(position=new_positions[role.id], reason=reason)
                updated_roles.append(f"{role.name} (position: {new_positions[role.id]})")
            except discord.Forbidden:
                errors.append(f"{role.name}: Missing permissions (bot role may be too low)")
                updated_roles.append(f"{role.name} (error: Missing permissions)")
            except Exception as e:
                errors.append(f"{role.name}: {str(e)}")
                updated_roles.append(f"{role.name} (error: {str(e)})")
        
        hierarchy_list = "\n".join(f"{i+1}. {r.name} (ID: {r.id})" for i, r in enumerate(roles_to_reorder))
        result_text = f"Role hierarchy updated:\n\nNew order (highest to lowest):\n{hierarchy_list}\n\nUpdated roles:\n" + "\n".join(updated_roles)
        
        if skipped_bot_role and bot_role:
            result_text += f"\n\nNote: {bot_role.name} (bot's role) was skipped - bots cannot edit their own role position."
        
        if errors:
            result_text += f"\n\nNote: Some roles could not be updated. The bot's role must be higher than roles it manages."
        
        return [TextContent(type="text", text=result_text)]

    # Advanced Channel Management
    elif name == "list_channels":
        server_id = int(arguments["server_id"])
        channel_type = arguments.get("channel_type", "all")
        
        # Use cached guild object which has channels in cache
        guild = discord_client.get_guild(server_id)
        if not guild:
            # Fallback to fetching if not in cache
            guild = await discord_client.fetch_guild(server_id)
        
        channels = []
        # guild.channels is a cached property that should work if bot has proper intents
        all_channels = list(guild.channels)
        
        # If still no channels, try to get them from the guild's channel cache
        if not all_channels:
            # Try accessing channels through different methods
            try:
                # Get all text channels
                text_channels = [ch for ch in guild.text_channels] if hasattr(guild, 'text_channels') else []
                # Get all voice channels
                voice_channels = [ch for ch in guild.voice_channels] if hasattr(guild, 'voice_channels') else []
                # Get all categories
                categories = [ch for ch in guild.categories] if hasattr(guild, 'categories') else []
                all_channels = text_channels + voice_channels + categories
            except Exception as e:
                logger.warning(f"Could not get channels: {e}")
        
        for channel in sorted(all_channels, key=lambda c: (c.position if hasattr(c, 'position') else 0, c.name)):
            channel_info = f"{channel.name} (ID: {channel.id})"
            if hasattr(channel, 'category') and channel.category:
                channel_info += f" [Category: {channel.category.name}]"
            
            if channel_type == "all":
                channels.append(f"{channel_info} - {channel.type.name}")
            elif channel_type == "text" and isinstance(channel, discord.TextChannel):
                channels.append(channel_info)
            elif channel_type == "voice" and isinstance(channel, discord.VoiceChannel):
                channels.append(channel_info)
            elif channel_type == "category" and isinstance(channel, discord.CategoryChannel):
                channels.append(channel_info)
        
        return [TextContent(
            type="text",
            text=f"Channels ({len(channels)}):\n" + "\n".join(channels) if channels else "No channels found"
        )]

    elif name == "get_channel_info":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        info = {
            "name": channel.name,
            "id": str(channel.id),
            "type": channel.type.name,
            "created_at": channel.created_at.isoformat() if hasattr(channel, "created_at") else None
        }
        
        if isinstance(channel, discord.TextChannel):
            info["topic"] = channel.topic
            info["nsfw"] = channel.nsfw
            info["slowmode_delay"] = channel.slowmode_delay
        
        return [TextContent(
            type="text",
            text=f"Channel information:\n" + "\n".join(f"{k}: {v}" for k, v in info.items() if v is not None)
        )]

    elif name == "modify_channel":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        
        kwargs = {"reason": "Channel modified via MCP"}
        
        if "name" in arguments:
            kwargs["name"] = arguments["name"]
        if "topic" in arguments and isinstance(channel, discord.TextChannel):
            kwargs["topic"] = arguments["topic"]
        if "nsfw" in arguments and isinstance(channel, discord.TextChannel):
            kwargs["nsfw"] = arguments["nsfw"]
        if "slowmode_delay" in arguments and isinstance(channel, discord.TextChannel):
            kwargs["slowmode_delay"] = arguments["slowmode_delay"]
        if "category_id" in arguments:
            if arguments["category_id"]:
                category = await discord_client.fetch_channel(int(arguments["category_id"]))
                if not isinstance(category, discord.CategoryChannel):
                    raise ValueError("category_id must be a category channel")
                kwargs["category"] = category
            else:
                kwargs["category"] = None
        
        if "position" in arguments:
            kwargs["position"] = int(arguments["position"])
        
        await channel.edit(**kwargs)
        return [TextContent(type="text", text=f"Modified channel: {channel.name}")]

    elif name == "create_voice_channel":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        
        kwargs = {"name": arguments["name"], "reason": "Voice channel created via MCP"}
        
        if "category_id" in arguments:
            kwargs["category"] = guild.get_channel(int(arguments["category_id"]))
        if "bitrate" in arguments:
            kwargs["bitrate"] = arguments["bitrate"]
        if "user_limit" in arguments:
            kwargs["user_limit"] = arguments["user_limit"]
        
        channel = await guild.create_voice_channel(**kwargs)
        return [TextContent(
            type="text",
            text=f"Created voice channel: {channel.name} (ID: {channel.id})"
        )]

    # Advanced Message Features
    elif name == "edit_message":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        message = await channel.fetch_message(int(arguments["message_id"]))
        await message.edit(content=arguments["content"])
        return [TextContent(type="text", text="Message edited successfully")]

    elif name == "pin_message":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        message = await channel.fetch_message(int(arguments["message_id"]))
        await message.pin()
        return [TextContent(type="text", text="Message pinned successfully")]

    elif name == "unpin_message":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        message = await channel.fetch_message(int(arguments["message_id"]))
        await message.unpin()
        return [TextContent(type="text", text="Message unpinned successfully")]

    elif name == "get_message":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        message = await channel.fetch_message(int(arguments["message_id"]))
        info = {
            "id": str(message.id),
            "author": str(message.author),
            "content": message.content,
            "timestamp": message.created_at.isoformat(),
            "pinned": message.pinned,
            "edited": message.edited_at.isoformat() if message.edited_at else None
        }
        return [TextContent(
            type="text",
            text=f"Message information:\n" + "\n".join(f"{k}: {v}" for k, v in info.items() if v is not None)
        )]

    elif name == "bulk_delete_messages":
        channel = await discord_client.fetch_channel(int(arguments["channel_id"]))
        message_ids = [int(mid) for mid in arguments["message_ids"]]
        messages = [await channel.fetch_message(mid) for mid in message_ids]
        await channel.delete_messages(messages, reason=arguments.get("reason", "Bulk deleted via MCP"))
        return [TextContent(type="text", text=f"Deleted {len(messages)} messages successfully")]

    # User Management Tools
    elif name == "ban_user":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        user = await discord_client.fetch_user(int(arguments["user_id"]))
        
        kwargs = {"reason": arguments.get("reason", "Banned via MCP")}
        if "delete_message_days" in arguments:
            kwargs["delete_message_days"] = arguments["delete_message_days"]
        
        await guild.ban(user, **kwargs)
        return [TextContent(type="text", text=f"Banned user: {user.name}")]

    elif name == "unban_user":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        user = await discord_client.fetch_user(int(arguments["user_id"]))
        await guild.unban(user, reason=arguments.get("reason", "Unbanned via MCP"))
        return [TextContent(type="text", text=f"Unbanned user: {user.name}")]

    elif name == "kick_user":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        member = await guild.fetch_member(int(arguments["user_id"]))
        await member.kick(reason=arguments.get("reason", "Kicked via MCP"))
        return [TextContent(type="text", text=f"Kicked user: {member.name}")]

    elif name == "modify_member":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        member = await guild.fetch_member(int(arguments["user_id"]))
        
        kwargs = {"reason": arguments.get("reason", "Member modified via MCP")}
        
        if "nickname" in arguments:
            kwargs["nick"] = arguments["nickname"] if arguments["nickname"] else None
        
        if "timeout_minutes" in arguments:
            if arguments["timeout_minutes"] > 0:
                timeout_until = discord.utils.utcnow() + timedelta(minutes=arguments["timeout_minutes"])
                kwargs["timed_out_until"] = timeout_until
            else:
                kwargs["timed_out_until"] = None
        
        await member.edit(**kwargs)
        return [TextContent(type="text", text=f"Modified member: {member.name}")]

    elif name == "get_member_info":
        guild = await discord_client.fetch_guild(int(arguments["server_id"]))
        member = await guild.fetch_member(int(arguments["user_id"]))
        
        info = {
            "id": str(member.id),
            "name": member.name,
            "nickname": member.nick,
            "joined_at": member.joined_at.isoformat() if member.joined_at else None,
            "roles": [r.name for r in member.roles[1:]],  # Skip @everyone
            "top_role": member.top_role.name if member.top_role else None,
            "timed_out_until": member.timed_out_until.isoformat() if member.timed_out_until else None,
            "permissions": [name for name, value in member.guild_permissions if value]
        }
        
        return [TextContent(
            type="text",
            text=f"Member information:\n" + "\n".join(f"{k}: {v}" for k, v in info.items() if v is not None)
        )]

    raise ValueError(f"Unknown tool: {name}")

async def main():
    # Start Discord bot in the background with error handling
    async def start_bot():
        try:
            await bot.start(DISCORD_TOKEN)
        except Exception as e:
            logger.error(f"Failed to start Discord bot: {e}")
            raise
    
    bot_task = asyncio.create_task(start_bot())
    
    # Give bot a moment to start connecting
    await asyncio.sleep(0.1)
    
    # Run MCP server
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
