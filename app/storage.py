import json
import os
import shutil
from datetime import datetime

from app.config import DATA_DIR

DATA_FILE = os.path.join(DATA_DIR, "data.json")

# Quantos backups datados manter em data/. Acima disso, os mais antigos são removidos.
BACKUP_KEEP = 10


def _backup_existing():
    """Cria backup datado do data.json atual antes de uma sobrescrita.

    Blindagem contra perda de estado: um save acidental (teste rodando sem
    isolamento, bug, intervenção manual) deixa o conteúdo anterior recuperável
    em data/data.json.bak-<AAAAMMDD-HHMMSS>.
    """
    if not os.path.exists(DATA_FILE):
        return
    # Microssegundos no sufixo: escritas rápidas no mesmo segundo ainda geram
    # backups distintos (sem isso, um save acidental em rajada ficaria sem cópia).
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    backup_path = f"{DATA_FILE}.bak-{stamp}"
    shutil.copy2(DATA_FILE, backup_path)
    _prune_backups()


def _prune_backups():
    """Mantém apenas os BACKUP_KEEP backups mais recentes, remove os antigos.

    Deriva o diretório do próprio DATA_FILE (não do módulo DATA_DIR) para
    operar sempre junto ao arquivo que está sendo protegido.
    """
    directory = os.path.dirname(DATA_FILE)
    backups = sorted(
        f
        for f in os.listdir(directory)
        if f.startswith("data.json.bak-")
    )
    excesso = len(backups) - BACKUP_KEEP
    for nome in backups[:excesso] if excesso > 0 else []:
        os.remove(os.path.join(directory, nome))


def load_data():
    if not os.path.exists(DATA_FILE):
        default_data = {
            "grupos": ["garimpeirosoficial", "achadinhosnapromoo", "pelandobr"],
            "alertas": ["shampoo", "teclado", "notebook"],
        }
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=4, ensure_ascii=False)
        return default_data
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_data(data):
    _backup_existing()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
