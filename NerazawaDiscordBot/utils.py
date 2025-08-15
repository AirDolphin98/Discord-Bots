from __future__ import annotations # Allows type hinting classes that haven't been setup yet - Requires Python 3.7+
import json, os, pprint, discord, typing
from enum import Enum
from datetime import datetime


def abs_path_of(filename: str):
    """Assumes filename is a file/folder in the same directory as this"""
    return os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), filename.removeprefix("./")))


class JSONDatabase:
    _instance = None
    main_file_path: str = "./data/main.json"
    data: dict = {}
    easter_eggs_db: dict = {}

    def __init__(self, file_path: str, easter_eggs_path: str):
        self.main_file_path = file_path
        self._load(file_path)
        self.easter_eggs_db = self.load_json(easter_eggs_path)
        
    def _load(self, file_path):
        """
        Loads main.json ONLY
        """
        print(f"Loading database from: {file_path}")
        with open(file_path, 'r') as f:
            self.data: dict = json.load(f)
        print(f"Database loaded successfully. Users count: {len(self.data.get('users', {}))}")

    def load_json(self, file_path):
        """
        Loads any json file, and returns it.
        """
        with open(abs_path_of(file_path), 'r') as f:
            data: dict = json.load(f)
        return data

    def reload_from_file(self, filepath:str|None=None):
        if self.main_file_path or filepath:
            if filepath is not None:
                print("Reloading database from given file path (most likely a backup)...")
                self._load(filepath)
            else:
                print(f"Reloading database from starting file...")
                self._load(self.main_file_path)
        else:
            print("No file path set for database reload!")

    def get(self, key, default=None):
        return self.data.get(key, default)

    def all(self) -> dict:
        return self.data
    
    def users(self) -> dict:
        return self.data["users"]
    
    def set_users(self, users: dict):
        self.data["users"] = users

    def user(self, user_id: int|str) -> dict:
        try:
            return self.users()[str(user_id)]
        except KeyError:
            # print(f"[WARNING] Given user by the id `{user_id}` does not exist!")
            return self.create_user(user_id)

    def create_user(self, user_id: int|str) -> dict:
        data = {
            "unlocked_easter_eggs": [],
            "vc_durations": {},
            "birthday": {"day": None, "month": None}
        }
        self.set_user(user_id, data)
        return data

    def set_user(self, user_id: int|str, user_data: dict):
        users = self.users()
        users[str(user_id)] = user_data
        self.set_users(users)

    def verify_users_database(self):
        """
        Run at the start of the program to make sure all users in database have all the updated keys.
        Currently adds these keys if missing:
        -   `unlocked_easter_eggs`
        -   `vc_durations`
        -   `birthday`
        -   `warnings`
        
        Also fixes duplicate channel IDs in vc_durations by merging the data.
        """
        users = self.users()
        for u_id in users:
            # Get user
            user = self.user(u_id)
            
            # UNLOCKED EASTER EGGS
            if "unlocked_easter_eggs" not in user.keys():
                print("Added missing `unlocked_easter_eggs` key!")
                user["unlocked_easter_eggs"] = []
            
            # VC DURATIONS - Fix duplicates first
            if "vc_durations" not in user.keys():
                print("Added missing `vc_durations` key!")
                user["vc_durations"] = {}
            else:
                # Fix duplicate channel IDs by merging data
                user["vc_durations"] = self._fix_duplicate_vc_channels(user["vc_durations"], u_id)

            # Now process each channel normally
            for channel_id in user["vc_durations"].keys():
                data: dict = user["vc_durations"][channel_id]
                has_longest_duration_value = "longest_duration_seconds" in data.keys()
                has_total_duration_value = "total_time_seconds" in data.keys()
                
                if not has_longest_duration_value:
                    print(f"Added missing `longest_duration_seconds` in `vc_durations` for user {u_id}")
                    if has_total_duration_value:
                        data["longest_duration_seconds"] = data["total_time_seconds"]
                    else:
                        data["longest_duration_seconds"] = 0

                if not has_total_duration_value:
                    print(f"Added missing `total_time_seconds` in `vc_durations` for user {u_id}")
                    if has_longest_duration_value:
                        data["total_time_seconds"] = data["longest_duration_seconds"]
                    else:
                        data["total_time_seconds"] = 0
                        
                if has_longest_duration_value and has_total_duration_value:
                    # Fix if total time is less than the longest recorded time
                    if data["total_time_seconds"] < data["longest_duration_seconds"]:
                        print(f"Fixed `total_time_seconds` being less than `longest_duration_seconds` for user {u_id}")
                        data["total_time_seconds"] = data["longest_duration_seconds"]

            # BIRTHDAY
            if "birthday" not in user.keys():
                print("Added missing `birthday` key!")
                user["birthday"] = {"day": None, "month": None, "timezone": None}

            # WARNINGS
            if "warnings" not in user.keys():
                print("Added missing `warnings` key!")
                user["warnings"] = []

            # Set user with fixed data
            self.set_user(u_id, user)

        if "easter_eggs" in list(self.data.keys()):
            print("Easter eggs are now stored in a seperate file so removing from main.json!")
            self.data.pop("easter_eggs")

    def _fix_duplicate_vc_channels(self, vc_durations: dict, user_id: str) -> dict:
        """
        Fix duplicate channel IDs in vc_durations by merging the data.
        Takes the maximum longest_duration_seconds and sums total_time_seconds.
        """
        # Convert to a format we can work with to detect duplicates
        channel_data = {}
        
        # Read through the raw JSON data to collect all instances
        for channel_id, data in vc_durations.items():
            if channel_id not in channel_data:
                channel_data[channel_id] = {
                    "longest_duration_seconds": data.get("longest_duration_seconds", 0),
                    "total_time_seconds": data.get("total_time_seconds", 0),
                    "instances": 1
                }
            else:
                
                # Take the maximum longest duration
                current_longest = channel_data[channel_id]["longest_duration_seconds"]
                new_longest = data.get("longest_duration_seconds", 0)
                channel_data[channel_id]["longest_duration_seconds"] = max(current_longest, new_longest)
                
                # Add to total time (this is the most logical approach)
                channel_data[channel_id]["total_time_seconds"] += data.get("total_time_seconds", 0)
        
        # Return clean data without the 'instances' tracking
        clean_data = {}
        for channel_id, data in channel_data.items():
            clean_data[channel_id] = {
                "longest_duration_seconds": data["longest_duration_seconds"],
                "total_time_seconds": data["total_time_seconds"]
            }
        
        return clean_data

    def easter_eggs(self) -> dict:
        return self.easter_eggs_db

    def _easter_egg_as_dict(self, egg_id:int|str) -> dict|None:
        return self.easter_eggs().get(str(egg_id), None)

    def easter_egg(self, egg_id: int|str) -> EasterEgg:
        return EasterEgg(egg_id, self)

    def unlock_easter_egg(self, user_id: int|str, egg_id: int|str, timestamp: float|int):
        """
        Unlocks a easter egg and logs it into the database so they don't unlock it again.
        """
        user = self.user(str(user_id))

        unlocked_eggs: list = user["unlocked_easter_eggs"]
        unlocked_eggs.append({
            "egg_id": str(egg_id),
            "timestamp": timestamp # Should be from a `datetime.now().timestamp()` call
        })
        user["unlocked_easter_eggs"] = unlocked_eggs
        self.set_user(user_id, user)

    def _add_missing_vc_duration_channel(self, user_id: int|str, channel_id: int|str):
        """
        Will add missing vc duration as -1 if missing in that channel.
        """
        user = self.user(user_id)

        vc_durations: dict = user["vc_durations"]
        if channel_id not in vc_durations.keys():
            vc_durations[channel_id] = {
                "longest_duration_seconds": 0,
                "total_time_seconds": 0
            }
            user["vc_durations"] = vc_durations

        self.set_user(user_id, user)

    def get_vc_duration(self, user_id: int|str, channel_id: int|str) -> dict[str, int|float]:
        """
        Get total VC duration, and longest VC duration of a specific user for a specific channel.
        """
        user = self.user(user_id)

        self._add_missing_vc_duration_channel(user_id, channel_id)

        return user["vc_durations"][channel_id]

    def new_vc_duration(self, user_id: int|str, channel_id: int|str, length_seconds: int|float):
        """
        Override `longest_duration_seconds` value if given value is longer.
        Also adds `length_seconds` to `total_time_seconds` value for this VC.

        Please use `set_vc_duration` instead so that it can check automatically if the length is longer.
        """
        user = self.user(user_id)
        self._add_missing_vc_duration_channel(user_id, channel_id)
        user = self.user(user_id)

        if length_seconds > user["vc_durations"][channel_id]["longest_duration_seconds"]:
            user["vc_durations"][channel_id]["longest_duration_seconds"] = length_seconds

        total_time_seconds = self.get_total_vc_duration(user_id, channel_id) + length_seconds
        user["vc_durations"][channel_id]["total_time_seconds"] = total_time_seconds

        self.set_user(user_id, user)

    def get_total_vc_duration(self, user_id: int|str, channel_id: int|str) -> float|int:
        """
        Get the total seconds a user has been in a VC channel. (`total_time_seconds` value)
        """
        user = self.user(user_id)

        self._add_missing_vc_duration_channel(user_id, channel_id)

        return user["vc_durations"][channel_id]["total_time_seconds"]


    def add_warning(self, user_id: int|str, warning_message: str, moderator_id: int):
        warnings = self.get_warnings(user_id)
        warnings.append({
            "moderator_id": moderator_id, 
            "message": warning_message
        })
        self.set_warnings(user_id, warnings)

    def set_warnings(self, user_id: int|str, warnings: list[dict]):
        user = self.user(user_id)
        user["warnings"] = warnings
        self.set_user(user_id, user)

    def get_warnings(self, user_id: int|str) -> list[dict]:
        user = self.user(user_id)
        return user["warnings"]

    def set_birthday(self, user_id: int|str, day: int, month: int, timezone: str):
        user = self.user(user_id)

        user["birthday"]["day"] = day # 1-30...
        user["birthday"]["month"] = month # 1-12
        user["birthday"]["timezone"] = timezone # Asia/Tokyo etc 

        self.set_user(user_id, user)

    def get_birthday(self, user_id: int|str) -> tuple[bool, dict[str, int|str|None]]:
        user = self.user(user_id)
        
        exists = user["birthday"]["day"] is not None \
                    and user["birthday"]["month"] is not None \
                        and user["birthday"]["timezone"] is not None

        return exists, user["birthday"]


    def top_vc_duration(self, user_id: int|str) -> dict:
        """
        Get the duration of the longest VC channel they have been in. Also returns user's channel.
        """
        top_duration = -1
        top_channel_id = -1

        try:
            channel_ids = self.user(user_id)["vc_durations"].keys()
            for c_id in channel_ids:
                data = self.get_vc_duration(user_id, c_id)
                channel_top_duration = data["longest_duration_seconds"]
                if channel_top_duration > top_duration:
                    top_duration = channel_top_duration
                    top_channel_id = c_id

        except KeyError as e: # Shouldn't happen if `verify_users_database` was run at the start of the script!
            print(f"[WARN] Error while finding *top* vc duration for user of id: {user_id}. Make sure you ran `verify_users_database` at the start of your script! Error: {e}")

        return {
            "found": top_duration != -1 and top_channel_id != -1,
            "duration": top_duration,
            "channel_id": top_channel_id
        }
    
    def total_vc_duration(self, user_id: int|str) -> dict:
        total_duration = -1

        try:
            channel_ids: str = self.user(user_id)["vc_durations"].keys()
            for c_id in channel_ids:
                data = self.get_vc_duration(user_id, c_id)
                channel_total_duration = data["total_time_seconds"]
                total_duration += channel_total_duration

        except KeyError as e: # Shouldn't happen if `verify_users_database` was run at the start of the script!
            print(f"[WARN] Error while finding *total* vc duration for user of id: {user_id}. Make sure you ran `verify_users_database` at the start of your script! Error: {e}")

        return {
            "found": total_duration != -1,
            "duration": total_duration,
            "channel_id": "Global"
        }

    def prettifier(self, dict_:None|dict=None):
        """Will either pretty print all of the Database to terminal. Or pretty print the part given determined by the `dict_` argument."""
        if dict_ is not None:
            pprint.pprint(dict_)
        else:
            pprint.pprint(self.data)

    def backup(self):
        if self.main_file_path is None:
            print("[WARN] No file path has been set for database! This could lead to missing data as it cannot be committed to the file!")
            return
        
        now = datetime.now()

        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S") # Must be filepath friendly

        # Find folder and filename
        head, tail = os.path.split(self.main_file_path)
        tail_no_ext = os.path.splitext(tail)[0]

        # Backup Folder - ...\backups\YEAR-MONTH-DAY\
        backup_folder = abs_path_of(os.path.join(head, "backups", now.strftime("%Y-%m-%d")))
        if not os.path.exists(backup_folder):
            os.makedirs(backup_folder, exist_ok=True)

        # Filename - main-Backup-YEAR-MONTH-DAY_HOUR_MINUTE_SECOND
        file_name = f"{tail_no_ext}-Backup-{timestamp}.json"

        # Create full path - ...\backups\YEAR-MONTH-DAY\main-Backup-YEAR-MONTH-DAY_HOUR_MINUTE_SECOND
        full_path = os.path.join(backup_folder, file_name)

        # Create backup
        self.commit(filepath=full_path)

    def commit(self, *, filepath: str|None=None):
        """
        Saves all changes to the database file.
        ## Be careful not to corrupt the whole file!!

        Should be run after functions like:
        -   `set_user`
        -   `set_users`
        -   `unlock_easter_egg`
        -   `vc_leaderboard_stats`
        -   `set_warnings`
        -   `add_warning`
        -   ...

        If `filepath` is None it will use the default path given to it at the start.
        Usually will only provide the `filepath` argument when creating backups.
        """
        if self.main_file_path is None and filepath is None:
            print("[WARN] No file path has been set for database! This could lead to missing data as it cannot be committed to the file!")
            return
        

        target_path = filepath if filepath else self.main_file_path
        target_path = abs_path_of(target_path)

        head, _ = os.path.split(target_path)
        if not os.path.exists(head): 
            os.makedirs(head, exist_ok=True)

        with open(abs_path_of(target_path), "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4)

        

class EasterEgg():
    def __init__(self, egg_id: int|str, db: JSONDatabase) -> None:
        self.id = egg_id
        self.db = db

        self.egg_data = self.db.easter_eggs()[str(egg_id)]

        if self.egg_data is None:
            raise KeyError(f"Given egg_id of `{egg_id}` does not exist!")
        self.type = self.egg_data["type"]
        self.__load_for_type(self.egg_data)
        self.title_ = self.egg_data["title"]
        self.description_ = self.egg_data["description"]
        self.personalised_description = self.egg_data["personalised_description"]


    def __load_for_type(self, egg_data: dict):
        match (self.type):
            case "command":
                self.command = egg_data["command"]
                self.name_ = f"Related to the `{self.command}` command"
            case "reaction":
                self.reaction = egg_data["reaction"]
                self.name_ = f"Requires the `{self.reaction}` reaction."
            case "message":
                self.mentions = egg_data["mentions"]
                self.name_ = f"Requires to mention `{', '.join(self.mentions)}`."
                
    def name(self) -> str:
        return self.name_
    
    def title(self) -> str:
        return self.title_
    
    def description(self, *, personalised=False) -> str:
        if personalised:
            return self.personalised_description
        else:
            return self.description_
    
    def is_unlocked(self, user_id:int|str):
        user = self.db.user(user_id)

        for unlocked_egg in user["unlocked_easter_eggs"]:
            egg_id, timestamp = unlocked_egg["egg_id"], unlocked_egg["timestamp"]
            if str(self.id) == str(egg_id):
                return True
        return False     

    def unlock(self, user_id):
        self.db.unlock_easter_egg(user_id, self.id, datetime.now().timestamp())

    def get_data(self):
        return self.egg_data

class VCStatType(Enum):
    top = "top"
    total = "total"

    def __str__(self):
        return self.value

# Same as: discord.interactions.InteractionChannel (however we can't access that variable)
AllChannelTypes = typing.Union[
    discord.VoiceChannel,
    discord.StageChannel,
    discord.TextChannel,
    discord.ForumChannel,
    discord.CategoryChannel,
    discord.Thread,
    discord.DMChannel,
    discord.GroupChannel,
]

def find_role(name, *, guild: discord.Guild) -> discord.Role|None:
    for r in guild.roles:
        if r.name == name:
            return r
    return None

def has_role(role_name: str):
    async def predicate(interaction: discord.Interaction) -> bool:
        if isinstance(interaction.user, discord.Member):
            return any(role.name == role_name for role in interaction.user.roles)
        return False # user was not of type discord.Member so we couldn't check there roles.
    return discord.app_commands.check(predicate)

async def command_error(reason: str, *, interaction: discord.Interaction, followup=False):

    description = "There was an error running the given command."

    embed = discord.Embed(title=f"Error while running command!", description=description, color=discord.Colour.orange(), timestamp=datetime.now())
    embed.add_field(name="Reason", value=reason)

    if followup:
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def find_category(name, guild: discord.Guild) -> discord.CategoryChannel:
    tickets_category = next(
        (c for c in guild.categories if c.name == name),
        None
    )
    # Create category if missing
    if tickets_category is None:
        print("Nerazawa Bot: Creating missing tickets category...")
        tickets_category = await guild.create_category(name=name)
        print("Nerazawa Bot: Created missing tickets category!")
    
    return tickets_category

def is_ticket_channel(channel: discord.TextChannel|None|AllChannelTypes):
    if not isinstance(channel, discord.TextChannel) or channel is None:
        return False
    
    valid_starts = [
        "ticket-",
        "✅ticket-",
        "💀ticket-"
    ]
    for start in valid_starts:
        if channel.name.startswith(start):
            return True

    return False


if __name__ == "__main__":
    db = JSONDatabase("data/main.json", "data/static/easter_eggs.json")
    db.prettifier()
    egg = db.easter_egg(1)
    print(egg.is_unlocked(123))