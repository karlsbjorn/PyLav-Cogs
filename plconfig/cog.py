from __future__ import annotations

import shutil
from pathlib import Path

import discord
from discord.utils import maybe_coroutine
from red_commons.logging import getLogger
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import bold, box, inline
from tabulate import tabulate

import pylavcogs_shared
from pylav import Client
from pylav.localfiles import LocalFile
from pylav.types import BotT
from pylav.utils import PyLavContext
from pylav.vendored import aiopath
from pylavcogs_shared.ui.menus.player import StatsMenu
from pylavcogs_shared.ui.sources.player import PlayersSource

LOGGER = getLogger("red.3pt.PyLavConfigurator")

_ = Translator("PyLavConfigurator", Path(__file__))


@cog_i18n(_)
class PyLavConfigurator(commands.Cog):
    """Configure PyLav library settings"""

    lavalink: Client

    __version__ = "1.0.0.0rc0"

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot

    @commands.group(name="plset", aliases=["plconfig"])
    async def command_plset(self, ctx: PyLavContext) -> None:
        """Change global settings for PyLav"""

    @command_plset.command(name="version")
    async def command_plset_version(self, context: PyLavContext) -> None:
        """Show the version of the Cog and it's PyLav dependencies"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        data = [
            (self.__class__.__name__, self.__version__),
            ("PyLavCogs-Shared", pylavcogs_shared.__VERSION__),
            ("PyLav", self.bot.lavalink.lib_version),
        ]

        await context.send(
            embed=await self.lavalink.construct_embed(
                description=box(tabulate(data, headers=(_("Library/Cog"), _("Version")), tablefmt="fancy_grid")),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plset.command(name="info")
    async def command_plset_info(self, context: PyLavContext) -> None:
        """Show the config values"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        is_owner = await self.bot.is_owner(context.author)
        enabled = _("Enabled")
        disabled = _("Disabled")
        embed_list = []
        pylav_config = await self.lavalink.lib_db_manager.get_config().fetch_all()
        if is_owner:
            data = [
                (_("Use Managed Node"), enabled if pylav_config["enable_managed_node"] else disabled),
                (_("Auto Update\nManaged Node"), enabled if pylav_config["auto_update_managed_nodes"] else disabled),
                (_("Change Bot activity"), enabled if pylav_config["update_bot_activity"] else disabled),
                (_("Use Bundled\nPyLav Nodes"), enabled if pylav_config["use_bundled_pylav_external"] else disabled),
                (
                    _("Use Bundled\nlava.link Nodes"),
                    enabled if pylav_config["use_bundled_lava_link_external"] else disabled,
                ),
            ]

            embed_list.append(
                await self.lavalink.construct_embed(
                    description=box(tabulate(data, headers=(_("PyLav Config"), _("State")), tablefmt="fancy_grid")),
                    messageable=context,
                )
            )
        global_config = await self.lavalink.player_config_manager.get_global_config().fetch_all()
        data = [
            (_("Volume"), global_config["volume"]),
            (_("Maximum Volume"), global_config["max_volume"]),
            (_("AutoPlay"), enabled if global_config["auto_play"] else disabled),
            (_("Shuffling"), enabled if global_config["shuffle"] else disabled),
            (_("Auto Shuffle"), enabled if global_config["auto_shuffle"] else disabled),
            (_("Auto Deafen"), enabled if global_config["self_deaf"] else disabled),
            (
                _("Auto Disconnect"),
                "{enabled}\n{timer}s".format(enabled=enabled, timer=global_config["empty_queue_dc"].time)
                if global_config["empty_queue_dc"].enabled
                else disabled,
            ),
            (
                _("Auto Alone Pause"),
                "{enabled}\n{timer}s".format(enabled=enabled, timer=global_config["alone_pause"].time)
                if global_config["alone_pause"].enabled
                else disabled,
            ),
            (
                _("Auto Alone Disconnect"),
                "{enabled}\n{timer}s".format(enabled=enabled, timer=global_config["alone_dc"].time)
                if global_config["alone_dc"].enabled
                else disabled,
            ),
        ]

        embed_list.append(
            await self.lavalink.construct_embed(
                description=box(tabulate(data, headers=(_("Global Player Config"), _("Value")), tablefmt="fancy_grid")),
                messageable=context,
            )
        )
        if context.guild:
            config = await self.bot.lavalink.player_config_manager.get_config(context.guild.id).fetch_all()
            dj_user_str = (
                "\n".join(
                    [
                        discord.utils.escape_markdown(str(context.guild.get_member(user) or user))
                        for user in config["dj_users"]
                    ]
                )
                if len(config["dj_users"]) <= 5
                else _("Too many to show {count}").format(count=len(config["dj_users"]))
            )
            dj_role_str = (
                "\n".join(
                    [
                        discord.utils.escape_markdown(str(context.guild.get_role(role) or role))
                        for role in config["dj_roles"]
                    ]
                )
                if len(config["dj_roles"]) <= 5
                else _("Too many to show {count}").format(count=len(config["dj_roles"]))
            )

            data = [
                (_("Volume"), config["volume"]),
                (_("Maximum Volume"), config["max_volume"]),
                (_("AutoPlay"), enabled if config["auto_play"] else disabled),
                (_("AutoPlay Playlist"), config["auto_play_playlist_id"]),
                (_("Loop track"), enabled if config["repeat_current"] else disabled),
                (_("Loop Queue"), enabled if config["repeat_queue"] else disabled),
                (_("Shuffling"), enabled if config["shuffle"] else disabled),
                (_("Auto Shuffle"), enabled if config["auto_shuffle"] else disabled),
                (_("Auto Deafen"), enabled if config["self_deaf"] else disabled),
                (
                    _("Auto Disconnect"),
                    _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=config["empty_queue_dc"].time)
                    if config["empty_queue_dc"].enabled
                    else disabled,
                ),
                (
                    _("Auto Alone Pause"),
                    _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=config["alone_pause"].time)
                    if config["alone_pause"].enabled
                    else disabled,
                ),
                (
                    _("Auto Alone Disconnect"),
                    _("{enabled}\n{timer} seconds").format(enabled=enabled, timer=config["alone_dc"].time)
                    if config["alone_dc"].enabled
                    else disabled,
                ),
                (_("Forced Voice Channel"), config["forced_channel_id"] or _("None")),
                (_("Forced Command Channel"), config["text_channel_id"] or _("None")),
                (_("Forced Notification Channel"), config["notify_channel_id"] or _("None")),
                (_("DJ Users"), dj_user_str),
                (_("DJ Roles"), dj_role_str),
            ]

            embed_list.append(
                await self.lavalink.construct_embed(
                    description=box(
                        tabulate(data, headers=(_("Server Player Config"), _("Value")), tablefmt="fancy_grid")
                    ),
                    messageable=context,
                )
            )

            ac_max_volume = await self.bot.lavalink.player_config_manager.get_max_volume(context.guild.id)
            ac_volume = await self.bot.lavalink.player_config_manager.get_volume(context.guild.id)
            ac_alone_dc = await self.bot.lavalink.player_config_manager.get_alone_dc(context.guild.id)
            ac_alone_pause = await self.bot.lavalink.player_config_manager.get_alone_pause(context.guild.id)
            ac_empty_queue_dc = await self.bot.lavalink.player_config_manager.get_empty_queue_dc(context.guild.id)
            ac_shuffle = await self.bot.lavalink.player_config_manager.get_shuffle(context.guild.id)
            ac_auto_shuffle = await self.bot.lavalink.player_config_manager.get_auto_shuffle(context.guild.id)
            ac_self_deaf = await self.bot.lavalink.player_config_manager.get_self_deaf(context.guild.id)
            ac_auto_play = await self.bot.lavalink.player_config_manager.get_auto_play(context.guild.id)

            data = [
                (_("Volume"), ac_volume),
                (_("Maximum Volume"), ac_max_volume),
                (_("AutoPlay"), enabled if ac_auto_play else disabled),
                (_("Shuffling"), enabled if ac_shuffle else disabled),
                (_("Auto Shuffle"), enabled if ac_auto_shuffle else disabled),
                (_("Auto Deafen"), enabled if ac_self_deaf else disabled),
                (
                    _("Auto Disconnect"),
                    f"{enabled}\n{ac_empty_queue_dc.time}s" if ac_empty_queue_dc.enabled else disabled,
                ),
                (
                    _("Auto Alone Pause"),
                    f"{enabled}\n{ac_alone_pause.time}s" if ac_alone_pause.enabled else disabled,
                ),
                (
                    _("Auto Alone Disconnect"),
                    f"{enabled}\n{ac_alone_dc.time}s" if ac_alone_dc.enabled else disabled,
                ),
            ]
            embed_list.append(
                await self.lavalink.construct_embed(
                    description=box(
                        tabulate(data, headers=(_("Context Player Config"), _("Value")), tablefmt="fancy_grid")
                    ),
                    messageable=context,
                )
            )

        data = [
            (
                _("Next Bundled\nPlaylist Update"),
                pylav_config["next_execution_update_bundled_playlists"].strftime("%Y/%m/%d\n%H:%M:%S UTC"),
            ),
            (
                _("Next Bundled External\nPlaylist Update"),
                pylav_config["next_execution_update_bundled_external_playlists"].strftime("%Y/%m/%d\n%H:%M:%S UTC"),
            ),
            (
                _("Next External\nPlaylist Update"),
                pylav_config["next_execution_update_external_playlists"].strftime("%Y/%m/%d\n%H:%M:%S UTC"),
            ),
        ]
        embed_list.append(
            await self.lavalink.construct_embed(
                description=box(
                    tabulate(data, headers=(_("Playlist Tasks"), _("Date and Time (UTC)")), tablefmt="fancy_grid")
                ),
                messageable=context,
            )
        )
        if is_owner:
            data = [
                (_("Config Folder"), pylav_config["config_folder"]),
                (_("Local Tracks"), pylav_config["localtrack_folder"]),
                (_("Java Executable"), shutil.which(pylav_config["java_path"])),
            ]
            embed_list.append(
                await self.lavalink.construct_embed(
                    description=box(tabulate(data, headers=(_("Paths"), _("Path")), tablefmt="plain")),
                    messageable=context,
                )
            )

        await context.send(
            embeds=embed_list,
            ephemeral=True,
        )

    @command_plset.command(name="dj")
    @commands.guild_only()
    async def command_plset_dj(self, context: PyLavContext, *, role_or_member: discord.Role | discord.Member):
        """Checks if a user or role is considered a DJ"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        if isinstance(role_or_member, discord.Role):
            config = self.bot.lavalink.player_config_manager.get_config(context.guild.id)
            dj_roles = await config.fetch_dj_roles()
            dj_roles = dj_roles.union(await config.fetch_dj_users())
            is_dj = role_or_member.id in dj_roles if dj_roles else True
            message = (
                _("{role} is a DJ role").format(role=role_or_member.mention)
                if is_dj
                else _("{role} is not a DJ role").format(role=role_or_member.mention)
            )
        else:
            is_dj = await self.bot.lavalink.is_dj(user=role_or_member, guild=context.guild, bot=self.bot)
            message = (
                _("{user} is a DJ").format(user=role_or_member.mention)
                if is_dj
                else _("{user} is not a DJ").format(user=role_or_member.mention)
            )
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=message,
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plset.command(name="folder")
    @commands.is_owner()
    async def command_plset_folder(self, context: PyLavContext, create: bool, *, folder: str) -> None:
        """Set the folder for PyLav's config files

        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        path = aiopath.AsyncPath(folder)
        if await path.is_file():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{folder} is not a folder").format(
                        folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if create:
            await path.mkdir(parents=True, exist_ok=True)
        elif not await path.exists():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "{folder} does not exist, "
                        "run the command again with the create argument "
                        "set to 1 to automatically create this folder"
                    ).format(
                        folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        global_config = self.lavalink.lib_db_manager.get_config()
        await global_config.update_config_folder(str(await maybe_coroutine(path.absolute)))

        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("PyLav's config folder has been set to {folder}").format(
                    folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plset.command(name="tracks")
    @commands.is_owner()
    async def command_plset_tracks(self, context: PyLavContext, create: bool, *, folder: str) -> None:
        """Set the local tracks folder for PyLav.

        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        path = aiopath.AsyncPath(folder)
        if await path.is_file():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{folder} is not a folder").format(
                        folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if create:
            await path.mkdir(parents=True, exist_ok=True)
        elif not await path.exists():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "{folder} does not exist, "
                        "run the command again with "
                        "the create argument "
                        "set to 1 to automatically "
                        "create this folder"
                    ).format(
                        folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        global_config = self.lavalink.lib_db_manager.get_config()
        await global_config.update_localtrack_folder(str(await maybe_coroutine(path.absolute)))

        await LocalFile.add_root_folder(path=path)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("PyLav's local tracks folder has been set to {folder}").format(
                    folder=inline(f"{await maybe_coroutine(path.absolute)}"),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plset.command(name="java")
    @commands.is_owner()
    async def command_plset_java(self, context: PyLavContext, *, java: str) -> None:
        """Set the java executable for PyLav.

        Default is "java"
        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        from stat import S_IXGRP, S_IXOTH, S_IXUSR

        java = shutil.which(java)
        path = aiopath.AsyncPath(java)
        if not await path.exists():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "{java} does not exist, "
                        "run the command again with "
                        "the java argument "
                        "set to the correct path"
                    ).format(
                        java=inline(f"{await maybe_coroutine(path.absolute)}"),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        elif not await path.is_file():
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("{java} is not an executable file").format(
                        java=inline(f"{await maybe_coroutine(path.absolute)}"),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        stats = await path.stat()
        if not stats.st_mode & (S_IXUSR | S_IXGRP | S_IXOTH):
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_(
                        "{java} is not an executable, "
                        "run the command again with "
                        "the java argument "
                        "set to the correct path"
                    ).format(
                        java=inline(f"{await maybe_coroutine(path.absolute)}"),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        global_config = self.lavalink.lib_db_manager.get_config()
        await global_config.update_java_path(str(await maybe_coroutine(path.absolute)))
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=_("PyLav's java executable has been set to {java}").format(
                    java=inline(f"{java}"),
                ),
                messageable=context,
            ),
            ephemeral=True,
        )

    @command_plset.group(name="node")
    @commands.is_owner()
    async def command_plset_node(self, context: PyLavContext) -> None:
        """Change the managed node configuration"""

    @command_plset_node.command(name="toggle")
    async def command_plset_node_toggle(self, context: PyLavContext) -> None:
        """Toggle the managed node on/off.

        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        global_config = self.lavalink.lib_db_manager.get_config()
        current = await global_config.fetch_enable_managed_node()
        await global_config.update_enable_managed_node(not current)

        if current:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed node has been enabled"),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed node has been disabled"),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plset_node.command(name="updates")
    async def command_plset_node_updates(self, context: PyLavContext) -> None:
        """Toggle the managed node auto updates on/off.

        Changes will be applied after restarting the bot.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        global_config = self.lavalink.lib_db_manager.get_config()
        current = await global_config.fetch_auto_update_managed_nodes()
        await global_config.update_auto_update_managed_nodes(not current)

        if current:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed node auto updates have been enabled"),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed node auto updates have been disabled"),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plset_node.group(name="external")
    async def command_plset_node_external(self, context: PyLavContext) -> None:
        """Change the bundled external nodes state"""

    @command_plset_node_external.command(name="pylav")
    async def command_plset_node_external_pylav(self, context: PyLavContext) -> None:
        """Toggle the managed external draper.wtf nodes on/off"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        global_config = self.lavalink.lib_db_manager.get_config()
        current_state = global_config.fetch_use_bundled_pylav_external()
        await global_config.update_use_bundled_pylav_external(not current_state)
        if current_state:
            await self.lavalink.remove_node(1)
        else:
            node_config = self.lavalink.node_db_manager.get_node_config(1)
            await self.lavalink.add_node(**(await node_config.get_connection_args()))

        if current_state:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed pylav external node has been enabled"),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed pylav external node has been disabled"),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plset_node_external.command(name="lavalink")
    async def command_plset_node_lavalink(self, context: PyLavContext) -> None:
        """Toggle the managed external lava.link node on/off"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        global_config = self.lavalink.lib_db_manager.get_config()
        current_state = await global_config.fetch_use_bundled_lava_link_external()
        await global_config.update_use_bundled_lava_link_external(not current_state)
        if current_state:
            await self.lavalink.remove_node(2)
        else:
            node_config = self.lavalink.node_db_manager.get_node_config(2)
            await self.lavalink.add_node(**(await node_config.get_connection_args()))

        if current_state:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed lava.link external node has been enabled"),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav's managed lava.link external node has been disabled"),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @command_plset.command(name="spotifyapi")
    @commands.is_owner()
    async def command_plset_spotifyapi(self, context: PyLavContext) -> None:
        """Instructions on how to set the Spotify API Tokens"""
        message = _(
            "1. Go to Spotify developers and log in with your Spotify account.\n"
            "(https://developer.spotify.com/dashboard/applications)\n"
            '2. Click "Create An App".\n'
            "3. Fill out the form provided with your app name, etc.\n"
            '4. When asked if you\'re developing commercial integration select "No".\n'
            "5. Accept the terms and conditions.\n"
            "6. Copy your client ID and your client secret into:\n"
            "`{prefix}set api spotify client_id <your_client_id_here> "
            "client_secret <your_client_secret_here>`"
        ).format(prefix=context.clean_prefix)
        await context.send(
            embed=await context.lavalink.construct_embed(
                description=message,
                messageable=context,
            )
        )

    @command_plset.command(name="stats")
    @commands.is_owner()
    async def command_plset_stats(self, context: PyLavContext, *, server: discord.Guild = None) -> None:
        """Manage active players"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        if server and (self.lavalink.player_manager.get(server.id) is None):
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("No active player in {name}").format(bold(server.name)),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        elif not self.lavalink.player_manager.connected_players:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("No connected players"),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        await StatsMenu(
            cog=self,
            bot=self.bot,
            source=PlayersSource(cog=self, specified_guild=server.id if server else None),
            original_author=context.author,
        ).start(ctx=context)

    @command_plset.command(name="activity")
    @commands.is_owner()
    async def command_plset_activity(self, context: PyLavContext) -> None:
        """Toggle whether or not to change the bot's activity"""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)
        global_config = self.lavalink.lib_db_manager.get_config()
        current = await global_config.fetch_update_bot_activity()
        await global_config.update_update_bot_activity(not current)
        if not current:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav will change bot activity"),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.lavalink.construct_embed(
                    description=_("PyLav will no longer change the bot activity"),
                    messageable=context,
                ),
                ephemeral=True,
            )
