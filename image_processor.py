import requests
import io
import logging
from PIL import Image

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def download_image(url: str) -> Image.Image | None:
    """Download image from URL and return PIL Image"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content)).convert("RGB")
        return img
    except Exception as e:
        logger.warning(f"Failed to download image {url}: {e}")
        return None

def merge_screenshots(screenshot_urls: list) -> io.BytesIO | None:
    """
    Download screenshots and merge into a 2-column grid.
    Returns BytesIO buffer of the merged image.
    """
    if not screenshot_urls:
        return None

    images = []
    for url in screenshot_urls[:6]:  # max 6
        img = download_image(url)
        if img:
            images.append(img)

    if not images:
        return None

    # Resize all to same size
    thumb_w, thumb_h = 640, 360
    resized = [img.resize((thumb_w, thumb_h), Image.LANCZOS) for img in images]

    # Calculate grid: 2 columns
    cols = 2
    rows = (len(resized) + 1) // cols

    grid_w = cols * thumb_w
    grid_h = rows * thumb_h

    grid = Image.new("RGB", (grid_w, grid_h), (20, 20, 20))

    for idx, img in enumerate(resized):
        col = idx % cols
        row = idx // cols
        x = col * thumb_w
        y = row * thumb_h
        grid.paste(img, (x, y))

    # Save to buffer
    buffer = io.BytesIO()
    grid.save(buffer, format="JPEG", quality=85)
    buffer.seek(0)

    return buffer
