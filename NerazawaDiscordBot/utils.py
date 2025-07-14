from __future__ import annotations # Allows type hinting classes that haven't been setup yet - Requires Python 3.7+
import json, os, pprint, discord
from datetime import datetime


def abs_path_of(filename: str):
    # Assumes filename is a file in the same directory as this
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)


class JSONDatabase:
    _instance = None
    file_path = None

    def __new__(cls, file_path: str):
        """Loads JSON database"""
        if cls._instance is None:
            cls._instance = super(JSONDatabase, cls).__new__(cls)
            cls._instance._load(file_path)
        return cls._instance

    def _load(self, file_path):
        with open(abs_path_of(file_path), 'r') as f:
            self.data: dict = json.load(f)
            self.file_path = file_path

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
        """
        users = self.users()
        for u_id in users:
            user = self.user(u_id)
            if "unlocked_easter_eggs" not in user.keys():
                print("Added missing unlocked_easter_eggs key!")
                user["unlocked_easter_eggs"] = []
            if "vc_durations" not in user.keys():
                print("Added missing vc_durations key!")
                user["vc_durations"] = {}
            if "birthday" not in user.keys():
                print("Added missing birthday key!")
                user["birthday"] = {"day": None, "month": None, "timezone": None}
            if "warnings" not in user.keys():
                print("Added missing warnings key!")
                user["warnings"] = []

            self.set_user(u_id, user)
            
    def easter_eggs(self) -> dict:
        return self.data["easter_eggs"]

    def _easter_egg_as_dict(self, egg_id:int|str) -> dict|None:
        return self.easter_eggs().get(str(egg_id), None)

    def easter_egg(self, egg_id: int|str) -> EasterEgg:
        return EasterEgg(egg_id, self)

    def unlock_easter_egg(self, user_id: int|str, egg_id: int|str, timestamp: float|int):
        user = self.user(str(user_id))

        unlocked_eggs: list = user["unlocked_easter_eggs"]
        unlocked_eggs.append({
            "egg_id": str(egg_id),
            "timestamp": timestamp # Should be from a `datetime.now().timestamp()` call
        })
        user["unlocked_easter_eggs"] = unlocked_eggs
        self.set_user(user_id, user)

    def _add_missing_vc_duration(self, user_id: int|str, channel_id: int|str):
        """
        Will add missing vc duration as -1 if missing in that channel.
        """
        user = self.user(user_id)

        vc_durations: dict = user["vc_durations"]
        if channel_id not in vc_durations.keys():
            vc_durations[channel_id] = {
                "longest_duration_seconds": -1
            }
            user["vc_durations"] = vc_durations

        self.set_user(user_id, user)

    def get_vc_duration(self, user_id: int|str, channel_id: int|str) -> int|float:
        """
        Get VC duration of a specific user for a specific channel.
        Returns `-1` if the user has not spent any time in that VC
        """
        user = self.user(user_id)

        self._add_missing_vc_duration(user_id, channel_id)

        return user["vc_durations"][channel_id]["longest_duration_seconds"]

    def _override_vc_duration(self, user_id: int|str, channel_id: int|str, length_seconds: int|float):
        """
        Used to override `longest_duration_seconds` value.

        Please use `set_vc_duration` instead so that it can check automatically if the length is longer.
        """
        user = self.user(user_id)

        self._add_missing_vc_duration(user_id, channel_id)
        user["vc_durations"][channel_id]["longest_duration_seconds"] = length_seconds

        self.set_user(user_id, user)

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

    def set_vc_duration(self, user_id: int|str, channel: discord.VoiceChannel, length_seconds: int|float):
        """
        Will determine if value is larger than current time, and will update if required.
        """
        self._add_missing_vc_duration(user_id, channel.id)

        longest_duration_secs = self.get_vc_duration(user_id, channel.id)
        
        if length_seconds > longest_duration_secs:
            # New highscore of how long being in VC
            self._override_vc_duration(user_id, channel.id, length_seconds)

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


    def top_vc_duration(self, user_id: int|str) -> dict|None:
        """
        Get the duration of the longest VC channel they have been in. Also returns user's channel.
        """
        top_duration = -1
        top_channel_id = -1

        try:
            channel_ids = self.user(user_id)["vc_durations"].keys()
            for c_id in channel_ids:
                duration = self.get_vc_duration(user_id, c_id)
                if duration > top_duration:
                    top_duration = duration
                    top_channel_id = c_id

        except KeyError as e: # Shouldn't happen if `verify_users_database` was run at the start of the script!
            print(f"[WARN] Error while finding top vc duration for user of id: {user_id}. Make sure you ran `verify_users_database` at the start of your script! Error: {e}")

        return {
            "found": top_duration != -1 and top_channel_id != -1,
            "duration": top_duration,
            "channel_id": top_channel_id
        }

    def prettifier(self, dict_:None|dict=None):
        """Will either pretty print all of the Database to terminal. Or pretty print the part given determined by the `dict_` argument."""
        if dict_ is not None:
            pprint.pprint(dict_)
        else:
            pprint.pprint(self.data)

    def backup(self):
        if self.file_path is None:
            print("[WARN] No file path has been set for database! This could lead to missing data as it cannot be committed to the file!")
            return
        
        now = datetime.now()

        timestamp = now.strftime("%Y-%m-%d_%H-%M-%S") # Must be filepath friendly

        # Find folder and filename
        head, tail = os.path.split(self.file_path)
        tail_no_ext = os.path.splitext(tail)[0]

        # Backup Folder - ...\backups\YEAR-MONTH-DAY\
        backup_folder = os.path.join(head, "backups", now.strftime("%Y-%m-%d"))
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
        if self.file_path is None and filepath is None:
            print("[WARN] No file path has been set for database! This could lead to missing data as it cannot be committed to the file!")
            return
        

        target_path = filepath if filepath else self.file_path

        head, _ = os.path.split(target_path) # type: ignore
        if not os.path.exists(head): # type: ignore
            os.makedirs(head, exist_ok=True)

        with open(abs_path_of(target_path), "w", encoding="utf-8") as f: # type: ignore
            json.dump(self.data, f, indent=4)

        

class EasterEgg():
    def __init__(self, egg_id: int|str, db: JSONDatabase) -> None:
        self.id = egg_id
        self.db = db
        egg_data = self.db._easter_egg_as_dict(egg_id)
        if egg_data is None:
            raise KeyError(f"Given egg_id of `{egg_id}` does not exist!")
        self.type = egg_data["type"]
        self.__load_for_type(egg_data)
        self.title_ = egg_data["title"]
        self.description_ = egg_data["description"]
        self.personalised_description = egg_data["personalised_description"]
        del egg_data


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
        

if __name__ == "__main__":
    db = JSONDatabase("data/main.json")
    db.prettifier()
    egg = db.easter_egg(1)
    print(egg.is_unlocked(123))