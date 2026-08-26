"""
Testes para o módulo watchdog.
"""

import asyncio
import logging

from unittest.mock import MagicMock

from app.services.watchdog import (
    WATCHDOG_LOGGER_NAME,
    ActivityLoggingHandler,
    ActivityTracker,
    _default_on_timeout,
    watchdog_loop,
)


class TestActivityTracker:
    """Testes do rastreador de atividade."""

    def test_nova_instancia_tem_inatividade_zero(self):
        tracker = ActivityTracker()
        assert tracker.seconds_inactive() < 0.1

    def test_seconds_inactive_cresce_com_tempo(self):
        now = [0.0]
        tracker = ActivityTracker(clock=lambda: now[0])
        now[0] = 12.5
        assert tracker.seconds_inactive() == 12.5

    def test_touch_zera_inatividade(self):
        now = [0.0]
        tracker = ActivityTracker(clock=lambda: now[0])
        now[0] = 30.0
        tracker.touch()
        assert tracker.seconds_inactive() == 0.0


class TestActivityLoggingHandler:
    """Testes do handler que converte logs em atividade."""

    def _record(self, name):
        return logging.LogRecord(name, logging.INFO, __file__, 1, "msg", None, None)

    def test_log_externo_marca_atividade(self):
        now = [0.0]
        tracker = ActivityTracker(clock=lambda: now[0])
        handler = ActivityLoggingHandler(tracker)
        now[0] = 10.0
        handler.emit(self._record("telethon.client.updates"))
        assert tracker.seconds_inactive() == 0.0

    def test_log_do_watchdog_nao_marca_atividade(self):
        now = [0.0]
        tracker = ActivityTracker(clock=lambda: now[0])
        handler = ActivityLoggingHandler(tracker)
        now[0] = 10.0
        handler.emit(self._record(WATCHDOG_LOGGER_NAME))
        assert tracker.seconds_inactive() == 10.0


class TestWatchdogLoop:
    """Testes do loop assíncrono do watchdog."""

    def test_dispara_ao_exceder_timeout(self):
        on_timeout = MagicMock()

        async def run():
            tracker = ActivityTracker()
            await asyncio.wait_for(
                watchdog_loop(
                    tracker,
                    timeout_seconds=0.05,
                    check_interval_seconds=0.02,
                    on_timeout=on_timeout,
                ),
                timeout=2.0,
            )

        asyncio.run(run())
        on_timeout.assert_called_once()

    def test_nao_dispara_com_atividade_recente(self):
        on_timeout = MagicMock()

        async def run():
            tracker = ActivityTracker()
            task = asyncio.create_task(
                watchdog_loop(
                    tracker,
                    timeout_seconds=5.0,
                    check_interval_seconds=0.02,
                    on_timeout=on_timeout,
                )
            )
            done, pending = await asyncio.wait({task}, timeout=0.2)
            for t in pending:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            return done

        done = asyncio.run(run())
        assert done == set()
        on_timeout.assert_not_called()


class TestDefaultOnTimeout:
    """Testes do comportamento padrão de timeout."""

    def test_encerra_processo_com_codigo_1(self, monkeypatch):
        exit_mock = MagicMock()
        monkeypatch.setattr("app.services.watchdog.os._exit", exit_mock)
        _default_on_timeout()
        exit_mock.assert_called_once_with(1)
