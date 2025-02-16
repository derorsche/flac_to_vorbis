import glob
import os
import shutil
import stat
import subprocess
from logging import getLogger
from shutil import copy2, rmtree
from typing import Callable

logger = getLogger(__name__)


def check_prerequisite():
    # 必要な変数が設定されていることを確認する
    try:
        os.environ["FLAC_ROOT"]
        os.environ["VORBIS_ROOT"]
    except KeyError:
        print(
            "Please specify the necessary variables in `.env` file. A sample file is provided as `.env.sample`."
        )
        return False

    # ffmpeg が利用できることを確認する
    if shutil.which("ffmpeg") is None:
        print(
            "Please make sure that `ffmpeg` is downloaded and that its path is added to the Windows environment variable `Path`."
        )
        return False

    return True


def create_vorbis(f_abs_path: str, v_abs_path: str):
    subprocess.run(
        [
            "ffmpeg",
            "-i",
            f_abs_path,
            "-vn",
            "-acodec",
            "libvorbis",
            "-aq",
            "6",
            v_abs_path,
        ]
    )


def remove_readonly(func: Callable[[str], None], path: str, _):
    # see: https://docs.python.org/3/library/shutil.html#rmtree-example
    os.chmod(path, stat.S_IWRITE)
    func(path)


def sync_vorbis():
    # フォルダ構造として `[ROOT]/[artist_name]/[album_name]/[song_name].[ext]` を仮定している

    # 1. ファイル単位で flac の側から vorbis を同期するための処理
    for f_path in glob.iglob(
        pathname="**/*.flac", root_dir=os.environ["FLAC_ROOT"], recursive=True
    ):
        # root_dir 直下またはそのサブディレクトリ内の全ての .ogg ファイルにヒットする
        # f_path は root_dir からの相対パスを返すので、絶対パスを取得
        f_abs_path = os.path.join(os.environ["FLAC_ROOT"], f_path)
        v_abs_path = os.path.join(
            os.environ["VORBIS_ROOT"], os.path.splitext(f_path)[0] + ".ogg"
        )

        # 操作するディレクトリの存在を保証する
        os.makedirs(os.path.dirname(v_abs_path), exist_ok=True)

        # ogg ファイルが存在しない場合には作成する
        # 既に ogg ファイルが存在する場合には、更新日時が古い場合のみ再作成する
        if not os.path.exists(v_abs_path):
            create_vorbis(f_abs_path, v_abs_path)
        else:
            if os.path.getmtime(v_abs_path) < os.path.getmtime(f_abs_path):
                os.remove(v_abs_path)
                create_vorbis(f_abs_path, v_abs_path)
                logger.info(
                    f"File updated: {os.path.relpath(v_abs_path, os.environ['VORBIS_ROOT'])}"
                )

    # 2. ディレクトリ単位で flac の側から vorbis を同期するための処理
    for f_dir in glob.iglob(
        pathname="**/", root_dir=os.environ["FLAC_ROOT"], recursive=True
    ):
        f_abs_dir = os.path.join(os.environ["FLAC_ROOT"], f_dir)
        v_abs_dir = os.path.join(os.environ["VORBIS_ROOT"], f_dir)

        # 操作するディレクトリの存在を保証する
        os.makedirs(os.path.dirname(v_abs_dir), exist_ok=True)

        # flac を含むディレクトリの場合には、カバー画像に関する処理を行う
        if len(glob.glob(pathname="*.flac", root_dir=f_abs_dir)) > 0:
            covers = glob.glob(pathname="Cover.*", root_dir=f_abs_dir)

            # カバー画像が存在しない場合には警告する
            if len(covers) == 0:
                logger.info(f"No cover art found in {f_abs_dir}")

            # カバー画像が存在する場合には、vorbis 側に画像を同期する
            # なお、ディレクトリ内に複数のカバー画像が存在することは想定していない
            else:
                fc_path = os.path.join(f_abs_dir, covers[0])
                vc_path = os.path.join(v_abs_dir, covers[0])

                if not os.path.exists(vc_path):
                    copy2(fc_path, vc_path)
                else:
                    if os.path.getmtime(fc_path) < os.path.getmtime(vc_path):
                        os.remove(vc_path)
                        copy2(fc_path, vc_path)

    # 3. flac 側に存在しないファイルを vorbis 側から削除する処理
    for v_path in glob.iglob(
        pathname="**", root_dir=os.environ["VORBIS_ROOT"], recursive=True
    ):
        # 拡張子が .ogg の場合には対応するファイルは .flac になるので場合分けをしている
        if os.path.splitext(v_path)[1] == ".ogg":
            f_abs_path = os.path.join(
                os.environ["FLAC_ROOT"], os.path.splitext(v_path)[0] + ".flac"
            )
        else:
            f_abs_path = os.path.join(os.environ["FLAC_ROOT"], v_path)
        v_abs_path = os.path.join(os.environ["VORBIS_ROOT"], v_path)

        # 念のため、ファイルを削除してからディレクトリを削除する建付けにしている
        if os.path.isdir(v_abs_path):
            continue

        # 対応するファイルが flac 側に存在しない場合には削除する
        if not os.path.exists(f_abs_path):
            os.remove(v_abs_path)
            logger.info(f"File removed: {f_abs_path}")

    # 4. flac 側に存在しないディレクトリを vorbis 側から削除する処理
    for v_dir in glob.glob(
        pathname="**/", root_dir=os.environ["VORBIS_ROOT"], recursive=True
    ):
        f_abs_dir = os.path.join(os.environ["FLAC_ROOT"], v_dir)
        v_abs_dir = os.path.join(os.environ["VORBIS_ROOT"], v_dir)

        # それ以前の処理でディレクトリが削除されている可能性があるため、その場合にはスキップする
        if not os.path.exists(v_abs_dir):
            continue

        # flac 側のディレクトリが存在しない場合には、まず vorbis 側のディレクトリがファイルを含むかを確認する
        # ファイルが存在しない場合には、ディレクトリをツリーごと削除する
        if not os.path.exists(f_abs_dir):
            if (
                len(glob.glob(pathname="**", root_dir=v_abs_dir, recursive=True))
                - len(glob.glob(pathname="**/", root_dir=v_abs_dir, recursive=True))
                > 0
            ):
                print(
                    f"Although {f_abs_dir} doesn't exist, the relevant directory (i.e., {v_abs_dir}) contains some files. "
                    f"Therefore, we will skip the deletion of {v_abs_dir}"
                )
            else:
                rmtree(v_abs_dir, onexc=remove_readonly)  # type: ignore
                logger.info(f"Directory removed: {v_abs_dir}")
