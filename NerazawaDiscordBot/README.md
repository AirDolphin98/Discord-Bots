# Nerazawa Discord Bot
This is a discord bot - that depending on what Nera says - might be used in her server!

It has been designed to be bunny themed and somewhat have a personality compared to other Discord dull bots these days.

And in each command there a easter egg has been created and found! `If you know coding don't spoil it for others please!!`


## Commands
There are a couple commands to get through so they have been split up into user commands and mod commands!

### User Commands

Firstly we have the `/help` command which as all bots do will show a help menu in a embed.

The ~~`/quickjisho`~~ `/lookup` (renamed) command inspired to look like and be as helpful as Kotoba's discord bot.

Next there is the `/wheretfami` command an extension of the #server-guide channel. To help users understand what each channel does with a bit of an extra flare!

We of course then also have the `/credits` command so that all the helpful people that created, inspired, and helped with the development can be creditted and thanked for their work.

Then the very normal and not scary `/countdown` which you guessed it. Seems to be counting down to something.

The `/setbirthday <day> <month> <timezone>` allows our bot to wish people happy birthday on there birthday! Relevant to their timezone around 9-9:10AM in their time.

Of course we also have `/credits` so that we can remember who helped make this! And of course so I can flex my huge ego (AAphid :D).

Find today's bunny using the `/todaysbunny`!

Quickly get everyone's time using `/timelord <timezone>`. The timezone argument being option as if it is not given it will give a bunch of most common timezones (relevant to the different roles in the server)

The `/vcleaderboard` is a fun command allowing users to see the longest time they've spent in VC compared to others!

### Mod Commands
We have a bulk messages delete command called `/cleanup <amount>` which deletes up to 50 messages at a time with a cooldown. These hardcaps have been introduced to avoid misuse incase of a staff member being hacked. 

The next mod command is `/warn <member> <reason>` which warns the user to make sure they avoid doing something wrong again!

Then there is `/embed <title> <description> <color> <image> <thumbnail> <field 1/2/... name/value/inline>` which allows you to quickly make embeds without making seperate code. It currently supports up to 5 fields compared to normal embeds which support up to 25. This is a mod command as it could be used to bypass text/image filters by hiding NSFW content in the embed - which I don't believe automod can detect.

However if you want a nice UI try `/embedui <include_images> <include_fields>` which will use discord's Modal features. This also supports up to 5 fields. Toggle each argument to true if you want to include that in the embed.

To find some info on a member try using `/userinfo <member>` which will also include things like how many times they have been warned (using the `/warn` command)

## To Do
Here are some possible features that could be added in the future.

- [ ] There was/is a Bocchi the Rock problem were people keep sending bocchi related messages so we could keep track of when the last one was sent `/timesincelastbochii`
- [ ] A ticketing system so it is easier to privately report things to moderators
- [ ] Add multiple pages to `/quickjisho` and `/timelord` commands
- [ ] Add sentence argument to `/quickjisho`
- [x] Add search (region) argument to `/timelord`
- [x] Add easter egg to `/timelord` command
- [ ] `/obliterate` command which not only bans a user but also deletes all their messages. This would be used in case of someone spamming NSFW content in the server. Would have to be heavily restricted with permissions (possibly only runnable by Nera).
- [ ] Make sure everyone censors `work` and `job` by reminding them to send it as `w*rk` and `j*b`. This is a joke from the discord.
- [ ] Switch to SQL databases when more users are in the server - this would be more efficient compared to JSON.
- [ ] Change it so you can also search which VC channels users have spent a lot of time in for vcleaderboard. Not just their top VC.
- [x] Save member's previous warnings so you can display them later - Possible new command: `/warnings <member>`
- [ ] `/history <member>` command to get previous history of moderation towards that user
- [ ] Reminder command
- [ ] Mass role which allows Moderators to add roles to every user - example of use: EarlyBun role
- [ ] Anime lookup command - gets info on the provided anime name
- [x] Get info on a user - ability to get there pfp. `/userinfo <member>`
- [ ] Custom welcome message
- [ ] Change vcleaderboard to also include total time - so you can choose longest or total VC time.