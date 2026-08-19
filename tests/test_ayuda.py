from comandos.ayuda import Ayuda
from tests.factories import bind_commands, make_bot, make_ctx, make_member


class TestGetModHelp:
    def test_lists_moderation_commands(self):
        cog = Ayuda(make_bot())

        embed = cog.get_mod_help()

        names = [f.name for f in embed.fields]
        assert "`%mod`" in names
        assert "`%aceptar ID`" in names
        assert "`%rechazar ID RAZON`" in names


class TestMensajeAyuda:
    async def test_ignores_the_bot_itself(self, config):
        cog = bind_commands(Ayuda(make_bot()))
        ctx = make_ctx(author=make_member(id=config.BOT_ID))

        await cog.mensaje_ayuda(ctx)

        ctx.channel.send.assert_not_awaited()

    async def test_sends_mod_help(self):
        cog = bind_commands(Ayuda(make_bot()))
        ctx = make_ctx()

        await cog.mensaje_ayuda(ctx)

        ctx.channel.send.assert_awaited_once()
        _, kwargs = ctx.channel.send.call_args
        assert kwargs["embed"].title == "Comandos Disponibles"
        names = [f.name for f in kwargs["embed"].fields]
        assert "`%mod`" in names
        assert "`%terminos`" in names


class TestTerminos:
    async def test_sends_the_terms_url(self, config):
        cog = bind_commands(Ayuda(make_bot()))
        ctx = make_ctx()

        await cog.terminos(ctx)

        ctx.channel.send.assert_awaited_once()
        (msg,), _ = ctx.channel.send.call_args
        assert config.TERMS_URL in msg
