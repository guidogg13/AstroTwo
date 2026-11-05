# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Collegamento SAMP dell'interfaccia (40 §3.12, sprint B1, decisioni del proprietario del 2026-11-05).

Il protocollo è del 14 (``SampHub`` con ``pyvo.samp``); qui ci sono soltanto:

- **tempo massimo** di ogni chiamata all'hub (le chiamate XML-RPC di ``pyvo`` non ne hanno): la chiamata gira in un
  thread proprio e, oltre ``timeout`` secondi, si abbandona con ``SAMP_UNAVAILABLE`` (``timeout``);
- **ricezione portata al thread principale**: le funzioni di ricezione girano nei thread del server XML-RPC di
  ``pyvo``, non toccano mai Qt ed emettono segnali (consegnati in coda al thread principale, dove vive l'oggetto);
- **tabelle note** (mandate da AstroTwo o ricevute via SAMP) → livello, per le selezioni ricevute;
- copia locale dei VOTable ricevuti (``save_votable`` del 14), che la finestra apre con ``catalog.open_file``;
- **identificativo delle tabelle inviate** ``astrotwo-<avvio>-<livello>-<n>`` (sprint B1b): ``<avvio>`` è casuale per
  ogni ``SampLink`` (ogni avvio della finestra), perché TOPCAT rifiuta un ``table-id`` già ricevuto e ``<livello>-<n>``
  ripartono a ogni avvio;
- **esito di ogni destinatario** (14 §3 punto 7): chi rifiuta o non risponde va in ``rejected`` del risultato.

Nessun calcolo: le posizioni le converte il 14 (con il 10), le tabelle le scrive e le legge il 13/14.
"""

from __future__ import annotations

import itertools
import secrets
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from astrotwo.core.cache import NETWORK_TIMEOUTS
from astrotwo.core.vo_protocols import (
    SAMP_TABLE_REPLY_TIMEOUT,
    SampClient,
    SampHub,
    SampSelection,
    VoProtocolsError,
)

#: Tempo massimo di una chiamata all'hub e della risposta dei destinatari (D40-9 (2)): il tempo di connessione del 04.
DEFAULT_TIMEOUT = float(NETWORK_TIMEOUTS.connect)
#: Tempo di risposta per ``table.load.votable`` (D40-9 (7), decisa dal proprietario il 2026-11-05).
DEFAULT_TABLE_TIMEOUT = float(SAMP_TABLE_REPLY_TIMEOUT)


def default_received_dir() -> Path:
    """Cartella dei VOTable ricevuti (D40-9): mai cancellati da AstroTwo, servono per riaprire le sessioni."""
    return Path.home() / "Library" / "Application Support" / "AstroTwo" / "SAMP" / "received"


@dataclass(frozen=True)
class SampStatus:
    connected: bool
    own_hub: bool
    clients: tuple[SampClient, ...] = ()  # solo i programmi: mai l'hub né AstroTwo (sprint B1b)
    hub_name: str | None = None  # nome dichiarato dall'hub, mostrato a parte nel suggerimento


@dataclass(frozen=True)
class ReceivedTable:
    path: Path
    table_id: str
    name: str | None
    url: str
    sender_id: str
    sender: str | None


@dataclass(frozen=True)
class ReceivedSelection:
    layer: str
    rows: tuple[int, ...]
    table_id: str
    sender_id: str
    sender: str | None


@dataclass(frozen=True)
class ReceivedPoint:
    ra_deg: float  # gradi ICRS come nel messaggio (epoca non dichiarata da SAMP)
    dec_deg: float
    sender_id: str
    sender: str | None


class SampLink(QObject):
    """``SampHub`` del 14 per la finestra: stato, elenco dei client, invio con tempo massimo, ricezione in segnali."""

    status_changed = Signal(object)  # SampStatus
    table_received = Signal(object)  # ReceivedTable
    selection_received = Signal(object)  # ReceivedSelection
    point_received = Signal(object)  # ReceivedPoint
    notice = Signal(object, bool)  # eccezione con codice e params, errore sì/no (pannello Messaggi)

    def __init__(self, received_dir: Path | None = None, *, timeout: float = DEFAULT_TIMEOUT,
                 table_timeout: float = DEFAULT_TABLE_TIMEOUT, hub_factory: Callable[..., SampHub] = SampHub,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.received_dir = Path(received_dir) if received_dir is not None else default_received_dir()
        self.timeout = float(timeout)
        self.table_timeout = float(table_timeout)
        self.hub_factory = hub_factory
        self._hub: SampHub | None = None
        self._lock = threading.RLock()
        self._clients: tuple[SampClient, ...] = ()
        self._hub_name: str | None = None
        self.launch = secrets.token_hex(4)  # <avvio> degli identificativi delle tabelle inviate (sprint B1b)
        self._known: dict[str, str] = {}  # table-id o URL → livello
        self._sent: dict[str, tuple[str, str]] = {}  # livello → (table-id, URL) da usare per le selezioni
        self._tables = itertools.count(1)
        self._files = itertools.count(1)

    # --- stato -------------------------------------------------------------------------------------------------

    @property
    def status(self) -> SampStatus:
        with self._lock:
            hub = self._hub
            return SampStatus(hub is not None, bool(hub is not None and hub.own_hub), self._clients,
                              self._hub_name if hub is not None else None)

    @property
    def connected(self) -> bool:
        return self.status.connected

    def _emit_status(self) -> None:
        self.status_changed.emit(self.status)

    def _require(self) -> SampHub:
        with self._lock:
            hub = self._hub
        if hub is None:
            raise VoProtocolsError("SAMP_UNAVAILABLE", "non collegato a un hub SAMP: chiamare connect()",
                                   params={"reason": "not_connected"})
        return hub

    def reply_timeout(self, mtype: str) -> float:
        """Tempo di risposta di ogni destinatario per ``mtype`` (D40-9 (7)): 60 s per le tabelle, 10 s per il resto."""
        return self.table_timeout if mtype == "table.load.votable" else self.timeout

    def _timed(self, operation: str, function: Callable, margin: float = 0.0, wait: float | None = None):
        """``function()`` in un thread proprio; oltre ``timeout`` s ``SAMP_UNAVAILABLE`` (``timeout``), mai un'attesa
        senza fine: chi chiama (thread dei comandi) torna libero e l'interfaccia non aspetta mai l'hub. ``wait`` e
        ``margin``: per gli invii, che aspettano già al più ``wait`` s la risposta di ogni destinatario (14 §3 punto 7;
        ``wait`` = ``reply_timeout`` del tipo di messaggio)."""
        seconds = self.timeout if wait is None else wait
        limit = seconds + margin
        box: dict[str, object] = {}
        done = threading.Event()

        def run() -> None:
            try:
                box["value"] = function()
            except BaseException as exc:  # noqa: BLE001 - riportata al chiamante
                box["error"] = exc
            finally:
                done.set()

        threading.Thread(target=run, name=f"astrotwo-samp-{operation}", daemon=True).start()
        if not done.wait(limit):
            raise VoProtocolsError("SAMP_UNAVAILABLE", f"l'hub SAMP non ha risposto entro {seconds:g} s "
                                   f"({operation}): operazione abbandonata",
                                   params={"reason": "timeout", "operation": operation, "seconds": seconds})
        if "error" in box:
            raise box["error"]  # type: ignore[misc]
        return box.get("value")

    # --- collegamento (thread dei comandi) ---------------------------------------------------------------------

    def connect(self) -> dict:
        """Hub già attivo se c'è, altrimenti hub proprio con profilo web spento (14); già collegato: stato attuale."""
        with self._lock:
            hub = self._hub
        if hub is not None:
            return self._connect_values(hub)
        hub = self.hub_factory(name="AstroTwo", web_profile=False)
        hub.on_table_reference(lambda ref, sender, h=hub: self._receive_table(h, ref, sender))
        hub.on_selection(lambda sel, sender, h=hub: self._receive_selection(h, sel, sender))
        hub.on_point(lambda pos, sender, h=hub: self._receive_point(h, pos, sender))
        hub.on_hub_event(lambda mtype, params, h=hub: self._hub_event(h, mtype, params))
        abandoned = threading.Event()

        def attempt():
            hub.connect()
            if abandoned.is_set():  # arrivato dopo il tempo massimo: si chiude subito
                hub.disconnect()
                return None
            return hub.clients(), self._read_hub_name(hub)

        try:
            clients, hub_name = self._timed("connect", attempt)
        except VoProtocolsError as exc:
            if exc.params.get("reason") == "timeout":
                abandoned.set()
            raise
        with self._lock:
            self._hub, self._clients, self._hub_name = hub, tuple(clients), hub_name
        self._emit_status()
        return self._connect_values(hub)

    @staticmethod
    def _read_hub_name(hub: SampHub) -> str | None:
        try:
            return None if hub.hub_id is None else hub.client_name(hub.hub_id)
        except Exception:  # noqa: BLE001 - nome facoltativo
            return None

    def _connect_values(self, hub: SampHub) -> dict:
        return {"hub": "own" if hub.own_hub else "external", "web_profile": bool(hub.web_profile),
                "clients": [{"id": c.id, "name": c.name} for c in self.status.clients]}

    def disconnect(self) -> dict:
        """Scollega; l'hub di AstroTwo si spegne (file di blocco tolto), con un hub altrui ci si scollega e basta."""
        with self._lock:
            hub, self._hub, self._clients, self._hub_name = self._hub, None, (), None
            self._sent.clear()
        if hub is None:
            return {"was_connected": False, "own_hub_stopped": False}
        own = hub.own_hub
        self._emit_status()
        self._timed("disconnect", hub.disconnect)
        return {"was_connected": True, "own_hub_stopped": bool(own)}

    def shutdown(self) -> None:
        """Alla chiusura della finestra: come ``disconnect``, senza errori (al più il tempo massimo)."""
        try:
            self.disconnect()
        except Exception:  # noqa: BLE001 - la finestra si chiude comunque
            pass

    def refresh_clients(self) -> None:
        """Rilegge l'elenco dei client in un thread proprio (eventi dell'hub); poi ``status_changed``."""
        with self._lock:
            hub = self._hub
        if hub is None:
            return

        def run() -> None:
            try:
                clients, hub_name = self._timed("clients", lambda: (hub.clients(), self._read_hub_name(hub)))
            except Exception:  # noqa: BLE001 - l'elenco resta quello di prima
                return
            with self._lock:
                if self._hub is not hub:
                    return
                self._clients, self._hub_name = tuple(clients), hub_name
            self._emit_status()

        threading.Thread(target=run, name="astrotwo-samp-refresh", daemon=True).start()

    # --- invio (thread dei comandi) ----------------------------------------------------------------------------

    def _rejected(self, sent) -> list[dict]:
        """Destinatari falliti del 14 in forma JSON, con il nome dichiarato (testo esterno) quando c'è."""
        out = []
        for failure in sent.failures:
            name = None
            for client in self.status.clients:
                if client.id == failure.id:
                    name = client.name
            out.append({"id": failure.id, "name": name, "reason": failure.reason, "detail": failure.detail,
                        "mtype": sent.mtype})
        return out

    def send_table(self, layer, recipient: str | None = None) -> dict:
        hub = self._require()
        table_id = f"astrotwo-{self.launch}-{layer.id}-{next(self._tables)}"
        wait = self.reply_timeout("table.load.votable")
        sent = self._timed("send", lambda: hub.send_table(layer.data, table_id=table_id, name=layer.name,
                                                          recipient=recipient, timeout=wait),
                           margin=2.0, wait=wait)
        url = str(sent.params["url"])
        with self._lock:
            self._known[table_id] = self._known[url] = layer.id
            self._sent[layer.id] = (table_id, url)
        return {"layer": layer.id, "table_id": table_id, "url": url, "name": layer.name,
                "rows": len(layer.data.table), "recipients": list(sent.recipients),
                "rejected": self._rejected(sent)}

    def send_selection(self, layer, recipient: str | None = None) -> dict:
        """Righe selezionate; tabella mai passata da SAMP → prima la tabella (D40-9 (4)) e la selezione solo a chi ha
        risposto di averla caricata. Una tabella già passata da SAMP non si rimanda mai (sprint B1b)."""
        hub = self._require()
        with self._lock:
            ref = self._sent.get(layer.id)
        table_sent = ref is None
        rejected: list[dict] = []
        among = None
        if ref is None:
            values = self.send_table(layer, recipient)
            ref = (values["table_id"], values["url"])
            rejected, among = list(values["rejected"]), values["recipients"]
        rows = tuple(sorted(int(r) for r in layer.selection))  # ordine della tabella, non quello mostrato (§3.12)
        sent = self._timed("send", lambda: hub.send_selection(SampSelection(ref[0], ref[1], rows), recipient,
                                                              among=among, timeout=self.timeout), margin=2.0)
        return {"layer": layer.id, "table_id": ref[0], "url": ref[1], "rows": list(rows), "table_sent": table_sent,
                "recipients": list(sent.recipients), "rejected": rejected + self._rejected(sent)}

    def point_at(self, position, recipient: str | None = None) -> dict:
        hub = self._require()
        sent = self._timed("send", lambda: hub.send_point(position, recipient, timeout=self.timeout), margin=2.0)
        return {"ra": {"value": float(sent.params["ra"]), "unit": "deg"},
                "dec": {"value": float(sent.params["dec"]), "unit": "deg"}, "frame": "icrs",
                "recipients": list(sent.recipients), "rejected": self._rejected(sent)}

    # --- tabelle note ------------------------------------------------------------------------------------------

    def remember(self, layer_id: str, table_id: str, url: str) -> None:
        """Tabella ricevuta via SAMP e aperta come ``layer_id``: le selezioni del mittente la ritrovano."""
        with self._lock:
            if table_id:
                self._known[table_id] = layer_id
            self._known[url] = layer_id
            self._sent[layer_id] = (table_id or url, url)

    def keep_layers(self, layer_ids) -> None:
        """Dimentica le tabelle dei livelli rimossi."""
        alive = set(layer_ids)
        with self._lock:
            self._known = {k: v for k, v in self._known.items() if v in alive}
            self._sent = {k: v for k, v in self._sent.items() if k in alive}

    def layer_for(self, table_id: str, url: str) -> str | None:
        with self._lock:
            return self._known.get(table_id) or self._known.get(url)

    # --- ricezione (thread di pyvo: mai Qt, solo segnali) -------------------------------------------------------

    def _sender_name(self, hub: SampHub, sender_id: str) -> str | None:
        for client in self.status.clients:
            if client.id == sender_id and client.name is not None:
                return client.name
        try:
            return hub.client_name(sender_id)
        except Exception:  # noqa: BLE001 - nome facoltativo
            return None

    def _receive_table(self, hub: SampHub, ref, sender_id: str) -> None:
        try:
            self.received_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            path = self.received_dir / f"{stamp}-{next(self._files)}.xml"
            while path.exists():
                path = self.received_dir / f"{stamp}-{next(self._files)}.xml"
            SampHub.save_votable(ref.url, path)
        except Exception as exc:
            self.notice.emit(exc, True)
            raise  # risposta d'errore al mittente (14)
        self.table_received.emit(ReceivedTable(path, ref.table_id, ref.name, ref.url, str(sender_id),
                                               self._sender_name(hub, sender_id)))

    def _receive_selection(self, hub: SampHub, selection: SampSelection, sender_id: str) -> None:
        layer = self.layer_for(selection.table_id, selection.url)
        sender = self._sender_name(hub, sender_id)
        if layer is None:
            exc = VoProtocolsError("SAMP_TABLE_UNKNOWN", f"selezione da {sender or sender_id} per la tabella "
                                   f"{selection.table_id!r} ({selection.url}): tabella non nota, nessuna riga "
                                   "selezionata", params={"reason": "unknown", "table_id": selection.table_id,
                                                          "url": selection.url, "sender": sender or sender_id})
            self.notice.emit(exc, True)
            raise exc
        self.selection_received.emit(ReceivedSelection(layer, tuple(selection.rows), selection.table_id,
                                                       str(sender_id), sender))

    def _receive_point(self, hub: SampHub, position, sender_id: str) -> None:
        import astropy.units as u

        ra = float(position.lon.to_value(u.deg))
        dec = float(position.lat.to_value(u.deg))
        self.point_received.emit(ReceivedPoint(ra, dec, str(sender_id), self._sender_name(hub, sender_id)))

    def _hub_event(self, hub: SampHub, mtype: str, params) -> None:
        with self._lock:
            current = self._hub is hub
        if not current:
            return
        if mtype == "samp.hub.event.shutdown":
            with self._lock:
                self._hub, self._clients, self._hub_name = None, (), None
                self._sent.clear()
            self._emit_status()
            self.notice.emit(VoProtocolsError("SAMP_UNAVAILABLE", "l'hub SAMP si è spento: AstroTwo non è più "
                                              "collegato", params={"reason": "hub_shutdown"}), False)
            threading.Thread(target=self._drop, args=(hub,), name="astrotwo-samp-drop", daemon=True).start()
            return
        self.refresh_clients()

    def _drop(self, hub: SampHub) -> None:
        try:
            self._timed("disconnect", hub.disconnect)
        except Exception:  # noqa: BLE001 - l'hub non c'è più
            pass
