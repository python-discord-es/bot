import csv
from datetime import datetime, timedelta

import pytest

from comandos.retencion import (
    ConfirmErasureView,
    count_rows_for_author,
    prune_old_rows,
    remove_rows_for_author,
)
from tests.factories import (
    bind_commands,
    make_ctx,
    make_interaction,
    make_member,
    read_last_csv_row,
)

OLD = str(datetime.now() - timedelta(days=40))
RECENT = str(datetime.now() - timedelta(days=1))


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


# ---------------------------------------------------------------------------
# prune_old_rows
# ---------------------------------------------------------------------------
class TestPruneOldRows:
    def test_removes_rows_older_than_max_age(self, tmp_path):
        path = tmp_path / "data.csv"
        write_csv(path, ["date", "message_id"], [[OLD, "1"], [RECENT, "2"]])

        removed = prune_old_rows(path, max_age_days=30)

        assert [r["message_id"] for r in removed] == ["1"]
        assert [r["message_id"] for r in read_csv(path)] == ["2"]

    def test_keeps_rows_with_unparseable_dates(self, tmp_path):
        """Fail safe: if we can't tell how old a row is, don't delete it."""
        path = tmp_path / "data.csv"
        write_csv(path, ["date", "message_id"], [["not-a-date", "1"], [RECENT, "2"]])

        removed = prune_old_rows(path, max_age_days=30)

        assert removed == []
        assert len(read_csv(path)) == 2

    def test_header_only_file_is_a_noop(self, tmp_path):
        path = tmp_path / "data.csv"
        write_csv(path, ["date", "message_id"], [])

        assert prune_old_rows(path, max_age_days=30) == []

    def test_uses_configured_retention_days_by_default(self, tmp_path, config):
        path = tmp_path / "data.csv"
        just_inside = str(datetime.now() - timedelta(days=config.RETENTION_DAYS - 1))
        just_outside = str(datetime.now() - timedelta(days=config.RETENTION_DAYS + 1))
        write_csv(path, ["date", "message_id"], [[just_inside, "1"], [just_outside, "2"]])

        removed = prune_old_rows(path)

        assert [r["message_id"] for r in removed] == ["2"]

    def test_does_not_rewrite_the_file_when_nothing_is_removed(self, tmp_path):
        path = tmp_path / "data.csv"
        write_csv(path, ["date", "message_id"], [[RECENT, "1"]])
        original_mtime = path.stat().st_mtime_ns

        prune_old_rows(path, max_age_days=30)

        assert path.stat().st_mtime_ns == original_mtime


# ---------------------------------------------------------------------------
# remove_rows_for_author / count_rows_for_author
# ---------------------------------------------------------------------------
class TestRemoveRowsForAuthor:
    def test_removes_only_matching_author(self, tmp_path):
        path = tmp_path / "data.csv"
        write_csv(path, ["date", "author_id", "message_id"], [
            [RECENT, "10", "1"],
            [RECENT, "20", "2"],
            [RECENT, "10", "3"],
        ])

        removed = remove_rows_for_author(path, 10)

        assert sorted(r["message_id"] for r in removed) == ["1", "3"]
        assert [r["message_id"] for r in read_csv(path)] == ["2"]

    def test_count_matches_without_mutating(self, tmp_path):
        path = tmp_path / "data.csv"
        write_csv(path, ["date", "author_id", "message_id"], [
            [RECENT, "10", "1"],
            [RECENT, "20", "2"],
        ])

        assert count_rows_for_author(path, 10) == 1
        assert len(read_csv(path)) == 2  # unchanged


# ---------------------------------------------------------------------------
# Retencion.run_prune_once
# ---------------------------------------------------------------------------
class TestRunPruneOnce:
    async def test_prunes_personal_data_logs_and_evicts_pending_entries(
        self, retencion_cog, isolated_logs
    ):
        write_csv(isolated_logs.log_main_file, ["date", "message_id"], [[OLD, "1"], [RECENT, "2"]])
        write_csv(
            isolated_logs.log_mod_file, ["date", "message_id"], [[OLD, "10"], [RECENT, "11"]]
        )
        retencion_cog.bot.data_mod = {"10": {"date": OLD}, "11": {"date": RECENT}}

        await retencion_cog.run_prune_once()

        assert [r["message_id"] for r in read_csv(isolated_logs.log_main_file)] == ["2"]
        assert [r["message_id"] for r in read_csv(isolated_logs.log_mod_file)] == ["11"]
        assert retencion_cog.bot.data_mod == {"11": {"date": RECENT}}

    async def test_does_not_touch_spam_caches(self, retencion_cog, isolated_logs):
        isolated_logs.log_spam_file.write_text("mensaje viejo\n")
        isolated_logs.log_image_spam_file.write_text("deadbeef\n")

        await retencion_cog.run_prune_once()

        assert isolated_logs.log_spam_file.read_text() == "mensaje viejo\n"
        assert isolated_logs.log_image_spam_file.read_text() == "deadbeef\n"


# ---------------------------------------------------------------------------
# Retencion.erase_user_data
# ---------------------------------------------------------------------------
class TestEraseUserData:
    def test_removes_matching_rows_across_logs_and_logs_the_erasure(
        self, retencion_cog, isolated_logs
    ):
        write_csv(isolated_logs.log_main_file, ["date", "author_id", "message_id"], [
            [RECENT, "42", "1"], [RECENT, "99", "2"],
        ])
        write_csv(isolated_logs.log_mod_file, ["date", "author_id", "message_id"], [
            [RECENT, "42", "10"],
        ])
        retencion_cog.bot.data_mod = {"10": {"author_id": "42"}}
        moderator = make_member(name="mod1", id=1)

        counts = retencion_cog.erase_user_data(42, requested_by=moderator)

        assert counts["log_main_file"] == 1
        assert counts["log_mod_file"] == 1
        assert [r["message_id"] for r in read_csv(isolated_logs.log_main_file)] == ["2"]
        assert retencion_cog.bot.data_mod == {}

        gdpr_row = read_last_csv_row(isolated_logs.log_gdpr_file)
        assert gdpr_row[1] == "42"  # user_id
        assert gdpr_row[2] == "mod1"  # requested_by
        assert gdpr_row[4] == "2"  # total_removed

    def test_does_not_touch_spam_caches(self, retencion_cog, isolated_logs):
        isolated_logs.log_spam_file.write_text("mensaje\n")

        retencion_cog.erase_user_data(42, requested_by=make_member(name="mod1"))

        assert isolated_logs.log_spam_file.read_text() == "mensaje\n"


# ---------------------------------------------------------------------------
# %olvidar command
# ---------------------------------------------------------------------------
class TestOlvidarUsuario:
    async def test_no_data_found_sends_plain_message(self, retencion_cog, isolated_logs):
        cog = bind_commands(retencion_cog)
        ctx = make_ctx()
        target = make_member(name="nadie", id=404)

        await cog.olvidar_usuario(ctx, target)

        ctx.send.assert_awaited_once()
        (msg,), kwargs = ctx.send.call_args
        assert "No se encontraron datos" in msg
        assert "embed" not in kwargs

    async def test_data_found_sends_confirmation_embed(self, retencion_cog, isolated_logs):
        write_csv(isolated_logs.log_main_file, ["date", "author_id", "message_id"], [
            [RECENT, "42", "1"],
        ])
        cog = bind_commands(retencion_cog)
        ctx = make_ctx()
        target = make_member(name="alguien", id=42)

        await cog.olvidar_usuario(ctx, target)

        ctx.send.assert_awaited_once()
        _, kwargs = ctx.send.call_args
        assert "1" in kwargs["embed"].description
        assert isinstance(kwargs["view"], ConfirmErasureView)


# ---------------------------------------------------------------------------
# ConfirmErasureView
# ---------------------------------------------------------------------------
class TestConfirmErasureView:
    async def test_confirm_by_a_mod_erases_and_edits_message(self, retencion_cog, isolated_logs):
        write_csv(isolated_logs.log_main_file, ["date", "author_id", "message_id"], [
            [RECENT, "42", "1"],
        ])
        target = make_member(name="alguien", id=42)
        view = ConfirmErasureView(retencion_cog, target)
        mod = make_member(name="mod1", roles=[retencion_cog.coord_role])
        interaction = make_interaction(user=mod)

        await view.confirm.callback(interaction)

        assert read_csv(isolated_logs.log_main_file) == []
        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        assert "eliminados" in kwargs["content"]
        assert kwargs["view"] is None

    async def test_confirm_by_a_non_mod_is_rejected(self, retencion_cog, isolated_logs):
        write_csv(isolated_logs.log_main_file, ["date", "author_id", "message_id"], [
            [RECENT, "42", "1"],
        ])
        target = make_member(name="alguien", id=42)
        view = ConfirmErasureView(retencion_cog, target)
        interaction = make_interaction(user=make_member(name="randomuser", roles=[]))

        await view.confirm.callback(interaction)

        assert len(read_csv(isolated_logs.log_main_file)) == 1  # untouched
        interaction.response.send_message.assert_awaited_once()
        interaction.response.edit_message.assert_not_awaited()

    async def test_cancel_does_not_erase_anything(self, retencion_cog, isolated_logs):
        write_csv(isolated_logs.log_main_file, ["date", "author_id", "message_id"], [
            [RECENT, "42", "1"],
        ])
        target = make_member(name="alguien", id=42)
        view = ConfirmErasureView(retencion_cog, target)
        mod = make_member(name="mod1", roles=[retencion_cog.coord_role])
        interaction = make_interaction(user=mod)

        await view.cancel.callback(interaction)

        assert len(read_csv(isolated_logs.log_main_file)) == 1  # untouched
        interaction.response.edit_message.assert_awaited_once()
        _, kwargs = interaction.response.edit_message.call_args
        assert "cancelada" in kwargs["content"]
