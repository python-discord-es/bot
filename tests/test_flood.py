from unittest.mock import AsyncMock

import discord
import pytest

from tests.factories import (
    make_attachment,
    make_member,
    make_message,
    make_png_bytes,
    make_text_channel,
    prime_cog,
)


# ---------------------------------------------------------------------------
# spam_check
# ---------------------------------------------------------------------------
class TestSpamCheck:
    async def test_ignores_non_member_author(self, flood_cog):
        message = make_message(content="discord nitro free http://evil")
        message.author = object()  # not a discord.Member

        assert await flood_cog.spam_check(message) is None

    async def test_no_match_returns_false(self, flood_cog):
        message = make_message(content="hola a todos, buen dia")

        assert await flood_cog.spam_check(message) is False

    @pytest.mark.parametrize(
        "content",
        [
            "gana discord nitro free aqui http://scam.example",
            "everyone free steam gift http://scam.example",
        ],
    )
    async def test_match_mutes_and_notifies(self, flood_cog, content):
        member = make_member(name="victima")
        message = make_message(content=content, author=member)
        prime_cog(flood_cog, message)

        result = await flood_cog.spam_check(message)

        assert result is True
        member.add_roles.assert_awaited_once_with(flood_cog.muted_role)
        message.channel.send.assert_awaited_once()
        _, kwargs = message.channel.send.call_args
        assert kwargs["embed"].title.endswith("Alerta de posible SCAM")


# ---------------------------------------------------------------------------
# flood_check
# ---------------------------------------------------------------------------
class TestFloodCheck:
    async def test_empty_content_is_a_noop(self, flood_cog):
        message = make_message(content="")
        prime_cog(flood_cog, message)

        assert await flood_cog.flood_check(message) is False
        assert flood_cog.messages.normal == {}

    async def test_below_flood_limit_does_not_mute(self, flood_cog, config):
        member = make_member(name="repetidor")
        message = make_message(content="hola hola hola", author=member)
        prime_cog(flood_cog, message)

        for _ in range(config.FLOOD_LIMIT - 1):
            await flood_cog.flood_check(message)

        member.add_roles.assert_not_awaited()

    async def test_reaching_flood_limit_mutes_and_caches(self, flood_cog, config):
        member = make_member(name="repetidor")
        message = make_message(content="hola hola hola", author=member)
        prime_cog(flood_cog, message)

        for _ in range(config.FLOOD_LIMIT):
            await flood_cog.flood_check(message)

        member.add_roles.assert_awaited_once_with(flood_cog.muted_role)
        assert "hola hola hola" in flood_cog.messages.spam
        # Counter resets after muting
        assert flood_cog.messages.normal[member] == {}

    async def test_different_authors_counted_separately(self, flood_cog, config):
        alice = make_member(name="alice", id=1)
        bob = make_member(name="bob", id=2)

        for _ in range(config.FLOOD_LIMIT - 1):
            msg = make_message(content="mismo mensaje", author=alice)
            prime_cog(flood_cog, msg)
            await flood_cog.flood_check(msg)

        msg = make_message(content="mismo mensaje", author=bob)
        prime_cog(flood_cog, msg)
        await flood_cog.flood_check(msg)

        alice.add_roles.assert_not_awaited()
        bob.add_roles.assert_not_awaited()


# ---------------------------------------------------------------------------
# mention_check
# ---------------------------------------------------------------------------
class TestMentionCheck:
    async def test_below_limit_returns_false(self, flood_cog, config):
        mentions = [make_member(id=i) for i in range(config.MENTIONS_LIMIT - 1)]
        message = make_message(mentions=mentions)
        prime_cog(flood_cog, message)

        assert await flood_cog.mention_check(message) is False

    async def test_at_limit_mutes_and_alerts(self, flood_cog, config):
        member = make_member(name="mencionador")
        mentions = [make_member(id=i) for i in range(config.MENTIONS_LIMIT)]
        message = make_message(author=member, mentions=mentions)
        prime_cog(flood_cog, message)

        assert await flood_cog.mention_check(message) is True
        member.add_roles.assert_awaited_once_with(flood_cog.muted_role)

    async def test_mentions_and_role_mentions_add_up(self, flood_cog, config):
        member = make_member(name="mencionador")
        mentions = [make_member(id=1)]
        role_mentions = [object() for _ in range(config.MENTIONS_LIMIT - 1)]
        message = make_message(author=member, mentions=mentions, role_mentions=role_mentions)
        prime_cog(flood_cog, message)

        assert await flood_cog.mention_check(message) is True


# ---------------------------------------------------------------------------
# attachment_check
# ---------------------------------------------------------------------------
class TestAttachmentCheckFastPath:
    async def test_no_images_returns_false(self, flood_cog):
        message = make_message(attachments=[make_attachment(content_type="text/plain")])
        prime_cog(flood_cog, message)

        assert await flood_cog.attachment_check(message) is False

    async def test_known_hash_mutes_and_deletes_regardless_of_channel_count(
        self, flood_cog, patched_message_delete
    ):
        data = make_png_bytes()
        digest = __import__("hashlib").sha256(data).hexdigest()
        flood_cog.messages.image_spam.add(digest)

        member = make_member(name="reincidente")
        message = make_message(
            author=member,
            attachments=[make_attachment(data=data)],
        )
        prime_cog(flood_cog, message)

        assert await flood_cog.attachment_check(message) is True
        member.add_roles.assert_awaited_once_with(flood_cog.muted_role)
        patched_message_delete.assert_awaited_once_with(message)


class TestAttachmentCheckBurstPath:
    async def test_single_channel_two_images_does_not_trigger(self, flood_cog):
        member = make_member(name="autor")
        message = make_message(
            author=member,
            attachments=[make_attachment(filename="a.png"), make_attachment(filename="b.png")],
        )
        prime_cog(flood_cog, message)

        assert await flood_cog.attachment_check(message) is False
        member.add_roles.assert_not_awaited()

    async def test_single_image_across_channels_does_not_trigger(self, flood_cog):
        member = make_member(name="autor")
        channel_a = make_text_channel(id=1)
        channel_b = make_text_channel(id=2)

        for channel in (channel_a, channel_b):
            message = make_message(
                author=member, channel=channel, attachments=[make_attachment()]
            )
            prime_cog(flood_cog, message)
            assert await flood_cog.attachment_check(message) is False

        member.add_roles.assert_not_awaited()

    async def test_two_images_two_channels_triggers_on_the_second_message(
        self, flood_cog, patched_message_delete
    ):
        member = make_member(name="comprometido")
        channel_a = make_text_channel(id=1)
        channel_b = make_text_channel(id=2)

        first = make_message(
            author=member,
            channel=channel_a,
            attachments=[make_attachment(filename="a1.png"), make_attachment(filename="a2.png")],
        )
        prime_cog(flood_cog, first)
        first_result = await flood_cog.attachment_check(first)

        second = make_message(
            author=member,
            channel=channel_b,
            attachments=[make_attachment(filename="b1.png"), make_attachment(filename="b2.png")],
        )
        prime_cog(flood_cog, second)
        second_result = await flood_cog.attachment_check(second)

        # The first channel's message is never retroactively touched - only
        # the message that crosses the 2-channel threshold gets acted on.
        assert first_result is False
        assert second_result is True
        member.add_roles.assert_awaited_once_with(flood_cog.muted_role)
        patched_message_delete.assert_awaited_once_with(second)

    async def test_images_get_cached_for_the_fast_path(self, flood_cog):
        member = make_member(name="comprometido")
        data_a, data_b = make_png_bytes((255, 0, 0)), make_png_bytes((0, 255, 0))

        first = make_message(
            author=member,
            channel=make_text_channel(id=1),
            attachments=[make_attachment(data=data_a), make_attachment(data=data_b)],
        )
        prime_cog(flood_cog, first)
        await flood_cog.attachment_check(first)

        second = make_message(
            author=member,
            channel=make_text_channel(id=2),
            attachments=[make_attachment(data=data_a), make_attachment(data=data_b)],
        )
        prime_cog(flood_cog, second)
        await flood_cog.attachment_check(second)

        import hashlib

        assert hashlib.sha256(data_a).hexdigest() in flood_cog.messages.image_spam
        assert hashlib.sha256(data_b).hexdigest() in flood_cog.messages.image_spam

    async def test_outside_burst_window_does_not_trigger(self, flood_cog, config, monkeypatch):
        import comandos.flood as flood_module

        member = make_member(name="lento")
        clock = iter([1000.0, 1000.0 + config.IMAGE_BURST_WINDOW + 1])
        monkeypatch.setattr(flood_module.time, "time", lambda: next(clock))

        first = make_message(
            author=member,
            channel=make_text_channel(id=1),
            attachments=[make_attachment(filename="a1.png"), make_attachment(filename="a2.png")],
        )
        prime_cog(flood_cog, first)
        await flood_cog.attachment_check(first)

        second = make_message(
            author=member,
            channel=make_text_channel(id=2),
            attachments=[make_attachment(filename="b1.png"), make_attachment(filename="b2.png")],
        )
        prime_cog(flood_cog, second)
        result = await flood_cog.attachment_check(second)

        assert result is False
        member.add_roles.assert_not_awaited()

    async def test_same_channel_twice_is_not_two_distinct_channels(self, flood_cog):
        member = make_member(name="autor")
        channel = make_text_channel(id=1)

        for _ in range(3):
            message = make_message(
                author=member,
                channel=channel,
                attachments=[make_attachment(filename="a.png"), make_attachment(filename="b.png")],
            )
            prime_cog(flood_cog, message)
            result = await flood_cog.attachment_check(message)

        assert result is False
        member.add_roles.assert_not_awaited()


# ---------------------------------------------------------------------------
# _sanitize_attachment / _hash_attachment
# ---------------------------------------------------------------------------
class TestSanitizeAttachment:
    async def test_valid_image_round_trips_as_spoiler_file(self, flood_cog):
        attachment = make_attachment(data=make_png_bytes())

        result = await flood_cog._sanitize_attachment(attachment)

        assert result is not None
        assert isinstance(result, discord.File)
        assert result.spoiler is True
        assert result.filename.endswith("evidencia.png") or "SPOILER" in result.filename

    async def test_garbage_bytes_returns_none(self, flood_cog):
        attachment = make_attachment(data=b"not an image, just garbage" * 10)

        assert await flood_cog._sanitize_attachment(attachment) is None

    async def test_truncated_image_returns_none(self, flood_cog):
        attachment = make_attachment(data=make_png_bytes()[:15])

        assert await flood_cog._sanitize_attachment(attachment) is None


class TestHashAttachment:
    async def test_matches_sha256_of_bytes(self, flood_cog):
        import hashlib

        data = b"some bytes"
        attachment = make_attachment(data=data)

        assert await flood_cog._hash_attachment(attachment) == hashlib.sha256(data).hexdigest()


# ---------------------------------------------------------------------------
# add_spam_message / add_spam_image_hash
# ---------------------------------------------------------------------------
class TestAddSpamHelpers:
    def test_add_spam_message_persists_and_caches(self, flood_cog, isolated_logs):
        flood_cog.add_spam_message("mensaje malo")

        assert "mensaje malo" in flood_cog.messages.spam
        assert "mensaje malo" in isolated_logs.log_spam_file.read_text()

    def test_add_spam_image_hash_persists_and_caches(self, flood_cog, isolated_logs):
        flood_cog.add_spam_image_hash("deadbeef")

        assert "deadbeef" in flood_cog.messages.image_spam
        assert "deadbeef" in isolated_logs.log_image_spam_file.read_text()


# ---------------------------------------------------------------------------
# alert_moderation
# ---------------------------------------------------------------------------
class TestAlertModeration:
    async def test_creates_thread_and_sends_embed(self, flood_cog):
        member = make_member(name="alguien")
        message = make_message(author=member)
        prime_cog(flood_cog, message)

        await flood_cog.alert_moderation("Alerta de prueba", "scam")

        flood_cog.main_mod_channel.create_thread.assert_awaited_once()
        _, kwargs = flood_cog.main_mod_channel.create_thread.call_args
        assert member.mention in kwargs["name"]

        thread = flood_cog.main_mod_channel.create_thread.return_value
        thread.send.assert_awaited_once()

    async def test_unknown_reason_raises(self, flood_cog):
        message = make_message()
        prime_cog(flood_cog, message)

        with pytest.raises(KeyError):
            await flood_cog.alert_moderation("Título", "no-existe")

    async def test_attachments_are_forwarded_sanitized_and_spoilered(self, flood_cog):
        message = make_message()
        prime_cog(flood_cog, message)
        images = [make_attachment(data=make_png_bytes())]

        await flood_cog.alert_moderation("Alerta", "known_image", attachments=images)

        thread = flood_cog.main_mod_channel.create_thread.return_value
        _, kwargs = thread.send.call_args
        assert len(kwargs["files"]) == 1
        assert kwargs["files"][0].spoiler is True

    async def test_undecodable_attachment_is_skipped_not_forwarded(self, flood_cog):
        message = make_message()
        prime_cog(flood_cog, message)
        images = [make_attachment(data=b"garbage" * 10)]

        await flood_cog.alert_moderation("Alerta", "known_image", attachments=images)

        thread = flood_cog.main_mod_channel.create_thread.return_value
        _, kwargs = thread.send.call_args
        assert kwargs["files"] == []

    async def test_no_attachments_means_no_warning_field(self, flood_cog):
        message = make_message()
        prime_cog(flood_cog, message)

        await flood_cog.alert_moderation("Alerta", "scam")

        thread = flood_cog.main_mod_channel.create_thread.return_value
        _, kwargs = thread.send.call_args
        field_names = [f.name for f in kwargs["embed"].fields]
        assert not any("Imágenes adjuntas" in name for name in field_names)


# ---------------------------------------------------------------------------
# on_message pipeline
# ---------------------------------------------------------------------------
class TestOnMessagePipeline:
    async def test_uses_message_channel_directly_not_a_bot_cache_lookup(self, flood_cog):
        """Regression test: on_message used to do
        ``self._msg_channel = self.bot.get_channel(message.channel.id)``
        instead of just using ``message.channel``. A cache miss there made
        ``_msg_channel`` None and crashed the first ``.send()`` downstream -
        here the channel is never registered on the bot at all, so this
        would fail the old way if the bug came back.
        """
        member = make_member(name="repetidor")
        message = make_message(content="discord nitro free http://x", author=member)
        assert flood_cog.bot.get_channel(message.channel.id) is None

        await flood_cog.on_message(message)

        # The point here isn't *how many* times it's sent, just that it
        # didn't crash trying to call .send() on a None channel.
        message.channel.send.assert_awaited()

    async def test_ignores_messages_from_bots(self, flood_cog):
        member = make_member(name="unbot", bot=True)
        message = make_message(content="discord nitro free http://x", author=member)

        await flood_cog.on_message(message)

        member.add_roles.assert_not_awaited()

    async def test_ignores_the_configured_bot_id(self, flood_cog, config):
        member = make_member(name="elbot", id=config.BOT_ID, bot=False)
        message = make_message(content="discord nitro free http://x", author=member)

        await flood_cog.on_message(message)

        member.add_roles.assert_not_awaited()

    async def test_ignores_short_textless_messages_without_attachments(self, flood_cog):
        member = make_member(name="alguien")
        message = make_message(content="ok", author=member)

        await flood_cog.on_message(message)

        # Never even gets far enough to set up per-message state.
        assert flood_cog._msg_author is None

    async def test_short_caption_with_attachments_is_still_processed(self, flood_cog):
        member = make_member(name="alguien")
        message = make_message(
            content="ok",
            author=member,
            attachments=[make_attachment(filename="a.png"), make_attachment(filename="b.png")],
        )

        await flood_cog.on_message(message)

        # It went through the pipeline (attachment_check saw it), even though
        # the caption alone would have been skipped.
        assert flood_cog._msg_author is member

    async def test_skips_coordination_role_members(self, flood_cog):
        message = make_message(
            content="discord nitro free http://x",
            author=make_member(name="mod", roles=[flood_cog.coord_role]),
        )

        result = None
        try:
            result = await flood_cog.on_message(message)
        finally:
            pass

        message.author.add_roles.assert_not_awaited()

    async def test_known_spam_text_is_deleted_and_author_muted(
        self, flood_cog, patched_message_delete
    ):
        flood_cog.messages.spam.add("mensaje ya conocido como spam")
        member = make_member(name="repetidor")
        message = make_message(content="Mensaje YA conocido como SPAM", author=member)

        await flood_cog.on_message(message)

        member.add_roles.assert_awaited_once_with(flood_cog.muted_role)
        patched_message_delete.assert_awaited_once_with(message)
