from types import SimpleNamespace

from comandos.limpia import Limpia
from tests.factories import (
    bind_commands,
    make_bot,
    make_ctx,
    make_dm_channel,
    make_message,
    make_text_channel,
)


class TestPurge:
    async def test_ignores_unsupported_channel_types(self):
        cog = bind_commands(Limpia(make_bot()))
        ctx = make_ctx(channel=make_dm_channel())

        await cog.purge(ctx, limit=5)

        # Nothing to assert on the channel itself (it's not a spec that
        # exposes purge/delete_messages), just that we returned early
        # without raising.

    async def test_no_reply_purges_the_channel_and_the_command_message(self):
        channel = make_text_channel(id=1, name="general")
        cog = bind_commands(Limpia(make_bot()))
        ctx = make_ctx(channel=channel)

        await cog.purge(ctx, limit=3)

        ctx.defer.assert_awaited_once_with(ephemeral=True)
        channel.purge.assert_any_await(limit=4)
        ctx.message.delete.assert_awaited_once()
        ctx.send.assert_awaited_once()
        channel.purge.assert_any_await(limit=1)

    async def test_reply_deletes_messages_up_to_the_referenced_one(self):
        target = make_message(id=42)
        history = [make_message(id=1), make_message(id=2), target, make_message(id=3)]
        channel = make_text_channel(id=1, name="general", history_messages=history)
        cog = bind_commands(Limpia(make_bot()))
        ctx = make_ctx(channel=channel, reference=SimpleNamespace(message_id=42))
        ctx.message.channel = channel

        await cog.purge(ctx)

        channel.delete_messages.assert_awaited_once()
        (deleted,), _ = channel.delete_messages.call_args
        assert [m.id for m in deleted] == [1, 2, 42]
