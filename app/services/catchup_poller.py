"""
Varredura de segurança (catch-up) dos grupos monitorados.

O Telethon entrega mensagens por push, mas o servidor corta a fila de updates
de um canal quando ela cresce demais (`channelTooLong`); o cliente só percebe
e busca o que faltou no timeout interno de 15 minutos (`NO_UPDATES_TIMEOUT`).
Resultado: a oferta pode chegar até 15 min atrasada — foi o que aconteceu com
o BUG das 17:20/17:21, entregue às 17:31 em 10/11/2026.

Esta varredura relê o topo de cada grupo monitorado em rodízio (1 grupo por
vez, com pausa entre eles) e processa pelo mesmo `MessageHandler` o que o
push não entregou. Custo: 1 requisição por grupo por volta (~53s com 53
grupos), o que fica bem abaixo do flood limit.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


class CatchupPoller:
    """Relê o topo dos grupos monitorados e recupera mensagens perdidas."""

    def __init__(
        self,
        client,
        handler,
        offer_service,
        interval=1.0,
        limit=20,
        prime_delay=60,
    ):
        self.client = client
        self.handler = handler
        self.offer_service = offer_service
        self.interval = interval
        self.limit = limit
        self.prime_delay = prime_delay
        self._cursor = {}

    async def run(self):
        """Loop infinito: uma volta completa pelos grupos a cada ciclo."""
        await asyncio.sleep(self.prime_delay)
        await self.prime()
        while True:
            for group in list(self.offer_service.state["grupos"]):
                try:
                    await self.scan_group(group)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    logger.warning(f"Catch-up falhou em '{group}': {e}")
                await asyncio.sleep(self.interval)

    @staticmethod
    def _resolve_target(group):
        """Traduz o nome guardado no estado para o que o Telethon aceita.

        O estado guarda canais privados pelo `chat.id` cru (ex.: "1007742949"),
        que não resolve como string — o peer id de canal é `-100<id>`.
        """
        if isinstance(group, str) and group.isdigit():
            return int(f"-100{group}")
        return group

    async def prime(self):
        """Marca o topo atual de cada grupo para não reenviar histórico no start.

        Mensagens publicadas entre o último estado salvo e o start continuam
        cobertas pelo catch-up do próprio Telethon.
        """
        for group in list(self.offer_service.state["grupos"]):
            try:
                messages = await self.client.get_messages(
                    self._resolve_target(group), limit=1
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Catch-up: não consegui ler '{group}': {e}")
                continue
            if messages:
                self._cursor[group] = messages[0].id
            await asyncio.sleep(self.interval)
        logger.info(
            f"Catch-up: prime concluído em {len(self._cursor)}"
            f"/{len(self.offer_service.state['grupos'])} grupos"
        )

    async def scan_group(self, group):
        """Processa mensagens do grupo mais novas que o cursor. Retorna quantas."""
        messages = await self.client.get_messages(
            self._resolve_target(group), limit=self.limit
        )
        if not messages:
            return 0

        cursor = self._cursor.get(group)
        if cursor is None:
            # Grupo adicionado depois do prime: começa do topo.
            self._cursor[group] = messages[0].id
            return 0

        pending = sorted(
            (m for m in messages if m.id > cursor), key=lambda m: m.id
        )
        if not pending:
            return 0

        # Avança o cursor antes de processar: se o handler falhar numa
        # mensagem, ela não trava a fila do grupo (o push ainda pode entregar).
        self._cursor[group] = pending[-1].id

        processed = 0
        for message in pending:
            if not (message.message or "").strip():
                continue
            chat = await message.get_chat()
            if not chat:
                continue
            if self.handler.was_processed(str(chat.id), message.id):
                continue
            await self.handler.process_message(message, chat)
            processed += 1

        if processed:
            logger.info(f"Catch-up: {processed} mensagem(ns) recuperada(s) de '{group}'")
        return processed
