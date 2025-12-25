# Discord Changelog Automation Setup

This guide shows you how to set up automated changelog messages in your Discord server using webhooks.

## Quick Setup

### Step 1: Create a Changelog Channel

You can create a channel using the MCP Discord tools:

```python
# Using MCP Discord
create_text_channel(
    server_id="YOUR_SERVER_ID",
    name="changelog",
    topic="Project updates and changelogs"
)
```

Or create it manually in Discord.

### Step 2: Create a Webhook

Create a webhook in your changelog channel:

```python
# Using MCP Discord
create_webhook(
    channel_id="YOUR_CHANGELOG_CHANNEL_ID",
    name="Changelog Bot"
)
```

**Important**: Save the webhook URL that's returned! It will look like:
```
https://discord.com/api/webhooks/123456789/abcdefghijklmnopqrstuvwxyz
```

### Step 3: Set Up Integration

Choose one of the integration methods below:

## Integration Methods

### Method 1: GitHub Actions (Recommended)

1. Add the webhook URL as a GitHub secret:
   - Go to your repository → Settings → Secrets and variables → Actions
   - Add a new secret named `DISCORD_WEBHOOK_URL` with your webhook URL

2. The workflow file (`.github/workflows/discord-changelog.yml`) is already set up!

3. It will automatically send changelogs when you:
   - **Publish a GitHub Release** - Uses the release tag and body
   - **Manually trigger** - Use "Run workflow" with version and changelog inputs

### Method 2: Manual Script

Use the `send_changelog.py` script directly:

```bash
# Basic usage
python send_changelog.py \
  --webhook-url "YOUR_WEBHOOK_URL" \
  --version "1.2.3" \
  --changelog "Fixed bugs and added new features"

# From a changelog file
python send_changelog.py \
  --webhook-url "YOUR_WEBHOOK_URL" \
  --version "1.2.3" \
  --changelog-file "CHANGELOG.md"

# With custom styling
python send_changelog.py \
  --webhook-url "YOUR_WEBHOOK_URL" \
  --version "1.2.3" \
  --changelog "New features!" \
  --project-name "My Awesome Project" \
  --color 0xff0000 \
  --author-name "Your Name" \
  --thumbnail "https://example.com/logo.png"
```

### Method 3: CI/CD Integration

Add to your CI/CD pipeline (GitLab CI, Jenkins, etc.):

```yaml
# Example for GitLab CI
send_changelog:
  stage: deploy
  script:
    - pip install requests
    - |
      python send_changelog.py \
        --webhook-url "$DISCORD_WEBHOOK_URL" \
        --version "$CI_COMMIT_TAG" \
        --changelog "$(cat CHANGELOG.md)" \
        --project-name "$CI_PROJECT_NAME"
  only:
    - tags
```

### Method 4: npm/pip/packagist Scripts

Add to your `package.json`:

```json
{
  "scripts": {
    "discord:changelog": "python send_changelog.py --webhook-url $DISCORD_WEBHOOK_URL --version $npm_package_version --changelog-file CHANGELOG.md"
  }
}
```

Or in `setup.py`/`pyproject.toml`:

```python
# In your release script
import subprocess
subprocess.run([
    "python", "send_changelog.py",
    "--webhook-url", os.getenv("DISCORD_WEBHOOK_URL"),
    "--version", version,
    "--changelog-file", "CHANGELOG.md"
])
```

## Changelog Format

The script supports Markdown formatting. Example:

```markdown
## 🎉 New Features
- Added dark mode support
- New dashboard interface

## 🐛 Bug Fixes
- Fixed login issue
- Resolved memory leak

## 🔧 Improvements
- Performance optimizations
- Updated dependencies
```

## Advanced Options

### Custom Colors

Use hex colors for different types of releases:

- `0x00ff00` - Green (default, for stable releases)
- `0xff0000` - Red (for breaking changes)
- `0xffa500` - Orange (for beta releases)
- `0x5865F2` - Discord blurple (for GitHub releases)

### Embed Customization

```bash
python send_changelog.py \
  --webhook-url "WEBHOOK_URL" \
  --version "1.2.3" \
  --changelog "Updates" \
  --project-name "My Project" \
  --author-name "Developer" \
  --author-url "https://github.com/username" \
  --author-icon "https://github.com/username.png" \
  --thumbnail "https://example.com/logo.png" \
  --footer "Released via CI/CD" \
  --footer-icon "https://example.com/icon.png" \
  --color 0x00ff00
```

## Security Notes

⚠️ **Important**: Never commit webhook URLs to your repository!

- Use environment variables or secrets management
- GitHub: Use Secrets and variables → Actions
- GitLab: Use CI/CD variables (masked)
- Local: Use `.env` file (add to `.gitignore`)

## Troubleshooting

### Webhook URL not working
- Check that the webhook URL is correct
- Verify the webhook hasn't been deleted
- Ensure the channel still exists

### Message not appearing
- Check Discord server permissions
- Verify webhook has permission to send messages
- Check for rate limits (Discord allows 30 requests/minute per webhook)

### Formatting issues
- Discord supports a subset of Markdown
- Use `**bold**`, `*italic*`, `[links](url)`, code blocks
- Some Markdown features may not work in embeds

## Example Output

The webhook will send a nicely formatted embed like:

```
🚀 My Project v1.2.3
─────────────────────
🎉 New Features
• Added dark mode support
• New dashboard interface

🐛 Bug Fixes
• Fixed login issue
• Resolved memory leak
─────────────────────
Released: 2025-12-25T15:30:00Z
```

## Need Help?

If you need to create the channel and webhook programmatically, use the MCP Discord tools:

1. List servers to get your server ID
2. Create the changelog channel
3. Create the webhook and save the URL
4. Use the URL in your automation





