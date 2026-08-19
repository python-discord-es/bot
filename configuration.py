import logging
import sys
import toml

from pathlib import Path

logger = logging.getLogger(__name__)


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Config(metaclass=Singleton):
    def __init__(self):
        # Configuration file
        logger.debug("Config __init__")
        config = None
        with open("config.toml") as f:
            config = toml.loads(f.read())

        if not config:
            logger.error("Failed to load the config")
            sys.exit(-1)

        try:
            self.TOKEN = config["bot"]["token"]
            self.BOT_ID = config["bot"]["id"]
            self.LOG_FILE = config["bot"]["log_file"]

            self.MOD_MAIN = config["moderation"]["channel_id"]
            self.MOD_ROLE = config["moderation"]["role"]
            self.MUTED_ROLE = config["moderation"]["muted_role"]
            self.LOG_MOD_FILE = config["moderation"]["log_file"]

            self.GUILD = config["server"]["guild"]

            self.CHANNELS = config["channels"]
            self.FLOOD_LIMIT = 3
            self.MENTIONS_LIMIT = 3
            # Minimum number of images in a single message, and the time
            # window (seconds) in which the same author posting such a
            # message in 2+ different channels is treated as a spam burst.
            self.IMAGE_ATTACHMENT_LIMIT = 2
            self.IMAGE_BURST_WINDOW = 60 * 5
            # Data-retention policy (see comandos/retencion.py): personal-data
            # logs older than this are deleted daily.
            self.RETENTION_DAYS = 30
        except KeyError:
            logger.error(
                "Error while reading the configuration file. "
                "Make sure it contains all the required field"
            )
            sys.exit(-1)

        # Public URL to TERMS.md (the bot's terms of use / data policy),
        # surfaced via the %terminos command and (separately, outside this
        # repo) the Discord Developer Portal's privacy-policy field.
        # Optional/`.get()`-based on purpose: older configs without a
        # [links] section shouldn't fail to start over this.
        self.TERMS_URL = config.get("links", {}).get(
            "terms_url", "https://raw.githubusercontent.com/python-discord-es/bot/main/TERMS.md"
        )

        self.setup_log_files()

    def setup_log_files(self):
        self.log_file = Path(self.LOG_FILE)
        self.log_mod_file = Path(self.LOG_MOD_FILE)
        self.log_spam_file = Path("logs/spam_log.csv")
        self.log_image_spam_file = Path("logs/image_spam_log.csv")
        self.log_main_file = Path("logs/main_log.csv")

        # create an '_accepted' file based on the moderation log file
        LOG_MOD_ACCEPTED_FILE = f"logs/{self.log_mod_file.stem}_accepted{self.log_mod_file.suffix}"
        # create an '_rejected' file based on the moderation log file
        LOG_MOD_REJECTED_FILE = f"logs/{self.log_mod_file.stem}_rejected{self.log_mod_file.suffix}"

        self.log_accepted_file = Path(LOG_MOD_ACCEPTED_FILE)
        self.log_rejected_file = Path(LOG_MOD_REJECTED_FILE)

        # Audit trail for right-to-erasure requests (comandos/retencion.py).
        # Only ever holds a user id, who requested it, and a row count - no
        # personal content - so it's safe to keep indefinitely as evidence
        # a request was honored.
        self.log_gdpr_file = Path("logs/gdpr_erasure_log.csv")

        # Audit trail for right-of-access/export requests (comandos/exportar.py).
        # Same shape/rationale as log_gdpr_file above: id, requester and a
        # count only, never the exported content itself.
        self.log_gdpr_access_file = Path("logs/gdpr_access_log.csv")

        # Checking files
        self.check_create_file(
            self.log_file, "date;command;message_id;channel;author_id;author;message\n"
        )
        self.check_create_file(
            self.log_mod_file, "date;message_id;channel;author_id;author;message\n"
        )
        self.check_create_file(
            self.log_accepted_file,
            "date;message_id;channel;author_id;author;message;moderator\n",
        )
        self.check_create_file(
            self.log_rejected_file,
            "date;message_id;channel;author_id;author;message;moderator;reason\n",
        )
        self.check_create_file(self.log_spam_file, "\n")
        self.check_create_file(self.log_image_spam_file, "\n")
        self.check_create_file(
            self.log_main_file,
            "date;command;message_id;channel;author_id;author;message\n",
        )
        self.check_create_file(
            self.log_gdpr_file,
            "date;user_id;requested_by;requested_by_id;total_removed\n",
        )
        self.check_create_file(
            self.log_gdpr_access_file,
            "date;user_id;requested_by;requested_by_id;total_exported\n",
        )

    def get_spam_messages(self):
        # Adding spam messages
        d = set()
        with open(self.log_spam_file) as f:
            for line in f.readlines():
                logger.debug("Loaded known spam message: %r", line.strip())
                d.add(line.strip())
        logger.debug("get_spam_messages: %s", d)
        return d

    def get_spam_image_hashes(self):
        # Adding known scam image hashes (sha256 of the raw attachment bytes)
        d = set()
        with open(self.log_image_spam_file) as f:
            for line in f.readlines():
                line = line.strip()
                if line:
                    d.add(line)
        logger.debug("get_spam_image_hashes: %s", d)
        return d

    def check_create_file(self, fname: Path, msg: str) -> None:
        if not fname.is_file():
            with open(str(fname), "w") as f:
                f.write(msg)
