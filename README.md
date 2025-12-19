# Discord MCP Server

A Model Context Protocol (MCP) server that provides Discord integration capabilities to MCP clients.

**Note**: This is an **enhanced fork** of the original [mcp-discord](https://github.com/pashpashpash/mcp-discord) repository with an **immense amount of new features** added.

## Features

### Server Information
- `list_servers`: List all Discord servers (guilds) the bot is a member of
- `get_server_info`: Get detailed server information
- `list_members`: List server members and their roles
- `get_server_settings`: Retrieve current server configuration
- `modify_server_settings`: Update server name, description, icon, banner, verification, notifications, AFK, system channel, explicit content filter, and locale

### Message Management
- `send_message`: Send a message to a channel
- `read_messages`: Read recent message history
- `edit_message`: Edit an existing message
- `get_message`: Get a specific message by ID
- `add_reaction`: Add a reaction to a message
- `add_multiple_reactions`: Add multiple reactions to a message
- `remove_reaction`: Remove a reaction from a message
- `pin_message`: Pin a message in a channel
- `unpin_message`: Unpin a message from a channel
- `moderate_message`: Delete messages and timeout users
- `bulk_delete_messages`: Delete multiple messages at once (2-100 messages)

### Channel Management
- `create_text_channel`: Create a new text channel
- `create_voice_channel`: Create a new voice channel
- `list_channels`: List all channels in a server (shows categories and sorts channels)
- `get_channel_info`: Get detailed information about a channel
- `modify_channel`: Modify channel properties (name, topic, permissions, category, etc.)
- `delete_channel`: Delete an existing channel

### Role Management
- `create_role`: Create a new role in a server
- `delete_role`: Delete a role from a server
- `modify_role`: Modify role properties (name, color, permissions, position, etc.)
- `list_roles`: List all roles in a server with details (includes position information)
- `get_role_info`: Get detailed information about a specific role
- `set_role_hierarchy`: Set the role hierarchy by specifying role order (from highest to lowest)
  - Supports both role IDs and role names (case-insensitive)
  - Automatically handles bot role restrictions
  - Intelligently calculates positions below the bot's role
- `add_role`: Add a role to a user
- `remove_role`: Remove a role from a user

### Permission Management
- `check_bot_permissions`: Check what permissions the bot has in a channel or server
- `check_member_permissions`: Check what permissions a member has in a channel or server
- `configure_channel_permissions`: Configure permissions for a role or member in a channel
- `list_discord_permissions`: List all available Discord permissions with descriptions

### Invite Management
- `create_invite`: Create channel invites with usage limits and expiration
- `list_invites`: List active server invites
- `get_invite_info`: Get details about an invite
- `delete_invite`: Revoke an invite

### Auto-Moderation & Rules
- `create_automod_rule`: Create auto-moderation rules
- `list_automod_rules`: List auto-moderation rules
- `modify_automod_rule`: Update auto-moderation rules
- `delete_automod_rule`: Delete auto-moderation rules

### Thread Management
- `create_thread`: Create threads from messages or standalone
- `list_threads`: List active or archived threads
- `archive_thread`: Archive a thread
- `unarchive_thread`: Unarchive a thread
- `delete_thread`: Delete a thread

### Category Management
- `create_category`: Create channel categories
- `modify_category`: Modify category name, position, or permissions
- `delete_category`: Delete categories (optionally moving channels)

### Emoji & Sticker Management
- `create_emoji`: Create custom emojis
- `list_emojis`: List server emojis
- `delete_emoji`: Delete custom emojis
- `create_sticker`: Create custom stickers
- `list_stickers`: List server stickers
- `delete_sticker`: Delete custom stickers

### Webhook Management
- `create_webhook`: Create a new webhook
- `list_webhooks`: List webhooks in a channel
- `send_webhook_message`: Send messages via webhook
- `modify_webhook`: Update webhook settings
- `delete_webhook`: Delete a webhook

### User Management
- `get_user_info`: Get information about a Discord user
- `get_member_info`: Get detailed information about a server member
- `modify_member`: Modify member properties (nickname, timeout, etc.)
- `ban_user`: Ban a user from the server
- `unban_user`: Unban a user from the server
- `kick_user`: Kick a user from the server

## 🆕 New Features in This Fork

This enhanced fork includes **extensive new features** beyond the original project:

### Recent Improvements
- **Enhanced `list_channels`**: Now displays channel categories and sorts channels by position
- **Category Support in `modify_channel`**: Move channels between categories or remove them from categories
- **`list_servers` Tool**: List all servers the bot is a member of
- **Role Hierarchy Management**: Enhanced `set_role_hierarchy` tool with improved position calculation and automatic bot role handling
  - Supports both role IDs and role names (case-insensitive matching)
  - Automatically skips the bot's own role (bots cannot edit their own role position)
  - Intelligently calculates positions to ensure roles are placed below the bot's role
  - Handles permission errors gracefully when roles are above the bot's position
- **Enhanced `list_roles`**: Now displays role positions to help visualize hierarchy
- **Position Support in `modify_role`**: Set individual role positions to control hierarchy

### Permission Management
- `check_bot_permissions`: Check what permissions the bot has in a channel or server
- `check_member_permissions`: Check what permissions a member has in a channel or server
- `configure_channel_permissions`: Configure permissions for a role or member in a channel
- `list_discord_permissions`: List all available Discord permissions with descriptions

### Bulk Operations
- `bulk_add_roles`: Add a role to multiple users
- `bulk_modify_members`: Update multiple members (nickname, timeout) in one call

### Smart Search & Filtering
- `search_messages`: Search messages by content, author, or date range within channels
- `find_members_by_criteria`: Find members by role, join date, name, or bot status

### Scheduled Tasks
- `schedule_task`: Schedule a supported task to run later
- `send_scheduled_message`: Schedule a message to be sent later

### Analytics
- `generate_server_analytics`: Generate basic server analytics
- `generate_channel_analytics`: Generate basic analytics for a channel

### Automation Rules
- `create_automation_rule`: Create an automation rule definition

### Templates
- `create_message_template`: Create a reusable message template
- `create_role_template`: Create a reusable role template

### Smart Moderation & Analysis
- `analyze_message_patterns`: Analyze message patterns for spam indicators
- `auto_moderate_by_pattern`: Auto-moderate messages based on simple spam patterns

### Advanced Analytics
- `track_metrics`: Track custom metrics over time
- `export_data`: Export stored data (metrics, templates, automation rules)

### Channel Organization
- `auto_organize_channels`: Move inactive channels into a target category
- `create_channel_structure`: Create channel structure from a template

## Prerequisites

1. **Set up your Discord bot**:
   - Create a new application at [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a bot and copy the token
   - Enable required privileged intents:
     - MESSAGE CONTENT INTENT
     - PRESENCE INTENT
     - SERVER MEMBERS INTENT
   - Invite the bot to your server using OAuth2 URL Generator

2. **Python Requirements**:
   - Python 3.10 or higher
   - pip (Python package installer)

## Installation

1. **Clone the Repository**:
   ```bash
   git clone <your-repo-url>
   cd mcp-discord-main
   ```

2. **Create and Activate Virtual Environment**:
   ```bash
   # On Windows
   python -m venv venv
   venv\Scripts\activate

   # On macOS/Linux
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies**:
   ```bash
   pip install -e .
   ```
   Note: If using Python 3.13+, also install audioop: `pip install audioop-lts`

4. **Configure your MCP Client**:

Add this to your MCP client configuration file:

```json
{
  "mcpServers": {
    "discord": {
      "command": "python",
      "args": ["-m", "discord_mcp"],
      "cwd": "path/to/mcp-discord-main",
      "env": {
        "DISCORD_TOKEN": "your_bot_token"
      }
    }
  }
}
```

Note:
- Replace "path/to/mcp-discord-main" with the actual path to your cloned repository
- Replace "your_bot_token" with your Discord bot token
- Consult your MCP client's documentation for the exact configuration file location

## Debugging

If you run into issues, check your MCP client's logs for detailed error messages.

Common issues:

1. **Token Errors**:
   - Verify your Discord bot token is correct
   - Check that all required intents are enabled

2. **Permission Issues**:
   - Ensure the bot has proper permissions in your Discord server
   - Verify the bot's role hierarchy for role management commands

3. **Installation Issues**:
   - Make sure you're using the correct Python version
   - Try recreating the virtual environment
   - Check that all dependencies are installed correctly

## License

GNU General Public License v3.0 (GPLv3) - see LICENSE file for details.

---

**Note**: This is an enhanced fork of the original [mcp-discord](https://github.com/pashpashpash/mcp-discord) repository with extensive new features added.
