from unittest.mock import MagicMock

import discord

from comandos.archivar import Archivar
from tests.factories import (
    bind_commands,
    make_bot,
    make_category,
    make_ctx,
    make_dm_channel,
    make_message,
    make_text_channel,
)


class TestArchivarCanal:
    def test_writes_header_and_rows(self, tmp_path):
        cog = Archivar(make_bot())
        channel = make_text_channel(id=1, name="general")
        messages = [
            make_message(id=10, content="hola\ncon salto de linea", channel=channel),
            make_message(id=11, content="segundo mensaje", channel=channel),
        ]
        target = tmp_path / "archivo.csv"

        status = cog.archivar_canal(str(target), messages)

        assert status == (True, str(target))
        lines = target.read_text().splitlines()
        assert lines[0].startswith("id;content;channel_id")
        assert len(lines) == 3
        # Newlines inside content are escaped, not left as real line breaks.
        assert "hola\\ncon salto de linea" in lines[1]

    def test_stops_and_returns_false_for_unsupported_channel_type(self, tmp_path):
        cog = Archivar(make_bot())
        messages = [make_message(id=1, channel=make_dm_channel())]
        target = tmp_path / "archivo.csv"

        assert cog.archivar_canal(str(target), messages) == (False, None)

    def test_write_failure_returns_false_none(self, tmp_path):
        cog = Archivar(make_bot())
        messages = [make_message(id=1)]
        # A directory can't be opened for writing as a file.
        bad_target = tmp_path

        assert cog.archivar_canal(str(bad_target), messages) == (False, None)


class TestArchivarCommand:
    async def test_sends_success_embed_with_the_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod_channel = make_text_channel(id=1, name="mod")
        cog = bind_commands(Archivar(make_bot()))
        cog.mod_channel = mod_channel

        channel = make_text_channel(
            id=2,
            name="general",
            history_messages=[make_message(id=1), make_message(id=2)],
        )
        ctx = make_ctx(channel=mod_channel)

        await cog.archivar(ctx, channel=channel)

        mod_channel.send.assert_awaited_once()
        _, kwargs = mod_channel.send.call_args
        assert "2 mensajes" in kwargs["embed"].description
        # The mod-channel message just sent is the durable copy (see
        # TERMS.md section 4) - the local temp file shouldn't linger on
        # disk outside the retention policy in comandos/retencion.py.
        assert list(tmp_path.glob("*.csv")) == []

    async def test_sends_error_embed_when_archiving_fails(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod_channel = make_text_channel(id=1, name="mod")
        cog = bind_commands(Archivar(make_bot()))
        cog.mod_channel = mod_channel

        channel = make_text_channel(
            id=2, name="general", history_messages=[make_message(id=1, channel=make_dm_channel())]
        )
        ctx = make_ctx(channel=mod_channel)

        await cog.archivar(ctx, channel=channel)

        mod_channel.send.assert_awaited_once()
        (msg,), _ = mod_channel.send.call_args
        assert "Error" in msg

    async def test_write_exception_reports_error_instead_of_crashing(self, tmp_path, monkeypatch):
        """Regression test: archivar_canal() returning (False, None) on a
        write failure used to be treated as success by ``if status:``
        (a non-empty tuple is always truthy), which would then try to
        attach a file that was never written - crashing instead of just
        reporting the error.
        """
        monkeypatch.chdir(tmp_path)
        mod_channel = make_text_channel(id=1, name="mod")
        cog = bind_commands(Archivar(make_bot()))
        cog.mod_channel = mod_channel

        # A channel name containing "/" makes the auto-generated filename
        # point at a non-existent subdirectory, so open(filename, "w") fails.
        channel = make_text_channel(
            id=2, name="no-existe/canal", history_messages=[make_message(id=1)]
        )
        ctx = make_ctx(channel=mod_channel)

        await cog.archivar(ctx, channel=channel)

        mod_channel.send.assert_awaited_once()
        (msg,), kwargs = mod_channel.send.call_args
        assert "Error" in msg
        assert "file" not in kwargs


class TestArchivarCategoria:
    async def test_only_archives_text_channels(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        mod_channel = make_text_channel(id=1, name="mod")
        cog = bind_commands(Archivar(make_bot()))
        cog.mod_channel = mod_channel

        text_channel = make_text_channel(id=2, name="canal-texto", history_messages=[])
        voice_channel = MagicMock(spec=discord.VoiceChannel)
        category = make_category(channels=[text_channel, voice_channel])
        ctx = make_ctx(channel=mod_channel)

        await cog.archivar_categoria(ctx, category=category)

        # Only one embed sent - for the TextChannel. The VoiceChannel was skipped.
        mod_channel.send.assert_awaited_once()
