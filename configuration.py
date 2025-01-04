import sys
import toml

from pathlib import Path


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Config(metaclass=Singleton):
    def __init__(self):
        # Configuration file
        print("Config __init__")
        config = None
        with open("config.toml") as f:
            config = toml.loads(f.read())

        if not config:
            print("Error: Failed to load the config")
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
        except KeyError:
            print("Error while reading the configuration file. "
                  "Make sure it contains all the required field")
            sys.exit(-1)

        self.setup_log_files()

    def setup_log_files(self):
        self.log_file = Path(self.LOG_FILE)
        self.log_mod_file = Path(self.LOG_MOD_FILE)
        self.log_spam_file = Path("logs/spam_log.csv")
        self.log_main_file = Path("logs/main_log.csv")

        # create an '_accepted' file based on the moderation log file
        LOG_MOD_ACCEPTED_FILE = f"logs/{self.log_mod_file.stem}_accepted{self.log_mod_file.suffix}"
        # create an '_rejected' file based on the moderation log file
        LOG_MOD_REJECTED_FILE = f"logs/{self.log_mod_file.stem}_rejected{self.log_mod_file.suffix}"

        self.log_accepted_file = Path(LOG_MOD_ACCEPTED_FILE)
        self.log_rejected_file = Path(LOG_MOD_REJECTED_FILE)

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
        self.check_create_file(
            self.log_main_file,
            "date;command;message_id;channel;author_id;author;message\n",
        )

    def get_spam_messages(self):
        # Adding spam messages
        d = set()
        with open(self.log_spam_file) as f:
            for line in f.readlines():
                print(">>>", line.strip())
                d.add(line.strip())
        print("LOG: get_spam_messages", d)
        return d

    def check_create_file(self, fname: Path, msg: str) -> None:
        if not fname.is_file():
            with open(str(fname), "w") as f:
                f.write(msg)
