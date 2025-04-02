# Conan Exiles Discord Bot

## Overview
This bot was designed for admins to get the below information within discord without having to login
- Online Players and their Teleport Co-Ordinates (!tplist)
- Show Structure Limits per clan (!structures < clan name >)
- Show structure count for all clans (!allclanstructures)
- List all players within a specific clan (!clan < clan name >)
- Get player info (Online Status, Level, Clan, Last Seen, TP location) (!player < name >)
- Show old clans that havent logged in over 30 days: Clan Name, days since last activity, numbers of members, number of structures, name of last online member (!oldclans) 
- Commands above can handle special characters such as chinese text

## Known Issues
- TP Player list may list recently disconnected players
- There is a 5min cooldown for any of the commands due to the fact the bot will copy the game DB and access data from that, running the copy process too many times will interfere with the save, and you shouldn't need so much info in quick sucession, this can be changed in the config (use at your own peril)

# Requirements
- Python
- pip install discord.py

# How to use
Download AdminBot.py and config.ini to a specific folder

Then run python AdminBot.py

# Config
Path = this goes to the games save location including game.db
e.g Path = G:\LocationTo\ConanSandbox\Saved\game.db

APIKEY = This is the discord API key which you can get by going here: https://discord.com/developers/applications

TeleportChannelID = Channel ID from your discord where it will post the info

StructuresChannelID = Channel ID from your discord where it will post the info

NotificationChannelID = Channel ID from your discord where it will post the info

AllClanStructuresRoleIds = Discord RoleID to restrict who can execute the commands

MaxStructures = this is based on using !structures or !allclanstructures and will alert when reaching the threshold

CommandCooldownMinutes = time in minutes when the bot will allow any command to run

InactiveDays = number in IRL days when to consider a clan old enough to show in this command
