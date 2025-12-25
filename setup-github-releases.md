# GitHub Release Notifications Setup

This guide will help you set up automatic Discord notifications for all your GitHub releases.

## Quick Setup

### Step 1: Get Your Changelog Channel Webhook URL

1. Go to your Discord server (Center's Center)
2. Navigate to your changelog channel
3. Go to Channel Settings → Integrations → Webhooks
4. Click "New Webhook" or "Create Webhook"
5. Name it something like "GitHub Releases"
6. Copy the webhook URL (it looks like: `https://discord.com/api/webhooks/123456789/abcdefgh...`)

### Step 2: Add Webhook URL to GitHub Secrets

1. Go to your GitHub repository (or create a `.github` repository for organization-wide settings)
2. Go to Settings → Secrets and variables → Actions
3. Click "New repository secret"
4. Name: `DISCORD_WEBHOOK_URL`
5. Value: Paste your webhook URL
6. Click "Add secret"

### Step 3: Add the Workflow File

The workflow file (`.github/workflows/discord-release-notification.yml`) is already created. You need to:

1. **For a single repository:**
   - Copy `.github/workflows/discord-release-notification.yml` to your repository's `.github/workflows/` folder
   - Commit and push

2. **For all repositories (organization-wide):**
   - Create a repository named `.github` in your organization
   - Add the workflow file there
   - It will apply to all repositories in your organization

### Step 4: Test It

1. Create a new release on GitHub:
   - Go to your repository → Releases → "Create a new release"
   - Choose a tag (or create a new one)
   - Add release title and description (this becomes the changelog)
   - Click "Publish release"

2. Check your Discord channel - you should see the release notification!

## What Gets Sent

The notification includes:
- 🚀 Release title
- Full changelog/description
- Version tag
- Repository link
- Author information
- Release URL
- Timestamp

## Customization

You can customize the workflow by editing `.github/workflows/discord-release-notification.yml`:

- **Color**: Change the `"color": 5865` value (Discord blurple is 5865, green is 5763719, red is 15548997)
- **Fields**: Add or remove embed fields
- **Formatting**: Modify the embed structure

## Multiple Repositories

If you want notifications from multiple repositories:

1. **Option 1**: Create a `.github` repository in your organization with the workflow
2. **Option 2**: Add the workflow to each repository individually
3. **Option 3**: Use different webhooks for different repositories (create multiple webhooks in Discord)

## Troubleshooting

### Notifications not appearing?
- Check that the webhook URL is correct in GitHub secrets
- Verify the workflow ran (check Actions tab in GitHub)
- Check Discord webhook settings (make sure it's not deleted)
- Look at workflow logs for errors

### Wrong format?
- Edit the workflow file to customize the embed
- Check Discord's embed limits (2000 chars for description)

### Want to filter releases?
- Modify the workflow to only trigger on specific tags
- Add conditions to check release name or tag pattern

## Example Release Format

When creating a release, use this format for best results:

```
## 🎉 New Features
- Added feature X
- Implemented feature Y

## 🐛 Bug Fixes
- Fixed issue with login
- Resolved memory leak

## 🔧 Improvements
- Performance optimizations
- Updated dependencies
```

The markdown will be preserved in the Discord embed!


