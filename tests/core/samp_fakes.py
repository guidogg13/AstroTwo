# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Hub e client SAMP simulati per i test del 14 e del 40 (sprint B1b, 2026-11-05).

Riproducono ciò che si è visto con TOPCAT 4.10-8 vero (hub JSAMP) il 2026-11-05:

- l'hub di TOPCAT si chiama ``hub`` (quello di ``pyvo`` ``cli#hub``) e i client ``c1``, ``c2``…;
- TOPCAT carica una tabella in differita (``ControlWindow.runLoading``) e, se il messaggio è una chiamata, risponde
  solo a caricamento finito; un ``table-id`` già ricevuto → errore "Duplicate table-id: table '…' has already been
  received";
- ``table.select.rowList``: tabella cercata per ``table-id`` (tra quelle ricevute via SAMP), poi per URL; non trovata →
  errore "No table with table-id=… or url=… is loaded"; trovata → subset con il nome del mittente (sostituisce quello
  con lo stesso nome), righe da 0 come arrivano;
- con una notifica gli errori restano muti (nessuna risposta), come per TOPCAT.
"""

from __future__ import annotations

import threading
import time

import pyvo.samp as pyvo_samp

from astrotwo.core.vo_protocols import SAMP_MTYPES


def ok_reply(client, msg_id) -> None:
    if msg_id is not None:
        client.reply(msg_id, {"samp.status": pyvo_samp.SAMP_STATUS_OK, "samp.result": {}})


def error_reply(client, msg_id, text: str) -> None:
    if msg_id is not None:
        client.reply(msg_id, {"samp.status": pyvo_samp.SAMP_STATUS_ERROR, "samp.error": {"samp.errortxt": text}})


def bind_recorder(client, received: list) -> None:
    """Client "di prima" (DS9 e simili): registra ogni messaggio dei tre tipi e risponde ``samp.ok`` alle chiamate."""
    def note(private_key, sender_id, msg_id, mtype, params, extra):
        received.append((private_key, sender_id, msg_id, mtype, params, extra))
        ok_reply(client, msg_id)

    for mtype in SAMP_MTYPES:
        client.bind_receive_notification(mtype, note)
        client.bind_receive_call(mtype, note)


class JsampLikeHub(pyvo_samp.SAMPHubServer):
    """Hub di ``pyvo`` con gli identificativi dell'hub di TOPCAT (JSAMP): ``hub`` per sé, ``c<n>`` per i client."""

    def _get_new_ids(self):
        key, public = super()._get_new_ids()
        return key, "hub" if public == "cli#hub" else public.replace("cli#", "c")


class TopcatLike:
    """Client SAMP che si comporta come TOPCAT 4.10-8 per i tre tipi di AstroTwo (vedi la docstring del modulo)."""

    def __init__(self, name: str = "topcat", load_delay: float = 0.4) -> None:
        self.load_delay = load_delay
        self.client = pyvo_samp.SAMPIntegratedClient(name=name, metadata={"samp.name": name})
        self.client.connect()
        self.tables: list[dict] = []  # come la finestra delle tabelle di TOPCAT: id, url, subsets
        self.by_id: dict[str, dict] = {}
        self.errors: list[str] = []  # anche quelli muti (notifiche)
        self.points: list[dict] = []
        self.lock = threading.Lock()
        for mtype, function in (("table.load.votable", self._load), ("table.select.rowList", self._select),
                                ("coord.pointAt.sky", self._point)):
            self.client.bind_receive_notification(mtype, function)
            self.client.bind_receive_call(mtype, function)

    @property
    def id(self) -> str:
        return self.client.get_public_id()

    def disconnect(self) -> None:
        if self.client.is_connected:
            self.client.disconnect()

    def _fail(self, msg_id, text: str) -> None:
        with self.lock:
            self.errors.append(text)
        error_reply(self.client, msg_id, text)

    def _load(self, private_key, sender_id, msg_id, mtype, params, extra) -> None:
        table_id = params.get("table-id")
        with self.lock:
            duplicate = table_id is not None and table_id in self.by_id
        if duplicate:
            self._fail(msg_id, f"Duplicate table-id: table '{table_id}' has already been received")
            return

        def later() -> None:  # caricamento in differita; la risposta solo a caricamento finito
            time.sleep(self.load_delay)
            entry = {"index": 0, "table_id": table_id, "url": params["url"], "name": params.get("name"),
                     "subsets": {}}
            with self.lock:
                entry["index"] = len(self.tables) + 1
                self.tables.append(entry)
                if table_id is not None:
                    self.by_id[table_id] = entry
            ok_reply(self.client, msg_id)

        threading.Thread(target=later, daemon=True).start()

    def _select(self, private_key, sender_id, msg_id, mtype, params, extra) -> None:
        table_id, url = params.get("table-id"), params.get("url")
        with self.lock:
            entry = self.by_id.get(table_id) or next((t for t in self.tables if t["url"] == url), None)
        if entry is None:
            self._fail(msg_id, f"No table with table-id={table_id} or url={url} is loaded")
            return
        name = self.client.get_metadata(sender_id).get("samp.name") or "samp"
        with self.lock:
            entry["subsets"][name] = [int(r) for r in params["row-list"]]
        ok_reply(self.client, msg_id)

    def _point(self, private_key, sender_id, msg_id, mtype, params, extra) -> None:
        with self.lock:
            self.points.append(dict(params))
        ok_reply(self.client, msg_id)


def dead_client(name: str = "morto"):
    """Client registrato sull'hub ma non più in ascolto (programma chiuso male): l'hub non lo raggiunge più."""
    client = pyvo_samp.SAMPIntegratedClient(name=name, metadata={"samp.name": name})
    client.connect()
    bind_recorder(client, [])
    client.client.stop()  # il server XML-RPC del client si ferma, la registrazione resta
    return client
