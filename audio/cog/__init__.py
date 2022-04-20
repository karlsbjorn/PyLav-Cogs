from __future__ import annotations

from abc import ABC
from pathlib import Path
from typing import Literal

from red_commons.logging import getLogger
from redbot.core import Config
from redbot.core import commands
from redbot.core import commands as red_commands
from redbot.core.bot import Red
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator

from pylav import Client, CogAlreadyRegistered, CogHasBeenRegistered, exceptions

from audio.cog import errors
from audio.cog.abc import MY_GUILD, MPMixin
from audio.cog.commands.hybrid_commands import HybridCommands
from audio.cog.commands.utility_commands import UtilityCommands


class CompositeMetaClass(type(red_commands.Cog), type(ABC)):
    """
    This allows the metaclass used for proper type detection to
    coexist with discord.py's metaclass
    """


_ = Translator("MediaPlayer", Path(__file__))

LOGGER_ERROR = getLogger("red.3pt.mp.error_handler")


class MediaPlayer(
    red_commands.Cog,
    HybridCommands,
    UtilityCommands,
    metaclass=CompositeMetaClass,
):
    def __init__(self, bot: Red, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        try:
            self.lavalink: Client = Client(bot=bot, cog=self, config_folder=cog_data_path(raw_name="PyLav"))
        except (CogHasBeenRegistered, CogAlreadyRegistered):
            self.lavalink: Client = self.bot.lavalink
            # self.lavalink is easier for type hinting
            #   However this is here just for the sake of completeness
            #   you can access the client via self.bot.lavalink if you prefer
            #   the only important thing here is that you initialize the client and handle the 3 exceptions it can throw
            #   CogHasBeenRegistered, CogAlreadyRegistered, AnotherClientAlreadyRegistered
            #   In this example I don't handle AnotherClientAlreadyRegistered, as I want the cog to error loading
            #   if another client is already registered (i.e lavalink.py)
        self.config = Config.get_conf(self, identifier=208903205982044161)
        self.config.register_guild(enable_slash=True, enable_context=False)
        self.config.register_global(
            enable_slash=False,
            enable_context=False,
        )

    async def initialize(self) -> None:
        if not self.lavalink.initialized:
            await self.lavalink.initialize()

    async def _sync_tree(self) -> None:
        await self.bot.wait_until_red_ready()
        await self.bot.tree.sync(guild=MY_GUILD)

    async def cog_unload(self) -> None:
        # await self.bot.lavalink.unregister(cog=self)
        pass

    @red_commands.command(name="sync")
    @red_commands.guild_only()
    @red_commands.is_owner()
    async def command_sync(self, context: red_commands.Context) -> None:
        """Sync the tree with the current guild."""
        await self._sync_tree()
        await context.send("Synced tree with guild")

    @red_commands.Cog.listener()
    async def on_red_api_tokens_update(self, service_name: str, api_tokens: dict[str, str]) -> None:
        if service_name == "spotify":
            ...  # Update lib with new token

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ) -> None:
        """
        Method for finding users data inside the cog and deleting it.
        """
        await self.config.user_from_id(user_id).clear()

    async def cog_command_error(self, context: commands.Context, error: Exception) -> None:
        error = getattr(error, "original", error)
        unhandled = True
        if isinstance(error, errors.MediaPlayerNotFoundError):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context, description=_("This command requires an existing player to be run.")
                ),
                ephemeral=True,
            )
        elif isinstance(error, exceptions.NoNodeAvailable):
            unhandled = False
            await context.send(
                embed=await self.lavalink.construct_embed(
                    messageable=context,
                    description=_(
                        "MediaPlayer cog is currently unavailable due to an outage with the backend services."
                    ),
                    footer=_("No Lavalink node currently available.")
                    if await self.bot.is_owner(context.author)
                    else None,
                ),
                ephemeral=True,
            )
        if unhandled:
            await self.bot.on_command_error(context, error, unhandled_by_cog=True)  # type: ignore