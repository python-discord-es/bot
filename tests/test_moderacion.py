from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from comandos.moderacion import (
    ApproveButton,
    RejectButton,
    RejectModal,
    _decode_message,
    _encode_message,
    _pending_author,
)
from tests.factories import (
    encode_for_mod_row,
    encode_for_mod_row_legacy,
    make_ctx,
    make_interaction,
    make_member,
    read_last_csv_row,
)


def add_pending_row(cog, post_id, *, channel="envio-eventos", author_id=42, author_name="autor",
                     content="contenido de prueba", legacy_encoding=False):
    encode = encode_for_mod_row_legacy if legacy_encoding else encode_for_mod_row
    new_row = {
        "date": "2026-01-01 00:00:00",
        "message_id": str(post_id),
        "channel": channel,
        "author_id": str(author_id),
        "author": author_name,
        "message": encode(content),
    }
    cog.bot.data_mod[str(post_id)] = new_row
    return new_row


class TestMessageEncoding:
    def test_round_trips(self):
        assert _decode_message(_encode_message("hola mundo")) == "hola mundo"

    def test_round_trips_accented_and_emoji(self):
        text = "¿Cómo estás? 🎉"
        assert _decode_message(_encode_message(text)) == text

    def test_decodes_the_legacy_bytes_repr_format(self):
        """Rows written before the eval()-removal fix stored the repr of a
        base64 bytes object (e.g. "b'aG9sYQ=='") instead of a plain base64
        string. _decode_message must still handle those without eval()."""
        legacy = encode_for_mod_row_legacy("mensaje antiguo")

        assert legacy.startswith("b'")
        assert _decode_message(legacy) == "mensaje antiguo"


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
class TestResolveAuthor:
    def test_regular_context_uses_author(self, moderacion_cog):
        member = make_member(name="alguien")
        ctx = make_ctx(author=member)

        assert moderacion_cog._resolve_author(ctx) is member

    def test_interaction_uses_user(self, moderacion_cog):
        member = make_member(name="alguien")
        interaction = make_interaction(user=member)

        assert moderacion_cog._resolve_author(interaction) is member


class TestLookupAuthor:
    async def test_cached_on_the_bot_resolves_directly(self, moderacion_cog):
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")

        author = await moderacion_cog._lookup_author(99)

        assert author.id == 99

    async def test_cache_miss_falls_back_to_fetching_the_guild_member(self, moderacion_cog):
        """The exact bug this guards against: bot.get_user() only checks
        the local cache - without the Members intent, that cache can miss
        someone who's genuinely still in the server but hasn't triggered
        an event the bot observed since its last reconnect/restart."""
        moderacion_cog.guild.members_by_id[770973060496359454] = make_member(
            id=770973060496359454, name="remitente"
        )

        author = await moderacion_cog._lookup_author(770973060496359454)

        assert author.id == 770973060496359454
        moderacion_cog.guild.fetch_member.assert_awaited_once_with(770973060496359454)

    async def test_not_cached_and_not_a_guild_member_returns_none(self, moderacion_cog):
        assert await moderacion_cog._lookup_author(404) is None

    async def test_no_guild_resolved_yet_returns_none_instead_of_crashing(self, moderacion_cog):
        moderacion_cog.guild = None

        assert await moderacion_cog._lookup_author(404) is None


class TestIsBot:
    def test_true_for_configured_bot_id(self, moderacion_cog, config):
        ctx = make_ctx(author=make_member(id=config.BOT_ID))

        assert moderacion_cog._is_bot(ctx) is True

    def test_false_for_regular_user(self, moderacion_cog):
        ctx = make_ctx(author=make_member(id=12345))

        assert moderacion_cog._is_bot(ctx) is False


class TestGetChannelsMainModSub:
    def test_resolves_the_three_channels(self, moderacion_cog, moderacion_channels):
        main, mod, sub = moderacion_cog.get_channels_main_mod_sub(moderacion_channels["sub"].id)

        assert main is moderacion_channels["main"]
        assert mod is moderacion_channels["mod"]
        assert sub is moderacion_channels["sub"]


# ---------------------------------------------------------------------------
# _parse_post_id
# ---------------------------------------------------------------------------
class TestParsePostId:
    async def test_interaction_with_message_id_returns_it_directly(
        self, moderacion_cog, moderacion_channels
    ):
        interaction = make_interaction(channel=moderacion_channels["mod"])

        result = await moderacion_cog._parse_post_id(interaction, 555, "%aceptar")

        assert result == "555"

    async def test_valid_numeric_id_from_message_content(self, moderacion_cog, moderacion_channels):
        ctx = make_ctx(channel=moderacion_channels["mod"], content="%aceptar 123")

        assert await moderacion_cog._parse_post_id(ctx, None, "%aceptar") == "123"

    async def test_non_numeric_id_reports_error_and_returns_none(
        self, moderacion_cog, moderacion_channels
    ):
        ctx = make_ctx(channel=moderacion_channels["mod"], content="%aceptar abc")

        result = await moderacion_cog._parse_post_id(ctx, None, "%aceptar")

        assert result is None
        moderacion_channels["mod"].send.assert_awaited_once()
        (msg,), _ = moderacion_channels["mod"].send.call_args
        assert "abc" in msg


# ---------------------------------------------------------------------------
# _get_validated_post
# ---------------------------------------------------------------------------
class TestGetValidatedPost:
    async def test_happy_path_resolves_everything(self, moderacion_cog, moderacion_channels):
        add_pending_row(moderacion_cog, post_id=1, author_id=99)
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")
        ctx = make_ctx(channel=moderacion_channels["mod"], content="%aceptar 1")

        vp = await moderacion_cog._get_validated_post(ctx, None, "%aceptar")

        assert vp is not None
        assert vp.post_id == "1"
        assert vp.message_dec == "contenido de prueba"
        assert vp.ch_main is moderacion_channels["main"]
        assert vp.ch_mod is moderacion_channels["mod"]
        assert vp.ch_sub is moderacion_channels["sub"]
        assert vp.author.id == 99

    async def test_resolves_a_row_logged_before_the_eval_removal_fix(
        self, moderacion_cog, moderacion_channels
    ):
        add_pending_row(moderacion_cog, post_id=2, author_id=99, legacy_encoding=True)
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")
        ctx = make_ctx(channel=moderacion_channels["mod"], content="%aceptar 2")

        vp = await moderacion_cog._get_validated_post(ctx, None, "%aceptar")

        assert vp is not None
        assert vp.message_dec == "contenido de prueba"

    async def test_unknown_post_id_reports_error_and_returns_none(
        self, moderacion_cog, moderacion_channels
    ):
        ctx = make_ctx(channel=moderacion_channels["mod"], content="%aceptar 999")

        vp = await moderacion_cog._get_validated_post(ctx, None, "%aceptar")

        assert vp is None
        moderacion_channels["mod"].send.assert_awaited_once()
        (msg,), _ = moderacion_channels["mod"].send.call_args
        assert "999" in msg

    async def test_bot_author_returns_none(self, moderacion_cog, moderacion_channels, config):
        add_pending_row(moderacion_cog, post_id=1)
        ctx = make_ctx(
            author=make_member(id=config.BOT_ID),
            channel=moderacion_channels["mod"],
            content="%aceptar 1",
        )

        assert await moderacion_cog._get_validated_post(ctx, None, "%aceptar") is None

    async def test_unknown_author_reports_error_and_returns_none(
        self, moderacion_cog, moderacion_channels
    ):
        """Regression test: this used to fall through with author=None and
        crash later on author.mention with no clear explanation - now it's
        an explicit, visible failure instead, mirroring get_mod_pending()'s
        handling of the same condition."""
        add_pending_row(moderacion_cog, post_id=1, author_id=404)
        # Not in the bot's user cache nor fetchable via the API - genuinely
        # no longer a member.
        ctx = make_ctx(channel=moderacion_channels["mod"], content="%aceptar 1")

        vp = await moderacion_cog._get_validated_post(ctx, None, "%aceptar")

        assert vp is None
        moderacion_channels["mod"].send.assert_awaited_once()
        (msg,), _ = moderacion_channels["mod"].send.call_args
        assert "404" in msg

    async def test_author_only_resolvable_via_the_api_still_succeeds(
        self, moderacion_cog, moderacion_channels
    ):
        """Regression test for a real report: clicking Aprobar on a
        genuinely-still-a-member's post got "el autor ya no está en el
        servidor" because bot.get_user() only consults the local user
        cache, which - without the privileged Members intent - can miss
        someone who's still in the server but hasn't triggered an event
        the bot observed since its last reconnect/restart. _lookup_author's
        fetch_member() fallback must still resolve them instead of treating
        a cache miss as "no longer in the server"."""
        add_pending_row(moderacion_cog, post_id=1, author_id=770973060496359454)
        moderacion_cog.guild.members_by_id[770973060496359454] = make_member(
            id=770973060496359454, name="remitente"
        )
        ctx = make_ctx(channel=moderacion_channels["mod"], content="%aceptar 1")

        vp = await moderacion_cog._get_validated_post(ctx, None, "%aceptar")

        assert vp is not None
        assert vp.author.id == 770973060496359454


# ---------------------------------------------------------------------------
# _log_action / log_on_message
# ---------------------------------------------------------------------------
class TestLogAction:
    def test_aceptar_writes_expected_line(self, moderacion_cog, isolated_logs):
        row = add_pending_row(moderacion_cog, post_id=1)

        moderacion_cog._log_action("aceptar", row, "1", "moderador#0")

        fields = read_last_csv_row(isolated_logs.log_accepted_file)
        assert fields[1] == "1"  # post_id
        assert fields[6] == "moderador#0"  # moderator
        assert len(fields) == 7  # no "reason" column for aceptar

    def test_rechazar_includes_reason(self, moderacion_cog, isolated_logs):
        row = add_pending_row(moderacion_cog, post_id=2)

        moderacion_cog._log_action("rechazar", row, "2", "moderador#0", "le falta info")

        fields = read_last_csv_row(isolated_logs.log_rejected_file)
        assert fields[-1] == "le falta info"

    def test_rechazar_without_reason_still_writes_the_reason_column(
        self, moderacion_cog, isolated_logs
    ):
        """Regression test: an empty reason used to skip the "reason" field
        entirely (``if reason: line += ...``), leaving that row one column
        short of log_rejected_file's fixed 8-column header - which the CSV
        reader (run on every bot startup) can choke on.
        """
        row = add_pending_row(moderacion_cog, post_id=3)

        moderacion_cog._log_action("rechazar", row, "3", "moderador#0", "")

        fields = read_last_csv_row(isolated_logs.log_rejected_file)
        assert len(fields) == 8
        assert fields[-1] == ""

    def test_embedded_quotes_and_delimiters_round_trip(self, moderacion_cog, isolated_logs):
        """Regression test: hand-built '"{value}"' quoting didn't escape
        embedded quotes/delimiters, silently corrupting the row. A proper
        csv.writer round-trips this correctly.
        """
        tricky_name = 'mod "raro"; con punto y coma'
        row = add_pending_row(moderacion_cog, post_id=4, author_name=tricky_name)

        moderacion_cog._log_action("aceptar", row, "4", tricky_name)

        fields = read_last_csv_row(isolated_logs.log_accepted_file)
        assert fields[6] == tricky_name


class TestLogOnMessage:
    def test_appends_row_and_writes_log_line(self, moderacion_cog, isolated_logs):
        moderacion_cog._msg_id = 777
        moderacion_cog._msg_enc = encode_for_mod_row("hola mundo")
        author = make_member(id=55, name="autor")

        before = len(moderacion_cog.bot.data_mod)
        moderacion_cog.log_on_message("envio-eventos", author)

        assert len(moderacion_cog.bot.data_mod) == before + 1
        fields = read_last_csv_row(isolated_logs.log_mod_file)
        assert fields[1] == "777"


# ---------------------------------------------------------------------------
# get_mod_pending
# ---------------------------------------------------------------------------
class TestGetModPending:
    async def test_empty_data_sets_footer(self, moderacion_cog):
        embed = await moderacion_cog.get_mod_pending(moderacion_cog.bot.data_mod)

        assert embed.footer.text == "No hay mensajes pendientes de moderación"
        assert len(embed.fields) == 0

    async def test_lists_pending_posts_with_known_authors(self, moderacion_cog):
        add_pending_row(moderacion_cog, post_id=1, author_id=99, content="hola" * 20)
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")

        embed = await moderacion_cog.get_mod_pending(moderacion_cog.bot.data_mod)

        assert len(embed.fields) == 1
        assert "1" in embed.fields[0].name

    async def test_lists_pending_posts_only_resolvable_via_the_api(self, moderacion_cog):
        """Regression test: bot.get_user()/guild.get_member() only consult
        the local cache, which (without the Members intent) can miss a
        member who's still in the server but hasn't triggered an event the
        bot observed since its last reconnect - _lookup_author's
        fetch_member() fallback must still resolve them."""
        add_pending_row(moderacion_cog, post_id=1, author_id=770973060496359454)
        moderacion_cog.guild.members_by_id[770973060496359454] = make_member(
            id=770973060496359454, name="remitente"
        )

        embed = await moderacion_cog.get_mod_pending(moderacion_cog.bot.data_mod)

        assert len(embed.fields) == 1

    async def test_skips_posts_from_users_no_longer_in_the_server(self, moderacion_cog):
        add_pending_row(moderacion_cog, post_id=1, author_id=404)
        # Not in the bot's user cache nor fetchable via the API - genuinely
        # no longer a member.

        embed = await moderacion_cog.get_mod_pending(moderacion_cog.bot.data_mod)

        assert len(embed.fields) == 0
        assert embed.footer.text == "No hay mensajes pendientes de moderación"


# ---------------------------------------------------------------------------
# _aceptar_mensaje / _rechazar_mensaje
# ---------------------------------------------------------------------------
class TestAceptarMensaje:
    async def test_removes_pending_row_and_notifies_channels(
        self, moderacion_cog, moderacion_channels, config
    ):
        add_pending_row(moderacion_cog, post_id=1, author_id=99, content="contenido aprobado")
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")
        moderacion_channels["main"].send = AsyncMock(
            return_value=SimpleNamespace(jump_url="https://discord.com/channels/1/2/3")
        )

        ctx = make_ctx(
            author=make_member(name="moderador"),
            channel=moderacion_channels["mod"],
            content="%aceptar 1",
        )

        await moderacion_cog._aceptar_mensaje(ctx)

        assert moderacion_cog.bot.data_mod == {}
        moderacion_channels["main"].send.assert_awaited_once()
        (msg,), _ = moderacion_channels["main"].send.call_args
        assert "contenido aprobado" in msg

        # Regression test: the confirmation sent to the mod channel used to
        # link to a jump_url built from self._msg_id (the *original
        # submission's* id, in a different channel) instead of the message
        # that was actually just posted to ch_main.
        moderacion_channels["mod"].send.assert_awaited_once()
        (mod_msg,), _ = moderacion_channels["mod"].send.call_args
        assert "https://discord.com/channels/1/2/3" in mod_msg

    async def test_unknown_post_id_does_not_touch_channels(self, moderacion_cog, moderacion_channels):
        ctx = make_ctx(channel=moderacion_channels["mod"], content="%aceptar 999")

        await moderacion_cog._aceptar_mensaje(ctx)

        moderacion_channels["main"].send.assert_not_awaited()

    async def test_send_failure_keeps_the_row_pending_and_reports_the_error(
        self, moderacion_cog, moderacion_channels, isolated_logs
    ):
        """Regression test: sending to ch_main used to happen *after*
        logging the accept and dropping the row from bot.data_mod, so a
        failure there (message too long, missing permissions, a transient
        network error, ...) silently lost the post - it was already logged
        "aceptado" and gone from the pending queue with no visible error
        anywhere. Now the row must survive a send failure so it can be
        retried, and the failure must be visible in the mod channel."""
        add_pending_row(moderacion_cog, post_id=1, author_id=99, content="contenido")
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")
        moderacion_channels["main"].send = AsyncMock(side_effect=RuntimeError("boom"))

        ctx = make_ctx(channel=moderacion_channels["mod"], content="%aceptar 1")
        await moderacion_cog._aceptar_mensaje(ctx)

        assert "1" in moderacion_cog.bot.data_mod  # still pending, not lost
        moderacion_channels["mod"].send.assert_awaited_once()
        (msg,), _ = moderacion_channels["mod"].send.call_args
        assert "No se pudo enviar" in msg
        with isolated_logs.log_accepted_file.open() as f:
            assert f.read().strip() == ""  # nothing falsely logged as accepted


class TestRechazarMensaje:
    async def test_removes_pending_row_and_notifies_with_reason(
        self, moderacion_cog, moderacion_channels
    ):
        add_pending_row(moderacion_cog, post_id=2, author_id=99, content="contenido rechazado")
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")

        ctx = make_ctx(
            author=make_member(name="moderador"),
            channel=moderacion_channels["mod"],
            content="%rechazar 2 le falta info aqui",
        )

        await moderacion_cog._rechazar_mensaje(ctx)

        assert moderacion_cog.bot.data_mod == {}
        moderacion_channels["sub"].send.assert_awaited_once()
        _, kwargs = moderacion_channels["sub"].send.call_args
        assert "le falta info aqui" in kwargs["embed"].fields[0].value

    async def test_interaction_path_uses_the_provided_reason(
        self, moderacion_cog, moderacion_channels
    ):
        add_pending_row(moderacion_cog, post_id=3, author_id=99, content="contenido")
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")
        interaction = make_interaction(channel=moderacion_channels["mod"])

        await moderacion_cog._rechazar_mensaje(interaction, message_id=3, reason="motivo modal")

        _, kwargs = moderacion_channels["sub"].send.call_args
        assert "motivo modal" in kwargs["embed"].fields[0].value

    async def test_notify_failure_keeps_the_row_pending_and_reports_the_error(
        self, moderacion_cog, moderacion_channels, isolated_logs
    ):
        """Same reordering fix as the aceptar-side regression test above:
        a failure notifying the submitter must not lose the row or make the
        mod channel claim success anyway."""
        add_pending_row(moderacion_cog, post_id=4, author_id=99, content="contenido")
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")
        moderacion_channels["sub"].send = AsyncMock(side_effect=RuntimeError("boom"))

        ctx = make_ctx(channel=moderacion_channels["mod"], content="%rechazar 4 motivo")
        await moderacion_cog._rechazar_mensaje(ctx)

        assert "4" in moderacion_cog.bot.data_mod  # still pending, not lost
        moderacion_channels["mod"].send.assert_awaited_once()
        (msg,), _ = moderacion_channels["mod"].send.call_args
        assert "No se pudo notificar" in msg
        with isolated_logs.log_rejected_file.open() as f:
            assert f.read().strip() == ""  # nothing falsely logged as rejected


# ---------------------------------------------------------------------------
# on_message listener
# ---------------------------------------------------------------------------
class TestOnMessage:
    async def test_ignores_limpia_command(self, moderacion_cog, moderacion_channels):
        message = make_ctx(channel=moderacion_channels["sub"], content="%limpia").message
        message.author = make_member()
        message.id = 1

        before = len(moderacion_cog.bot.data_mod)
        await moderacion_cog.on_message(message)

        assert len(moderacion_cog.bot.data_mod) == before

    async def test_ignores_channels_outside_the_submission_mapping(
        self, moderacion_cog, moderacion_channels
    ):
        other_channel = moderacion_channels["mod"]  # not a "submission" channel
        message = make_ctx(channel=other_channel, content="hola").message
        message.author = make_member()
        message.id = 2

        before = len(moderacion_cog.bot.data_mod)
        await moderacion_cog.on_message(message)

        assert len(moderacion_cog.bot.data_mod) == before

    async def test_submission_gets_logged_and_forwarded_to_mod_channel(
        self, moderacion_cog, moderacion_channels, monkeypatch
    ):
        import comandos.moderacion as moderacion_module

        monkeypatch.setattr(moderacion_module.asyncio, "sleep", AsyncMock())

        member = make_member(name="remitente")
        message = make_ctx(channel=moderacion_channels["sub"], content="mi propuesta de evento").message
        message.author = member
        message.id = 321

        before = len(moderacion_cog.bot.data_mod)
        await moderacion_cog.on_message(message)

        assert len(moderacion_cog.bot.data_mod) == before + 1
        moderacion_channels["sub"].send.assert_awaited_once()
        moderacion_channels["mod"].send.assert_awaited_once()


# ---------------------------------------------------------------------------
# Persistent Aprobar/Rechazar buttons (discord.ui.DynamicItem)
#
# These reconstruct themselves from custom_id alone (from_custom_id) and
# resolve the cog via interaction.client.get_cog(...) instead of a Python
# closure, which is exactly what makes them keep working after a bot
# restart - see ApproveButton's docstring in comandos/moderacion.py.
# ---------------------------------------------------------------------------
def _match_custom_id(button_cls, message_id):
    """A real re.Match for button_cls's template, the same kind
    discord.py hands to from_custom_id() when routing an interaction."""
    custom_id = f"moderacion:{'aprobar' if button_cls is ApproveButton else 'rechazar'}:{message_id}"
    return button_cls.__discord_ui_compiled_template__.match(custom_id)


class TestPendingAuthor:
    async def test_resolves_the_author_of_a_pending_row(self, moderacion_cog):
        add_pending_row(moderacion_cog, post_id=1, author_id=99)
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")

        author = await _pending_author(moderacion_cog, 1)
        assert author.id == 99

    async def test_unknown_message_id_returns_none(self, moderacion_cog):
        assert await _pending_author(moderacion_cog, 404) is None


class TestApproveButton:
    async def test_from_custom_id_round_trips_the_message_id(self):
        match = _match_custom_id(ApproveButton, 12345)

        button = await ApproveButton.from_custom_id(None, None, match)

        assert button.message_id == 12345
        assert button.item.custom_id == "moderacion:aprobar:12345"

    async def test_callback_resolves_cog_via_interaction_client_and_delegates(
        self, moderacion_cog, moderacion_channels
    ):
        add_pending_row(moderacion_cog, post_id=1, author_id=99)
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")
        moderacion_cog._aceptar_mensaje = AsyncMock()
        interaction = make_interaction(channel=moderacion_channels["mod"])
        interaction.client = SimpleNamespace(get_cog=lambda name: moderacion_cog)

        button = ApproveButton(message_id=1)
        await button.callback(interaction)

        interaction.response.send_message.assert_awaited_once()
        (msg,), _ = interaction.response.send_message.call_args
        assert "<@99>" in msg  # make_member()'s fake mention
        moderacion_cog._aceptar_mensaje.assert_awaited_once_with(interaction, 1)

    async def test_callback_with_no_longer_pending_row_still_delegates(
        self, moderacion_cog, moderacion_channels
    ):
        """The row may already be gone (already handled, or from a message
        old enough the bot restarted since) - _pending_author then returns
        None, and the button falls back to a generic message instead of
        crashing on author.mention."""
        moderacion_cog._aceptar_mensaje = AsyncMock()
        interaction = make_interaction(channel=moderacion_channels["mod"])
        interaction.client = SimpleNamespace(get_cog=lambda name: moderacion_cog)

        button = ApproveButton(message_id=999)
        await button.callback(interaction)

        (msg,), _ = interaction.response.send_message.call_args
        assert "ya no está disponible" in msg
        moderacion_cog._aceptar_mensaje.assert_awaited_once_with(interaction, 999)

    async def test_callback_without_a_registered_cog_does_nothing(self):
        """If the bot somehow has no Moderacion cog loaded, don't crash -
        just skip (nothing to delegate to)."""
        interaction = make_interaction()
        interaction.client = SimpleNamespace(get_cog=lambda name: None)

        await ApproveButton(message_id=1).callback(interaction)

        interaction.response.send_message.assert_not_awaited()


class TestRejectButton:
    async def test_from_custom_id_round_trips_the_message_id(self):
        match = _match_custom_id(RejectButton, 777)

        button = await RejectButton.from_custom_id(None, None, match)

        assert button.message_id == 777

    async def test_callback_opens_a_modal_for_the_resolved_author(
        self, moderacion_cog, moderacion_channels
    ):
        add_pending_row(moderacion_cog, post_id=2, author_id=99)
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")
        interaction = make_interaction(channel=moderacion_channels["mod"])
        interaction.client = SimpleNamespace(get_cog=lambda name: moderacion_cog)

        await RejectButton(message_id=2).callback(interaction)

        interaction.response.send_modal.assert_awaited_once()
        (modal,), _ = interaction.response.send_modal.call_args
        assert isinstance(modal, RejectModal)
        assert modal.message_id == 2
        assert modal.author.id == 99


class TestRejectModal:
    async def test_on_submit_delegates_with_the_entered_reason(self, moderacion_cog):
        cog = moderacion_cog
        cog._rechazar_mensaje = AsyncMock()
        author = make_member(id=99, name="remitente")
        modal = RejectModal(cog=cog, message_id=5, author=author)
        modal.reason._value = "no cumple los requisitos"
        interaction = make_interaction()

        await modal.on_submit(interaction)

        interaction.response.send_message.assert_awaited_once()
        (msg,), _ = interaction.response.send_message.call_args
        assert "<@99>" in msg
        cog._rechazar_mensaje.assert_awaited_once_with(
            interaction, 5, "no cumple los requisitos"
        )
