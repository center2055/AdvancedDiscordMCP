## New Features

- **Reaction Roles Support**: Added automatic role assignment/removal based on message reactions
  - Users can react to messages to get roles
  - Automatically removes roles when reactions are removed
  - Supports both Unicode and custom emojis
  - Fully integrated with automation rules system

## Bug Fixes

- **Fixed list_channels function**: Now properly fetches and displays all channels
  - Uses cached guild object for better performance
  - Improved error handling
  - Better channel type filtering

## Improvements

- Enhanced channel listing with category information
- Better support for different channel types (text, voice, category)
- Improved error handling in channel operations
