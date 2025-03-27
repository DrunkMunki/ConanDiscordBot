import discord
from discord.ext import commands
import sqlite3
import os
import shutil
import asyncio
import configparser
from datetime import datetime, timedelta

# Read configuration
config = configparser.ConfigParser()
config.read("config.ini")

# Bot configuration
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Cooldown tracking
last_used = {}

# Configuration values
ORIGINAL_DB = config.get("DATABASE", "Path", fallback="game.db")
TP_CHANNEL_ID = int(config.get("DISCORD", "TeleportChannelId", fallback="0"))
STRUCTURES_CHANNEL_ID = int(config.get("DISCORD", "StructuresChannelId", fallback="0"))
MAX_STRUCTURES = int(config.get("LIMITS", "MaxStructures", fallback="5000"))
NOTIFICATION_CHANNEL_ID = int(config.get("DISCORD", "NotificationChannelId", fallback="0"))
ALLOWED_ROLE_IDS = [int(role_id.strip()) for role_id in 
                    config.get("DISCORD", "AllClanStructuresRoleIds", fallback="").split(",") 
                    if role_id.strip()]

#-------------------------
# Database Helper Functions
#-------------------------
async def create_temp_db(source_db):
    """Create a temporary copy of the database"""
    temp_db = f"{os.path.splitext(source_db)[0]}_temp.db"
    try:
        shutil.copy2(source_db, temp_db)
        print(f"Created temporary database: {temp_db}")
        return temp_db
    except Exception as e:
        print(f"Error creating temporary database: {e}")
        return source_db

async def cleanup_temp_db(temp_db):
    """Remove the temporary database with retry logic"""
    max_attempts = 5
    attempt = 0
    
    while attempt < max_attempts:
        try:
            # Force Python's garbage collector to run
            import gc
            gc.collect()
            
            # Small delay to allow connections to close
            await asyncio.sleep(1)
            
            if os.path.exists(temp_db) and "_temp.db" in temp_db:
                os.remove(temp_db)
                print(f"Removed temporary database: {temp_db}")
                return True
            return True  # File doesn't exist, so we're good
        except Exception as e:
            attempt += 1
            print(f"Error removing temporary database (attempt {attempt}/{max_attempts}): {e}")
            await asyncio.sleep(5)  # Wait longer between attempts
    
    print(f"Failed to remove temporary database after {max_attempts} attempts.")
    return False

#-------------------------
# Player Teleport Functions
#-------------------------
async def get_online_player_positions(db_path):
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # First, get all online accounts with their IDs
        cursor.execute("SELECT id, user FROM account WHERE online = 1")
        online_accounts = cursor.fetchall()
        print(f"Found {len(online_accounts)} online accounts")
        
        results = []
        # For each online account, check if there's a character with matching ID
        for acc_id, acc_user in online_accounts:
            # Try to find a character with ID matching the account ID
            query = """
            SELECT c.char_name, ap.x, ap.y, ap.z
            FROM characters c
            JOIN actor_position ap ON c.id = ap.id
            WHERE c.playerId = ?
            """
            cursor.execute(query, (str(acc_id),))
            char_results = cursor.fetchall()
            
            if char_results:
                results.extend(char_results)
            
            # If no direct match, try alternative approach
            if not char_results:
                query = """
                SELECT c.char_name, ap.x, ap.y, ap.z
                FROM characters c
                JOIN actor_position ap ON c.id = ap.id
                WHERE c.playerId = ?
                ORDER BY c.lastTimeOnline DESC
                LIMIT 1
                """
                cursor.execute(query, (str(acc_user),))
                alt_results = cursor.fetchall()
                
                if alt_results:
                    results.extend(alt_results)
        
        return results
    except Exception as e:
        print(f"Error in get_online_player_positions: {e}")
        return []
    finally:
        if conn:
            conn.close()

async def get_all_characters_with_positions(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    query = """
    SELECT c.char_name, ap.x, ap.y, ap.z
    FROM characters c
    JOIN actor_position ap ON c.id = ap.id
    ORDER BY c.char_name
    """
    cursor.execute(query)
    results = cursor.fetchall()
    
    conn.close()
    print(f"Found {len(results)} characters with positions")
    return results

def format_positions(results):
    if not results:
        return "No player positions found."
        
    formatted = []
    for player in results:
        name = player[0]
        x = round(player[1], 2)
        y = round(player[2], 2)
        z = round(player[3] + 100, 2)  # Add 100 to Z coordinate
        formatted.append(f"{name} : TeleportPlayer {x} {y} {z}")
    
    return '\n'.join(formatted)

#-------------------------
# Clan & Structure Functions
#-------------------------
async def get_structure_count(db_path, clan_name):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find the guild ID
        cursor.execute("SELECT guildId FROM guilds WHERE name = ?", (clan_name,))
        guild_result = cursor.fetchone()
        if guild_result is None:
            print(f"No guild found with name: {clan_name}")
            return None
        guild_id = guild_result[0]
        print(f"Found guild ID: {guild_id} for clan: {clan_name}")

        # Count building instances associated with the guild's buildings
        cursor.execute("""
            SELECT COUNT(*)
            FROM building_instances bi
            JOIN buildings b ON bi.object_id = b.object_id
            WHERE b.owner_id = ?
        """, (guild_id,))
        structure_count = cursor.fetchone()[0]
        print(f"Total structures (building instances) for guild ID {guild_id}: {structure_count}")

        # Count different types of structures
        cursor.execute("""
            SELECT bi.class, COUNT(*)
            FROM building_instances bi
            JOIN buildings b ON bi.object_id = b.object_id
            WHERE b.owner_id = ?
            GROUP BY bi.class
        """, (guild_id,))
        structure_types = cursor.fetchall()
        for structure_type, count in structure_types:
            print(f"  {structure_type.split('.')[-1]}: {count}")

        conn.close()
        return structure_count
    except Exception as e:
        print(f"Error in get_structure_count: {e}")
        print(f"Clan name: {clan_name}")
        print(f"Database path: {db_path}")
        return None

async def get_clan_members(db_path, clan_name):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Find the guild ID
        cursor.execute("SELECT guildId FROM guilds WHERE name = ?", (clan_name,))
        guild_result = cursor.fetchone()
        if guild_result is None:
            print(f"No guild found with name: {clan_name}")
            return None
        guild_id = guild_result[0]
        
        # Get all characters in the guild
        cursor.execute("""
            SELECT char_name, level, rank 
            FROM characters 
            WHERE guild = ? 
            ORDER BY rank DESC, char_name ASC
        """, (guild_id,))
        members = cursor.fetchall()
        
        conn.close()
        return members
    except Exception as e:
        print(f"Error in get_clan_members: {e}")
        print(f"Clan name: {clan_name}")
        print(f"Database path: {db_path}")
        return None

async def get_all_clan_structures(db_path):
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT g.name, COUNT(bi.instance_id)
            FROM guilds g
            JOIN buildings b ON g.guildId = b.owner_id
            JOIN building_instances bi ON b.object_id = bi.object_id
            GROUP BY g.guildId
        """)
        clan_structures = cursor.fetchall()
        
        conn.close()
        return clan_structures
    except Exception as e:
        print(f"Error in get_all_clan_structures: {e}")
        return []

#-------------------------
# Helper Functions
#-------------------------
def check_cooldown(user_id, minutes=5):
    current_time = datetime.now()
    
    if user_id in last_used:
        time_diff = current_time - last_used[user_id]
        if time_diff < timedelta(minutes=minutes):
            remaining = minutes - (time_diff.total_seconds() / 60)
            return False, remaining
    
    # Set cooldown
    last_used[user_id] = current_time
    return True, 0

def has_allowed_role():
    async def predicate(ctx):
        if not ALLOWED_ROLE_IDS:  # If no roles specified, deny all
            return False
        return any(role.id in ALLOWED_ROLE_IDS for role in ctx.author.roles)
    return commands.check(predicate)

#-------------------------
# Bot Events
#-------------------------
@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')

#-------------------------
# Bot Commands
#-------------------------
@bot.command(name='tplist')
async def teleport_list(ctx):
    # Check if command was used in the allowed channel
    if TP_CHANNEL_ID != 0 and ctx.channel.id != TP_CHANNEL_ID:
        await ctx.send("This command can only be used in the designated channel.")
        return
    
    # Check cooldown
    can_use, remaining = check_cooldown(ctx.author.id, 5)
    if not can_use:
        await ctx.send(f"Command on cooldown. Try again in {remaining:.1f} minutes.")
        return
    
    await ctx.send("Fetching online player positions...")
    
    # Create temporary database
    temp_db = await create_temp_db(ORIGINAL_DB)
    
    try:
        # Get positions
        results = await get_online_player_positions(temp_db)
        
        if not results:
            results = await get_all_characters_with_positions(temp_db)
        
        # Format results
        formatted = format_positions(results)
        
        # Split into chunks if too long (Discord has 2000 char limit)
        if len(formatted) <= 1990:
            await ctx.send(f"```\n{formatted}\n```")
        else:
            chunks = [formatted[i:i+1990] for i in range(0, len(formatted), 1990)]
            for i, chunk in enumerate(chunks):
                await ctx.send(f"```\n{chunk}\n```")
                if i < len(chunks) - 1:
                    await asyncio.sleep(1)  # Avoid rate limits
    
    finally:
        # Clean up temp database
        await cleanup_temp_db(temp_db)

@bot.command()
async def structures(ctx, *, clan_name: str):
    if STRUCTURES_CHANNEL_ID != 0 and ctx.channel.id != STRUCTURES_CHANNEL_ID:
        return
    
    # Check cooldown
    can_use, remaining = check_cooldown(ctx.author.id, 5)
    if not can_use:
        await ctx.send(f"Command on cooldown. Try again in {remaining:.1f} minutes.")
        return
    
    print(f"Retrieving structure count for clan: {clan_name}")
    await ctx.send(f"Checking structure count for '{clan_name}'...")
    
    # Create temporary database
    temp_db = await create_temp_db(ORIGINAL_DB)
    
    try:
        structure_count = await get_structure_count(temp_db, clan_name)
        if structure_count is not None:
            message = f"```\nClan '{clan_name}' has {structure_count} structures"
            if structure_count > MAX_STRUCTURES:
                over_limit = structure_count - MAX_STRUCTURES
                message += f" (⚠️ {over_limit} over limit!)"
            message += "\n```"
            await ctx.send(message)
        else:
            await ctx.send(f"```\nAn error occurred or clan '{clan_name}' was not found.\n```")
    finally:
        # Clean up temp database
        await cleanup_temp_db(temp_db)

@bot.command()
@has_allowed_role()
async def allclanstructures(ctx):
    if STRUCTURES_CHANNEL_ID != 0 and ctx.channel.id != STRUCTURES_CHANNEL_ID:
        return
    
    # Check cooldown
    can_use, remaining = check_cooldown(ctx.author.id, 5)
    if not can_use:
        await ctx.send(f"Command on cooldown. Try again in {remaining:.1f} minutes.")
        return
    
    await ctx.send("Fetching clan structure counts...")
    
    # Create temporary database
    temp_db = await create_temp_db(ORIGINAL_DB)
    
    try:
        clan_structures = await get_all_clan_structures(temp_db)
        if clan_structures:
            message = "Clan Structure Counts:\n"
            for clan, count in clan_structures:
                message += f"{clan}: {count} structures"
                if count > MAX_STRUCTURES:
                    over_limit = count - MAX_STRUCTURES
                    message += f" (⚠️ {over_limit} over limit!)"
                message += "\n"
            
            # Split into chunks if too long (Discord has 2000 char limit)
            if len(message) <= 1990:
                await ctx.send(f"```\n{message}\n```")
            else:
                chunks = [message[i:i+1990] for i in range(0, len(message), 1990)]
                for i, chunk in enumerate(chunks):
                    await ctx.send(f"```\n{chunk}\n```")
                    if i < len(chunks) - 1:
                        await asyncio.sleep(1)  # Avoid rate limits
        else:
            await ctx.send("No clan structure data found.")
    finally:
        # Clean up temp database
        await cleanup_temp_db(temp_db)

@bot.command()
async def clan(ctx, *, clan_name: str):
    if STRUCTURES_CHANNEL_ID != 0 and ctx.channel.id != STRUCTURES_CHANNEL_ID:
        return
    
    # Check cooldown
    can_use, remaining = check_cooldown(ctx.author.id, 5)
    if not can_use:
        await ctx.send(f"Command on cooldown. Try again in {remaining:.1f} minutes.")
        return
    
    print(f"Retrieving members for clan: {clan_name}")
    await ctx.send(f"Looking up members in clan '{clan_name}'...")
    
    # Create temporary database
    temp_db = await create_temp_db(ORIGINAL_DB)
    
    try:
        members = await get_clan_members(temp_db, clan_name)
        if members is not None and len(members) > 0:
            message = f"Members in clan '{clan_name}':\n\n"
            message += "Name                 Level   Rank\n"
            message += "---------------------------------\n"
            
            rank_names = {
                0: "Recruit",
                1: "Member",
                2: "Officer",
                3: "Leader",
                None: "-"
            }
            
            for member in members:
                name = member[0]
                level = member[1] if member[1] is not None else "?"
                rank_num = member[2]
                rank_name = rank_names.get(rank_num, f"Unknown({rank_num})")
                
                # Pad name for alignment
                padded_name = name.ljust(20)
                message += f"{padded_name} {str(level).ljust(7)} {rank_name}\n"
            
            # Split into chunks if too long (Discord has 2000 char limit)
            if len(message) <= 1990:
                await ctx.send(f"```\n{message}\n```")
            else:
                chunks = [message[i:i+1990] for i in range(0, len(message), 1990)]
                for i, chunk in enumerate(chunks):
                    await ctx.send(f"```\n{chunk}\n```")
                    if i < len(chunks) - 1:
                        await asyncio.sleep(1)  # Avoid rate limits
        else:
            await ctx.send(f"```\nNo members found for clan '{clan_name}' or clan does not exist.\n```")
    finally:
        # Clean up temp database
        await cleanup_temp_db(temp_db)

@allclanstructures.error
async def allclanstructures_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to use this command.")

# Run bot with token from config
if __name__ == "__main__":
    try:
        bot.run(config.get("DISCORD", "APIKEY"))
    except Exception as e:
        print(f"An error occurred: {e}")