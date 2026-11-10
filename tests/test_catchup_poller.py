"""
Testes do catch-up (varredura de segurança dos grupos monitorados).

Cobre: prime marca o topo sem reprocessar histórico, só mensagens mais novas
que o cursor são processadas, mensagem sem texto é ignorada, o que o push já
tratou não é repetido e uma falha de rede não mata o loop.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.catchup_poller import CatchupPoller


def _chat(chat_id=-100123, title="promotop", username="promotop"):
    return MagicMock(id=chat_id, title=title, username=username)


def _message(msg_id, text="iPhone por R$ 1500 https://loja.com/x", chat=None):
    chat = chat or _chat()
    message = MagicMock()
    message.id = msg_id
    message.message = text
    message.get_chat = AsyncMock(return_value=chat)
    return message


def _client(by_group):
    client = MagicMock()

    async def get_messages(group, limit=20):
        value = by_group.get(group, [])
        if isinstance(value, Exception):
            raise value
        return value

    client.get_messages = get_messages
    return client


@pytest.fixture
def handler():
    handler = MagicMock()
    handler.was_processed = MagicMock(return_value=False)
    handler.process_message = AsyncMock()
    return handler


@pytest.fixture
def state():
    return {"grupos": ["promotop"], "alertas": ["iphone"], "forward_to": 1}


def _poller(client, handler, state, **kwargs):
    return CatchupPoller(
        client,
        handler,
        MagicMock(state=state),
        interval=0,
        prime_delay=0,
        **kwargs,
    )


def _run(coro):
    return asyncio.run(coro)


class TestScanGroup:
    def test_prime_marks_top_without_processing(self, handler, state):
        client = _client({"promotop": [_message(500)]})
        poller = _poller(client, handler, state)

        _run(poller.prime())

        assert poller._cursor["promotop"] == 500
        handler.process_message.assert_not_called()

    def test_processes_only_newer_than_cursor_in_order(self, handler, state):
        client = _client(
            {"promotop": [_message(503), _message(502), _message(500)]}
        )
        poller = _poller(client, handler, state)
        poller._cursor["promotop"] = 500

        processed = _run(poller.scan_group("promotop"))

        assert processed == 2
        ids = [call.args[0].id for call in handler.process_message.await_args_list]
        assert ids == [502, 503]
        assert poller._cursor["promotop"] == 503

    def test_empty_or_textless_messages_are_ignored(self, handler, state):
        client = _client(
            {"promotop": [_message(502, text=None), _message(501, text="  ")]}
        )
        poller = _poller(client, handler, state)
        poller._cursor["promotop"] = 500

        assert _run(poller.scan_group("promotop")) == 0
        handler.process_message.assert_not_called()

    def test_skips_messages_already_handled_by_push(self, handler, state):
        client = _client({"promotop": [_message(502), _message(501)]})
        poller = _poller(client, handler, state)
        poller._cursor["promotop"] = 500
        handler.was_processed.side_effect = lambda chat_id, msg_id: msg_id == 501

        assert _run(poller.scan_group("promotop")) == 1
        handled = [call.args[0].id for call in handler.process_message.await_args_list]
        assert handled == [502]

    def test_unknown_group_starts_from_top(self, handler, state):
        client = _client({"promotop": [_message(700)]})
        poller = _poller(client, handler, state)

        assert _run(poller.scan_group("promotop")) == 0
        assert poller._cursor["promotop"] == 700


class TestResolveTarget:
    def test_numeric_channel_id_becomes_peer_id(self):
        assert CatchupPoller._resolve_target("1007742949") == -1001007742949

    def test_username_is_kept_as_is(self):
        assert CatchupPoller._resolve_target("achadinhosnapromoo") == "achadinhosnapromoo"

    def test_int_is_kept_as_is(self):
        assert CatchupPoller._resolve_target(-100123) == -100123


class TestRunLoop:
    def test_network_failure_does_not_kill_the_loop(self, handler, state):
        client = _client({"promotop": RuntimeError("boom")})
        poller = _poller(client, handler, state)

        async def scenario():
            task = asyncio.create_task(poller.run())
            await asyncio.sleep(0.05)
            assert not task.done(), "a excecao derrubou o loop de catch-up"
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        _run(scenario())
