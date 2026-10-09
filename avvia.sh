#!/usr/bin/env bash
# Rinnova i cookie da Firefox e avvia lo scraping.
#
# Uso:   ./avvia.sh CREATOR [ALTRO_CREATOR ...]
# Esempio: ./avvia.sh Queen_37
#
# Prima di lanciarlo, fai login su callingfans.com con Firefox.
set -euo pipefail

cd "$(dirname "$0")"

if [ "$#" -eq 0 ]; then
    echo "Uso: ./avvia.sh CREATOR [ALTRO_CREATOR ...]   (es. ./avvia.sh Queen_37)" >&2
    exit 2
fi

if [ ! -d .venv ]; then
    echo "Prima installazione: creo l'ambiente Python..."
    python3 -m venv .venv
    .venv/bin/pip install -q -e .
fi
source .venv/bin/activate

echo "== Rinnovo i cookie da Firefox"
if ! callingfans-scraper auth --firefox; then
    echo "Apri callingfans.com in Firefox, fai login e rilancia ./avvia.sh" >&2
    exit 2
fi

echo "== Avvio lo scraping"
callingfans-scraper scrape -u "$@" -a posts purchased
