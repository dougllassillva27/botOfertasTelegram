"""
Envio de ofertas para o WhatsApp via ponte local (sessão do Sol).

Único módulo que conhece a API da ponte (bridge.js em 127.0.0.1:3001).
POST /send com { chatId, message, mentions } — menção nativa no grupo.
"""

import json
import logging
import os
import urllib.request
from datetime import timedelta, timezone

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


def build_offer_text(message_text, chat_title, msg_date, mention=True):
    """Monta o texto da oferta para o WhatsApp: menção + original + origem + data.

    `mention=False` é pro envio em conversa individual: em DM não existe menção
    nativa e o `@número` apareceria como texto solto na primeira linha.
    """
    msg_date_br = msg_date.astimezone(BR_TZ).strftime("%d/%m/%Y às %H:%M")
    header = f"🔔 {_mention_handle()} Nova oferta" if mention else "🔔 Nova oferta"
    parts = [
        header,
        "",
        message_text.strip() if message_text else "(sem texto)",
        "",
        f"📦 Origem: {chat_title}",
        f"📅 Data: {msg_date_br}",
    ]
    return "\n".join(parts)


def _post_send(chat_id, text, mentions=None):
    """POST /send na ponte. Retorna True se a ponte confirmou o envio.

    A ponte não valida o destino: JID sem conta no WhatsApp também volta
    `success: true` e a mensagem apenas não chega. Sucesso aqui significa
    "a ponte aceitou", não "a pessoa recebeu".
    """
    payload = {"chatId": chat_id, "message": text}
    if mentions:
        payload["mentions"] = mentions

    request = urllib.request.Request(
        f"{BRIDGE_URL}/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=BRIDGE_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            if body.get("success"):
                logger.info(
                    f"Oferta enviada pro WhatsApp em {chat_id} "
                    f"(messageId={body.get('messageId')})"
                )
                return True
            logger.warning(f"Ponte WhatsApp recusou o envio para {chat_id}: {body}")
            return False
    except Exception as e:
        logger.warning(f"Falha ao enviar oferta pro WhatsApp em {chat_id}: {e}")
        return False


def send_offer_to_whatsapp(message_text, chat_title, msg_date, destinos=None, group=True):
    """Envia a oferta pro grupo Sol (com menção) e para cada destino em DM.

    `group=False` é o caso em que nenhuma keyword marcada disparou — a oferta só
    interessa a algum destino em DM (ex.: `moedor` no recorte do amigo), então o
    grupo do dono não recebe nada.

    Retorna True se o envio pro grupo funcionou (ou se ele não era pra acontecer).
    Falha num destino em DM não impede os outros e não interrompe nada: o envio
    pro WhatsApp é extra, a oferta já foi pro Telegram antes desta chamada.
    """
    ok_grupo = True
    if group:
        ok_grupo = _post_send(
            WHATSAPP_GROUP_ID,
            build_offer_text(message_text, chat_title, msg_date),
            [WHATSAPP_MENTION_JID],
        )

    for destino in destinos or []:
        try:
            _post_send(
                destino["jid"],
                build_offer_text(message_text, chat_title, msg_date, mention=False),
            )
        except Exception as e:  # payload malformado não derruba o grupo já enviado
            logger.warning(f"Destino {destino.get('nome')} falhou: {e}")

    return ok_grupo
