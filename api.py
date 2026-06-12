from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from scraper import scrape_movie_data
from image_processor import merge_screenshots, download_image
import io
import requests
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

@app.route('/')
def index():
    return jsonify({"status": "Movie Extractor API is running ✅"})

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

@app.route('/scrape', methods=['POST'])
def scrape():
    body = request.get_json()
    if not body or 'url' not in body:
        return jsonify({"error": "No URL provided"}), 400

    url = body['url'].strip()
    if not url.startswith('http'):
        return jsonify({"error": "Invalid URL"}), 400

    try:
        data = scrape_movie_data(url)
        if 'error' in data:
            return jsonify(data), 500
        return jsonify(data)
    except Exception as e:
        logger.error(f"Scrape error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/download-image', methods=['POST'])
def download_image_route():
    body = request.get_json()
    img_url = body.get('url', '')
    filename = body.get('filename', 'image.jpg')

    try:
        resp = requests.get(img_url, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        buf = io.BytesIO(resp.content)
        buf.seek(0)
        return send_file(buf, mimetype='image/jpeg', as_attachment=True, download_name=filename)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/merge-screenshots', methods=['POST'])
def merge_route():
    body = request.get_json()
    screenshots = body.get('screenshots', [])

    if not screenshots:
        return jsonify({"error": "No screenshots provided"}), 400

    try:
        merged = merge_screenshots(screenshots)
        if not merged:
            return jsonify({"error": "Could not merge screenshots"}), 500
        merged.seek(0)
        return send_file(merged, mimetype='image/jpeg', as_attachment=True,
                         download_name='screenshots_merged.jpg')
    except Exception as e:
        logger.error(f"Merge error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7860, debug=False)
