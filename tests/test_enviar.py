from unittest.mock import AsyncMock

from comandos.enviar import Enviar
from tests.factories import bind_commands, make_bot, make_ctx, make_text_channel


class TestEnviar:
    async def test_replies_and_sends_to_target_channel(self):
        cog = bind_commands(Enviar(make_bot()))
        target = make_text_channel(id=1, name="anuncios")
        ctx = make_ctx()
        ctx.reply = AsyncMock()

        await cog.enviar(ctx, channel=target, message="hola a todos")

        ctx.reply.assert_awaited_once()
        target.send.assert_awaited_once()
        _, kwargs = target.send.call_args
        assert kwargs["embed"].description == "hola a todos"

    async def test_falls_back_to_channel_send_when_reply_unavailable(self):
        cog = bind_commands(Enviar(make_bot()))
        target = make_text_channel(id=1, name="anuncios")
        # A plain SimpleNamespace ctx has no ``.reply`` attribute at all,
        # which is exactly the AttributeError the production code falls
        # back on (e.g. a hybrid command invoked in a context without it).
        ctx = make_ctx()

        await cog.enviar(ctx, channel=target, message="hola a todos")

        ctx.channel.send.assert_awaited_once()
        target.send.assert_awaited_once()
