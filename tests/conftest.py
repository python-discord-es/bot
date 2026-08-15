import pytest

from comandos.flood import FloodSpam
from comandos.moderacion import Moderacion
from comandos.retencion import Retencion
from tests.factories import make_bot, make_role, make_text_channel


@pytest.fixture
def coord_role():
    return make_role(name="Coordinacion", id=1)


@pytest.fixture
def muted_role():
    return make_role(name="Muted", id=2)


@pytest.fixture
def mod_channel():
    return make_text_channel(id=999, name="mod-general")


@pytest.fixture
def flood_cog(isolated_logs, coord_role, muted_role, mod_channel):
    """A FloodSpam cog wired up the way on_ready() would, without needing a
    real discord.Client/Guild."""
    bot = make_bot(channels={mod_channel.id: mod_channel})
    cog = FloodSpam(bot)
    cog._coord_role = coord_role
    cog._muted_role = muted_role
    cog._main_mod_channel = mod_channel
    return cog


@pytest.fixture
def moderacion_channels(config):
    ids = config.CHANNELS["eventos"]
    return {
        "main": make_text_channel(id=ids["main"], name="eventos"),
        "mod": make_text_channel(id=ids["moderation"], name="eventos-mod"),
        "sub": make_text_channel(id=ids["submission"], name="envio-eventos"),
    }


@pytest.fixture
async def moderacion_cog(isolated_logs, moderacion_channels):
    """A Moderacion cog wired up the way on_ready() would (channel mapping
    populated from config.CHANNELS), with an empty ``data_mod`` table."""
    from types import SimpleNamespace

    channels = {c.id: c for c in moderacion_channels.values()}
    bot = make_bot(channels=channels, guild=SimpleNamespace(id=333333333333333333))
    bot.data_mod = {}  # message_id -> row dict, same shape as read_csv_dicts() rows
    cog = Moderacion(bot)
    await cog.on_ready()
    return cog


@pytest.fixture
def retencion_cog(isolated_logs, coord_role):
    """A Retencion cog wired up the way on_ready() would, without needing a
    real discord.Client/Guild or starting the real @tasks.loop."""
    bot = make_bot()
    bot.data_mod = {}
    cog = Retencion(bot)
    cog._coord_role = coord_role
    return cog
