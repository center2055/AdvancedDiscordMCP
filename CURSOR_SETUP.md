# MCP Client Setup Guide

## Quick Setup Steps

1. **Open your MCP client's settings/configuration**
   - Locate the MCP server configuration section
   - Add a new MCP server entry

2. **Configure the MCP Server**
   - **Name:** `discord` (or any name you prefer)
   - **Type:** `stdio`
   - **Command:** Path to your Python executable
     ```
     D:\path\to\mcp-discord-main\venv\Scripts\python.exe
     ```
     Or on macOS/Linux:
     ```
     /path/to/mcp-discord-main/venv/bin/python
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
     - Add environment variable:
       - **Name:** `DISCORD_TOKEN`
       - **Value:** `your_bot_token_here`

3. **Save and Restart your MCP client**
   - Save the configuration
   - Restart your MCP client to apply changes

4. **Verify Connection**
   - Check your MCP client's connection status
   - Verify that the discord server shows as connected

## Testing the Setup

You can test if the server works by running:
```powershell
cd "D:\path\to\mcp-discord-main"
$env:DISCORD_TOKEN="your_bot_token_here"
.\venv\Scripts\python.exe -m discord_mcp
```

## Troubleshooting

- **Token Errors:** Verify your Discord bot token is correct
- **Permission Issues:** Ensure the bot has proper permissions in your Discord server
- **Connection Issues:** Check that all required intents are enabled in Discord Developer Portal:
  - MESSAGE CONTENT INTENT
  - PRESENCE INTENT
  - SERVER MEMBERS INTENT
