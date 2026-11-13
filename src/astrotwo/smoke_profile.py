# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Prova di fumo della finestra Profili **dentro l'app costruita** (D62-2, decisione del proprietario del 2026-11-13).

Specifica: ``mdfiles/60-distribuzione-dmg.md`` (§3.8, controllo V10, e §7). L'eseguibile dell'app la esegue con
``AstroTwo --smoke-profile CARTELLA`` (``app_bundle.main``), dove ``CARTELLA`` contiene le risposte vere registrate dei
servizi (``index.json`` e i file: ``tests/analysis/data/profile`` del repository, **fuori dall'app**). Nessuna rete:
un server HTTP locale su 127.0.0.1 risponde al posto di SIMBAD, archivio Gaia, IRSA, NASA Exoplanet Archive, VizieR
(una SED sintetica di un punto), MocServer e tile HiPS; ``scripts/build_app.py`` la lancia con
``QT_QPA_PLATFORM=offscreen``, una HOME temporanea e un proxy verso una porta chiusa per tutto il resto.

Fa ciò che fa l'utente: apre la finestra Profili con un profilo **completo** di 51 Peg (cinque sezioni), aspetta che
tutte le sezioni arrivino («Done»), controlla che **Export…** e **Load SED points as catalog** siano attivi, poi
esporta ECSV, PDF e PNG della SED e carica i punti della SED come catalogo (comandi registrati, come dal menu).
Ogni eccezione Python non gestita durante la prova (anche dentro uno slot di Qt, dove non ferma il programma: il caso
di D62-2) fa fallire la prova. Questo modulo non calcola nulla di scientifico.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

#: Bersaglio della prova: 51 Peg ha risposte registrate per tutte e cinque le sezioni.
TARGET = "51 Peg"
SECTIONS = ("identity", "images", "astrometry", "photometry", "planets")
#: Voci dell'elenco dei server (14) dirette al server locale → percorso.
_TAP = {"cds-simbad-tap": "simbad", "esa-gaia-tap": "gaia", "nasa-exoplanet-tap": "exoplanet",
        "nasa-irsa-tap": "irsa"}
#: Survey delle miniature (12) → percorso registrato dei tile.
_SURVEYS = {"CDS/P/DSS2/color": "skies.esac.esa.int/DSSColor", "CDS/P/2MASS/color": "skies.esac.esa.int/2MASSColor",
            "CDS/P/allWISE/color": "skies.esac.esa.int/AllWISEColor"}
#: SED sintetica di VizieR (un punto 2MASS Ks alla posizione di 51 Peg): basta che la serie arrivi.
_VIZIER_SED = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><INFO name="QUERY_STATUS" value="OK"/>
<TABLE><FIELD name="_RAJ2000" datatype="double" unit="deg"/><FIELD name="_DEJ2000" datatype="double" unit="deg"/>
<FIELD name="_tabname" datatype="char" arraysize="*"/><FIELD name="_ID" datatype="char" arraysize="*"/>
<FIELD name="_sed_freq" datatype="double" unit="GHz"/><FIELD name="_sed_flux" datatype="float" unit="Jy"/>
<FIELD name="_sed_eflux" datatype="float" unit="Jy"/><FIELD name="_sed_filter" datatype="char" arraysize="*"/>
<DATA><TABLEDATA>
<TR><TD>344.3666</TD><TD>20.7688</TD><TD>II/246/out</TD><TD>2MASS=1</TD><TD>136.89e+3</TD><TD>17.5</TD><TD>0.3</TD><TD>2MASS:Ks</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>"""


class RecordedServer:
    """Server locale con le risposte registrate (stessa forma di ``tests/analysis/profile_fakes.py``)."""

    def __init__(self, data: Path) -> None:
        self.data = Path(data)
        self.index = json.loads((self.data / "index.json").read_text(encoding="utf-8"))
        self.missing: list[str] = []
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:
                pass

            def _serve(self) -> None:
                parsed = urllib.parse.urlsplit(self.path)
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                params = dict(urllib.parse.parse_qsl(parsed.query))
                if self.headers.get("Content-Type", "").startswith("application/x-www-form"):
                    params.update(urllib.parse.parse_qsl(body.decode()))
                status, ctype, payload = owner.answer(parsed.path, params)
                payload = payload.encode() if isinstance(payload, str) else payload
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = _serve  # noqa: N815 - nomi di http.server

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def _file(self, key: str):
        if key not in self.index:
            self.missing.append(key)
            return 400, "text/plain", f"risposta non registrata: {key}"
        return 200, "application/x-votable+xml", (self.data / self.index[key]["file"]).read_bytes()

    def answer(self, path: str, params: dict) -> tuple[int, str, bytes | str]:
        if path.startswith("/hips/"):
            key = "hips|" + path.removeprefix("/hips/")
            status, _, payload = self._file(key)
            return status, "text/plain" if key.endswith("properties") else "image/jpeg", payload
        if path == "/mocserver":
            survey = _SURVEYS.get(params.get("ID", ""))
            records = [] if survey is None else [{"ID": params["ID"], "dataproduct_type": "image",
                                                  "hips_service_url": f"{self.url}/hips/{survey}"}]
            return 200, "application/json", json.dumps(records)
        if path == "/vizier/sed":
            return 200, "application/x-votable+xml", _VIZIER_SED
        if path == "/irsa/SCS":
            return self._file("irsa-scs|" + "&".join(f"{k}={v}" for k, v in sorted(params.items())))
        for service in _TAP.values():
            if path == f"/{service}/sync":
                return self._file(f"{service}|{params.get('QUERY', '')}")
        self.missing.append(path)
        return 404, "text/plain", f"percorso sconosciuto: {path}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


def _redirect_services(server: RecordedServer) -> None:
    """Indirizzi dei servizi del profilo verso il server locale (come la fixture ``services`` dei test)."""
    import dataclasses

    import astrotwo.analysis.object_profile as op
    import astrotwo.core.hips as hips
    import astrotwo.core.vo_protocols as vo

    vo.BUILTIN_SERVERS = tuple(dataclasses.replace(e, url=f"{server.url}/{_TAP[e.id]}") if e.id in _TAP else e
                               for e in vo.BUILTIN_SERVERS)
    vo.VIZIER_PHOTOMETRY_URL = f"{server.url}/vizier/sed"
    vo.MOCSERVER_URL = f"{server.url}/mocserver"
    op._IRSA_SCS = f"{server.url}/irsa/SCS"
    hips.MIRROR_FALLBACKS = {}  # nessun mirror: il MocServer locale risponde


def _wait(app, condition, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.processEvents()
        if condition():
            return True
        time.sleep(0.02)
    app.processEvents()
    return condition()


def run(data: Path, *, timeout: float = 120.0) -> dict:
    """Esegue la prova; rapporto ``{"ok", "checks": [{"name", "ok", "detail"}], "errors", "missing"}``."""
    errors: list[str] = []
    checks: list[dict] = []

    def check(name: str, ok: bool, detail: object = None) -> bool:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        return bool(ok)

    def hook(kind, value, tb) -> None:  # eccezione in uno slot di Qt o nel thread principale
        errors.append("".join(traceback.format_exception(kind, value, tb))[-3000:])

    def thread_hook(args) -> None:
        errors.append("".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_traceback))[-3000:])

    previous, previous_thread = sys.excepthook, threading.excepthook
    sys.excepthook, threading.excepthook = hook, thread_hook
    server = RecordedServer(Path(data))
    work = Path(tempfile.mkdtemp(prefix="astrotwo-smoke-"))
    try:
        _redirect_services(server)
        from PySide6.QtCore import QSettings
        from PySide6.QtWidgets import QApplication

        from astrotwo.core.commands import default_registry
        from astrotwo.ui.main_window import MainWindow, ThreadCache, register_analysis_commands

        app = QApplication.instance() or QApplication([sys.argv[0] if sys.argv else "AstroTwo"])
        check("qt_platform", True, app.platformName())
        settings = QSettings(str(work / "settings.ini"), QSettings.Format.IniFormat)
        registry = default_registry(cache=ThreadCache(root=work / "cache"))
        register_analysis_commands(registry)
        window = MainWindow(registry=registry, settings=settings, startup_commands=False)
        window.confirm = lambda title, text: True
        modals: list = []
        window.show_modal = lambda title, text: modals.append([title, text])
        window.auto_column_dialogs = False
        window.resize(1000, 700)
        window.show()
        tab = window.open_profile({"name": TARGET})
        finished = _wait(app, lambda: not window.busy() and tab.state in ("done", "cancelled", "error"), timeout)
        states = {name: view.state for name, view in tab.views.items()}
        check("profile_finished", finished and tab.state == "done", {"tab": tab.state, "status": tab.status.text()})
        check("all_sections_done", list(states) == list(SECTIONS) and set(states.values()) == {"done"}, states)
        check("sed_plot", tab.views["photometry"].findChild(object, "sedPlot") is not None)
        check("export_enabled", tab.export_button.isEnabled())
        check("load_sed_enabled", tab.catalog_button.isEnabled())
        out = work / "exports"
        out.mkdir()
        for fmt, name in (("ecsv", "51peg.ecsv"), ("pdf", "51peg.pdf"), ("sed_png", "51peg-sed.png")):
            tab.export(fmt, str(out / name))
            done = _wait(app, lambda: not window.busy(), timeout)
            path = out / name
            check(f"export_{fmt}", done and path.is_file() and path.stat().st_size > 0,
                  {"bytes": path.stat().st_size if path.is_file() else None})
        window.profiles.sed_folder = work / "Profiles"
        layers_before = len(window.session.workspace.state.layers)
        tab.load_sed_catalog()
        loaded = _wait(app, lambda: not window.busy() and len(window.session.workspace.state.layers) > layers_before,
                       timeout)
        layer = window.session.workspace.state.layers[-1] if loaded else None
        check("load_sed_catalog", loaded and layer is not None and layer.kind == "catalog",
              None if layer is None else layer.name)
        check("no_error_windows", not modals, modals)
        window.profiles.close()
        window.confirm = lambda title, text: True
        window.close()
        app.processEvents()
    except Exception:  # noqa: BLE001 - qualsiasi errore è un fallimento della prova, con il motivo
        errors.append(traceback.format_exc()[-3000:])
    finally:
        sys.excepthook, threading.excepthook = previous, previous_thread
        server.close()
    check("no_unhandled_exceptions", not errors, errors)
    check("no_unrecorded_requests", not server.missing, server.missing)
    return {"ok": all(c["ok"] for c in checks), "target": TARGET, "checks": checks, "errors": errors,
            "missing": server.missing, "work": str(work)}


def main(data: str) -> int:
    """Rapporto JSON sullo standard output; uscita 0 solo se la prova è riuscita."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    report = run(Path(data))
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report["ok"] else 1
