import glob
import os
import subprocess
from logging import config, getLogger
from shutil import copy2

import dotenv
from yaml import safe_load

logger = getLogger(__name__)


def main():
    dotenv.load_dotenv()

    with open("etc/log-conf.yaml", "r", encoding="utf-8") as f:
        config.dictConfig(safe_load(f))

    flac_dir = os.environ["FLAC_PATH"]
    vorbis_dir = os.environ["VORBIS_PATH"]

    for flac in glob.glob("**/*.flac", root_dir=flac_dir, recursive=True):
        dst = os.path.join(vorbis_dir, os.path.splitext(flac)[0] + ".ogg")

        if os.path.exists(dst):
            continue

        if not os.path.exists(os.path.dirname(dst)):
            os.makedirs(os.path.dirname(dst), exist_ok=True)

        subprocess.run(
            [
                "ffmpeg",
                "-i",
                os.path.join(flac_dir, flac),
                "-vn",
                "-acodec",
                "libvorbis",
                "-aq",
                "6",
                dst,
            ]
        )

    visited: set[str] = set()

    for flac in glob.glob("**/*.flac", root_dir=flac_dir, recursive=True):
        dir = os.path.dirname(flac)

        if dir in visited:
            continue
        else:
            visited.add(dir)

        if covers := glob.glob("Cover.*", root_dir=os.path.join(flac_dir, dir)):
            for cover in covers:
                copy2(
                    os.path.join(flac_dir, dir, cover),
                    os.path.join(vorbis_dir, dir, cover),
                )
        else:
            logger.info(f"No cover art found in {dir}")


if __name__ == "__main__":
    main()
