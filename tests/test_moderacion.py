import csv
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from comandos.moderacion import _decode_message, _encode_message
from tests.factories import (
    encode_for_mod_row,
    encode_for_mod_row_legacy,
    make_ctx,
    make_interaction,
    make_member,
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
    cog.bot.data_mod = pd.concat([cog.bot.data_mod, pd.DataFrame([new_row])], ignore_index=True)
    return new_row


def read_last_csv_row(path, delimiter=";"):
    """isolated_logs seeds each log file with a blank line instead of the
    real header, so skip empty rows and return the last one actually
    written."""
    with path.open(newline="") as f:
        rows = [row for row in csv.reader(f, delimiter=delimiter) if row]
    return rows[-1]


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


# ---------------------------------------------------------------------------
# _log_action / log_on_message
# ---------------------------------------------------------------------------
class TestLogAction:
    def test_aceptar_writes_expected_line(self, moderacion_cog, isolated_logs):
        row = pd.DataFrame([add_pending_row(moderacion_cog, post_id=1)])

        moderacion_cog._log_action("aceptar", row, "1", "moderador#0")

        fields = read_last_csv_row(isolated_logs.log_accepted_file)
        assert fields[1] == "1"  # post_id
        assert fields[6] == "moderador#0"  # moderator
        assert len(fields) == 7  # no "reason" column for aceptar

    def test_rechazar_includes_reason(self, moderacion_cog, isolated_logs):
        row = pd.DataFrame([add_pending_row(moderacion_cog, post_id=2)])

        moderacion_cog._log_action("rechazar", row, "2", "moderador#0", "le falta info")

        fields = read_last_csv_row(isolated_logs.log_rejected_file)
        assert fields[-1] == "le falta info"

    def test_rechazar_without_reason_still_writes_the_reason_column(
        self, moderacion_cog, isolated_logs
    ):
        """Regression test: an empty reason used to skip the "reason" field
        entirely (``if reason: line += ...``), leaving that row one column
        short of log_rejected_file's fixed 8-column header - which
        pd.read_csv (run on every bot startup) can choke on.
        """
        row = pd.DataFrame([add_pending_row(moderacion_cog, post_id=3)])

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
        row = pd.DataFrame([add_pending_row(moderacion_cog, post_id=4, author_name=tricky_name)])

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
    def test_empty_data_sets_footer(self, moderacion_cog):
        embed = moderacion_cog.get_mod_pending(moderacion_cog.bot.data_mod)

        assert embed.footer.text == "No hay mensajes pendientes de moderación"
        assert len(embed.fields) == 0

    def test_lists_pending_posts_with_known_authors(self, moderacion_cog):
        add_pending_row(moderacion_cog, post_id=1, author_id=99, content="hola" * 20)
        moderacion_cog.bot.users_by_id[99] = make_member(id=99, name="remitente")

        embed = moderacion_cog.get_mod_pending(moderacion_cog.bot.data_mod)

        assert len(embed.fields) == 1
        assert "1" in embed.fields[0].name

    def test_skips_posts_from_users_no_longer_in_the_server(self, moderacion_cog):
        add_pending_row(moderacion_cog, post_id=1, author_id=404)
        # bot.get_user(404) resolves to None - author has left the server.

        embed = moderacion_cog.get_mod_pending(moderacion_cog.bot.data_mod)

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

        assert moderacion_cog.bot.data_mod.empty
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

        assert moderacion_cog.bot.data_mod.empty
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
