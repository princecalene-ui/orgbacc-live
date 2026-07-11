from flask import Flask, jsonify, send_from_directory
from bs4 import BeautifulSoup
import requests
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CHANNEL_URL = 'https://t.me/s/statistika_baccara'
USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36'

app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path='')

CARD_SUIT_RE = re.compile(r'(10|[2-9AJQK])\s*([♠♥♦♣])\s*')
GAME_RE = re.compile(r'#N\s*(\d+)', re.IGNORECASE)


def normalize_message_text(text: str) -> str:
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    text = re.sub(r'#N\s*(\d+)\s*\.', r'#N\1.', text, flags=re.IGNORECASE)
    text = re.sub(r'\(\s*', '(', text)
    text = re.sub(r'\s*\)', ')', text)
    text = re.sub(r'\s*-\s*', ' - ', text)

    def card_fix(match):
        return f"{match.group(1)}{match.group(2)}"

    text = CARD_SUIT_RE.sub(card_fix, text)
    text = re.sub(r'\)\s*-', ') -', text)
    text = re.sub(r'-\s*(\d+\()', r'- \1', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def fetch_latest_game():
    res = requests.get(CHANNEL_URL, headers={'User-Agent': USER_AGENT}, timeout=20)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, 'html.parser')
    messages = soup.select('.tgme_widget_message_wrap')
    if not messages:
        raise RuntimeError('Aucun message Telegram trouvé')

    target = None
    for msg in reversed(messages):
        text_el = msg.select_one('.tgme_widget_message_text')
        if not text_el:
            continue
        raw_text = text_el.get_text(' ', strip=True)
        if '#N' in raw_text:
            target = msg
            break

    if target is None:
        raise RuntimeError('Aucun jeu exploitable trouvé dans les messages récents')

    text_el = target.select_one('.tgme_widget_message_text')
    raw_text = text_el.get_text(' ', strip=True)
    normalized = normalize_message_text(raw_text)
    game_match = GAME_RE.search(normalized)
    if not game_match:
        raise RuntimeError('Le dernier message ne contient pas de numéro de jeu valide')

    date_el = target.select_one('time')
    link_el = target.select_one('a.tgme_widget_message_date')
    msg_wrap_id = target.get('data-post') or (link_el.get('href') if link_el else '')

    return {
        'channel_url': CHANNEL_URL,
        'game_number': int(game_match.group(1)),
        'raw_text': raw_text,
        'normalized': normalized,
        'published_at': date_el.get('datetime') if date_el else None,
        'source_url': link_el.get('href') if link_el else CHANNEL_URL,
        'message_id': msg_wrap_id,
    }


@app.get('/api/latest-game')
def api_latest_game():
    try:
        return jsonify(fetch_latest_game())
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.get('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')


@app.get('/health')
def health():
    return jsonify({'ok': True})


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)
