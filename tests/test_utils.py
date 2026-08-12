from tests.factories import make_message
from utils import get_message_to_moderate, get_moderation_channel, strip_message


class TestStripMessage:
    def test_lowercases(self):
        assert strip_message("HOLA Mundo") == "hola mundo"

    def test_removes_newlines_and_tabs(self):
        assert strip_message("hola\nmundo\tcon\rtabs") == "hola mundo con tabs"

    def test_collapses_multiple_whitespace(self):
        assert strip_message("hola     mundo") == "hola mundo"

    def test_removes_mentions(self):
        assert strip_message("hola <@123456789> mundo") == "hola mundo"

    def test_removes_multiple_mentions(self):
        assert strip_message("<@111> hola <@!222> mundo") == "hola mundo"

    def test_strips_surrounding_whitespace(self):
        assert strip_message("  hola mundo  ") == "hola mundo"

    def test_empty_string(self):
        assert strip_message("") == ""


class TestGetModerationChannel:
    def test_returns_bot_get_channel_result(self):
        sentinel = object()

        class FakeBot:
            def get_channel(self, channel_id):
                assert channel_id == 42
                return sentinel

        assert get_moderation_channel(FakeBot(), 42) is sentinel


class TestGetMessageToModerate:
    def test_embed_contains_message_and_commands(self):
        message = make_message(content="hola, este es mi post")
        message.id = 4242

        embed = get_message_to_moderate(message)

        assert "hola, este es mi post" in embed.description
        assert "%aceptar 4242" in embed.description
        assert "%rechazar 4242" in embed.description
        assert message.channel.mention in embed.description
        assert message.author.mention in embed.description
