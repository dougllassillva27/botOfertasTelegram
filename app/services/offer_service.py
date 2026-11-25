"""
Serviço de ofertas  -  lógica de negócio para busca, cadastro e gerenciamento.
"""

import re
import logging
from datetime import datetime, timedelta, timezone

from app.services.deduplication import OfferDeduplicator
from app.storage import save_data

logger = logging.getLogger(__name__)


class OfferService:
    """Encapsula toda a lógica de negócio do bot."""

    def __init__(self, state):
        self.state = state
        self.deduplicator = OfferDeduplicator()

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

    @staticmethod
    def _clean_group_name(group_name):
        """Normaliza nome de grupo: remove URLs do Telegram e '@'."""
        return (
            group_name.replace("https://web.telegram.org/k/#@", "")
            .replace("https://t.me/", "")
            .replace("@", "")
            .strip()
        )

    @staticmethod
    def _normalize_alert(keyword):
        """Normaliza palavra-chave de alerta: minúsculas e sem espaços nas pontas."""
        return keyword.lower().strip()

    def add_group(self, group_name):
        """Adiciona um grupo à lista de monitoramento."""
        clean_name = self._clean_group_name(group_name)
        if clean_name not in self.state["grupos"]:
            self.state["grupos"].append(clean_name)
            save_data(self.state)
            return True, f"✅ Grupo `{clean_name}` adicionado com sucesso!"
        return False, "⚠️ Este grupo já está na lista."

    def remove_group(self, group_name):
        """Remove um grupo da lista de monitoramento."""
        clean_name = self._clean_group_name(group_name)
        if clean_name in self.state["grupos"]:
            self.state["grupos"].remove(clean_name)
            save_data(self.state)
            return True, f"🗑️ Grupo `{clean_name}` removido."
        return False, "⚠️ Grupo não encontrado."

    def add_groups(self, group_names):
        """Adiciona grupos em massa. Retorna (results, changed).

        results: lista de tuplas (item, ok, msg) por item processado.
        changed: True se ao menos um grupo foi adicionado.
        save_data é chamado uma única vez ao final, somente se changed.
        """
        results = []
        changed = False
        for raw_name in group_names:
            clean_name = self._clean_group_name(raw_name)
            if clean_name not in self.state["grupos"]:
                self.state["grupos"].append(clean_name)
                changed = True
                results.append((clean_name, True, "adicionado com sucesso"))
            else:
                results.append((clean_name, False, "já está na lista"))
        if changed:
            save_data(self.state)
        return results, changed

    def remove_groups(self, group_names):
        """Remove grupos em massa. Retorna (results, changed).

        results: lista de tuplas (item, ok, msg) por item processado.
        changed: True se ao menos um grupo foi removido.
        save_data é chamado uma única vez ao final, somente se changed.
        """
        results = []
        changed = False
        for raw_name in group_names:
            clean_name = self._clean_group_name(raw_name)
            if clean_name in self.state["grupos"]:
                self.state["grupos"].remove(clean_name)
                changed = True
                results.append((clean_name, True, "removido"))
            else:
                results.append((clean_name, False, "não encontrado"))
        if changed:
            save_data(self.state)
        return results, changed

    def get_groups_list(self):
        """Retorna lista formatada dos grupos monitorados."""
        if not self.state["grupos"]:
            return "Nenhum grupo monitorado no momento."
        return "\n".join([f"• `{g}`" for g in self.state["grupos"]])

    def add_alert(self, keyword):
        """Adiciona uma palavra-chave de alerta."""
        kw = self._normalize_alert(keyword)
        if kw not in self.state["alertas"]:
            self.state["alertas"].append(kw)
            save_data(self.state)
            return True, f"✅ Alerta para `{kw}` adicionado com sucesso!"
        return False, "⚠️ Este alerta já está na lista."

    def _get_whatsapp_flags(self):
        """Retorna a lista de alertas marcados para WhatsApp (tolerante a estado antigo)."""
        return self.state.setdefault("alertas_whatsapp", [])

    def has_whatsapp_flag(self, keyword):
        """Verifica se o alerta está marcado para também ir pro WhatsApp."""
        kw = self._normalize_alert(keyword)
        return kw in self._get_whatsapp_flags()

    def set_whatsapp_flag(self, keyword, enabled=True):
        """Liga ou desliga a marca WhatsApp de um alerta existente.

        As respostas são autoexplicativas: sempre dizem o estado atual e
        repetem o comando contrário (ligar ↔ desligar), pra não depender de
        quem lembre a sintaxe.
        """
        kw = self._normalize_alert(keyword)
        if kw not in self.state["alertas"]:
            return False, (
                f"⚠️ Alerta `{kw}` não encontrado\n\n"
                f"🔔 Cadastre primeiro: `/alertas add {kw}`"
            )
        flags = self._get_whatsapp_flags()
        if enabled:
            if kw in flags:
                return False, (
                    f"⚠️ `{kw}` **já vai pro WhatsApp** 📲\n\n"
                    f"🔕 Pra desligar: `/alertas wa {kw}`"
                )
            flags.append(kw)
            save_data(self.state)
            return True, (
                f"✅ `{kw}` **agora também vai pro WhatsApp** 📲\n\n"
                "📩 Entrega no grupo Sol ☀️ com menção no Douglas\n"
                f"🔕 Pra desligar: `/alertas wa {kw}`"
            )
        if kw not in flags:
            return False, (
                f"⚠️ `{kw}` **não estava indo pro WhatsApp**\n\n"
                f"📲 Pra ligar: `/alertas wa {kw}`"
            )
        flags.remove(kw)
        save_data(self.state)
        return True, (
            f"🔕 `{kw}` **voltou a ir só pro Telegram**\n\n"
            f"📲 Pra ligar de novo: `/alertas wa {kw}`"
        )

    def remove_alert(self, keyword):
        """Remove uma palavra-chave de alerta (e sua marca WhatsApp)."""
        kw = self._normalize_alert(keyword)
        if kw in self.state["alertas"]:
            self.state["alertas"].remove(kw)
            flags = self._get_whatsapp_flags()
            if kw in flags:
                flags.remove(kw)
            save_data(self.state)
            return True, f"🗑️ Alerta para `{kw}` removido."
        return False, "⚠️ Alerta não encontrado."

    def add_alerts(self, keywords):
        """Adiciona alertas em massa. Retorna (results, changed).

        results: lista de tuplas (item, ok, msg) por item processado.
        changed: True se ao menos um alerta foi adicionado.
        save_data é chamado uma única vez ao final, somente se changed.
        """
        results = []
        changed = False
        for raw_keyword in keywords:
            kw = self._normalize_alert(raw_keyword)
            if kw not in self.state["alertas"]:
                self.state["alertas"].append(kw)
                changed = True
                results.append((kw, True, "adicionado com sucesso"))
            else:
                results.append((kw, False, "já está na lista"))
        if changed:
            save_data(self.state)
        return results, changed

    def remove_alerts(self, keywords):
        """Remove alertas em massa. Retorna (results, changed).

        results: lista de tuplas (item, ok, msg) por item processado.
        changed: True se ao menos um alerta foi removido.
        save_data é chamado uma única vez ao final, somente se changed.
        """
        results = []
        changed = False
        for raw_keyword in keywords:
            kw = self._normalize_alert(raw_keyword)
            if kw in self.state["alertas"]:
                self.state["alertas"].remove(kw)
                flags = self._get_whatsapp_flags()
                if kw in flags:
                    flags.remove(kw)
                changed = True
                results.append((kw, True, "removido"))
            else:
                results.append((kw, False, "não encontrado"))
        if changed:
            save_data(self.state)
        return results, changed

    def get_alerts_list(self):
        """Retorna lista formatada dos alertas ativos."""
        if not self.state["alertas"]:
            return "Nenhum alerta ativo no momento."
        return "\n".join([f"• `{a}`" for a in self.state["alertas"]])

    # ------------------------------------------------------------------
    # Promo tags (tags de urgência / promoção boa)
    # ------------------------------------------------------------------
    _VOGAIS = set("aeiouáéíóúâêîôûãõàèìòù")

    @staticmethod
    def _normalize_promo_tag(tag):
        return str(tag or "").lower().strip()

    @staticmethod
    def _promo_tag_pattern(tag):
        tag = str(tag or "").lower().strip()
        if not tag:
            return None
        words = tag.split()
        if len(words) > 1:
            escaped = [re.escape(w) for w in words]
            return re.compile(
                r"\b" + r"\s+".join(escaped) + r"\b", re.IGNORECASE
            )
        last = tag[-1]
        if last in OfferService._VOGAIS:
            base = re.escape(tag[:-1])
            return re.compile(
                r"\b" + base + re.escape(last) + r"+s?\b", re.IGNORECASE
            )
        return re.compile(r"\b" + re.escape(tag) + r"s?\b", re.IGNORECASE)

    def _get_promo_tags(self):
        return self.state.setdefault("promo_tags", [])

    def _get_promo_tags_whatsapp_flags(self):
        return self.state.setdefault("promo_tags_whatsapp", [])

    def add_promo_tag(self, tag):
        tg = self._normalize_promo_tag(tag)
        if not tg:
            return False, "⚠️ Tag inválida."
        tags = self._get_promo_tags()
        if tg not in tags:
            tags.append(tg)
            save_data(self.state)
            return True, f"✅ Tag de promoção `{tg}` adicionada."
        return False, f"⚠️ Tag `{tg}` já está na lista."

    def remove_promo_tag(self, tag):
        tg = self._normalize_promo_tag(tag)
        tags = self._get_promo_tags()
        if tg in tags:
            tags.remove(tg)
            flags = self._get_promo_tags_whatsapp_flags()
            if tg in flags:
                flags.remove(tg)
            save_data(self.state)
            return True, f"🗑️ Tag de promoção `{tg}` removida."
        return False, f"⚠️ Tag `{tg}` não encontrada."

    def add_promo_tags(self, tags):
        results = []
        changed = False
        for raw in tags or []:
            tg = self._normalize_promo_tag(raw)
            if not tg:
                continue
            lst = self._get_promo_tags()
            if tg not in lst:
                lst.append(tg)
                changed = True
                results.append((tg, True, "adicionada com sucesso"))
            else:
                results.append((tg, False, "já está na lista"))
        if changed:
            save_data(self.state)
        return results, changed

    def remove_promo_tags(self, tags):
        results = []
        changed = False
        for raw in tags or []:
            tg = self._normalize_promo_tag(raw)
            lst = self._get_promo_tags()
            if tg in lst:
                lst.remove(tg)
                flags = self._get_promo_tags_whatsapp_flags()
                if tg in flags:
                    flags.remove(tg)
                changed = True
                results.append((tg, True, "removida"))
            else:
                results.append((tg, False, "não encontrada"))
        if changed:
            save_data(self.state)
        return results, changed

    def get_promo_tags_list(self):
        tags = self._get_promo_tags()
        if not tags:
            return "Nenhuma tag de promoção ativa no momento."
        return "\n".join([f"• `{t}`" for t in tags])

    def has_promo_tag_whatsapp_flag(self, tag):
        tg = self._normalize_promo_tag(tag)
        return tg in self._get_promo_tags_whatsapp_flags()

    def set_promo_tag_whatsapp_flag(self, tag, enabled=True):
        tg = self._normalize_promo_tag(tag)
        tags = self._get_promo_tags()
        if tg not in tags:
            return False, (
                f"⚠️ Tag `{tg}` não encontrada\n\n"
                f"🔔 Cadastre primeiro: `/tags add {tg}`"
            )
        flags = self._get_promo_tags_whatsapp_flags()
        if enabled:
            if tg in flags:
                return False, (
                    f"⚠️ `{tg}` **já vai pro WhatsApp** 📲\n\n"
                    f"🔕 Pra desligar: `/tags wa {tg}`"
                )
            flags.append(tg)
            save_data(self.state)
            return True, (
                f"✅ `{tg}` **agora também vai pro WhatsApp** 📲\n\n"
                "📩 Entrega no grupo Sol ☀️ com menção no Douglas\n"
                f"🔕 Pra desligar: `/tags wa {tg}`"
            )
        if tg not in flags:
            return False, (
                f"⚠️ `{tg}` **não estava indo pro WhatsApp**\n\n"
                f"📲 Pra ligar: `/tags wa {tg}`"
            )
        flags.remove(tg)
        save_data(self.state)
        return True, (
            f"🔕 `{tg}` **voltou a ir só pro Telegram**\n\n"
            f"📲 Pra ligar de novo: `/tags wa {tg}`"
        )

    def check_promo_tag_matches(self, message_text):
        if not message_text:
            return []
        matches = []
        for tag in self._get_promo_tags():
            pat = self._promo_tag_pattern(tag)
            if pat is None:
                continue
            if pat.search(message_text):
                if tag not in matches:
                    matches.append(tag)
        return matches

    # ------------------------------------------------------------------
    # Regras de preço (valor bom)
    # ------------------------------------------------------------------

    def _get_price_rules(self):
        rules = self.state.setdefault("price_rules", {})
        rules.setdefault("discount_min", 60)
        rules.setdefault("price_max", 20)
        rules.setdefault("whatsapp", False)
        return rules

    def get_price_discount_min(self):
        return self._get_price_rules()["discount_min"]

    def get_price_max(self):
        return self._get_price_rules()["price_max"]

    def set_price_discount_min(self, value):
        try:
            v = int(value)
        except (ValueError, TypeError):
            return False, "⚠️ Valor inválido. Use número inteiro entre 1 e 100."
        if v < 1 or v > 100:
            return False, "⚠️ Threshold deve estar entre 1 e 100."
        self._get_price_rules()["discount_min"] = v
        save_data(self.state)
        return True, "✅ Threshold de desconto ajustado para {}%.".format(v)

    def set_price_max(self, value):
        try:
            v = int(value)
        except (ValueError, TypeError):
            return False, "⚠️ Valor inválido. Use número inteiro >= 1."
        if v < 1:
            return False, "⚠️ Teto deve ser >= 1."
        self._get_price_rules()["price_max"] = v
        save_data(self.state)
        return True, "✅ Teto de preço ajustado para R$ {}.".format(v)

    def has_price_whatsapp_flag(self):
        return bool(self._get_price_rules().get("whatsapp", False))

    def set_price_whatsapp_flag(self, enabled=True):
        self._get_price_rules()["whatsapp"] = bool(enabled)
        save_data(self.state)
        if enabled:
            return True, "✅ 'Preço bom' agora também vai pro WhatsApp 📲"
        return True, "🔕 'Preço bom' voltou a ir só pro Telegram"

    def check_price_good(self, message_text):
        from app.services.price_parser import check_price_good as _check

        rules = self._get_price_rules()
        return _check(
            message_text,
            discount_min=rules["discount_min"],
            price_max=rules["price_max"],
        )

    def check_keyword_matches(self, message_text):
        """Retorna TODAS as keywords monitoradas presentes na mensagem.

        Ordem: a da lista de alertas (quem vem primeiro na lista vem primeiro),
        para manter estável o "alerta principal".

        Por que não basta a primeira keyword: o envio pro WhatsApp é decidido
        por keyword marcada, e uma oferta pode citar várias (ex.: "ORFEU Café
        em Grãos" bate `café` E `orfeu`). Decidir só pela primeira da lista
        escondia a keyword marcada e a oferta nunca ia pro Zap.
        """
        if not message_text:
            return []

        message_lower = message_text.lower()
        matches = []
        for keyword in self.state["alertas"]:
            pattern = rf"\b{re.escape(keyword.lower())}s?\b"
            if re.search(pattern, message_lower):
                matches.append(keyword)
        return matches

    def check_keyword_match(self, message_text):
        """Verifica se a mensagem contém alguma palavra-chave monitorada.

        Retorna só a primeira (compatibilidade); use check_keyword_matches
        quando todas importarem, como no disparo pro WhatsApp.
        """
        matches = self.check_keyword_matches(message_text)
        return matches[0] if matches else None

    def extract_offer_info(self, message_text):
        """Extrai título, descrição e URL de uma mensagem."""
        if not message_text:
            return None, None, None

        # Tenta extrair URL
        url_match = re.search(r'(https?://\S+)', message_text)
        url = url_match.group(1) if url_match else None

        # Simples heurística: primeira linha é título, resto é descrição
        lines = message_text.strip().split('\n')
        title = lines[0] if lines else message_text[:100]
        description = '\n'.join(lines[1:]) if len(lines) > 1 else ''

        return title, description, url

    def should_send_offer(self, title, description, url=None):
        """
        Verifica se oferta deve ser enviada (não é duplicata).

        Returns:
            tuple: (should_send: bool, reason: str|None)
        """
        is_dup, reason, matched_hash = self.deduplicator.is_duplicate(title, description, url)

        if is_dup:
            self.deduplicator.log_skipped(title, description, url, reason)
            return False, reason

        return True, None

    def register_sent_offer(self, title, description, url=None, groups=None):
        """Registra oferta como enviada no sistema de deduplicação."""
        self.deduplicator.register_offer(title, description, url, groups)
