"""
Envio de ofertas para o WhatsApp via ponte local (sessão do Sol).

Único módulo que conhece a API da ponte (bridge.js em 127.0.0.1:3001).
POST /send com { chatId, message, mentions } — menção nativa no grupo.
"""

import json
import logging
import os
import urllib.request
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)

# Ponte do WhatsApp (sessão do Sol) — escuta em localhost por segurança
BRIDGE_URL = os.getenv("WHATSAPP_BRIDGE_URL", "http://127.0.0.1:3001")
BRIDGE_TIMEOUT = int(os.getenv("WHATSAPP_BRIDGE_TIMEOUT", "10"))

# Grupo Sol ☀️ | Personal Agent
WHATSAPP_GROUP_ID = os.getenv(
    "WHATSAPP_GROUP_ID", "120363428867776994@g.us"
)
# Número do Douglas (menção nativa)
WHATSAPP_MENTION_JID = os.getenv(
    "WHATSAPP_MENTION_JID", "555195782073@s.whatsapp.net"
)

BR_TZ = timezone(timedelta(hours=-3))


def _mention_handle():
    """Handle de menção pro texto: o WhatsApp só renderiza a menção (e notifica)
    quando o @número aparece no corpo da mensagem — o campo `mentions` sozinho
    não basta (validado em teste real em 09/10/2026)."""
    return "@" + WHATSAPP_MENTION_JID.split("@")[0]


def build_offer_text(message_text, chat_title, msg_date):
    """Monta o texto da oferta para o WhatsApp: menção + original + origem + data."""
    msg_date_br = msg_date.astimezone(BR_TZ).strftime("%d/%m/%Y às %H:%M")
    parts = [
        f"🔔 {_mention_handle()} Nova oferta",
        "",
        message_text.strip() if message_text else "(sem texto)",
        "",
        f"📦 Origem: {chat_title}",
        f"📅 Data: {msg_date_br}",
    ]
    return "\n".join(parts)


def send_offer_to_whatsapp(message_text, chat_title, msg_date):
    """Envia a oferta pro grupo Sol com menção. Retorna True se enviou.

    Falha silenciosa com log: o envio pro WhatsApp é um extra — a oferta
    já foi encaminhada pro Telegram antes desta chamada.
    """
    text = build_offer_text(message_text, chat_title, msg_date)
    payload = json.dumps(
        {
            "chatId": WHATSAPP_GROUP_ID,
            "message": text,
            "mentions": [WHATSAPP_MENTION_JID],
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{BRIDGE_URL}/send",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=BRIDGE_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("success"):
                logger.info(f"Oferta enviada pro WhatsApp (messageId={body.get('messageId')})")
                return True
            logger.warning(f"Ponte WhatsApp recusou a oferta: {body}")
            return False
    except Exception as e:
        logger.warning(f"Falha ao enviar oferta pro WhatsApp: {e}")
        return False
