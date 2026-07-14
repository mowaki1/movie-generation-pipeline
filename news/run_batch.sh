#!/bin/bash
set -e
cd "$(dirname "$0")/.."
source "$HOME/roujin_home_senka/venv/bin/activate"
python news/fetch_rss.py
python news/fetch_body.py
python news/classify_genre.py
python news/generate_embeddings.py
python news/generate_summary.py
