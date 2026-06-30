"""
Serviço de ofertas — lógica de negócio para busca, cadastro e gerenciamento.
"""

import re
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class OfferService:
    """Encapsula toda a lógica de negócio do bot."""

    def __init__(self, state):
        self.state = state

    async def search_offers(self, client, query, max_results=30):
        """Busca ofertas retroativas nos últimos 7 dias em todos os grupos monitorados."""
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        found_messages = []

        for group in self.state["grupos"]:
            try:
                async for message in client.iter_messages(group, search=query):
                    if message.date < seven_days_ago:
                        break
                    found_messages.append(message)
            except Exception as e:
                logger.warning(f"Erro ao buscar no grupo {group}: {e}")
                continue

        # Ordena da mais recente para a mais antiga
        found_messages.sort(key=lambda msg: msg.date, reverse=True)

        # Limita para evitar spam
        messages_to_forward = found_messages[:max_results]
        return found_messages, messages_to_forward

    @staticmethod
    def format_offer_message(msg, br_tz=None):
        """Formata mensagem de oferta com data e origem."""
        if br_tz is None:
            br_tz = timezone(timedelta(hours=-3))

        msg_date = msg.date.astimezone(br_tz).strftime("%d/%m/%Y às %H:%M")
        chat = None
        try:
            chat = msg.get_chat()
        except Exception:
            pass

        chat_title = getattr(chat, "title", "Desconhecido") if chat else "Desconhecido"
        return f"📅 **Data da oferta:** {msg_date}\n📦 **Origem:** {chat_title}"

    def add_group(self, group_name):
        """Adiciona um grupo à lista de monitoramento."""
        clean_name = (
            group_name.replace("https://web.telegram.org/k/#@", "")
            .replace("https://t.me/", "")
            .replace("@", "")
            .strip()
        )
        if clean_name not in self.state["grupos"]:
            self.state["grupos"].append(clean_name)
            return True, f"✅ Grupo `{clean_name}` adicionado com sucesso!"
        return False, "⚠️ Este grupo já está na lista."

    def remove_group(self, group_name):
        """Remove um grupo da lista de monitoramento."""
        clean_name = (
            group_name.replace("https://web.telegram.org/k/#@", "")
            .replace("https://t.me/", "")
            .replace("@", "")
            .strip()
        )
        if clean_name in self.state["grupos"]:
            self.state["grupos"].remove(clean_name)
            return True, f"🗑️ Grupo `{clean_name}` removido."
        return False, "⚠️ Grupo não encontrado."

    def get_groups_list(self):
        """Retorna lista formatada dos grupos monitorados."""
        if not self.state["grupos"]:
            return "Nenhum grupo monitorado no momento."
        return "\n".join([f"- `{g}`" for g in self.state["grupos"]])

    def add_alert(self, keyword):
        """Adiciona uma palavra-chave de alerta."""
        kw = keyword.lower().strip()
        if kw not in self.state["alertas"]:
            self.state["alertas"].append(kw)
            return True, f"✅ Alerta para `{kw}` adicionado com sucesso!"
        return False, "⚠️ Este alerta já está na lista."

    def remove_alert(self, keyword):
        """Remove uma palavra-chave de alerta."""
        kw = keyword.lower().strip()
        if kw in self.state["alertas"]:
            self.state["alertas"].remove(kw)
            return True, f"🗑️ Alerta para `{kw}` removido."
        return False, "⚠️ Alerta não encontrado."

    def get_alerts_list(self):
        """Retorna lista formatada dos alertas ativos."""
        if not self.state["alertas"]:
            return "Nenhum alerta ativo no momento."
        return "\n".join([f"- `{a}`" for a in self.state["alertas"]])

    def check_keyword_match(self, message_text):
        """Verifica se a mensagem contém alguma palavra-chave monitorada."""
        if not message_text:
            return None

        message_lower = message_text.lower()
        for keyword in self.state["alertas"]:
            pattern = rf"\b{re.escape(keyword.lower())}s?\b"
            if re.search(pattern, message_lower):
                return keyword
        return None
