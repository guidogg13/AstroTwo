# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Turno della CPU del 14 (``mdfiles/14-core-protocolli-vo.md`` §7, T29; sprint C4 per il profilo del 25 §3.12)."""

from __future__ import annotations

import threading
import time

import astrotwo.core.vo_protocols as vo
from astrotwo.core.cache import NETWORK_TIMEOUTS


def test_t29_turn_is_left_while_waiting_for_the_answer(service):
    service.routes["/slow"] = lambda request: (time.sleep(0.5), (200, "text/plain", "ok"))[1]
    turn = threading.Lock()
    inside = {"now": 0, "max": 0}
    guard = threading.Lock()
    worked_during_wait = threading.Event()
    waiting = threading.Event()

    def work(seconds: float) -> None:
        with guard:
            inside["now"] += 1
            inside["max"] = max(inside["max"], inside["now"])
        time.sleep(seconds)  # lavoro di CPU simulato, con il turno
        with guard:
            inside["now"] -= 1

    def first() -> None:
        with vo.cpu_turn(turn):
            work(0.05)
            waiting.set()
            response = vo._Session(NETWORK_TIMEOUTS).get(f"{service.url}/slow")  # turno lasciato qui
            assert response.text == "ok"
            work(0.05)

    def second() -> None:
        waiting.wait(5)
        with vo.cpu_turn(turn):
            work(0.05)
            worked_during_wait.set()

    threads = [threading.Thread(target=first), threading.Thread(target=second)]
    started = time.monotonic()
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert worked_during_wait.is_set()
    assert inside["max"] == 1  # mai due thread insieme fuori dalle richieste
    assert time.monotonic() - started < 1.0  # il secondo ha lavorato durante l'attesa del primo (0,5 s)


def test_t29_network_wait_without_a_turn_does_nothing():
    with vo.network_wait():
        pass
    lock = threading.Lock()
    with vo.cpu_turn(lock):
        assert lock.locked()
        with vo.network_wait():
            assert not lock.locked()
        assert lock.locked()
    assert not lock.locked()
