import requests
import io
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def download_image(url: str):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        return io.BytesIO(resp.content)
    except Exception as e:
        logger.warning(f"Failed to download image {url}: {e}")
        return None

def merge_screenshots(screenshot_urls: list):
    if not screenshot_urls:
        return None
    return download_image(screenshot_urls[0])
