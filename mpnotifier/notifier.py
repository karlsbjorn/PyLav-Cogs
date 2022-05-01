from __future__ import annotations

from pathlib import Path

from redbot.core import Config
from redbot.core.commands import commands
from redbot.core.data_manager import cog_data_path
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils.chat_formatting import box, inline
from tabulate import tabulate

from mpnotifier.notifier_commands import Commands
from pylav import Client, events
from pylav.filters import Equalizer, Volume
from pylav.types import BotT
from pylav.utils import format_time

_ = Translator("MPNotifier", Path(__file__))


@cog_i18n(_)
class MPNotifier(commands.Cog, Commands):
    lavalink: Client

    def __init__(self, bot: BotT, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bot = bot
        self._init_task = None
        self.lavalink = Client(bot=self.bot, cog=self, config_folder=cog_data_path(raw_name="PyLav"))
        self._config = Config.get_conf(self, identifier=208903205982044161)
        self._config.register_global(
            notify_channel_id=None, node_connected=[True, True], node_disconnected=[True, True]
        )
        self._config.register_guild(
            track_stuck=[True, True],
            track_exception=[True, True],
            track_end=[True, True],
            track_start_youtube_music=[True, True],
            track_start_spotify=[True, True],
            track_start_apple_music=[True, True],
            track_start_localfile=[True, True],
            track_start_http=[True, True],
            track_start_speak=[True, True],
            track_start_youtube=[True, True],
            track_start_clypit=[True, True],
            track_start_getyarn=[True, True],
            track_start_mixcloud=[True, True],
            track_start_ocrmix=[True, True],
            track_start_pornhub=[True, True],
            track_start_reddit=[True, True],
            track_start_soundgasm=[True, True],
            track_start_tiktok=[True, True],
            track_start_bandcamp=[True, True],
            track_start_soundcloud=[True, True],
            track_start_twitch=[True, True],
            track_start_vimeo=[True, True],
            track_start_gctts=[True, True],
            track_start_niconico=[True, True],
            track_start=[True, True],
            track_skipped=[True, True],
            track_seek=[True, True],
            track_replaced=[True, True],
            track_previous_requested=[True, True],
            tracks_requested=[True, True],
            track_autoplay=[True, True],
            track_resumed=[True, True],
            queue_shuffled=[True, True],
            queue_end=[True, True],
            queue_track_position_changed=[True, True],
            queue_tracks_removed=[True, True],
            player_update=[False, False],
            player_paused=[True, True],
            player_stopped=[True, True],
            player_resumed=[True, True],
            player_moved=[True, True],
            player_disconnected=[True, True],
            player_connected=[True, True],
            volume_changed=[True, True],
            player_repeat=[True, True],
            player_restored=[True, True],
            segment_skipped=[True, True],
            segments_loaded=[False, False],
            filters_applied=[True, True],
            node_connected=[False, False],
            node_disconnected=[False, False],
            node_changed=[False, False],
            websocket_closed=[False, False],
        )

    async def initialize(self) -> None:
        await self.lavalink.register(self)
        await self.lavalink.initialize()

    async def cog_unload(self) -> None:
        if self._init_task is not None:
            self._init_task.cancel()
        await self.bot.lavalink.unregister(cog=self)

    @commands.Cog.listener()
    async def on_pylav_track_stuck(self, event: events.TrackStuckEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Stuck Event"),
                description=_("[Node={node}] {track} is stuck for {threshold} seconds, skipping.").format(
                    track=await event.track.get_track_display_name(with_url=True),
                    threshold=event.threshold // 1000,
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_exception(self, event: events.TrackExceptionEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_exception", default=[True, True]
        )
        if not notify:
            return

        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Exception Event"),
                description=_("[Node={node}] There was an error while playing {track}:\n{exception}").format(
                    track=await event.track.get_track_display_name(with_url=True),
                    exception=event.exception,
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_end(self, event: events.TrackEndEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw("track_end", default=[True, True])
        if not notify:
            return
        if event.reason == "FINISHED":
            reason = _("the player reached the end of the tracks runtime.")
        elif event.reason == "REPLACED":
            reason = _("a new track started playing.")
        elif event.reason == "LOAD_FAILED":
            reason = _("it failed to start.")
        elif event.reason == "STOPPED":
            reason = _("because the player was stopped.")
        else:  # CLEANUP
            reason = _("the node told it to stop.")
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track End Event"),
                description=_("[Node={node}] {track} has finished playing because {reason}").format(
                    track=await event.track.get_track_display_name(with_url=True), reason=reason, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start(self, event: events.TrackStartEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_("[Node={node}] {track} has started playing.\nRequested by: {requester}").format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_youtube_music(self, event: events.TrackStartYouTubeMusicEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_youtube_music", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] YouTube Music track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_spotify(self, event: events.TrackStartSpotifyEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_spotify", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] Spotify track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_apple_music(self, event: events.TrackStartAppleMusicEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_apple_music", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] Apple Music track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_localfile(self, event: events.TrackStartLocalFileEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_localfile", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] Local track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_http(self, event: events.TrackStartHTTPEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_http", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] HTTP track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_speak(self, event: events.TrackStartSpeakEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_speak", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] Text-To-Speech track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_youtube(self, event: events.TrackStartYouTubeEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_youtube", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] YouTube track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user, node=event.node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_clypit(self, event: events.TrackStartGetYarnEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_clypit", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    node=event.node.name,
                    source=await event.track.query_source(),
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_getyarn(self, event: events.TrackStartGetYarnEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_getyarn", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    node=event.node.name,
                    source=await event.track.query_source(),
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_mixcloud(self, event: events.TrackStartMixCloudEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_mixcloud", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    node=event.node.name,
                    source=await event.track.query_source(),
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_ocrmix(self, event: events.TrackStartMixCloudEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_ocrmix", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_pornhub(self, event: events.TrackStartPornHubEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_pornhub", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_reddit(self, event: events.TrackStartPornHubEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_reddit", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_soundgasm(self, event: events.TrackStartSoundgasmEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_soundgasm", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_tiktok(self, event: events.TrackStartSoundgasmEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_tiktok", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_bandcamp(self, event: events.TrackStartBandcampEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_bandcamp", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_soundcloud(self, event: events.TrackStartSoundCloudEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_soundcloud", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_twitch(self, event: events.TrackStartTwitchEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_twitch", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_vimeo(self, event: events.TrackStartVimeoEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_vimeo", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_gctts(self, event: events.TrackStartGCTTSEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_gctts", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_start_niconicoo(self, event: events.TrackStartNicoNicoEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_start_niconico", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.track.requester or self.bot.user
            user = req.mention
        else:
            user = event.track.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Start Event"),
                description=_(
                    "[Node={node}] {source} track: {track} has started playing.\nRequested by: {requester}"
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                    source=await event.track.query_source(),
                    node=event.node.name,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_skipped(self, event: events.TrackSkippedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_skipped", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Skipped Event"),
                description=_("{track} has been skipped.\nRequested by {requester}").format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_seek(self, event: events.TrackSeekEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw("track_seek", default=[True, True])
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Seek Event"),
                description=_(
                    "{requester} requested that {track} is sought from position {fro} to position {after}."
                ).format(
                    track=await event.track.get_track_display_name(with_url=True),
                    fro=format_time(event.before),
                    after=format_time(event.after),
                    requester=user,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def pylav_track_previous_requested(self, event: events.TrackPreviousRequestedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "previous_requested", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Previous Requested Event"),
                description=_("{requester} requested that the previous track {track} be played.").format(
                    track=await event.track.get_track_display_name(with_url=True),
                    requester=user,
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_tracks_requested(self, event: events.TracksRequestedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "tracks_requested", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Tracks Requested Event"),
                description=_("{requester} added {track_count} to the queue.").format(
                    track_count=len(event.tracks), requester=user
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_autoplay(self, event: events.TrackAutoPlayEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_autoplay", default=[True, True]
        )
        if not notify:
            return
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track AutoPlay Event"),
                description=_("Auto-playing {track}.").format(
                    track=await event.track.get_track_display_name(with_url=True)
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_track_resumed(self, event: events.TrackResumedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "track_resumed", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Track Resumed Event"),
                description=_("{requester} resumed {track}.").format(
                    track=await event.track.get_track_display_name(with_url=True), requester=user
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_shuffled(self, event: events.QueueShuffledEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "queue_shuffled", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Queue Shuffled Event"),
                description=_("{requester} shuffled the queue.").format(requester=user),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_end(self, event: events.QueueEndEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw("queue_end", default=[True, True])
        if not notify:
            return
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Queue End Event"),
                description=_("All tracks in the queue have been played."),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_queue_tracks_removed(self, event: events.QueueTracksRemovedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "tracks_removed", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Tracks Removed Event"),
                description=_("{requester} removed {track_count} tracks from the queue.").format(
                    track_count=len(event.tracks), requester=user
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_paused(self, event: events.PlayerPausedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "player_paused", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Player Paused Event"),
                description=_("{requester} paused the player.").format(requester=user),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_stopped(self, event: events.PlayerStoppedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "player_stopped", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Player Stopped Event"),
                description=_("{requester} stopped the player.").format(requester=user),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_resumed(self, event: events.PlayerResumedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "player_resumed", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Player Resumed Event"),
                description=_("{requester} resumed the player.").format(requester=user),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_moved(self, event: events.PlayerMovedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "player_moved", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Player Moved Event"),
                description=_("{requester} moved the player from {before} to {after}.").format(
                    requester=user, before=event.before, after=event.after
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_disconnected(self, event: events.PlayerDisconnectedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "player_disconnected", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Player Disconnected Event"),
                description=_("{requester} disconnected the player.").format(requester=user),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_connected(self, event: events.PlayerConnectedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "player_connected", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Player Connected Event"),
                description=_("{requester} connected the player.").format(requester=user),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_volume_changed(self, event: events.PlayerVolumeChangedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "volume_changed", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Player Volume Changed Event"),
                description=_("{requester} changed the player's volume from {before} to {after}.").format(
                    requester=user, before=event.before, after=event.after
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_player_repeat(self, event: events.PlayerRepeatEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "player_repeat", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user

        if event.type == "disable":
            await player.notify_channel.send(
                embed=await self.lavalink.construct_embed(
                    title=_("Player Repeat Event"),
                    description=_("{requester} disabled repeat.").format(requester=user),
                    messageable=player.notify_channel,
                )
            )
        elif event.type == "queue":
            await player.notify_channel.send(
                embed=await self.lavalink.construct_embed(
                    title=_("Player Repeat Event"),
                    description=_("{requester} {status} repeat of the whole queue.").format(
                        requester=user, status=_("enabled") if event.queue_after else _("disabled")
                    ),
                    messageable=player.notify_channel,
                )
            )
        else:
            await player.notify_channel.send(
                embed=await self.lavalink.construct_embed(
                    title=_("Player Repeat Event"),
                    description=_("{requester} {status} repeat for {track}.").format(
                        requester=user,
                        status=_("enabled") if event.current_after else _("disabled"),
                        track=await event.player.current.get_track_display_name(with_url=True),
                    ),
                    messageable=player.notify_channel,
                )
            )

    @commands.Cog.listener()
    async def on_pylav_player_restored(self, event: events.PlayerRestoredEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "player_restored", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Player Restored Event"),
                description=_("{requester} restored the player.").format(requester=user),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_segment_skipped(self, event: events.SegmentSkippedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "segment_skipped", default=[True, True]
        )
        if not notify:
            return
        segment = event.segment

        if segment.category == "intro":
            explanation = _("an intro section")
        elif segment.category == "outro":
            explanation = _("an outro section")
        elif segment.category == "preview":
            explanation = _("a preview section")
        elif segment.category == "music_offtopic":
            explanation = _("an off-topic section")
        elif segment.category == "filler":
            explanation = _("a filler section")
        elif segment.category == "sponsor":
            explanation = _("a sponsor section")
        elif segment.category == "selfpromo":
            explanation = _("a self-promotion section")
        else:
            explanation = _("an interaction section")

        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Sponsor Segment Skipped Event"),
                description=_("Sponsorblock: Skipped {category} running from {start}s to {to}s.").format(
                    category=explanation, start=segment.start // 1000, to=segment.end // 1000
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_filters_applied(self, event: events.FiltersAppliedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "filters_applied", default=[True, True]
        )
        if not notify:
            return
        if mention:
            req = event.requester or self.bot.user
            user = req.mention
        else:
            user = event.requester or self.bot.user
        t_effect = _("Effect")
        t_values = _("Values")
        data = []
        for effect in (
            event.volume,
            event.equalizer,
            event.karaoke,
            event.timescale,
            event.tremolo,
            event.vibrato,
            event.rotation,
            event.distortion,
            event.low_pass,
            event.channel_mix,
        ):
            if not effect or isinstance(effect, Volume):
                continue

            data_ = {t_effect: effect.__class__.__name__}
            if effect.changed:
                values = effect.to_dict()
                values.pop("off")
                if not isinstance(effect, Equalizer):
                    data_[t_values] = "\n".join(f"{k.title()}: {v}" for k, v in values.items())
                else:
                    values = values["equalizer"]
                    data_[t_values] = "\n".join(
                        [f"Band {band['band']}: {band['gain']}" for band in values if band["gain"]]
                    )
            else:
                data_[t_values] = _("N/A")
            data.append(data_)
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Filters Applied Event"),
                description=_("{requester} changed the player filters.\n\n__**Currently Applied:**__\n{data}").format(
                    requester=user,
                    data=box(tabulate(data, headers="keys", tablefmt="fancy_grid")) if data else _("None"),
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_node_connected(self, event: events.NodeConnectedEvent) -> None:
        notify, mention = await self._config.get_raw("node_connected", default=[True, True])
        if not notify:
            return
        if channel_id := await self._config.notify_channel_id():
            if notify_channel := self.bot.get_channel(channel_id):
                await notify_channel.send(
                    embed=await self.lavalink.construct_embed(
                        title=_("Node Connected Event"),
                        description=_("Node {name} has been connected.").format(name=inline(event.node.name)),
                        messageable=notify_channel,
                    )
                )

    @commands.Cog.listener()
    async def on_pylav_node_disconnected(self, event: events.NodeDisconnectedEvent) -> None:
        notify, mention = await self._config.get_raw("node_disconnected", default=[True, True])
        if not notify:
            return
        if channel_id := await self._config.notify_channel_id():
            if notify_channel := self.bot.get_channel(channel_id):
                await notify_channel.send(
                    embed=await self.lavalink.construct_embed(
                        title=_("Node Disconnected Event"),
                        description=_(
                            "Node {name} has been disconnected with code {code} and reason: {reason}."
                        ).format(name=inline(event.node.name), code=event.code, reason=event.reason),
                        messageable=notify_channel,
                    )
                )

    @commands.Cog.listener()
    async def on_pylav_node_changed(self, event: events.NodeChangedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "node_changed", default=[True, True]
        )
        if not notify:
            return
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("Node Changed Event"),
                description=_("The node which the player is connected to changed from {fro} to {to}.").format(
                    fro=event.old_node.name, to=event.new_node.name
                ),
                messageable=player.notify_channel,
            )
        )

    @commands.Cog.listener()
    async def on_pylav_websocket_closed(self, event: events.WebSocketClosedEvent) -> None:
        player = event.player
        if player.notify_channel is None:
            return
        notify, mention = await self._config.guild(guild=event.player.guild).get_raw(
            "websocket_closed", default=[True, True]
        )
        if not notify:
            return
        await player.notify_channel.send(
            embed=await self.lavalink.construct_embed(
                title=_("WebSocket Closed Event"),
                description=_(
                    "The websocket connection to the Lavalink node closed with code {code} and reason {reason}."
                ).format(code=event.code, reason=event.reason),
                messageable=player.notify_channel,
            )
        )
