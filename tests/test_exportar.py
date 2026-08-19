import csv
import zipfile
from datetime import datetime, timedelta

from comandos.exportar import Exportar, build_export_zip
from tests.factories import bind_commands, make_bot, make_ctx, make_member, read_last_csv_row

RECENT = str(datetime.now() - timedelta(days=1))


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# build_export_zip
# ---------------------------------------------------------------------------
class TestBuildExportZip:
    def test_collects_matching_rows_from_every_personal_data_log(self, isolated_logs):
        write_csv(isolated_logs.log_main_file, ["date", "author_id", "message_id"], [
            [RECENT, "42", "1"], [RECENT, "99", "2"],
        ])
        write_csv(isolated_logs.log_mod_file, ["date", "author_id", "message_id"], [
            [RECENT, "42", "10"],
        ])

        buffer, counts = build_export_zip(42)

        assert counts["log_main_file"] == 1
        assert counts["log_mod_file"] == 1
        assert counts["log_accepted_file"] == 0
        assert counts["log_rejected_file"] == 0

        with zipfile.ZipFile(buffer) as zf:
            names = zf.namelist()
            assert "log_main_file.csv" in names
            assert "log_mod_file.csv" in names
            assert "log_accepted_file.csv" not in names  # nothing to write - skipped
            rows = list(csv.DictReader(zf.read("log_main_file.csv").decode().splitlines(), delimiter=";"))
            assert [r["message_id"] for r in rows] == ["1"]

    def test_no_data_returns_all_zero_counts(self, isolated_logs):
        buffer, counts = build_export_zip(404)

        assert sum(counts.values()) == 0
        with zipfile.ZipFile(buffer) as zf:
            assert zf.namelist() == []


# ---------------------------------------------------------------------------
# %exportar command
# ---------------------------------------------------------------------------
class TestExportarUsuario:
    async def test_no_data_found_sends_plain_message(self, isolated_logs):
        cog = bind_commands(Exportar(make_bot()))
        ctx = make_ctx()
        target = make_member(name="nadie", id=404)

        await cog.exportar_usuario(ctx, target)

        ctx.send.assert_awaited_once()
        (msg,), kwargs = ctx.send.call_args
        assert "No se encontraron datos" in msg
        assert "file" not in kwargs

    async def test_data_found_sends_zip_and_logs_the_access(self, isolated_logs):
        write_csv(isolated_logs.log_main_file, ["date", "author_id", "message_id"], [
            [RECENT, "42", "1"],
        ])
        cog = bind_commands(Exportar(make_bot()))
        ctx = make_ctx(author=make_member(name="mod1", id=1))
        target = make_member(name="alguien", id=42)

        await cog.exportar_usuario(ctx, target)

        ctx.send.assert_awaited_once()
        _, kwargs = ctx.send.call_args
        assert "1" in kwargs["content"]
        assert kwargs["file"].filename.endswith(".zip")

        access_row = read_last_csv_row(isolated_logs.log_gdpr_access_file)
        assert access_row[1] == "42"  # user_id
        assert access_row[2] == "mod1"  # requested_by
        assert access_row[4] == "1"  # total_exported
