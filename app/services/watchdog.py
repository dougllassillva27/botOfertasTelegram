"""
Watchdog de atividade do bot.

Monitora o ultimo log emitido (heartbeat). O Telethon gera logs a cada
~15 minutos quando a conexao esta saudavel. Se nenhuma atividade ocorrer
dentro do timeout configurado, o processo e encerrado com codigo 1 para
que o NSSM reinicie o servico automaticamente.
"""

import asyncio
import logging
import os
import time

WATCHDOG_LOGGER_NAME = "app.watchdog"

logger = logging.getLogger(WATCHDOG_LOGGER_NAME)


class ActivityTracker:
    """Registra o momento da ultima atividade observada."""

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._last_activity = clock()

    def touch(self):
        """Marca atividade no momento atual."""
        self._last_activity = self._clock()

    def seconds_inactive(self):
        """Segundos desde a ultima atividade."""
        return self._clock() - self._last_activity


class ActivityLoggingHandler(logging.Handler):
    """Handler que marca atividade a cada log emitido.

    Ignora logs do proprio watchdog para evitar auto-alimentacao.
    """

    def __init__(self, tracker):
        super().__init__()
        self._tracker = tracker

    def emit(self, record):
        if record.name == WATCHDOG_LOGGER_NAME:
            return
        self._tracker.touch()


def _default_on_timeout():
    """Encerra o processo para o NSSM reiniciar o servico."""
    logger.critical(
        "Watchdog: nenhuma atividade dentro do timeout. "
        "Encerrando processo para reinicio pelo NSSM."
    )
    os._exit(1)


async def watchdog_loop(tracker, timeout_seconds, check_interval_seconds, on_timeout=None):
    """Encerra o processo quando o bot ficar sem atividade por tempo demais.

    Args:
        tracker: ActivityTracker com o estado de atividade.
        timeout_seconds: inatividade maxima tolerada.
        check_interval_seconds: intervalo entre verificacoes.
        on_timeout: callback opcional (testes). Default encerra o processo.
    """
    if on_timeout is None:
        on_timeout = _default_on_timeout
    while True:
        await asyncio.sleep(check_interval_seconds)
        if tracker.seconds_inactive() >= timeout_seconds:
            on_timeout()
            return
