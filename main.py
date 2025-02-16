from logging import config, getLogger

import dotenv
from yaml import safe_load

from module import key_module

logger = getLogger(__name__)


def main():
    with open("etc/log-conf.yaml", "r", encoding="utf-8") as f:
        config.dictConfig(safe_load(f))

    dotenv.load_dotenv()
    key_module.check_prerequisite()
    key_module.sync_vorbis()


if __name__ == "__main__":
    main()
