# Conan Exiles Discord Bot

## Overview
This bot was designed for admins to get the below information within discord without having to login
- Online Players and their Teleport Co-Ordinates (!tplist)
- Show Structure Limits per clan (!structures < clan name >)
- Show structure count for all clans (!allclanstructures)
- List all players within a specific clan (!clan < clan name >)

## Known Issues
- TP Player list may list recently disconnected players
- There is a hardcoded 5min cooldown for any of the commands due to the fact the bot will copy the game DB and access data from that, running the copy process to many times will interfere with the save, and you shouldn't need so much info in quick sucession

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
