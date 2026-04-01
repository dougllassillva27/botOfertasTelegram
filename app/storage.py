import json
import os
from app.config import DATA_DIR

DATA_FILE = os.path.join(DATA_DIR, 'data.json')

def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "grupos": ["garimpeirosoficial", "achadinhosnapromoo", "pelandobr"],
            "alertas": ["shampoo", "teclado", "notebook"]
        }
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(default_data, f, indent=4, ensure_ascii=False)
        return default_data
    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)