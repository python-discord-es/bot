from comandos.ayuda import Ayuda
from tests.factories import bind_commands, make_bot, make_ctx, make_member, make_text_channel


class TestGetModHelp:
    def test_lists_moderation_commands(self):
        cog = Ayuda(make_bot())

        embed = cog.get_mod_help()

        names = [f.name for f in embed.fields]
        assert "`%mod`" in names
        assert "`%aceptar ID`" in names
        assert "`%rechazar ID RAZON`" in names


class TestGetMainHelp:
    def test_lists_encuesta_usage(self):
        cog = Ayuda(make_bot())

        embed = cog.get_main_help()

        assert any("encuesta" in f.name for f in embed.fields)


class TestMensajeAyuda:
    async def test_ignores_the_bot_itself(self, config):
        cog = bind_commands(Ayuda(make_bot()))
        ctx = make_ctx(author=make_member(id=config.BOT_ID))

        await cog.mensaje_ayuda(ctx)

        ctx.channel.send.assert_not_awaited()

    async def test_sends_mod_help_inside_a_moderation_channel(self):
        mod_channel = make_text_channel(id=1, name="mod")
        bot = make_bot(channels={mod_channel.id: mod_channel})
        cog = bind_commands(Ayuda(bot))
        ctx = make_ctx(channel=mod_channel)

        await cog.mensaje_ayuda(ctx)

        mod_channel.send.assert_awaited_once()
        _, kwargs = mod_channel.send.call_args
        assert kwargs["embed"].title == "Comandos Disponibles"
        names = [f.name for f in kwargs["embed"].fields]
        assert "`%mod`" in names

    async def test_sends_main_help_outside_a_moderation_channel(self):
        # bot.get_channel(ctx.channel.id) returns None - not a known channel.
        bot = make_bot(channels={})
        cog = bind_commands(Ayuda(bot))
        channel = make_text_channel(id=99, name="general")
        ctx = make_ctx(channel=channel)

        await cog.mensaje_ayuda(ctx)

        channel.send.assert_awaited_once()
        _, kwargs = channel.send.call_args
        names = [f.name for f in kwargs["embed"].fields]
        assert any("encuesta" in name for name in names)
