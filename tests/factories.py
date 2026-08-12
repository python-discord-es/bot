"""Lightweight fakes for discord.py objects used across the test suite.

We deliberately avoid a full discord.py test harness (e.g. dpytest) and
instead build just-enough fakes:

- Plain objects (``SimpleNamespace``/small classes) for anything the
  production code only reads attributes off of or calls async methods on.
- ``unittest.mock.MagicMock(spec=...)`` for anything the code runs
  ``isinstance()`` checks against - Mock's ``spec=`` makes
  ``isinstance(mock, SpecClass)`` return True, which a plain fake can't do.
"""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord
from PIL import Image

from utils import strip_message


def make_role(name="Coordinacion", id=1000):
    return SimpleNamespace(name=name, id=id, mention=f"@{name}")


def make_member(name="usuario", id=123, roles=None, bot=False):
    """A fake author. Uses ``spec=discord.Member`` so that the
    ``isinstance(author, discord.Member)`` check in ``spam_check`` passes."""
    member = MagicMock(spec=discord.Member)
    member.name = name
    member.id = id
    member.bot = bot
    member.discriminator = "0"
    member.mention = f"<@{id}>"
    member.roles = roles if roles is not None else []
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()
    member.__str__.return_value = name
    return member


def make_attachment(content_type="image/png", data=b"fake-image-bytes", filename="image.png"):
    return SimpleNamespace(
        content_type=content_type,
        filename=filename,
        read=AsyncMock(return_value=data),
    )


def make_thread():
    return SimpleNamespace(send=AsyncMock())


async def _async_history(messages):
    for m in messages:
        yield m


def make_text_channel(id=555, name="general", thread=None, history_messages=None):
    """Uses ``spec=discord.TextChannel`` for the isinstance checks in
    ``archivar.py``/``limpia.py``."""
    channel = MagicMock(spec=discord.TextChannel)
    channel.id = id
    channel.name = name
    channel.mention = f"#{name}"
    channel.category_id = None
    channel.send = AsyncMock()
    channel.create_thread = AsyncMock(return_value=thread or make_thread())
    channel.purge = AsyncMock()
    channel.delete_messages = AsyncMock()
    channel.history = MagicMock(
        side_effect=lambda *a, **kw: _async_history(history_messages or [])
    )
    return channel


def make_dm_channel():
    """A channel type NOT accepted by archivar.py/limpia.py's isinstance checks."""
    return MagicMock(spec=discord.DMChannel)


def make_category(name="categoria", channels=None):
    category = MagicMock(spec=discord.CategoryChannel)
    category.name = name
    category.channels = channels or []
    return category


def make_message(
    content="",
    author=None,
    channel=None,
    attachments=None,
    mentions=None,
    role_mentions=None,
    id=999,
):
    return SimpleNamespace(
        id=id,
        content=content,
        author=author if author is not None else make_member(),
        channel=channel if channel is not None else make_text_channel(),
        attachments=attachments if attachments is not None else [],
        mentions=mentions if mentions is not None else [],
        role_mentions=role_mentions if role_mentions is not None else [],
    )


def make_bot(channels=None, guild=None, user=None, users=None, guilds=None):
    """``channels``/``users`` are kept as live dicts on the returned bot (as
    ``bot.channels``/``bot.users_by_id``) so tests can register more entries
    later, e.g. when a message arrives on a channel ``on_message`` looks up
    via ``bot.get_channel(message.channel.id)``."""
    channels = dict(channels or {})
    users = dict(users or {})
    bot = SimpleNamespace(
        channels=channels,
        users_by_id=users,
        get_guild=lambda gid: guild,
        user=user,
        guilds=guilds if guilds is not None else ([guild] if guild else []),
        process_commands=AsyncMock(),
    )
    bot.get_channel = lambda cid: bot.channels.get(cid)
    bot.get_user = lambda uid: bot.users_by_id.get(uid)
    return bot


def make_ctx(author=None, channel=None, content="", reference=None):
    """A fake ``commands.Context`` - text-command style invocation (as
    opposed to a slash-command ``discord.Interaction``)."""
    channel = channel if channel is not None else make_text_channel()
    message = SimpleNamespace(
        content=content,
        channel=channel,
        reference=reference,
        delete=AsyncMock(),
    )
    return SimpleNamespace(
        author=author if author is not None else make_member(),
        channel=channel,
        message=message,
        send=AsyncMock(),
        defer=AsyncMock(),
    )


def make_interaction(user=None, channel=None):
    """Uses ``spec=discord.Interaction`` for the ``isinstance()`` checks
    Moderacion uses to tell slash-command interactions apart from regular
    text-command invocations."""
    interaction = MagicMock(spec=discord.Interaction)
    interaction.user = user if user is not None else make_member()
    interaction.channel = channel if channel is not None else make_text_channel()
    # `_is_valid_channel` compares `channel_mod.id == ctx.message.channel.id`
    # even for interactions, so this needs to line up with `.channel` too.
    interaction.message = SimpleNamespace(channel=interaction.channel)
    interaction.response = MagicMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.send_modal = AsyncMock()
    return interaction


def encode_for_mod_row(text: str) -> str:
    """Matches ``Moderacion``'s current encoding of a message's content into
    the ``data_mod``/log-file ``message`` column: a plain base64 string."""
    import base64

    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def encode_for_mod_row_legacy(text: str) -> str:
    """Matches the *old* (pre-fix) encoding: the repr of a base64 ``bytes``
    object, e.g. ``"b'aG9sYQ=='"``. Used to test that rows logged before
    the eval()-removal fix still decode correctly."""
    import base64

    return f"{base64.b64encode(text.encode('utf-8'))}"


def make_png_bytes(color=(255, 0, 0), size=(8, 8)):
    """A tiny, valid PNG - for tests that hash/sanitize real image bytes."""
    buf = BytesIO()
    Image.new("RGB", size, color=color).save(buf, format="PNG")
    return buf.getvalue()


def bind_commands(cog):
    """Set ``command.cog`` for every ``@commands.command``/``hybrid_command``
    defined on this cog, the way ``bot.add_cog()`` would.

    Our tests instantiate cogs directly without registering them on a real
    ``discord.ext.commands.Bot``, but discord.py's ``Command.__call__`` only
    binds ``self`` (the cog instance) to the callback when ``command.cog``
    is set - otherwise calling e.g. ``cog.some_command(ctx)`` directly (or a
    command calling a sibling command the same way) raises a confusing
    "missing 1 required positional argument: 'ctx'".
    """
    for command in cog.get_commands():
        command.cog = cog
    return cog


def make_context(message):
    """Build the ``MessageContext`` ``FloodSpam.on_message`` would build
    before delegating to its individual ``*_check`` methods, so those
    methods can be unit-tested directly without going through the full
    listener."""
    from comandos.flood import MessageContext

    return MessageContext(message=message, content=strip_message(message.content))
