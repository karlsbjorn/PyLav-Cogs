from __future__ import annotations

import contextlib
import datetime
from pathlib import Path

import discord
from redbot.core import commands
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import humanize_number

from pylav.core.context import PyLavContext
from pylav.extension.red.utils import rgetattr
from pylav.extension.red.utils.decorators import invoker_is_dj
from pylav.helpers.format.strings import shorten_string
from pylav.helpers.time import get_now_utc
from pylav.logging import getLogger
from pylav.players.player import Player
from pylav.players.query.obj import Query
from pylav.players.tracks.obj import Track
from pylav.type_hints.bot import DISCORD_COG_TYPE_MIXIN

LOGGER = getLogger("PyLav.cog.Player.commands.player")
_ = Translator("PyLavPlayer", Path(__file__))


@cog_i18n(_)
class PlayerCommands(DISCORD_COG_TYPE_MIXIN):
    @commands.command(
        name="bump",
        description=shorten_string(max_length=100, string=_("Reproducira navedenu pjesmu u redu čekanja")),
    )
    @commands.guild_only()
    @invoker_is_dj()
    async def command_bump(self, context: PyLavContext, queue_number: int, after_current: bool = False):
        """
        Plays the specified track from the queue.

        If you specify the `after_current` argument, the track will be played after the current track; otherwise, it will replace the current track.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        player = context.player

        if player.queue.empty():
            await context.send(
                embed=await context.construct_embed(
                    description=shorten_string(max_length=100, string=_("There are no songs in the queue.")),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        if queue_number < 1 or queue_number > player.queue.size():
            await context.send(
                embed=await context.construct_embed(
                    description=_("Track index must be between 1 and {size_of_queue_variable_do_not_translate}").format(
                        size_of_queue_variable_do_not_translate=player.queue.size()
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return
        queue_number -= 1

        try:
            if after_current:
                track = await player.move_track(queue_number, context.author, 0)
            else:
                track = player.queue.popindex(queue_number)
        except ValueError:
            await context.send(
                embed=await context.construct_embed(
                    description=_("There are no tracks in position {queue_position_variable_do_not_translate}.").format(
                        queue_position_variable_do_not_translate=humanize_number(queue_number + 1)
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            return

        if after_current:
            await context.send(
                embed=await context.construct_embed(
                    description=_(
                        "{track_name_variable_do_not_translate} will play after {current_track_name_variable_do_not_translate} "
                        "finishes ({estimated_time_variable_do_not_translate})."
                    ).format(
                        track_name_variable_do_not_translate=await track.get_track_display_name(with_url=True),
                        current_track_name_variable_do_not_translate=await player.current.get_track_display_name(
                            with_url=True
                        ),
                        estimated_time_variable_do_not_translate=discord.utils.format_dt(
                            datetime.timedelta(
                                milliseconds=await player.current.duration() - await player.fetch_position()
                            )
                            + get_now_utc(),
                            style="R",
                        ),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.construct_embed(
                    description=_(
                        "{track_name_variable_do_not_translate} will start now\n{current_track_name_variable_do_not_translate} has been skipped."
                    ).format(
                        track_name_variable_do_not_translate=await track.get_track_display_name(with_url=True),
                        current_track_name_variable_do_not_translate=await player.current.get_track_display_name(
                            with_url=True
                        ),
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
            await player.play(track=track, requester=context.author, query=await track.query())

    @commands.command(
        name="playnext",
        description=shorten_string(max_length=100, string=_("Reproduciraj pjesmu na vrhu reda čekanja")),
        aliases=["pn"],
    )
    @commands.guild_only()
    @invoker_is_dj()
    async def command_playnext(self, context: PyLavContext, *, query: str):
        """Enqueue a track at the top of the queue."""
        if isinstance(context, discord.Interaction) and not context.response.is_done():
            await context.response.defer(ephemeral=True)

        player = context.player

        if player is None:
            config = self.pylav.player_config_manager.get_config(context.guild.id)
            if (channel := context.guild.get_channel_or_thread(await config.fetch_forced_channel_id())) is None:
                channel = rgetattr(context.author, "voice.channel", None)
                if not channel:
                    await context.send(
                        embed=await self.pylav.construct_embed(
                            description=_("You must be in a voice channel to allow me to connect"), messageable=context
                        ),
                        ephemeral=True,
                    )
                    return
            if not (
                (permission := channel.permissions_for(context.guild.me)) and permission.connect and permission.speak
            ):
                await context.send(
                    embed=await self.pylav.construct_embed(
                        description=_(
                            "I do not have permission to connect or speak in {channel_name_variable_do_not_translate}."
                        ).format(channel_name_variable_do_not_translate=channel.mention),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            player = await self.pylav.connect_player(channel=channel, requester=context.author)

        queries = [await Query.from_string(qf) for q in query.split("\n") if (qf := q.strip("<>").strip())]
        total_tracks_enqueue = 0
        single_track = None
        if queries:
            single_track, total_tracks_enqueue = await self._process_queries(
                context, queries, player, single_track, total_tracks_enqueue
            )
        if not (player.is_playing or player.queue.empty()):
            await player.next(requester=context.author)

        await self._send_play_next_message(context, single_track, total_tracks_enqueue)

    async def _process_queries(
        self,
        context: PyLavContext,
        queries: list[Query],
        player: Player,
        single_track: Track,
        total_tracks_enqueue: int,
    ) -> tuple[Track, int]:
        successful, count, failed = await self.pylav.get_all_tracks_for_queries(
            *queries, requester=context.author, player=player
        )
        if successful:
            single_track = successful[0]
        total_tracks_enqueue += count
        if count:
            if count == 1:
                await player.add(requester=context.author.id, track=successful[0], index=0)
            else:
                await player.bulk_add(requester=context.author.id, tracks_and_queries=successful, index=0)
        return single_track, total_tracks_enqueue

    async def _send_play_next_message(
        self, context: PyLavContext, single_track: Track, total_tracks_enqueue: int
    ) -> None:
        if total_tracks_enqueue > 1:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("{number_of_tracks_variable_do_not_translate} tracks have been enqueued.").format(
                        number_of_tracks_variable_do_not_translate=total_tracks_enqueue
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
        elif total_tracks_enqueue == 1:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("{track_name_variable_do_not_translate} has been enqueued.").format(
                        track_name_variable_do_not_translate=await single_track.get_track_display_name(with_url=True)
                    ),
                    thumbnail=await single_track.artworkUrl(),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await self.pylav.construct_embed(
                    description=_("No tracks were found for your query."),
                    messageable=context,
                ),
                ephemeral=True,
            )

    @commands.command(name="remove", description=_("Ukloni navedenu pjesmu iz reda čekanja"))
    @commands.guild_only()
    @invoker_is_dj()
    async def command_remove(self, context: PyLavContext, track_url_or_index: str, remove_duplicates: bool = False):
        """
        Remove the specified track from the queue.

        If you specify the `remove_duplicates` argument, all tracks that are the same as your URL or the index track will be removed.
        """
        if isinstance(context, discord.Interaction):
            context = await self.bot.get_context(context)
        if context.interaction and not context.interaction.response.is_done():
            await context.defer(ephemeral=True)

        player = context.player
        # noinspection PyUnusedLocal
        queue_number = None
        if player.queue.empty():
            await context.send(
                embed=await context.construct_embed(description=_("Queue is empty."), messageable=context),
                ephemeral=True,
            )
            return
        with contextlib.suppress(ValueError):
            queue_number = int(track_url_or_index)
        # noinspection PyUnusedLocal
        track = None
        number_removed = 0
        if queue_number:
            if queue_number < 1 or queue_number > player.queue.size():
                await context.send(
                    embed=await context.construct_embed(
                        description=_(
                            "Track index must be between 1 and {queue_size_variable_do_not_translate}."
                        ).format(queue_size_variable_do_not_translate=player.queue.size()),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
            queue_number -= 1
            with contextlib.suppress(ValueError):
                track = player.queue.popindex(queue_number)
                number_removed += 1
            if not track:
                await context.send(
                    embed=await context.construct_embed(
                        description=_("There is no track in position {position_variable_do_not_translate}.").format(
                            position_variable_do_not_translate=queue_number
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return
        else:
            try:
                data = await self.pylav.decode_track(track_url_or_index, raise_on_failure=True)
                track = await Track.build_track(
                    node=player.node,
                    data=data,
                    query=None,
                    requester=context.author.id,
                )
            except Exception:  # noqa
                track = await Track.build_track(
                    node=player.node,
                    data=None,
                    query=await Query.from_string(track_url_or_index),
                    requester=context.author.id,
                )
        try:
            number_removed += await player.remove_from_queue(
                track, requester=context.author, duplicates=remove_duplicates
            )
        except IndexError:
            if not number_removed:
                await context.send(
                    embed=await context.construct_embed(
                        description=_("{track_name_variable_do_not_translate} not found in queue.").format(
                            track_name_variable_do_not_translate=await track.get_track_display_name(with_url=True)
                        ),
                        messageable=context,
                    ),
                    ephemeral=True,
                )
                return

        if number_removed == 0:
            await context.send(
                embed=await context.construct_embed(
                    description=_("No tracks were removed from the queue."),
                    messageable=context,
                ),
                ephemeral=True,
            )
        elif number_removed == 1:
            await context.send(
                embed=await context.construct_embed(
                    description=_(
                        "I have removed a single entry of {track_name_variable_do_not_translate} from the queue."
                    ).format(track_name_variable_do_not_translate=await track.get_track_display_name(with_url=True)),
                    messageable=context,
                ),
                ephemeral=True,
            )
        else:
            await context.send(
                embed=await context.construct_embed(
                    description=_(
                        "I have removed {number_of_entries_variable_do_not_translate} entries of {track_name_variable_do_not_translate} from the queue."
                    ).format(
                        track_name_variable_do_not_translate=await track.get_track_display_name(with_url=True),
                        number_of_entries_variable_do_not_translate=number_removed,
                    ),
                    messageable=context,
                ),
                ephemeral=True,
            )
