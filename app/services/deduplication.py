"""
Serviço de deduplicação de ofertas — evita envio duplicado em múltiplos grupos.
"""

import re
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from thefuzz import fuzz

logger = logging.getLogger(__name__)


class OfferDeduplicator:
    """Gerencia registro de ofertas enviadas e detecta duplicatas."""

    def __init__(self, data_file="data/offers_sent.json", log_file=None):
        self.data_file = Path(data_file)
        # Usa Logs.txt unificado por padrão
        if log_file is None:
            log_file = str(Path(__file__).parent.parent.parent / "logs" / "Logs.txt")
        self.log_file = Path(log_file)
        self.offers = {}
        self._load_data()

    def _load_data(self):
        """Carrega registro de ofertas do JSON."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r", encoding="utf-8") as f:
                    self.offers = json.load(f).get("offers", {})
                logger.info(f"Carregadas {len(self.offers)} ofertas do registro")
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Erro ao carregar registro: {e}, iniciando vazio")
                self.offers = {}
        else:
            logger.info("Registro de ofertas não existe, iniciando vazio")

    def _save_data(self):
        """Persiste registro de ofertas no JSON."""
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump({"offers": self.offers}, f, ensure_ascii=False, indent=2)

    def _cleanup_expired(self, hours=48):
        """Remove registros mais antigos que 48h."""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        expired = [
            h for h, data in self.offers.items()
            if datetime.fromisoformat(data["sent_at"]) < cutoff
        ]
        for h in expired:
            del self.offers[h]
        if expired:
            logger.info(f"Removidos {len(expired)} registros expirados")
            self._save_data()

    def _normalize_text(self, text):
        """Normaliza texto para hash: minúsculas, remove espaços extras e URLs."""
        if not text:
            return ""
        # Remove URLs
        text = re.sub(r'https?://\S+', '', text)
        # Normaliza espaços e converte para minúsculas
        text = ' '.join(text.lower().split())
        # Remove caracteres especiais mantendo apenas alfanuméricos e espaços
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip()

    def _extract_url(self, text):
        """Extrai primeira URL do texto."""
        if not text:
            return None
        match = re.search(r'(https?://\S+)', text)
        return match.group(1) if match else None

    def generate_hash(self, title, description, url=None):
        """Gera hash único para oferta baseado em título + descrição + URL."""
        normalized = self._normalize_text(f"{title} {description}")
        if url:
            normalized += f"|{url}"
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def calculate_similarity(self, text1, text2):
        """Calcula similaridade fuzzy entre dois textos (0-100)."""
        norm1 = self._normalize_text(text1)
        norm2 = self._normalize_text(text2)
        return fuzz.ratio(norm1, norm2)

    def is_duplicate(self, title, description, url=None, threshold=80):
        """
        Verifica se oferta é duplicata baseada em hash exato ou similaridade fuzzy.

        Returns:
            tuple: (is_dup: bool, reason: str, matched_hash: str|None)
        """
        self._cleanup_expired()

        current_hash = self.generate_hash(title, description, url)

        # 1. Verifica hash exato
        if current_hash in self.offers:
            logger.info(f"Duplicata exata detectada: hash {current_hash[:8]}...")
            return True, "hash_exato", current_hash

        # 2. Verifica similaridade fuzzy com ofertas recentes (últimas 48h)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
        recent_offers = {
            h: data for h, data in self.offers.items()
            if datetime.fromisoformat(data["sent_at"]) >= cutoff
        }

        current_text = f"{title} {description}"

        for stored_hash, stored_data in recent_offers.items():
            stored_text = f"{stored_data.get('title', '')} {stored_data.get('description', '')}"
            similarity = self.calculate_similarity(current_text, stored_text)

            if similarity >= threshold:
                logger.info(
                    f"Similaridade {similarity}% detectada: "
                    f"'{title[:30]}...' vs '{stored_data.get('title', '')[:30]}...'"
                )
                return True, f"similaridade_{similarity}%", stored_hash

        return False, None, None

    def register_offer(self, title, description, url=None, groups=None):
        """Registra oferta como enviada."""
        self._cleanup_expired()

        offer_hash = self.generate_hash(title, description, url)
        self.offers[offer_hash] = {
            "title": title,
            "description": description,
            "url": url,
            "sent_at": datetime.now(timezone.utc).isoformat(),
            "groups_sent": groups or []
        }
        self._save_data()
        logger.info(f"Oferta registrada: hash {offer_hash[:8]}...")

    def log_skipped(self, title, description, url=None, reason="duplicata"):
        """Registra oferta pulada no arquivo de log unificado."""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # Formato ISO para ordenação: YYYY-MM-DD HH:MM:SS
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        url_str = url or "N/A"

        log_line = f"[{timestamp}] [PULADA] {title[:50]}... | URL: {url_str} | Motivo: {reason}\n"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_line)

        logger.info(f"Oferta pulada (motivo: {reason}) — não reencaminhando")
