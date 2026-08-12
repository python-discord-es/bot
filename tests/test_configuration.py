from configuration import Config


class TestSingleton:
    def test_config_is_a_singleton(self, config):
        assert Config() is config

    def test_reflects_sandboxed_toml(self, config):
        assert config.MOD_ROLE == "Coordinacion"
        assert config.MUTED_ROLE == "Muted"
        assert config.BOT_ID == 111111111111111111
        assert "eventos" in config.CHANNELS

    def test_hardcoded_limits(self, config):
        # Not read from config.toml - always set in __init__.
        assert config.FLOOD_LIMIT == 3
        assert config.MENTIONS_LIMIT == 3
        assert config.IMAGE_ATTACHMENT_LIMIT == 2
        assert config.IMAGE_BURST_WINDOW == 60 * 5


class TestCheckCreateFile:
    def test_creates_missing_file_with_header(self, config, tmp_path):
        target = tmp_path / "new_log.csv"
        assert not target.exists()

        config.check_create_file(target, "a;b;c\n")

        assert target.read_text() == "a;b;c\n"

    def test_does_not_overwrite_existing_file(self, config, tmp_path):
        target = tmp_path / "existing_log.csv"
        target.write_text("already;here\nfoo;bar\n")

        config.check_create_file(target, "a;b;c\n")

        assert target.read_text() == "already;here\nfoo;bar\n"


class TestGetSpamMessages:
    def test_reads_lines_as_a_set(self, config, isolated_logs):
        isolated_logs.log_spam_file.write_text("mensaje uno\nmensaje dos\n")

        assert config.get_spam_messages() == {"mensaje uno", "mensaje dos"}

    def test_empty_file_returns_empty_set(self, config, isolated_logs):
        isolated_logs.log_spam_file.write_text("")

        assert config.get_spam_messages() == set()


class TestGetSpamImageHashes:
    def test_reads_hashes_as_a_set(self, config, isolated_logs):
        isolated_logs.log_image_spam_file.write_text("abc123\ndef456\n")

        assert config.get_spam_image_hashes() == {"abc123", "def456"}

    def test_skips_blank_lines(self, config, isolated_logs):
        isolated_logs.log_image_spam_file.write_text("abc123\n\n\ndef456\n")

        assert config.get_spam_image_hashes() == {"abc123", "def456"}
