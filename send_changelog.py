#!/usr/bin/env python3
"""
Script to send changelog messages to Discord via webhook.
Can be used in CI/CD pipelines, GitHub Actions, or manually.
"""

import os
import sys
import json
import argparse
from datetime import datetime
from typing import Optional

try:
    import requests
except ImportError:
    print("Error: requests library not found. Install it with: pip install requests")
    sys.exit(1)


def send_changelog_webhook(
    webhook_url: str,
    version: str,
    changelog: str,
    project_name: Optional[str] = None,
    color: int = 0x00ff00,  # Green color
    author_name: Optional[str] = None,
    author_url: Optional[str] = None,
    author_icon: Optional[str] = None,
    thumbnail_url: Optional[str] = None,
    footer_text: Optional[str] = None,
    footer_icon: Optional[str] = None,
):
    """
    Send a changelog message to Discord via webhook.
    
    Args:
        webhook_url: Discord webhook URL
        version: Version number (e.g., "1.2.3")
        changelog: Changelog content (supports markdown)
        project_name: Name of the project
        color: Embed color (hex integer, default: green)
        author_name: Author name for embed
        author_url: Author URL
        author_icon: Author icon URL
        thumbnail_url: Thumbnail image URL
        footer_text: Footer text
        footer_icon: Footer icon URL
    """
    
    # Build embed
    embed = {
        "title": f"🚀 {project_name or 'Project'} v{version}" if project_name else f"🚀 New Release v{version}",
        "description": changelog,
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
    }
    
    if author_name:
        embed["author"] = {"name": author_name}
        if author_url:
            embed["author"]["url"] = author_url
        if author_icon:
            embed["author"]["icon_url"] = author_icon
    
    if thumbnail_url:
        embed["thumbnail"] = {"url": thumbnail_url}
    
    if footer_text:
        embed["footer"] = {"text": footer_text}
        if footer_icon:
            embed["footer"]["icon_url"] = footer_icon
    
    payload = {
        "embeds": [embed]
    }
    
    response = requests.post(webhook_url, json=payload)
    
    if response.status_code == 204:
        print(f"✅ Changelog sent successfully for version {version}")
        return True
    else:
        print(f"❌ Error sending changelog: {response.status_code}")
        print(f"Response: {response.text}")
        return False


def read_changelog_file(file_path: str) -> str:
    """Read changelog from a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: Changelog file not found: {file_path}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading changelog file: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Send changelog messages to Discord via webhook",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Send changelog from command line
  python send_changelog.py --webhook-url WEBHOOK_URL --version 1.2.3 --changelog "Fixed bugs"

  # Send changelog from file
  python send_changelog.py --webhook-url WEBHOOK_URL --version 1.2.3 --changelog-file CHANGELOG.md

  # With project name and custom color
  python send_changelog.py --webhook-url WEBHOOK_URL --version 1.2.3 \\
    --changelog "New features" --project-name "My Project" --color 0xff0000

  # Using environment variable for webhook URL
  export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
  python send_changelog.py --version 1.2.3 --changelog "Updates"
        """
    )
    
    parser.add_argument(
        "--webhook-url",
        type=str,
        default=os.getenv("DISCORD_WEBHOOK_URL"),
        help="Discord webhook URL (or set DISCORD_WEBHOOK_URL env var)"
    )
    parser.add_argument(
        "--version",
        type=str,
        required=True,
        help="Version number (e.g., 1.2.3)"
    )
    parser.add_argument(
        "--changelog",
        type=str,
        help="Changelog content (markdown supported)"
    )
    parser.add_argument(
        "--changelog-file",
        type=str,
        help="Path to changelog file (alternative to --changelog)"
    )
    parser.add_argument(
        "--project-name",
        type=str,
        help="Name of the project"
    )
    parser.add_argument(
        "--color",
        type=str,
        default="0x00ff00",
        help="Embed color in hex format (default: 0x00ff00 for green)"
    )
    parser.add_argument(
        "--author-name",
        type=str,
        help="Author name for embed"
    )
    parser.add_argument(
        "--author-url",
        type=str,
        help="Author URL"
    )
    parser.add_argument(
        "--author-icon",
        type=str,
        help="Author icon URL"
    )
    parser.add_argument(
        "--thumbnail",
        type=str,
        help="Thumbnail image URL"
    )
    parser.add_argument(
        "--footer",
        type=str,
        help="Footer text"
    )
    parser.add_argument(
        "--footer-icon",
        type=str,
        help="Footer icon URL"
    )
    
    args = parser.parse_args()
    
    # Validate webhook URL
    if not args.webhook_url:
        print("Error: Webhook URL is required. Use --webhook-url or set DISCORD_WEBHOOK_URL environment variable.")
        sys.exit(1)
    
    # Get changelog content
    if args.changelog_file:
        changelog = read_changelog_file(args.changelog_file)
    elif args.changelog:
        changelog = args.changelog
    else:
        print("Error: Either --changelog or --changelog-file is required.")
        sys.exit(1)
    
    # Parse color
    try:
        color = int(args.color, 16) if args.color.startswith("0x") else int(args.color)
    except ValueError:
        print(f"Error: Invalid color format: {args.color}")
        sys.exit(1)
    
    # Send webhook
    success = send_changelog_webhook(
        webhook_url=args.webhook_url,
        version=args.version,
        changelog=changelog,
        project_name=args.project_name,
        color=color,
        author_name=args.author_name,
        author_url=args.author_url,
        author_icon=args.author_icon,
        thumbnail_url=args.thumbnail,
        footer_text=args.footer,
        footer_icon=args.footer_icon,
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()





