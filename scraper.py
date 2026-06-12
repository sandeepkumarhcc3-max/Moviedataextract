import requests
from bs4 import BeautifulSoup
import re
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}

def extract_quality(raw_quality: str) -> str:
    """
    Extract only the quality type — stop before resolution numbers like 4K, 1080p, 720p, 480p.
    Examples:
      'DS4K WEB-DL 4K | 1080p | 720p | 480p' -> 'DS4K WEB-DL'
      'BluRay 1080p 720p 480p'               -> 'BluRay'
      'HDCAM 480p'                            -> 'HDCAM'
      'WEB-DL 4K | 1080p'                    -> 'WEB-DL'
      'HQ-HDTC 1080p 720p'                   -> 'HQ-HDTC'
    """
    if not raw_quality:
        return "N/A"

    # Remove content inside brackets first e.g. [Hindi DD5.1]
    cleaned = re.sub(r'\[.*?\]', '', raw_quality).strip()

    # Stop at resolution patterns: 4K, 1080p, 720p, 480p, 360p, or pipe |
    match = re.split(r'\s*[\|&]\s*|\s+(?:4K|DS4K|\d{3,4}p)', cleaned, maxsplit=1)

    if match:
        quality = match[0].strip()
        # Remove trailing punctuation
        quality = quality.rstrip('|&, ')
        return quality if quality else raw_quality.strip()

    return raw_quality.strip()

def clean_imdb(raw: str) -> str:
    """Extract IMDb rating like 8.6/10"""
    if not raw:
        return "N/A"
    # Find pattern like 7.5/10 or x/10
    match = re.search(r'[\d.x]+/10', raw)
    if match:
        return match.group()
    return raw.strip()

def clean_name(raw: str) -> str:
    """Extract clean movie/series name from page title"""
    if not raw:
        return "N/A"
    # Remove common suffixes like ' – HDHub4u Official'
    name = re.sub(r'\s*[–—-]\s*HDHub4u.*$', '', raw, flags=re.IGNORECASE)
    # Remove the quality/format part after the name in brackets
    # Keep everything before the first '[' or quality keyword
    name = re.split(r'\s+(?:DS4K|WEB-DL|BluRay|HDTC|HDRip|WEBRip)\b', name, maxsplit=1)[0]
    return name.strip()

def extract_screenshots(soup: BeautifulSoup) -> list:
    """Find screenshot image URLs from catimages.co or similar hosts"""
    screenshots = []
    
    # Look for links to catimages.co (thumbnail preview links)
    for a_tag in soup.find_all('a', href=True):
        href = a_tag['href']
        if 'catimages.co' in href or 'imgshare' in href or 'myimg' in href:
            # These are usually lightbox links to full images
            screenshots.append(href)
    
    # Also look for img tags within screenshot sections
    screenshot_section = soup.find(lambda tag: tag.name and 
                                    'screen' in tag.get_text().lower() and 
                                    tag.name in ['h2', 'h3', 'p'])
    if screenshot_section:
        parent = screenshot_section.find_parent()
        if parent:
            for img in parent.find_all('img', src=True):
                src = img.get('src', '')
                if src and 'http' in src and 'logo' not in src.lower():
                    screenshots.append(src)

    # Fallback: look for any catimages links in page
    if not screenshots:
        for a_tag in soup.find_all('a', href=re.compile(r'catimages\.co/image/')):
            screenshots.append(a_tag['href'])

    return screenshots[:6]  # Max 6 screenshots

def scrape_movie_data(url: str) -> dict:
    """Main scraper function for HDHub4u"""
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Request failed: {e}")
        return {"error": str(e)}

    soup = BeautifulSoup(response.text, 'html.parser')

    data = {}

    # ── THUMBNAIL (og:image) ──────────────────────────────────────────
    og_image = soup.find('meta', property='og:image')
    if og_image:
        data['thumbnail'] = og_image.get('content', '')

    # ── PAGE TITLE → CLEAN NAME ───────────────────────────────────────
    h1 = soup.find('h1')
    if h1:
        raw_title = h1.get_text(strip=True)
        # Remove leading emoji-like symbols (**, etc.)
        raw_title = re.sub(r'^[\*\s✦★•►]+', '', raw_title).strip()
        data['name'] = clean_name(raw_title)
    else:
        title_tag = soup.find('title')
        if title_tag:
            data['name'] = clean_name(title_tag.get_text(strip=True))
        else:
            data['name'] = 'N/A'

    # ── METADATA FROM POST BODY ───────────────────────────────────────
    # HDHub4u uses bold labels like "Genre:", "Language:", etc.
    content_area = soup.find('div', class_=re.compile(r'entry|post|content', re.I))
    if not content_area:
        content_area = soup

    full_text = content_area.get_text(separator='\n')

    def extract_field(label: str, text: str) -> str:
        """Extract value after a label like 'Genre:' from text"""
        pattern = rf'{re.escape(label)}\s*[:\|]?\s*(.+?)(?:\n|$)'
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return 'N/A'

    # IMDb Rating
    raw_imdb = extract_field('iMDB Rating', full_text)
    if raw_imdb == 'N/A':
        raw_imdb = extract_field('IMDb', full_text)
    data['imdb'] = clean_imdb(raw_imdb)

    # Genre
    raw_genre = extract_field('Genre', full_text)
    # Clean up pipes and extra spaces
    if raw_genre != 'N/A':
        raw_genre = ' | '.join([g.strip() for g in re.split(r'[|\n]', raw_genre) if g.strip()])
    data['genre'] = raw_genre

    # Language
    raw_lang = extract_field('Language', full_text)
    if raw_lang != 'N/A':
        # Keep first part before newline
        raw_lang = raw_lang.split('\n')[0].strip()
    data['language'] = raw_lang

    # Quality — MOST IMPORTANT: extract only type, not resolution
    raw_quality = extract_field('Quality', full_text)
    data['quality'] = extract_quality(raw_quality)

    # Stars / Cast
    raw_stars = extract_field('Stars', full_text)
    if raw_stars == 'N/A':
        raw_stars = extract_field('Cast', full_text)
    data['stars'] = raw_stars

    # Episodes (for series)
    raw_eps = extract_field('No. of Episodes', full_text)
    if raw_eps == 'N/A':
        raw_eps = extract_field('Episodes', full_text)
    data['episodes'] = raw_eps if raw_eps != 'N/A' else ''

    # Creator (for series)
    raw_creator = extract_field('Creator', full_text)
    data['creator'] = raw_creator if raw_creator != 'N/A' else ''

    # Storyline — look for "Storyline" heading
    storyline = ''
    storyline_h = content_area.find(lambda t: t.name in ['h2','h3','h4','p','strong'] and
                                     'storyline' in t.get_text().lower())
    if storyline_h:
        next_p = storyline_h.find_next('p')
        if next_p:
            storyline = next_p.get_text(strip=True)
    data['storyline'] = storyline

    # ── SCREENSHOTS ───────────────────────────────────────────────────
    data['screenshots'] = extract_screenshots(soup)

    logger.info(f"Scraped: {data.get('name')} | Quality: {data.get('quality')}")
    return data
