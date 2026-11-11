"""
Handler de mensagens — monitora grupos e encaminha ofertas com alertas.

Duas fontes de mensagem chegam aqui:

1. Push do Telethon (`handle_message`), o caminho normal;
2. Varredura de segurança (`CatchupPoller`), que relê o topo dos grupos e
   entrega o que o push não entregou (gap de updates) — chama
   `process_message` direto.

O processamento roda em task própria (`dispatch`): o Telethon espera o
retorno do handler antes de despachar a próxima mensagem, então qualquer
envio lento aqui paralisaria a recepção de todos os grupos.
"""

import asyncio
import logging
from collections import deque
from datetime import datetime, timedelta, timezone

from app.services.whatsapp_destinos import destinos_for
from app.services.whatsapp_sender import send_offer_to_whatsapp

logger = logging.getLogger(__name__)

BR_TZ = timezone(timedelta(hours=-3))

# Quantos (chat, mensagem) recentes lembramos, para a varredura de segurança
# não reprocessar o que o push já entregou.
SEEN_IDS_MAX = 2000

# Atraso a partir do qual a entrega é registrada como "atrasada" no log.
LAG_WARN_SECONDS = 60


class MessageHandler:
    """Handler responsável por processar mensagens dos grupos monitorados."""

    def __init__(self, client, offer_service):
        self.client = client
        self.offer_service = offer_service
        # Serializa checagem + registro da deduplicação: com processamento
        # concorrente, duas mensagens iguais chegando juntas passariam as duas
        # pela checagem antes de qualquer registro.
        self._lock = asyncio.Lock()
        self._tasks = set()
        self._seen = deque(maxlen=SEEN_IDS_MAX)
        self._seen_set = set()

    # ------------------------------------------------------------------
    # Entrada
    # ------------------------------------------------------------------
    def dispatch(self, event):
        """Agenda o processamento sem segurar o loop de updates do Telethon."""
        task = asyncio.create_task(self._run(event))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _run(self, event):
        try:
            await self.handle_message(event)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falha ao processar mensagem recebida")

    async def handle_message(self, event):
        """Processa uma mensagem recebida e verifica se há keywords de alerta."""
        # Ignora mensagens enviadas pelo próprio bot que sejam comandos
        if (
            event.out
            and event.message.message
            and event.message.message.startswith("/")
        ):
            return

        chat = await event.get_chat()
        if not chat:
            return

        await self.process_message(event.message, chat)

    # ------------------------------------------------------------------
    # Núcleo (compartilhado pelo push e pela varredura)
    # ------------------------------------------------------------------
    async def process_message(self, message, chat):
        """Avalia uma mensagem de um chat e encaminha se bater algum alerta."""
        chat_username = getattr(chat, "username", "") or ""
        chat_id = str(chat.id)
        chat_title = getattr(chat, "title", "Desconhecido")

        if not self._is_monitored(chat_username, chat_id):
            return

        # Marca como visto antes de qualquer decisão: a varredura de catch-up
        # usa isso para saber o que o push NÃO entregou (métrica real de gap).
        self._mark_processed(chat_id, getattr(message, "id", None))

        message_text = message.message if message.message else ""

        # Keyword primeiro: a checagem de duplicidade usa comparação fuzzy e é
        # a parte cara do fluxo. Só faz sentido para mensagem que iria adiante.
        matched_keywords = self.offer_service.check_keyword_matches(message_text)
        if not matched_keywords:
            return

        title, description, url = self.offer_service.extract_offer_info(message_text)

        async with self._lock:
            should_send, _reason = self.offer_service.should_send_offer(
                title, description, url
            )
            if not should_send:
                return
            if title:
                self.offer_service.register_sent_offer(
                    title, description, url, [chat_title]
                )

        lag = self._lag_seconds(getattr(message, "date", None))
        if lag is not None and lag > LAG_WARN_SECONDS:
            logger.warning(
                f"Oferta atrasada em {int(lag)}s (publicada {self._fmt_date(message.date)})"
                f" — entregue por catch-up, não por push"
            )

        chat_title = getattr(chat, "title", "Desconhecido")
        logger.info(
            f"Keyword(s) {matched_keywords} found in chat '{chat_title}'!"
            " Forwarding..."
        )

        fw_msg = await message.forward_to(self.offer_service.state["forward_to"])

        alert_label = ", ".join(f"`{kw}`" for kw in matched_keywords)
        await self.client.send_message(
            self.offer_service.state["forward_to"],
            f"🔔 **Alerta:** {alert_label}\n"
            f"📅 **Data:** {self._fmt_date(message.date)}\n"
            f"📦 **Origem:** {chat_title}",
            reply_to=fw_msg,
            silent=True,
        )

        # Rota WhatsApp: dois gatilhos independentes.
        #   - keyword marcada (`/alertas wa`) → grupo Sol com menção + destinos
        #     em DM que incluam a keyword;
        #   - keyword fora das marcas, mas no recorte de algum destino → só a DM
        #     (o grupo do dono não recebe o que ele não pediu).
        flagged = [kw for kw in matched_keywords if self.offer_service.has_whatsapp_flag(kw)]
        destinos = destinos_for(self.offer_service.state, matched_keywords)
        if flagged or destinos:
            logger.info(
                f"Oferta pro WhatsApp: alertas {flagged}"
                f" | grupo={'sim' if flagged else 'não'}"
                f" | destinos={[d['nome'] for d in destinos]}"
            )
            try:
                # to_thread: a ponte é HTTP síncrono (urllib) e bloquearia o
                # event loop por até WHATSAPP_BRIDGE_TIMEOUT segundos.
                await asyncio.to_thread(
                    send_offer_to_whatsapp,
                    message_text,
                    chat_title,
                    message.date,
                    destinos,
                    bool(flagged),
                )
            except Exception as e:
                logger.warning(f"Falha ao enviar oferta pro WhatsApp: {e}")

    # ------------------------------------------------------------------
    # Apoio
    # ------------------------------------------------------------------
    def _is_monitored(self, chat_username, chat_id):
        return any(
            g.lower() in [chat_username.lower(), chat_id]
            for g in self.offer_service.state["grupos"]
        )

    def was_processed(self, chat_id, message_id):
        """A varredura usa isto para não repetir o que o push já tratou."""
        return (str(chat_id), message_id) in self._seen_set

    def _mark_processed(self, chat_id, message_id):
        if message_id is None:
            return
        key = (chat_id, message_id)
        if key in self._seen_set:
            return
        if len(self._seen) >= SEEN_IDS_MAX:
            self._seen_set.discard(self._seen[0])
        self._seen.append(key)
        self._seen_set.add(key)

    @staticmethod
    def _lag_seconds(msg_date):
        """Segundos entre a publicação no Telegram e o processamento."""
        try:
            lag = (datetime.now(timezone.utc) - msg_date).total_seconds()
        except Exception:
            return None
        return lag if isinstance(lag, (int, float)) else None

    @staticmethod
    def _fmt_date(msg_date):
        try:
            return msg_date.astimezone(BR_TZ).strftime("%d/%m/%Y às %H:%M")
        except Exception:
            return "desconhecida"
