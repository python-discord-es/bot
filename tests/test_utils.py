from tests.factories import make_message
from utils import get_message_to_moderate, read_csv_dicts, strip_message


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


class TestReadCsvDicts:
    def test_reads_rows_as_dicts(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text("date;message_id;author\n2026-01-01;1;alice\n2026-01-02;2;bob\n")

        rows = read_csv_dicts(path)

        assert rows == [
            {"date": "2026-01-01", "message_id": "1", "author": "alice"},
            {"date": "2026-01-02", "message_id": "2", "author": "bob"},
        ]

    def test_handles_embedded_quotes_delimiters_and_newlines(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text('date;author;message\n2026-01-01;"mod ""raro""; con coma";"linea uno\nlinea dos"\n')

        rows = read_csv_dicts(path)

        assert rows[0]["author"] == 'mod "raro"; con coma'
        assert rows[0]["message"] == "linea uno\nlinea dos"

    def test_only_header_returns_empty_list(self, tmp_path):
        path = tmp_path / "data.csv"
        path.write_text("date;message_id;author\n")

        assert read_csv_dicts(path) == []


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
