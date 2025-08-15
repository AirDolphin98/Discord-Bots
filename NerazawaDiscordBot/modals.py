import discord, typing
from discord.ui import Modal, TextInput, View, Button, DynamicItem
from discord.ui import UserSelect, ChannelSelect, RoleSelect, MentionableSelect, Select
from discord.utils import MISSING

####
# NOTES!
# - Title is required for embeds
# - Cannot exceed 6000 character limit for all inputs combined into modal!
# - Each label must be <=45 characters long
# - Max of 5 "items" for each modal
# - Can't string multiple modals together - unless you use a inbetween like View
####


class NextStepView(discord.ui.View):
    def __init__(self, second_modal:Modal):
        super().__init__()
        self.modal = second_modal

    @discord.ui.button(label="Proceed to Next Step", custom_id="next_step_button")
    async def next_step_button_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.modal)


class CreateEmbedModal_Page1(Modal):
    def __init__(self, on_complete_callback, *args, **kwargs) -> None:
        kwargs["title"] = "Fancy Pants Embed Creator!" # Required
        super().__init__(*args, **kwargs)

        self.add_item(TextInput(label="Title of the embed!", max_length=256, required=True))
        self.add_item(TextInput(label="Description of the embed!", max_length=4000, required=True, style=discord.TextStyle.paragraph))
        self.add_item(TextInput(label="Footer text", max_length=1500, required=False, style=discord.TextStyle.paragraph))
        self.add_item(TextInput(label="HEX Colour of Sidebar", max_length=7, required=False, default=str(discord.Colour.default())))

        self.on_complete_callback = on_complete_callback

    async def on_submit(self, interaction: discord.Interaction) -> None:
        hex_colour = int(self.children[3].value.lstrip("#"), base=16) # type: ignore

        await self.on_complete_callback(interaction, {
            "title": self.children[0].value, # type: ignore
            "description": self.children[1].value, # type: ignore
            "footer_text": self.children[2].value, # type: ignore
            "hex_colour": hex_colour, 
        })


class CreateEmbedModal_Page2(Modal):
    def __init__(self, on_complete_callback, include_images:bool=False, include_fields:bool=False, *args, **kwargs) -> None:
        kwargs["title"] = "Fancy Pants Embed Creator!" # Required
        super().__init__(*args, **kwargs)

        self.on_complete_callback = on_complete_callback

        if include_images:
            self.add_item(TextInput(label="Thumbnail image URL", required=False, custom_id="thumbnail_url"))
            self.add_item(TextInput(label="Image URL!", required=False, custom_id="image_url"))
        elif include_fields:
            
            field_placeholder_text = "> Title should have arrow at start\nMain text goes here\nand on following lines as well!"

            self.add_item(TextInput(label="Field 1!", required=False, custom_id="field_1", placeholder=field_placeholder_text, style=discord.TextStyle.paragraph))
            self.add_item(TextInput(label="Field 2!", required=False, custom_id="field_2", placeholder=field_placeholder_text, style=discord.TextStyle.paragraph))
            self.add_item(TextInput(label="Field 3!", required=False, custom_id="field_3", placeholder=field_placeholder_text, style=discord.TextStyle.paragraph))
            self.add_item(TextInput(label="Field 4!", required=False, custom_id="field_4", placeholder=field_placeholder_text, style=discord.TextStyle.paragraph))
            self.add_item(TextInput(label="Field 5!", required=False, custom_id="field_5", placeholder=field_placeholder_text, style=discord.TextStyle.paragraph))
        else:
            self.add_item(TextInput(label="YOU DIDN'T SET ANY OF THE INCLUDES AAAAAAAAA!"))
            
    async def on_submit(self, interaction: discord.Interaction) -> None:
        data = {}
        
        for c in self.children:
            if c._provided_custom_id:
                custom_id: str = c.custom_id # type: ignore
                val: str = c.value # type: ignore
                if val.strip() == "":
                    continue

                if custom_id.startswith("field_"):
                    lines = val.splitlines()
                    title = lines[0].removeprefix("> ")
                    body = "\n".join(lines[1:])
                    data.update({custom_id: {"title": title, "body": body}})

                else:
                    data.update({custom_id: val})
        
        await self.on_complete_callback(interaction, data)


class DeleteTicketConfirmation_View(View):
    def __init__(self, user_who_abandoned: discord.Member|discord.User, callback = lambda interaction: interaction):
        super().__init__()
        self.on_click_callback = callback
        self.who_abandoned = user_who_abandoned

    @discord.ui.button(label="Click to delete channel", style=discord.ButtonStyle.primary)
    async def test(self, interaction: discord.Interaction, button: discord.ui.Button, style=discord.ButtonStyle.primary):
        if self.who_abandoned.id != interaction.user.id:
            await interaction.response.send_message("You did not abandon this ticket so you can't delete it!", ephemeral=True)
            return
        
        await interaction.response.send_message("Deleting channel")
        await self.on_click_callback(interaction)


class FileSelect(Select):
    def __init__(self, files, backup_folder_path, async_callback):
        # Build the options for the dropdown
        options = [
            discord.SelectOption(label=file, value=file)
            for file in files
        ]
        super().__init__(
            placeholder="Select a backup to restore",
            min_values=1,
            max_values=1,
            options=options
        )

        self.backup_folder_path = backup_folder_path
        self.async_callback = async_callback

    async def callback(self, interaction: discord.Interaction):
        selected_file = self.values[0]
        
        if self.async_callback is not None and callable(self.async_callback):
            await self.async_callback(interaction, self.backup_folder_path, selected_file) # type: ignore
        

class FileSelectView(View):
    def __init__(self, files, backup_folder_path, async_callback):
        super().__init__()
        self.add_item(FileSelect(files, backup_folder_path, async_callback))
