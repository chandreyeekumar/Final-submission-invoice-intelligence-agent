from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

import gdown


GOOGLE_DRIVE_FILE_ID = "1ZyxAw1d-9UvhgNLGRvsJK4gBCMf0VpGD"

DOWNLOAD_ROOT = Path("data/public/sroie_source")
ZIP_PATH = DOWNLOAD_ROOT / "sroie.zip"
EXTRACT_PATH = DOWNLOAD_ROOT / "extracted"


def main() -> None:
    DOWNLOAD_ROOT.mkdir(
        parents=True,
        exist_ok=True,
    )

    url = (
        "https://drive.google.com/uc?id="
        f"{GOOGLE_DRIVE_FILE_ID}"
    )

    print("Downloading original SROIE archive...")

    downloaded = gdown.download(
    url=url,
    output=str(ZIP_PATH),
    quiet=False,
    )

    if not downloaded:
        raise RuntimeError(
            "SROIE download failed."
        )

    if not ZIP_PATH.exists():
        raise FileNotFoundError(
            f"Downloaded ZIP was not found: {ZIP_PATH}"
        )

    if EXTRACT_PATH.exists():
        shutil.rmtree(EXTRACT_PATH)

    EXTRACT_PATH.mkdir(
        parents=True,
        exist_ok=True,
    )

    print("Extracting SROIE archive...")

    with zipfile.ZipFile(
        ZIP_PATH,
        "r",
    ) as archive:
        archive.extractall(
            EXTRACT_PATH
        )

    print(
        "SROIE source extracted to: "
        f"{EXTRACT_PATH.resolve()}"
    )


if __name__ == "__main__":
    main()