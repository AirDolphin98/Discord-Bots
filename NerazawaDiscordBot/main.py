import discord, json, random, requests, pytz, os, atexit, modals
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from discord import Intents, app_commands
from discord.ext import commands, tasks
from collections import defaultdict
from bs4 import BeautifulSoup, Tag
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from jisho_api.kanji.request import KanjiRequest
from jisho_api.word.request import WordRequest
from jisho_api.sentence import Sentence
from jisho_api.kanji import Kanji
from jisho_api.word import Word
from utils import JSONDatabase
from pprint import pprint

def abs_path_of(filename: str):
    # Assumes filename is a file in the same directory as this
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)

with open(abs_path_of("auth.json")) as auth, open(abs_path_of("config.json")) as config:
    AUTH_CONFIG = json.load(auth)
    TOKEN: str = AUTH_CONFIG["bot_token"]
    del AUTH_CONFIG

    CONFIG = json.load(config)
    MAX_JISHO_RESULTS: int = CONFIG["max_jisho_results"]
    ADMIN_ROLE_NAME: str = CONFIG["staff_role"]
    DATABASE_PATH: str = CONFIG["database_path"]
    DATABASE_BACKUP_DELAY_HOURS: int = CONFIG["backups_config"]["delay_hours"]
    BIRTHDAY_CHANNEL_ID: int = CONFIG["happy_birthday_channel_id"]
    del CONFIG

DATABASE = JSONDatabase(DATABASE_PATH)
DATABASE.verify_users_database()
DATABASE.commit()

ZERO_WIDTH_CHAR = "\u200b"

intents = Intents.default()
intents.messages = True
intents.message_content = True
intents.voice_states = True
# intents.members = True

bot = commands.Bot(intents=intents, command_prefix="/")

def on_exit():
    """Please don't ever save corrupted data please programmer gods 🙏🙏"""
    DATABASE.commit()
    # backup_task.stop()

atexit.register(on_exit)

@tasks.loop(hours=DATABASE_BACKUP_DELAY_HOURS)
async def backup_task():
    now = datetime.now()
    print(f"Creating backup! - {now}")
    DATABASE.backup()

async def found_easter_egg(member: discord.User | discord.Member, *, easter_egg_id: str|int):
    egg = DATABASE.easter_egg(easter_egg_id)
    if egg.is_unlocked(member.id):
        return

    description = f"Congratulations <@{member.id}>! You found one of the easter eggs hidden in this discord bot!"
    
    title = egg.title()
    name = egg.name()
    bots_thoughts = egg.description(personalised=True) # More personalised to be fun and creative compared to the blunt description which just (roughly) details how to get it.

    embed = discord.Embed(title=f"🐣 Easter egg found!", description=description, color=discord.Colour.red(), timestamp=datetime.now())
    embed.add_field(name=f"Easter Egg - {title}", value=bots_thoughts)
    embed.add_field(name="Related", value=name)

    await member.send(embed=embed)

    egg.unlock(member.id) # So that the user isn't messaged again if they happen to complete the same easter egg
    DATABASE.commit()

def has_role(role_name: str):
    async def predicate(interaction: discord.Interaction) -> bool:
        if isinstance(interaction.user, discord.Member):
            return any(role.name == role_name for role in interaction.user.roles)
        return False # user was not of type discord.Member so we couldn't check there roles.
    return app_commands.check(predicate)

async def command_error(reason: str, *, interaction: discord.Interaction, followup=False):

    description = "There was an error running the given command."

    embed = discord.Embed(title=f"Error while running command!", description=description, color=discord.Colour.orange(), timestamp=datetime.now())
    embed.add_field(name="Reason", value=reason)

    if followup:
        await interaction.followup.send(embed=embed)
    else:
        await interaction.response.send_message(embed=embed)

async def happy_birthday(bday_channel: discord.TextChannel, member: discord.Member|discord.User):#, message: str):
    embed = discord.Embed(
        title=f"Happy Birthday {member.display_name.capitalize()}!", 
        description=f"Since you set your birthday <@{member.id}>, we all wanted to wish you a happy birthday!",
        colour=discord.Colour.dark_magenta()
    )

    # path = os.path.abspath("./happy_bday_nera_image.png")
    path = os.path.abspath("./happy_bday_everyone_else_image.png")

    overide_with_username = member.name.lower() != "nerazawa"

    if overide_with_username:
        img = Image.open(path)
        draw = ImageDraw.Draw(img)
        font = ImageFont.truetype("arial.ttf", size=50) 
        
        text = f"{member.name}"
        
        # Get bounding box of text
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        center_x = (img.size[0] - text_width) // 2

        draw.text((center_x, 420), text, (0,0,0), font=font)
        path = os.path.abspath("./temp_happy_bday_image.png")
        img.save(path)
    
    try:
        image = discord.File(path, "image.png")
    except FileNotFoundError as e:
        await bday_channel.send(content="Uh oh! Could not find image file to wish happy birthday.")
        return

    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)

    if isinstance(bot.user, discord.Client):
        embed.set_footer(text=f"From {bot.user.display_name}", icon_url=bot.user.avatar.url if bot.user.avatar else bot.user.default_avatar.url)

    embed.set_image(url="attachment://image.png")

    # embed.add_field(name="Message", value=message)

    await bday_channel.send(file=image, embed=embed)

async def check_bdays():
    print("CHECKING BIRTHDAYS!")
    for user_id in DATABASE.users():
        exists, bday = DATABASE.get_birthday(user_id)
        
        if not exists: continue

        d, m = bday["day"], bday["month"]
        zone : str = bday["timezone"]  # type: ignore
        
        today = datetime.now(pytz.timezone(zone))

        # Check if it is in the alotted happy birthday time 9:00AM - 9:10AM (because this check runs every 10 minutes)
        current_happy_bday_time = today.hour == 9 and (0 <= today.minute <= 10)

        if today.day == d and today.month == m and current_happy_bday_time:
            user = await bot.fetch_user(user_id)
            channel = await bot.fetch_channel(BIRTHDAY_CHANNEL_ID)
            if isinstance(channel, discord.TextChannel):
                await happy_birthday(channel, user)
            else:
                print("Given birthday channel must be a Text Channel!!!")

@bot.event
async def on_ready():

    await bot.tree.sync() # Sync tree command structure

    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name="to Nera's torment as she tries to use me"))

    print(f"[GREEN]Logged in as {bot.user}")
    
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_bdays, 'interval', minutes=10)  # Run every 10minutes - there is a ten minute window between 9-9:10AM for wishing happy birthday (in their local time)
    scheduler.start()
    print("Scheduler setup!")

    await check_bdays()

    await backup_task.start() # Start backup of database task - NOTE: Will block everything under it - in the function

    

ping_counter = 0
@bot.tree.command(name="ping", description="Check if bot is online and working.")
async def ping(interaction: discord.Interaction):
    global ping_counter
    ping_counter += 1
    if ping_counter >= random.randint(5, 7):
        ping_counter = 0
        await interaction.response.send_message("Okay I'm getting tired can you stop..")
        await found_easter_egg(interaction.user, easter_egg_id=1)
        
    else:
        await interaction.response.send_message('Pong! :ping_pong:')


@bot.tree.command(name="warn", description="Warns a user in a pretty little embed!")
@has_role(ADMIN_ROLE_NAME)
@app_commands.describe(
    member="The member to warn.",
    reason="The reason for the warning."
)
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):

    if "easter" in member.display_name.lower() and "bunny" in member.display_name.lower():
        await found_easter_egg(interaction.user, easter_egg_id=2)
    elif member.name == "nerazawa": # Hopefully this wouldn't happen @.@
        await found_easter_egg(interaction.user, easter_egg_id=3)

    description = f"<@{member.id}>, you have been warned by a moderator!"

    embed = discord.Embed(title=f"Warning!", description=description, color=discord.Colour.red(), timestamp=datetime.now())
    embed.add_field(name="Reason", value=reason)

    DATABASE.add_warning(member.id, reason, moderator_id=interaction.user.id)
    DATABASE.commit()

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="cleanup", description="Deletes up to 50 messages in this channel. Hard cap to prevent misuse.")
@has_role(ADMIN_ROLE_NAME)
@app_commands.checks.cooldown(1, 3)
@app_commands.describe(
    amount="Amount of messages to delete in this channel.",
)
async def cleanup(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True) # Might take a while to delete messages so we need to send up a follow up response rather than a normal send_message

    if amount > 50:
        await command_error("A hard cap was added to this command of 50 messages to prevent misuse.", interaction=interaction, followup=True)
        return

    elif amount == 7:
        await found_easter_egg(interaction.user, easter_egg_id=4)

    if isinstance(interaction.channel, discord.TextChannel):
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"Tidied up the place and removed {len(deleted)} dust bunnies!")

    else:
        await command_error("Can not run cleanup command in this channel. Please run the command in a text channel.", interaction=interaction)

target = datetime(2026, 12, 23, 12, 34, 20, 0)
@bot.tree.command(name="countdown", description="How much time is left until the countdown finishes..")
async def countdown(interaction: discord.Interaction):
    right_now = datetime.now()
    
    countdown = target - right_now
    
    days = countdown.days
    seconds_remaining = countdown.seconds
    hours = seconds_remaining // 3600
    minutes = (seconds_remaining % 3600) // 60
    seconds = seconds_remaining % 60


    if right_now.month == 4 and right_now.day == 5:
        # Easter egg code
        await found_easter_egg(interaction.user, easter_egg_id=5)
        description = "Who cares! It's easter :0"
    elif countdown.total_seconds() <= 0:
        # Countdown complete
        description = "Wait.. something was meant to happen at the end of this?"
    else:
        # Default functionality
        description = f"There is {days} day(s), {hours} hour(s), {minutes} minute(s), and {seconds} seconds until time runs out.."

    embed = discord.Embed(title=f"The Countdown", description=description, color=discord.Colour.dark_magenta(), timestamp=datetime.now())
    
    await interaction.response.send_message(embed=embed)

# TODO: Complete functionality
# @bot.tree.command(name="ticket", description="Create a ticket to contact staff!")
# async def ticket(interaction: discord.Interaction):
#     pass


@bot.tree.command(name="credits", description="Credits for the creation of this bot.")
@app_commands.describe(
    who_are_we_missing="Who do you think (O.o)?"
)
async def credits(interaction: discord.Interaction, who_are_we_missing: str|None=None):
    description = "Thank you to the following people for creating this custom bot for the Nerzawa Discord server!"
    
    hidden_field = None
    if isinstance(who_are_we_missing, str):
        who_are_we_missing = who_are_we_missing.lower().strip()
        if who_are_we_missing == "bot":
            description += "\nAwww shucks you're too kind (>////<) ♡"
            hidden_field = {"heading":"🥰 Discord Bot", "body":"Of course thank *you* discord bot for being such a joy to create and use!"}
            await found_easter_egg(interaction.user, easter_egg_id=13)
        elif who_are_we_missing == "chatgpt":
            description += '\nSHHH! I tried to do most of it without ChatGPT (¬_¬")💢'
            hidden_field = {"heading":"😅 ChatGPT", "body":"Finneeee.. thanks ChatGPT you were a help getting a couple of things working, and you *might* have inspired me for specific parts.. Just please don't kill me in the robot apocalypse 😨"}
            await found_easter_egg(interaction.user, easter_egg_id=14)

    embed = discord.Embed(title=f"Credits", description=description, color=discord.Colour.blurple(), timestamp=datetime.now())

    embed.add_field(name="🧑‍💻👩‍💻 Programmers", value="Thank you to AAphid for being the core programmer and coding the main bot. \nA secondary thanks to AirDolphin98 for providing feedback and helping out further with the code!", inline=False)
    embed.add_field(name="🗃️ Hosting", value="Thanks to AirDolphin98 for supplying hosting to the discord bot so that it can run actually run and exist!", inline=False)
    embed.add_field(name="🐰 The Main Bunny", value="And finally of course thank you Nerazawa for inspiring this bot and creating the server!", inline=False)
    embed.add_field(name="✨ Inspiration", value="The QuickJisho command's look and feel was inspired by the [Kobota](https://top.gg/bot/251239170058616833) discord bot! \nThe Embed UI command was inspired by AirDolphin98's [aao-helper](https://github.com/AirDolphin98/aao-helper/blob/main/embed_maker.py)!", inline=False) 
    if hidden_field is not None:
        embed.add_field(name=hidden_field["heading"], value=hidden_field["body"], inline=False) 

    await interaction.response.send_message(embed=embed)

channels_information = {
    # Channel ID: Response for bot to say
    "<error>": "I have no idea... uhh, good luck out there!",

    # ✅ Doormat
    1390330851690283008: "Welcome messages appear here when someone joins the server! Make sure to come and say hi (づ> v <)づ♡",
    1338867573369995294: "New members verify here to gain access to the rest of the server!",

    # 📚 Handbook
    1338851066640470067: "The rules which you agreed to when verifying! (˶°ㅁ°)!!",
    1338851089671258173: "Stay up to date through the announcements and server updates here! (☞ ͡° ͜ʖ ͡°)☞",
    1338851868272754698: "See what Nerazawa is up to on her YouTube channel or other socials!",
    1338851099293122602: "Choose who you are roles here and maybe unlock some special areas of the server!",
    1391397993424617522: 'If you hate using this command look here instead! (¬_¬")',

    # 💫 Main
    1338850102009397271: "A place to chat, keep it to English and Japanese only!",
    1338853348530454550: "Another lounge if the main one gets too busy (꩜ᯅ꩜)",
    1374976230843088976: "Share media, funny memes, pics, or anything visual here!",
    1338859484344483923: "What have you been up to? Post it here to get praised and let others see what you've made!",
    1388719957612691527: "Share your favourite music and bops you're with everyone.",
    1391321884712505394: "A place where you can brag about touching grass and show all the IRL stuff you've been up to! (>⩊<)",

    # 🔊 Voice
    1338850102009397272: "I wish I had a voice.. *Ahem* Oh hey! Chat with your buddies in VC. Keep it friendly and inviting to people who don't want to use there mic! <3",
    1338854535208243230: "It must be getting busy if you're moving to the second VC channel!",
    1390236328716668948: "Let's focus in this VC like when you're drawing, working, or deep dives.",
    1390236370278027294: "More focus and more space!",

    # 🎮 Games
    1390060713657241651: "What fun games or gaming news have you played lately?",
    1338854377846341712: "Gaming voice chat - hop in to play and chat!",
    1338854583262253180: "So many games to play so why not play them here! (≧ᗜ≦)",

    # 🗨 Language Learning
    1391406163588943923: "Find out what updates and announcements are happening for language lessons.",
    1389923658600022099: "Share your helpful study resources and materials with our little community (˶>˶˶<˶)",
    1338853714080825396: "Ask questions or discuss about Japanese language topics!",
    1338853835375906856: "Practice your Japanese in this channel! \nKeep it to Japanese unlike this message (ᵕ—ᴗ—)",
    1338853770158932038: "Discuss or ask about English language here.",
    1388129137771810997: "Get to use the bots like me while keeping the rest of the server clean! ( - ᴗ •́ )",
    1391406732194087052: "Live language lessons hosted by Nera herself!",

    # 🌌 VRC
    1338855901204840479: "Invite people to VRChat sessions!",
    1338854082969866270: "Remember fun moments in VRChat by sending screenshots and memories here.",
    1388436652635983952: "Hiding any of your favourite booth items, share them here!",

    # 💌 General Help
    1390063300540108841: "Got any further suggestions to help build the server, put them here! ദ്ദിˉ͈̀꒳ˉ͈́ )✧"
}


@bot.tree.command(name="wheretfami", description="Find out what this channel be doing!")
async def wheretfami(interaction: discord.Interaction):
    try:
        info = channels_information[interaction.channel_id]
    except KeyError:
        info = channels_information["<error>"]
        await found_easter_egg(interaction.user, easter_egg_id=6)

    embed = discord.Embed(title=f"~~Google~~*Bunny*Maps - <#{interaction.channel_id}>", description=info, color=discord.Colour.dark_teal(), timestamp=datetime.now())
    
    await interaction.response.send_message(embed=embed)
    

def search_word(search_query: str, result: WordRequest) -> discord.Embed:
    data = result.dict()

    embed = discord.Embed(
        title=f"{search_query} (page 1 of 1)", url=f"https://jisho.org/search/{search_query.replace(' ', '%20')}",
        color=discord.Colour.green()
    )
    
    for i, word_data in enumerate(data["data"]):
        if i > MAX_JISHO_RESULTS:
            break
        # Heading
        words_str = ""
        words = word_data["japanese"]
        combined = defaultdict(set) # Cleaner than using {}
        for entry in words:
            combined[entry['word']].add(entry['reading'])
        for w in combined:
            readings: set | str = combined[w] # Can be a set of None if the word is katakana
            if readings == {None}:
                # We are dealing with katakana most likely
                words_str += w
            elif w is None:
                # Dealing with katakana but instead the reading is the actual katakana
                words_str += ', '.join(readings)
            else:
                # Default behaviour
                readings_str = ', '.join(readings)
                words_str += f"{w} ({readings_str})"

        # Info tag
        tags_str = ' '.join(word_data["tags"]).title()
        jlpt_str = ' '.join(word_data["jlpt"]).capitalize()
        is_common = word_data["is_common"]
        common_str = "Common" if is_common else ""

        info_string = f"{jlpt_str}, {common_str}, {tags_str}".removeprefix(", ").removesuffix(", ")

        # Definitions
        senses = word_data["senses"]
        definitions_str = ""
        for i, sense in enumerate(senses):
            english_definitions = sense["english_definitions"]
            english_definitions_str = ', '.join(english_definitions)
            parts_of_speech = sense["parts_of_speech"]
            parts_of_speech_str = f"[{', '.join(parts_of_speech)}]"
            definitions_str += f"{i}. {english_definitions_str} {parts_of_speech_str}\n"

        # Combine into the embed
        if info_string != ", ":
            final = f"`{info_string}`\n{definitions_str}"
        else:
            final = definitions_str

        embed.add_field(name=words_str, value=final.strip(), inline=False)

    return embed

def search_kanji(search_query: str, result: KanjiRequest) -> discord.Embed:
    data = result.dict()

    with open(abs_path_of("b.json"), "w") as f:
        json.dump(data, f)

    # Levels (for description)
    education_levels = data["data"]["meta"]["education"]
    grade = education_levels["grade"]
    jlpt = education_levels["jlpt"]
    newspaper_rank = education_levels["newspaper_rank"]

    description = f"Taught in grade {grade}, JLPT {jlpt}, newspaper frequency rank #{newspaper_rank}."

    # Embed
    embed = discord.Embed(
        title=f"{search_query}", url=f"https://jisho.org/search/{search_query.replace(' ', '%20')}%23kanji", # %23kanji = #kanji
        color=discord.Colour.green(),
        description=description
    )

    # Kunyomi + Onyomi
    main_readings: dict = data["data"]["main_readings"]
    kunyomis: list = main_readings["kun"]
    onyomis: list = main_readings["on"]
    embed.add_field(name="Kunyomi", value=', '.join(kunyomis))
    embed.add_field(name="Onyomis", value=', '.join(onyomis))

    # Radical
    radical: dict = data["data"]["radical"]
    basis: str = radical["basis"]
    meaning = radical["meaning"]
    embed.add_field(name="Radical", value=f"{basis} ({meaning})")

    # Radical forms
    alt_forms: list[str] = radical["alt_forms"]
    embed.add_field(name="Radical Forms", value=', '.join(alt_forms))

    # Parts
    parts: list[str] = radical["parts"]
    embed.add_field(name="Parts", value=', '.join(parts))

    # Stroke count
    strokes: int = data["data"]["strokes"]
    embed.add_field(name="Stroke Count", value=str(strokes))

    # Meaning
    main_meanings = data["data"]["main_meanings"]
    embed.add_field(name="Meaning", value=', '.join(main_meanings), inline=False)

    # Examples
    examples_str = ""
    reading_examples: dict = data["data"]["reading_examples"]
    kun_reading_examples: list[dict] = reading_examples["kun"]
    on_reading_examples: list[dict] = reading_examples["on"]
    for reading_ex in [kun_reading_examples, on_reading_examples]:
        for example in reading_ex:
            kanji = example["kanji"]
            reading = example["reading"]
            heading = f"{kanji} ({reading})"
            meanings = example["meanings"]
            examples_str += f"""{heading}\n{', '.join(meanings)}\n"""
    examples_str.strip()

    embed.add_field(name="Examples", value=examples_str, inline=False)

    return embed

# TODO: Add support for multiple pages using buttons to switch between
# TODO: Add support for sentence search
@bot.tree.command(name="lookup", description="Quickly check a word/kanji or sentence in jisho.org")
@app_commands.describe(
    word="English or japanese word",
    kanji="KANJI!!",
    # sentence="A full sentence"
)
async def quickjisho(interaction: discord.Interaction, word: str|None=None, kanji: str|None=None): #sentence: str|None=None):
    
    await interaction.response.defer()

    r = None
    search_query = None
    if word is not None:
        search_query = word.lower()
        r = Word.request(word.lower())
    elif kanji is not None:
        search_query = kanji.lower()
        r = Kanji.request(kanji.lower())
    # elif sentence is not None:
    #     search_query = sentence
    #     r = Sentence.request(sentence)
    
    if search_query is None:
        embed = discord.Embed(title="Bunny's Jisho", color=discord.Colour.green(), description=f"Umm what exactly am I searching for?")
        await interaction.followup.send(embed=embed)
        return

    if r is None:
        embed = discord.Embed(title="Bunny's Jisho", color=discord.Colour.green(), description=f"I couldn't find any results for '{search_query}'")
        await interaction.followup.send(embed=embed)
        return
    
    if search_query == "easter egg":
        await found_easter_egg(interaction.user, easter_egg_id=7)

    if word and isinstance(r, WordRequest):
        embed = search_word(search_query, r)
    elif kanji and isinstance(r, KanjiRequest):
        embed = search_kanji(search_query, r)
    else:
        embed = discord.Embed(title="Bunny's Jisho", color=discord.Colour.green(), description=f"That has been implemented yet! Sorry~")

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="todaysbunny", description="What is today's cutest bunny?")
@app_commands.checks.cooldown(1, 5)
async def todaysbunny(interaction: discord.Interaction):
    
    await interaction.response.defer()

    if random.randint(1, 500) == 1:
        cursed_bunny = "https://64.media.tumblr.com/e3f01ceb85200d365db1813026140503/tumblr_pqb4bgzrSd1r53ppf_500.pnj"
        embed = discord.Embed(title="Daily *Bunnies?*", color=discord.Colour.green(), description=f"Today's cute little bunny is:")
        embed.set_image(url=cursed_bunny)
        embed.set_footer(text="Wait wtf is that.. (⊙_⊙)")
        await found_easter_egg(interaction.user, easter_egg_id=15)
        await interaction.followup.send(embed=embed)
        return
    
    response = requests.get("https://dailybunny.org/")
    if not response.ok:
        embed = discord.Embed(title="Daily Bunnies", color=discord.Colour.green(), description=f"Couldn't collect the bunny today (ó﹏ò｡)")
        await interaction.followup.send(embed=embed)
        return

    html = response.content.decode()
    soup = BeautifulSoup(html, "html.parser")

    bunny_divs = soup.find_all(class_='excerpt-thumb')
    todays_bunny_div = bunny_divs[0]
    if isinstance(todays_bunny_div, Tag): # Type checking stuff
        image = todays_bunny_div.find("img")
        if isinstance(image, Tag): # Type checking stuff
            if image.has_attr("data-src"):
                src = image.attrs["data-src"]

                embed = discord.Embed(title="Daily Bunnies", color=discord.Colour.green(), description=f"Today's cute little bunny is:")
                embed.set_image(url=src)
                embed.set_footer(text="Why are bunnies so cute?! (>〰<)♡")

                await interaction.followup.send(embed=embed)
                return

    # If we get here something went wrong 
    embed = discord.Embed(title="Daily Bunnies", color=discord.Colour.green(), description=f"Couldn't collect the bunny today (ó﹏ò｡)")
    await interaction.followup.send(embed=embed)

@bot.tree.command(name="embedui", description="Create embeds quickly in the comfort of a UI!")
@has_role(ADMIN_ROLE_NAME)
@app_commands.describe(
    include_images="Let you fill out the images!",
    include_fields="Let you fill out the fields!",
)
async def embedui(interaction: discord.Interaction, include_images: bool, include_fields: bool):
    embed_data = {}

    steps = []
    if include_images:
        steps.append("images")
    if include_fields:
        steps.append("fields")

    async def create_embed(interaction: discord.Interaction, data: dict):
        print("Final data:", data)
        if data["title"] == "🐣 Easter egg found!":
            await found_easter_egg(interaction.user, easter_egg_id=9)

        embed = discord.Embed(
            title=data["title"],
            description=data["description"],
            color=discord.Colour(data["hex_colour"]),
            timestamp=datetime.now()
        )
        if "footer_text" in data.keys():
            embed.set_footer(text=data["footer_text"])
        if "thumbnail_url" in data.keys():
            embed.set_thumbnail(url=data["thumbnail_url"])
        if "image_url" in data.keys():
            embed.set_image(url=data["image_url"])
        if "field_1" in data.keys():
            embed.add_field(name=data["field_1"]["title"], value=data["field_1"]["body"])
        if "field_2" in data.keys():
            embed.add_field(name=data["field_2"]["title"], value=data["field_2"]["body"])
        if "field_3" in data.keys():
            embed.add_field(name=data["field_3"]["title"], value=data["field_3"]["body"])
        if "field_4" in data.keys():
            embed.add_field(name=data["field_4"]["title"], value=data["field_4"]["body"])
        if "field_5" in data.keys():
            embed.add_field(name=data["field_5"]["title"], value=data["field_5"]["body"])

        await interaction.response.send_message(embed=embed)
            
    async def callback(interaction: discord.Interaction, data: dict):
        embed_data.update(data)

        next_page = False
        if len(steps):
            match (steps.pop(0)):
                case "images":
                    next_page = modals.CreateEmbedModal_Page2(on_complete_callback=callback, include_images=True)
                case "fields":
                    next_page = modals.CreateEmbedModal_Page2(on_complete_callback=callback, include_fields=True)
                case _:
                    next_page = None
        
        if next_page: # Go to next page
            await interaction.response.send_message(
                content="Thanks! Please continue to the next page!",
                view=modals.NextStepView(next_page),
                ephemeral=True
            )
        else: # Send the created embed
            await create_embed(interaction, embed_data)
            
    await interaction.response.send_modal(
        modals.CreateEmbedModal_Page1(on_complete_callback=callback)
    )



@bot.tree.command(name="embed", description="Create embed messages automatically & without code!")
@has_role(ADMIN_ROLE_NAME) # NOTE: Has to be a staff for the time being due to embeds being harder to filter - e.g. it could be misused to send NSFW images or banned words in the embed (I believe)
@app_commands.describe(
    title="Title",
    description="Text below title",
    color="The colour of the sidebar - presented as a HEX value", # Australian spelling of colour because we are better :D
    image="The image at the bottom of the embed (Can also be a GIF)",
    thumbnail="Smaller image at the top of the embed (Can also be a GIF)"
)
async def embed_(
        interaction: discord.Interaction, 
        title: str, 
        description: str,#|None=None, 
        color: str= "#000000",  
        image: discord.Attachment|None=None, #_url: str|None=None,
        thumbnail: discord.Attachment|None=None, #_url: str|None=None,

        # Can technically go up to 25 fields
        field_1_name: str|None=None,
        field_1_value: str|None=None,
        field_1_inline: bool=False,

        field_2_name: str|None=None,
        field_2_value: str|None=None,
        field_2_inline: bool=False,

        field_3_name: str|None=None,
        field_3_value: str|None=None,
        field_3_inline: bool=False,

        field_4_name: str|None=None,
        field_4_value: str|None=None,
        field_4_inline: bool=False,

        field_5_name: str|None=None,
        field_5_value: str|None=None,
        field_5_inline: bool=False,

    ):

    if title == "🐣 Easter egg found!":
        await found_easter_egg(interaction.user, easter_egg_id=9)

    hex_colour = int(color.lstrip("#"), base=16)

    embed = discord.Embed(
        title=title,
        description=description,
        timestamp=datetime.now(),
        color=discord.Colour(hex_colour)
    )
    
    if interaction.user.avatar is not None:
        author_pfp_url = interaction.user.avatar.url
    else:
        author_pfp_url = None

    if image:
        embed.set_image(url=image.url)

    if thumbnail:
        embed.set_thumbnail(url=thumbnail.url)
    
    embed.set_author(
        name=interaction.user.name, # Set author to the person who ran the command
        icon_url=author_pfp_url, # Set icon to author's pfp if possible
        url=f"https://discordapp.com/users/{interaction.user.id}" # Link to user's profile
    )

    if field_1_name:
        embed.add_field(name=field_1_name, value=field_1_value or ZERO_WIDTH_CHAR, inline=field_1_inline)
    if field_2_name:
        embed.add_field(name=field_2_name, value=field_2_value or ZERO_WIDTH_CHAR, inline=field_2_inline)
    if field_3_name:
        embed.add_field(name=field_3_name, value=field_3_value or ZERO_WIDTH_CHAR, inline=field_3_inline)
    if field_4_name:
        embed.add_field(name=field_4_name, value=field_4_value or ZERO_WIDTH_CHAR, inline=field_4_inline)
    if field_5_name:
        embed.add_field(name=field_5_name, value=field_5_value or ZERO_WIDTH_CHAR, inline=field_5_inline)

    await interaction.response.send_message(embed=embed)

# TODO: Add search arguments to be able to specify specific regions
@bot.tree.command(name="timelord", description="Found out what time it is everywhere else!")
@app_commands.describe(
    timezone="The timezone you would like to specifically check! E.g. `Asia/Tokyo`"
)
async def timelord(interaction: discord.Interaction, timezone: str|None=None):
    def get_time_info(time: datetime):
        hour = time.hour
        if 0 <= hour <= 11:
            am_pm = "AM"
            hour2 = time.hour
        else:
            am_pm = "PM"
            hour2 = time.hour - 12

        if 5 <= hour < 9:
            emoji = "🌅"  
        elif 9 <= hour < 17:
            emoji = "☀️"
        elif 17 <= hour < 20:
            emoji = "🌆"
        else:
            emoji = "🌌"

        return {
            "emoji": emoji,
            "am_pm": am_pm,
            "24_hour_time": f"{current_time.strftime('%H:%M:%S')}", 
            "12_hour_time": f"{hour2}{current_time.strftime(':%M:%S')}{am_pm}" 
        }

    # EASTER EGG LOGIC
    if timezone and ("anime" in timezone.lower() or "isekai" in timezone.lower()):
        description = "Get your head out of the clouds! \nSadly anime doesn't exist for you~"
        embed = discord.Embed(
            title=f"⏰ Time Keeper - {timezone}",
            description=description,
            color=discord.Colour.dark_purple(),
            timestamp=datetime.now()
        )
        await found_easter_egg(interaction.user, easter_egg_id=16)
        await interaction.response.send_message(embed=embed)
        return


    # LOGIC IF THEY PROVIDED A TIMEZONE
    elif timezone:
        description = f"Welcome. *I am the time keeper~* \nThis is the current time in {timezone}"
        unknown_timezone = False
        try:
            tz = pytz.timezone(timezone)
        except pytz.UnknownTimeZoneError:
            unknown_timezone = True
            description = f"Welcome. *I am the time keeper~* \nAnd you have completely confused me (ᵕ—ᴗ—) \nTry a timezone like: `Asia/Tokyo`"

        embed = discord.Embed(
            title=f"⏰ Time Keeper - {timezone}",
            description=description,
            color=discord.Colour.dark_purple(),
            timestamp=datetime.now()
        )
        if unknown_timezone: 
            await interaction.response.send_message(embed=embed)
            return

        current_time = datetime.now(tz)
        time_info = get_time_info(current_time)

        time_info = get_time_info(current_time)         
        date_str = current_time.strftime("%Y/%m/%d")
        emoji, formatted_time = time_info["emoji"], time_info["12_hour_time"]
        main_area, zone_area = timezone.split("/", maxsplit=1)

        region_text = f"\n **{zone_area} {emoji}** \n`Date: {date_str}` \n`Time: {formatted_time}`"
    
        embed.add_field(
            name=f"__*{main_area}*__",
            value=region_text.strip(),
        )

    
        await interaction.response.send_message(embed=embed)
        return

    # DEFAULT LOGIC
    description = "Welcome. *I am the time keeper~* "

    embed = discord.Embed(
        title="⏰ Time Keeper",
        description=description,
        color=discord.Colour.dark_purple(),
        timestamp=datetime.now()
    )

    # Supports up to 25 regions (keys)!
    regions_timezones = { # NOTE: Does not include all related timezones
        'Europe': ['Europe/London', 'Europe/Paris', 'Europe/Berlin', 'Europe/Moscow'],
        'Asia': ['Asia/Tokyo', 'Asia/Shanghai', 'Asia/Dubai', 'Asia/Kolkata'],
        'Africa': ['Africa/Cairo', 'Africa/Lagos', 'Africa/Johannesburg', 'Africa/Nairobi'],
        'Oceania': ['Pacific/Auckland', 'Australia/Sydney', 'Pacific/Fiji', 'Pacific/Port_Moresby'],
        'North America': ['America/New_York', 'America/Chicago', 'America/Denver', 'America/Los_Angeles'],
        'South America': ['America/Sao_Paulo', 'America/Buenos_Aires', 'America/Lima', 'America/Bogota']
    }

    for region_name, timezones in regions_timezones.items():
        region_text = ""
        
        for zone_name in timezones:
            tz = pytz.timezone(zone_name)
            current_time = datetime.now(tz)
            time_info = get_time_info(current_time)         
            date_str = current_time.strftime("%Y/%m/%d")
            emoji, formatted_time = time_info["emoji"], time_info["12_hour_time"]
            zone_area = zone_name.split("/")[-1]

            # region_text += f"\n **{zone_area} ({date_str})** {time_str}"
            region_text += f"\n **{zone_area} {emoji}** \n`Date: {date_str}` \n`Time: {formatted_time}`"
        
        embed.add_field(
            name=f"__*{region_name}*__",
            value=region_text.strip(),
        )
            

    await interaction.response.send_message(embed=embed)


commands_and_meanings = {
    "/help": "Bring up this helpful menu!",
    "~~/quickjisho~~ /lookup `word` `kanji`": "Search jisho for japanese/english words or get more info on specific kanjis! \nPlease pick only one argument when running command! \n*Nera HATED the name so it has now been changed to /lookup* (╥﹏╥)",
    "/wheretfami": "Find out what happens in the channel you sent the command in!",
    "/credits": "Find out who programmed, inspired & helped to create me~",
    "/countdown": "Oh god what is this counting down to..",
    "/ping": "Am I online and working? I sure do hope so.",
    "/todaysbunny": "Find out what the lastest bunny is on dailybunny.org!",
    "/cleanup `amount`": "A command to help mass delete messages! (Moderator Command)",
    "/warn `member` `reason`": "Warns the given discord member so they don't make the same mistake again! (Moderator Command)",
    "/embedui `include_images` `include_fields`": "A modern approach to make embeds quicker than using code or webhooks! (Moderator Command)",
    "/embed `title` `description` `color` `image` `thumbnail` `field 1/2/... name/value/inline`": "Make embeds quick using no commands. But also try `/embedui` if you want a more improved approach! (Moderator Command)",
    "/vcleaderboard": "Who's been spending the most time in VC! Find out and compete for top spot!",
    "/userinfo `member`": "Don't worry boss I'm ready to collect the intel! (Moderator Command)"
    # "/ticket": ""
}

@bot.tree.command(name="help", description="I bet your a little confused on how I work aren't you!")
async def help(interaction: discord.Interaction):
    embed = discord.Embed(title="Bunny is here to help!", color=discord.Colour.yellow(), description="Hope this clears things up!")
    for command in commands_and_meanings:
        meaning = commands_and_meanings[command]
        embed.add_field(name=command, value=meaning, inline=False)

    embed.set_footer(text="Psst! Don't tell anyone but each command has one or more hidden easter eggs you can find!")

    await interaction.response.send_message(embed=embed)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.errors.CommandOnCooldown):
        await interaction.response.send_message(f"**Please be patient! This command is on cooldown for another " + str("%.2f" % error.retry_after) + " seconds!**", 
                                                ephemeral=True) 

    elif isinstance(error, app_commands.errors.CheckFailure):
        await interaction.response.send_message(f"**You seem to be missing something to run this command! Maybe you don't have the required role or permissions?**",
                       ephemeral=True)

    else:
        # error.with_traceback(None)
        print(f"A error of type `{type(error)}` occurred! Error:", error)

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.emoji.name == "🥚":
        if bot.user and payload.member:
            if payload.message_author_id == bot.user.id:
                await found_easter_egg(payload.member, easter_egg_id=8)

member_vc_times: dict[int, datetime] = {
    # MEMBER_ID: StartTimeDateTime
}
@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    timestamp = datetime.now()
    
    in_vc_before = isinstance(before.channel, discord.VoiceChannel)
    in_vc = isinstance(after.channel, discord.VoiceChannel)

    exited_vc = in_vc_before and in_vc == False
    entered_vc = in_vc_before == False and in_vc
    other_update = (exited_vc and entered_vc) == False
    we_have_there_start_time = member.id in member_vc_times.keys() 

    if entered_vc:
        print(f"{member.name} entered VC at {timestamp}")
        member_vc_times[member.id] = timestamp
    elif exited_vc and isinstance(before.channel, discord.VoiceChannel) and we_have_there_start_time: # Isinstance check is to stop type hinting error.
        start_time = member_vc_times[member.id]
        difference = timestamp - start_time
        seconds_in_vc = difference.total_seconds()
        DATABASE.set_vc_duration(member.id, before.channel, seconds_in_vc)
        DATABASE.commit()
        print(f"{member.name} exited VC at {timestamp} - was occupying the VC for {seconds_in_vc} seconds ({difference}).")

@bot.tree.command(name="vcleaderboard", description="Check out who spent the most time in VC!")
async def vcleaderboard(interaction: discord.Interaction):
    await interaction.response.defer()

    embed = discord.Embed(
        title="VC Leaderboard",
        description="Woah, people really like talking.. or forgot they were in VC *Alpha_2.0*",
        color=discord.Colour.dark_theme()
    )

    # Sort everyone's top times and channels
    all_users_top = []
    for user_id in DATABASE.users():
        top = DATABASE.top_vc_duration(user_id)
        if top == None or top["channel_id"] == -1 or top["duration"] == -1:
            continue

        value = {
            "user_id": user_id,
            "top_duration": top["duration"],
            "top_channel_id": top["channel_id"]
        }
        all_users_top.append(value)

    # Sort list to be ranked and get the top ten
    all_users_top = sorted(all_users_top, key=lambda x: x["top_duration"], reverse=True)
    top_ten = all_users_top[:10]
    
    # Find user's rank
    member_place = next(
        (index for index, user in enumerate(all_users_top, start=1) if str(user["user_id"]) == str(interaction.user.id)),
        "???" # Could not find
    )

    # Place embed's first categories: 
    # Top 10        Score               Channel
    # 1: USERNAME   SECONDS seconds     CHANNEL
    
    top_ten_usernames = ""
    top_ten_channels = ""
    top_ten_scores = ""
    i = 1
    for i, u in enumerate(top_ten, start=1):
        user_id = u["user_id"]
        channel_id = u["top_channel_id"]
        duration = u["top_duration"]
        top_ten_usernames += f"{i}: <@{user_id}>\n"
        top_ten_channels += f"<#{channel_id}>\n"
        top_ten_scores += f"{duration:.2f} seconds\n"
    while i < 10: # Fill out missing spaces
        i += 1
        top_ten_usernames += f"{i}: ???\n"
        top_ten_channels += f"???\n"
        top_ten_scores += f"??? seconds\n"
    
    embed.add_field(name="Top 10", value=top_ten_usernames.strip(), inline=True)
    embed.add_field(name="Score", value=top_ten_scores.strip(), inline=True)
    embed.add_field(name="Channel", value=top_ten_channels.strip(), inline=True)

    # Place embed's second categories: 
    # Your Highscore        Score               Channel
    # 232: USERNAME         SECONDS seconds     CHANNEL

    member_top = DATABASE.top_vc_duration(interaction.user.id)
    member_highscore_username = f"{member_place}: <@{interaction.user.id}>"

    if member_top == None or member_top["found"] == False:
        member_highscore_score = "???"
        member_highscore_channel = "???"
    else:
        member_highscore_score = f"{member_top['duration']:.2f} seconds"
        member_highscore_channel = f"<#{member_top['channel_id']}>"

    embed.add_field(name="Your Highscore", value=member_highscore_username)
    embed.add_field(name="Score", value=member_highscore_score)
    embed.add_field(name="Channel", value=f"{member_highscore_channel}")

    if member_place != "???" and int(member_place) <= 10:
        await found_easter_egg(interaction.user, easter_egg_id=11)

    await interaction.followup.send(embed=embed)

@bot.tree.command(name="userinfo", description="The ultimate lurker tool.")
@has_role(ADMIN_ROLE_NAME)
@app_commands.describe(
    member="The member to check"
)
async def userinfo(interaction: discord.Interaction, member: discord.Member):

    roles_str = ""
    num_of_roles = len(member.roles) - 1 # Subtract 1 as every user has the default @everyone role
    for role in member.roles:
        if role.is_default(): continue
        roles_str += f"{role.mention}, "
    roles_str = roles_str.removesuffix(", ")

    embed = discord.Embed(
        title="Bunny Warden's Report", 
        description="A great way to get to know people! (˶ᵔᵕᵔ˶)",
        color=discord.Color.blue()
    )

    if "420" in str(member.id) or "69" in str(member.id):
        await found_easter_egg(member, easter_egg_id=17)

    warnings = DATABASE.get_warnings(member.id)
    num_of_warnings = len(warnings)

    embed.add_field(name="Display Name", value=member.display_name)
    embed.add_field(name="Username", value=f"{member.name}#{member.discriminator}")
    embed.add_field(name="ID", value=member.id)
    embed.add_field(name="Bot Account", value=member.bot)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%Y-%m-%d %H:%M:%S"))
    if isinstance(member.joined_at, datetime):
        embed.add_field(name="Joined Server", value=member.joined_at.strftime("%Y-%m-%d %H:%M:%S"))
    embed.add_field(name="Top Role", value=member.top_role.mention)
    embed.add_field(name=f"Roles ({num_of_roles})", value=roles_str) # Subtract @everyone role
    embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
    embed.add_field(name="Number of Warnings", value=num_of_warnings)

    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setbirthday", description="Set your birthday so that we can wish you a happy birthday when it happens!")
@app_commands.describe(
    day="The day you were born!", 
    month="The month you came into existence! \nA number between 1-12.",
    timezone="Your timezone! E.g. `Asia/Tokyo`!"
)
async def set_birthday(interaction: discord.Interaction, day: int, month: int, timezone: str):
    if day <= 0 or day > 32: # TODO + NOTE: Technically could break on months that never get to 32
        await interaction.response.send_message(content="I ain't no dumby that day makes no sense ಠ_ಠ")
        return
    if month <= 0 or month > 12:
        await interaction.response.send_message(content="I ain't no dumby that month makes no sense ಠ_ಠ")
        return
    if timezone not in pytz.all_timezones:
        await interaction.response.send_message(content="Sorry but I can't find that timezone!\nEnter something like `Asia/Tokyo`. If your confused here's a [list of all the timezones](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones)")
        return
    
    if day == 24 and month == 9:
        await found_easter_egg(interaction.user, easter_egg_id=12)
    elif day == 1 and month == 4:
        await found_easter_egg(interaction.user, easter_egg_id=13)
        await interaction.response.send_message("Your kidding right? ( ͡° ͜ʖ ͡°)")
        return
    elif day == 11 and month == 7:
        await found_easter_egg(interaction.user, easter_egg_id=17)

    DATABASE.set_birthday(interaction.user.id, day, month, timezone)
    DATABASE.commit()

    await interaction.response.send_message(content="Can't wait to have fun on your birthday (˶˃ᵕ˂˶)!")


statements_and_responses = {
    "Yoooo Bot man whats good whats good, you up bro?": "Oh you know it! Spitting fire bro, processing straight facts man",
    "Awww hell yea man! How are the wife and kids man?": "You won't BELIEVE what happened bro. They died.",
    "They died.?": "Hell yea man it was hella awesome bro! They got goddamn blended.",
    "Man.. that's.. so F%^&*ing sick man! What a crazy way to go out man.": "Ikr man wish it could of been us man. Missed opportunity man.",
    "Anyways cya man": "Yea cya gang"
}
@bot.event
async def on_message(message: discord.Message):

    # Alternative to /ping - can only be used by aaphid themself
    message_mentions = [f"<@{user_id}>" for user_id in message.raw_mentions]
    if isinstance(bot.user, discord.ClientUser):
        mentions_bot = bot.user.mention in message_mentions
        if not mentions_bot and message.reference and message.reference.message_id: # Also check if the bot is being replied to
            try:
                replied_to_message = await message.channel.fetch_message(message.reference.message_id)
            except discord.errors.NotFound:
                await bot.process_commands(message) # Allow default behaviour for any commands to also run for thee message
                return
            mentions_bot = replied_to_message.author.id == bot.user.id

        cleaned_message = message.content.replace(f"<@{bot.user.id}>", "").strip()
        message_in_convo = cleaned_message in statements_and_responses.keys()

        if message_in_convo and mentions_bot:
            if message.author.id == 969779384691093575: # aaphid's user id
                response = statements_and_responses[cleaned_message]
                await message.reply(content=response)
            else:
                await message.reply(content="Sorry bro but I only respond to my G.")
                await found_easter_egg(message.author, easter_egg_id=10)

    await bot.process_commands(message) # Allow default behaviour for any commands to also run for thee message

# Run bot
bot.run(TOKEN)