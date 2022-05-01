import asyncio
import contextlib
import json
from abc import ABC
from pathlib import Path

import discord
from redbot.core import commands
from redbot.core.i18n import Translator
from redbot.core.utils.chat_formatting import box, humanize_list, inline

from pylav.converters.nodes import NodeConverter
from pylav.utils import PyLavContext

from audio.cog import MPMixin
from audio.cog.menus.menus import AddNodeFlow
from audio.cog.utils.nodes import maybe_prompt_for_node

_ = Translator("MediaPlayer", Path(__file__))


class NodeCommands(MPMixin, ABC):
    @commands.is_owner()
    @commands.group(name="nodeset")
    async def command_nodeset(self, context: PyLavContext) -> None:
        """Configure PyLav Nodes."""

    @command_nodeset.command(name="add", aliases=["create", "new"])
    async def command_nodeset_add(self, context: PyLavContext) -> None:
        """Add a node PyLav."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        menu = AddNodeFlow(
            cog=self,
            original_author=context.author,
        )
        title = _("Let's add a node to PyLav!")
        info_description = _(
            "(**1**){space} - Apply changes and add the node to PyLav.\n"
            "(**2**){space} - Cancel any changes made and close the menu.\n"
            "(**3**){space} - Toggle between search-only and search and playback modes.\n"
            "(**4**){space} - Toggle between SSL on and off.\n"
            "(**5**){space} - Add a name to the node.\n"
            "(**6**){space} - Add the host address of the node.\n"
            "(**7**){space} - Add the port the node uses.\n"
            "(**8**){space} - Set the password for the node.\n"
            "(**9**){space} - Set the connection timeout.\n"
            "(**10**) - Select which sources to disable for this node (Multiple can be selected).\n"
            "If you interact with a button multiple times,  "
            "only the last interaction will take effect.\n\n\n"
        ).format(
            space="\N{EN SPACE}",
        )
        await menu.start(context, description=info_description, title=title)
        with contextlib.suppress(asyncio.TimeoutError):
            await menu.wait_until_complete()
        if menu.cancelled:
            return
        if not all([menu.host, menu.password, menu.unique_identifier, menu.port, menu.name, menu.resume_timeout]):
            return
        node = await self.lavalink.add_node(
            host=menu.host,
            password=menu.password,
            unique_identifier=menu.unique_identifier,
            port=menu.port,
            name=menu.name,
            resume_timeout=menu.resume_timeout,
            resume_key=f"{menu.name}-{menu.unique_identifier}",
            ssl=menu.ssl,
            reconnect_attempts=-1,
            search_only=menu.search_only,
            managed=False,
            disabled_sources=list(menu.disabled_sources_selector.values),
        )
        try:
            async with context.typing():
                if node:
                    with contextlib.suppress(asyncio.TimeoutError):
                        await node.wait_until_ready(timeout=120)
                        await node.update_features()
                        await node.update_disabled_sources(set(menu.disabled_sources_selector.values))
                disabled_capabilities = set(menu.disabled_sources_selector.values).union(
                    await node.get_unsupported_features()
                )
                embed = await self.lavalink.construct_embed(
                    description=(
                        "Added node {name} with the following settings:\n"
                        "Host: {host}\n"
                        "Port: {port}\n"
                        "Password: {password}\n"
                        "Resume Timeout: {resume_timeout}\n"
                        "Search Only: {search_only}\n"
                        "SSL: {ssl}\n"
                        "Disabled Sources: {disabled_sources}\n"
                    ).format(
                        name=inline(menu.name),
                        host=menu.host,
                        port=menu.port,
                        password=menu.password,
                        resume_timeout=menu.resume_timeout,
                        search_only=menu.search_only,
                        ssl=menu.ssl,
                        disabled_sources=humanize_list(list(disabled_capabilities)),
                    ),
                    messageable=context.channel,
                )
                if menu.last_interaction:
                    await menu.last_interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await context.author.send(
                        embed=embed,
                    )
        except Exception:
            if menu.last_interaction:
                await menu.last_interaction.followup.send(
                    embed=await self.lavalink.construct_embed(
                        description="Unable to add this node.", messageable=context.channel
                    ),
                    ephemeral=True,
                )
            else:
                await context.author.send(
                    embed=await self.lavalink.construct_embed(
                        description="Unable to add this node.", messageable=context.channel
                    ),
                )

    @command_nodeset.command(name="remove", aliases=["delete", "del", "rm"])
    async def command_nodeset_remove(self, context: commands.Context, *, nodes: NodeConverter):
        """Remove a node from PyLav instance."""
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        node = await maybe_prompt_for_node(cog=self, nodes=nodes, context=context)
        if not node:
            return
        if node.managed:
            await context.send(
                embed=await self.lavalink.construct_embed(
                    description=_("{name} is managed by PyLav and cannot be removed.").format(name=node.name),
                    messageable=context.channel,
                ),
                ephemeral=True,
            )
            return
        await self.lavalink.remove_node(node.id)
        node_data = node.to_dict()
        for k in ["id", "resume_key", "resume_timeout", "managed", "reconnect_attempts", "extras"]:
            node_data.pop(k, None)
        yaml = node_data.pop("yaml", None)
        if yaml:
            node_data["server"] = yaml["server"]
            node_data["server"].update(yaml["lavalink"]["server"])
        await context.author.send(
            embed=await self.lavalink.construct_embed(
                description=_("Removed node {name}.\n\n{data}").format(
                    name=node.name, data=box(lang="json", text=json.dumps(node_data, indent=2, sort_keys=True))
                ),
                messageable=context.channel,
            )
        )
        await context.send(
            embed=await self.lavalink.construct_embed(
                description=_(
                    "Removed node {name}, a DM was sent to you with the node details in case you wish to re-add it."
                ).format(name=node.name),
                messageable=context.channel,
            ),
            ephemeral=True,
        )
