from types import SimpleNamespace

from comandos.ping import Ping
from tests.factories import bind_commands, make_bot, make_ctx, make_message


def make_bot_user(mentioned=True):
    return SimpleNamespace(mentioned_in=lambda message: mentioned)


class TestHasGlobalMention:
    def test_true_for_everyone(self):
        cog = Ping(make_bot())
        assert cog.has_global_mention(SimpleNamespace(content="hola @everyone")) is True

    def test_true_for_here(self):
        cog = Ping(make_bot())
        assert cog.has_global_mention(SimpleNamespace(content="hola @here")) is True

    def test_false_for_a_regular_mention(self):
        cog = Ping(make_bot())
        assert cog.has_global_mention(SimpleNamespace(content="hola <@123>")) is False


class TestPingPong:
    async def test_replies_pong_ephemerally(self):
        cog = bind_commands(Ping(make_bot()))
        ctx = make_ctx()

        await cog.pingpong(ctx)

        ctx.send.assert_awaited_once_with("pong", ephemeral=True)


class TestOnMessage:
    async def test_sends_the_llama_gif_when_mentioned(self):
        bot = make_bot(user=make_bot_user(mentioned=True))
        cog = Ping(bot)
        message = make_message(content="hola bot")

        await cog.on_message(message)

        message.channel.send.assert_awaited_once()
        _, kwargs = message.channel.send.call_args
        assert kwargs["file"].filename == "resources/llama.gif"

    async def test_ignores_global_mentions(self):
        bot = make_bot(user=make_bot_user(mentioned=True))
        cog = Ping(bot)
        message = make_message(content="@everyone hola bot")

        await cog.on_message(message)

        message.channel.send.assert_not_awaited()

    async def test_ignores_messages_that_do_not_mention_the_bot(self):
        bot = make_bot(user=make_bot_user(mentioned=False))
        cog = Ping(bot)
        message = make_message(content="hola a todos")

        await cog.on_message(message)

        message.channel.send.assert_not_awaited()
