# Discord MCP Server (Enhanced Fork)

A powerful Model Context Protocol (MCP) server that provides comprehensive Discord integration capabilities to MCP clients like Cursor and Claude Desktop. This is an **enhanced fork** of the original [mcp-discord](https://github.com/pashpashpash/mcp-discord) project with an **immense amount of new features** added.

## 🚀 What is This?

This Discord MCP Server allows AI assistants (like those in Cursor IDE or Claude Desktop) to interact with and manage Discord servers directly through the Model Context Protocol. You can perform server management, moderation, analytics, automation, and much more - all through natural language commands to your AI assistant.

## ✨ New Features in This Fork

This fork includes **extensive enhancements** beyond the original project:

### 📊 Analytics & Insights
- **Server Analytics**: Generate comprehensive server statistics (members, channels, roles, emojis, etc.)
- **Channel Analytics**: Analyze message patterns, top authors, engagement metrics
- **Message Pattern Analysis**: Detect spam indicators, repeated messages, link spam, mention spam
- **Custom Metrics Tracking**: Track and export custom metrics over time

### 🔍 Advanced Search & Filtering
- **Message Search**: Search across multiple channels by content, author, date range
- **Member Search**: Find members by role, join date, name, bot status with complex criteria
- **Multi-channel Search**: Search across multiple channels simultaneously

### ⚡ Bulk Operations
- **Bulk Role Assignment**: Add roles to multiple users at once
- **Bulk Member Modification**: Update nicknames, timeouts for multiple members simultaneously

### ⏰ Scheduled Tasks
- **Scheduled Messages**: Schedule messages to be sent at specific times
- **Task Scheduling**: Schedule any supported task (send_message, bulk_add_roles, etc.) for later execution
- **Flexible Timing**: Use ISO timestamps or delay in seconds

### 🤖 Automation & Templates
- **Automation Rules**: Create rules that trigger on events (member_join, message_contains, reaction_added)
- **Message Templates**: Create reusable message templates with placeholders
- **Role Templates**: Save and reuse role configurations
- **Auto-execution**: Automation rules automatically execute when events occur

### 🛡️ Smart Moderation
- **Pattern-based Auto-moderation**: Automatically detect and moderate spam patterns
- **Configurable Actions**: Delete, timeout, or report based on detected patterns
- **Dry-run Mode**: Test moderation rules before applying them

### 📁 Channel Organization
- **Auto-organize Channels**: Automatically move inactive channels to categories
- **Channel Structure Creation**: Create entire channel hierarchies from templates
- **Bulk Channel Management**: Organize multiple channels at once

### 📤 Data Export
- **Export Templates**: Export message and role templates as JSON
- **Export Metrics**: Export tracked metrics data
- **Export Automation Rules**: Export automation rule configurations

## 📋 Original Features

All original features are preserved:
- Server information and settings management
- Channel and category management
- Message management (send, read, edit, delete)
- Member management (kick, ban, timeout, modify)
- Role management
- Invite management
- Thread management
- Auto-moderation rules
- Emoji and sticker management
- Webhook management
- Permission management

## 🛠️ Prerequisites

1. **Set up your Discord bot**:
   - Create a new application at [Discord Developer Portal](https://discord.com/developers/applications)
   - Create a bot and copy the token
   - **Enable required privileged intents** (CRITICAL):
     - ✅ **MESSAGE CONTENT INTENT**
     - ✅ **SERVER MEMBERS INTENT**
     - ✅ **PRESENCE INTENT** (optional but recommended)
   - Invite the bot to your server using OAuth2 URL Generator with appropriate permissions

2. **Python Requirements**:
   - Python 3.10 or higher
   - pip (Python package installer)

## 📦 Installation

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
   
   **Note**: If using Python 3.13+, also install audioop:
   ```bash
   pip install audioop-lts
   ```

## ⚙️ Configuration

### For Cursor IDE

1. **Open Cursor Settings**:
   - Go to `Settings` → `Features` → `MCP`
   - Click `+ Add New MCP Server`

2. **Configure the MCP Server**:
   - **Name:** `discord` (or any name you prefer)
   - **Type:** `stdio`
   - **Command:** Path to your Python executable
     ```
     D:\path\to\mcp-discord-main\venv\Scripts\python.exe
     ```
   - **Args:** 
     ```
     -m
     discord_mcp
     ```
   - **Working Directory (cwd):**
     ```
     D:\path\to\mcp-discord-main
     ```
   - **Environment Variables:**
     - **Name:** `DISCORD_TOKEN`
     - **Value:** Your Discord bot token

3. **Save and Restart Cursor**

### For Claude Desktop

Add this to your `claude_desktop_config.json`:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%/Claude/claude_desktop_config.json`

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

**Note**: 
- Replace `"path/to/mcp-discord-main"` with the actual path to your cloned repository
- Replace `"your_bot_token"` with your Discord bot token

## 🎯 Usage Examples

Once configured, you can use natural language commands with your AI assistant:

### Basic Operations
- "Get information about my Discord server"
- "List all channels in the server"
- "Send a message to #general saying hello"
- "Create a new role called Moderator with kick and ban permissions"

### Advanced Features
- "Generate analytics for my server"
- "Search for messages containing 'test' in the last week"
- "Find all members who joined in the last month"
- "Schedule a message to be sent tomorrow at 3 PM"
- "Create an automation rule to welcome new members"
- "Analyze message patterns in #general for spam"
- "Auto-organize inactive channels into an 'Archive' category"

### Bulk Operations
- "Add the Member role to users [list of IDs]"
- "Timeout these users for 10 minutes: [user IDs]"

## 🔧 Troubleshooting

### Common Issues

1. **"Discord client not ready" Error**:
   - Ensure privileged intents are enabled in Discord Developer Portal
   - Wait 10-30 seconds after starting Cursor for the bot to connect
   - Verify your bot token is correct

2. **"No server info found" Error**:
   - Check that the MCP server is properly configured in Cursor settings
   - Verify the Python path and working directory are correct
   - Ensure the `discord_mcp` module can be imported

3. **Token Errors**:
   - Verify your Discord bot token is correct
   - Ensure the bot hasn't been deleted or regenerated

4. **Permission Issues**:
   - Ensure the bot has proper permissions in your Discord server
   - Check that required intents are enabled:
     - MESSAGE CONTENT INTENT
     - SERVER MEMBERS INTENT
     - PRESENCE INTENT

5. **Module Import Errors**:
   - Make sure you've installed dependencies: `pip install -e .`
   - Verify you're using the correct Python environment

### Debugging

Check Cursor's MCP logs for detailed error messages:
- Look for MCP-related errors in Cursor's output panel
- The bot connection status should appear in logs

## 📚 Feature Documentation

### Automation Rules

Create rules that automatically execute when events occur:

```python
# Example: Welcome new members
{
  "name": "Welcome New Members",
  "trigger_type": "member_join",
  "action_type": "send_message",
  "action_payload": {
    "channel_id": "123456789",
    "content": "Welcome {user} to {server}! 🎉"
  }
}
```

### Scheduled Tasks

Schedule any task to run later:

```python
# Schedule a message
{
  "task_type": "send_message",
  "task_payload": {
    "channel_id": "123456789",
    "content": "Scheduled announcement!"
  },
  "run_at": "2025-12-20T15:00:00Z"  # ISO timestamp
}
```

### Message Templates

Create reusable message templates:

```python
{
  "template_name": "welcome",
  "content": "Welcome {user}! We're glad to have you here!"
}
```

### Analytics

Generate comprehensive analytics:

- **Server Analytics**: Member counts, channel breakdowns, role statistics
- **Channel Analytics**: Message counts, top authors, engagement metrics
- **Pattern Analysis**: Spam detection, repeated message analysis

## 🤝 Credits

This project is a fork of the original [mcp-discord](https://github.com/pashpashpash/mcp-discord) project by [pashpashpash](https://github.com/pashpashpash).

### Original Project
- Repository: https://github.com/pashpashpash/mcp-discord
- Original author: pashpashpash

### Enhancements in This Fork
This fork adds extensive new features including:
- Advanced analytics and insights
- Smart search and filtering
- Bulk operations
- Scheduled tasks
- Automation rules
- Message and role templates
- Pattern-based moderation
- Channel organization tools
- Data export capabilities

## 📝 License

This project maintains the same license as the original project. Please refer to the LICENSE file for details.

## 🐛 Reporting Issues

If you encounter any issues or have feature requests, please:
1. Check existing issues in the repository
2. Create a new issue with detailed information about the problem
3. Include error messages, configuration details, and steps to reproduce

## 🔄 Contributing

Contributions are welcome! This fork is actively maintained with new features being added regularly.

---

**Note**: This is an enhanced fork with significant additions. For the original project, please visit the [original repository](https://github.com/pashpashpash/mcp-discord).
