"""Periodically fetch an image from a source URL and push it to a Samsung Frame TV's Art Mode."""

import logging
import os
import signal
import sys
import threading
import time
from io import BytesIO
from pathlib import Path

import requests
from dotenv import load_dotenv
from PIL import Image, ImageOps, UnidentifiedImageError
from samsungtvws.art import SamsungTVArt

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

TV_IP = os.getenv("TV_IP", "")
TV_PORT = int(os.getenv("TV_PORT", "8002"))
SOURCE_URL = os.getenv("SOURCE_URL", "")
SYNC_INTERVAL = int(os.getenv("SYNC_INTERVAL", "3600"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "10"))
FRAME_WIDTH = int(os.getenv("FRAME_WIDTH", "3840"))
FRAME_HEIGHT = int(os.getenv("FRAME_HEIGHT", "2160"))
FRAME_BACKGROUND_COLOR = os.getenv("FRAME_BACKGROUND_COLOR", "#f2ede2")
AUTO_SELECT_IMAGE = os.getenv("AUTO_SELECT_IMAGE", "true").lower() in (
    "1",
    "true",
    "yes",
)
UPLOAD_TIMEOUT = int(os.getenv("UPLOAD_TIMEOUT", "300"))

# Persisted so the previous image can be deleted instead of piling up on the TV across restarts
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
CONTENT_ID_FILE = DATA_DIR / "content_id.txt"

_shutdown_requested = False


def _handle_shutdown_signal(signum, frame):
    global _shutdown_requested
    logger.info("Received signal %s, shutting down after current cycle...", signum)
    _shutdown_requested = True


def load_last_content_id() -> str | None:
    try:
        return CONTENT_ID_FILE.read_text().strip() or None
    except FileNotFoundError:
        return None


def save_content_id(content_id: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CONTENT_ID_FILE.write_text(content_id)


def validate_config() -> None:
    missing = [
        name
        for name, value in (("TV_IP", TV_IP), ("SOURCE_URL", SOURCE_URL))
        if not value
    ]
    if missing:
        logger.error(
            "Missing required environment variable(s): %s. "
            "Set them in your environment or .env file (see .env.example).",
            ", ".join(missing),
        )
        sys.exit(1)


def fetch_and_upload() -> None:
    logger.info("Fetching image from %s...", SOURCE_URL)
    try:
        response = requests.get(SOURCE_URL, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()

        # Pad instead of stretch, so non-16:9 sources aren't distorted on the TV
        img = Image.open(BytesIO(response.content)).convert("RGB")
        img = ImageOps.pad(
            img,
            (FRAME_WIDTH, FRAME_HEIGHT),
            color=FRAME_BACKGROUND_COLOR,
            centering=(0.5, 0.5),
        )
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, format="JPEG", quality=95)
        image_data = img_byte_arr.getvalue()
    except requests.RequestException:
        logger.exception("Failed to fetch source image")
        return
    except UnidentifiedImageError:
        logger.exception("Fetched content is not a valid image")
        return
    except Exception:
        logger.exception("Unexpected error while preparing the image")
        return

    # samsungtvws's art API is synchronous with no built-in timeout, so a hung
    # connection could otherwise block the sync loop forever
    thread = threading.Thread(target=_sync_to_tv, args=(image_data,), daemon=True)
    thread.start()
    thread.join(timeout=UPLOAD_TIMEOUT)
    if thread.is_alive():
        logger.error(
            "TV upload timed out after %ss; abandoning this cycle.", UPLOAD_TIMEOUT
        )


def _sync_to_tv(image_data: bytes) -> None:
    try:
        tv = SamsungTVArt(host=TV_IP, port=TV_PORT)

        logger.info("Uploading image to Samsung Frame TV at %s...", TV_IP)
        content_id = tv.upload(image_data, matte="none", file_type="jpg")
        if not content_id:
            logger.warning(
                "Upload did not return a content id; image may not be active."
            )
            return

        if AUTO_SELECT_IMAGE:
            tv.select_image(content_id)
            logger.info("Successfully updated Art Mode picture.")
        else:
            logger.info("Uploaded content id %s without selecting it.", content_id)

        previous_content_id = load_last_content_id()
        if previous_content_id and previous_content_id != content_id:
            try:
                tv.delete(previous_content_id)
            except Exception:
                logger.warning(
                    "Could not delete previous image %s",
                    previous_content_id,
                    exc_info=True,
                )
        save_content_id(content_id)
    except Exception:
        logger.exception("Unexpected error while syncing to the TV")


def main() -> None:
    validate_config()

    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)

    logger.info(
        "Starting Samsung Frame TV Sync Daemon (interval=%ss)...", SYNC_INTERVAL
    )
    while not _shutdown_requested:
        fetch_and_upload()
        for _ in range(SYNC_INTERVAL):
            if _shutdown_requested:
                break
            time.sleep(1)

    logger.info("Shutdown complete.")


if __name__ == "__main__":
    main()
