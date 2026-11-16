# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Impronte SHA-256 dei file di dati esportati da un **caso fisso**, senza rete (D65-10, sprint W2).

Specifica: ``mdfiles/65-windows-linux.md`` (§3.7, T9). I file di dati scritti da AstroTwo (CSV, ECSV, VOTable del 14,
sottoinsieme VOTable del 13, MOC FITS/JSON/testo del 16, ECSV dei valori e VOTable della SED del 25, file di sessione del 05)
devono avere **gli stessi byte** su macOS, Windows e Linux. Questo script li scrive in una cartella temporanea da un
caso fisso e stampa (o scrive con ``--output``) un JSON ``{"files": {nome: sha256}, "sizes": {...}, "system": ...}``.

Caso fisso: le Pleiadi in un VOTable scritto qui (testi non ASCII: η, Å, °), il profilo di 51 Peg di
``tests/data/fingerprint_profile.json`` (risposte registrate dei servizi), provenienza fissa (origine
``pleiadi.xml``, non il percorso assoluto della cartella temporanea, che cambia da un sistema all'altro) e un **orologio
fisso** al posto di ``datetime.now`` nei moduli che scrivono la data dell'esportazione (``A2EXPORT``, ``A2SAVED``,
``saved_at``…): è la «data fissa» di T9. Nessun valore scientifico viene calcolato qui: le esportazioni sono quelle
dell'app, chiamate con le loro funzioni pubbliche. PNG e PDF non ci sono (D65-10: stesso contenuto, non stessi byte).

Uso: ``uv run python scripts/export_fingerprints.py [--output impronte.json]``; confronto tra sistemi:
``… --compare macos.json windows.json linux.json`` (uscita 1 se un file è diverso). Il workflow ``tests`` lo esegue sui tre
sistemi e confronta le impronte (job ``fingerprints``); ``tests/test_export_fingerprints.py`` le confronta con
``tests/data/export_fingerprints.json``.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import json
import platform
import sys
import tempfile
import warnings
from datetime import UTC, datetime
from pathlib import Path
from unittest import mock

#: Istante fisso di tutte le date scritte nei file (T9).
FIXED_NOW = datetime(2026, 11, 16, 12, 0, 0, tzinfo=UTC)

VOTABLE = """<?xml version="1.0" encoding="UTF-8"?>
<VOTABLE version="1.4" xmlns="http://www.ivoa.net/xml/VOTable/v1.3">
<RESOURCE type="results"><COOSYS ID="s" system="ICRS" epoch="J2016.0"/>
<TABLE name="pleiadi">
<FIELD name="ra" datatype="double" unit="deg" ucd="pos.eq.ra;meta.main" ref="s"/>
<FIELD name="dec" datatype="double" unit="deg" ucd="pos.eq.dec;meta.main" ref="s"/>
<FIELD name="vmag" datatype="float" unit="mag" ucd="phot.mag;em.opt.V"/>
<FIELD name="name" datatype="char" arraysize="*"><DESCRIPTION>Nome (Ångström, 5′, 10°)</DESCRIPTION></FIELD>
<DATA><TABLEDATA>
<TR><TD>56.75095833</TD><TD>24.10513889</TD><TD>2.87</TD><TD>Alcyone η Tau</TD></TR>
<TR><TD>56.58155833</TD><TD>23.94834722</TD><TD>4.18</TD><TD>Merope 23 Tau</TD></TR>
<TR><TD>57.29059583</TD><TD>24.05341389</TD><TD>3.62</TD><TD>Atlas 27 Tau</TD></TR>
<TR><TD>56.21890000</TD><TD>24.11333611</TD><TD>3.70</TD><TD>Electra 17 Tau</TD></TR>
</TABLEDATA></DATA></TABLE></RESOURCE></VOTABLE>
"""

#: Forma JSON unita (``merge_profile_results``) del profilo di 51 Peg ottenuto dalle risposte registrate dei servizi
#: (``tests/analysis/data/profile``, gli stessi dati della prova di fumo V10), senza la sezione Immagini (miniature,
#: non esportate in ECSV): dati fissi, nessuna rete.
PROFILE_FILE = Path(__file__).resolve().parent.parent / "tests" / "data" / "fingerprint_profile.json"


class _FixedDatetime(datetime):
    """``datetime`` con ``now`` fisso (:data:`FIXED_NOW`); il resto invariato."""

    @classmethod
    def now(cls, tz=None):
        return FIXED_NOW if tz is None else FIXED_NOW.astimezone(tz)


@contextlib.contextmanager
def fixed_clock():
    """Orologio fisso nei moduli che scrivono date nei file esportati."""
    from astrotwo.core import calculators, catalogs, commands, vo_protocols

    with contextlib.ExitStack() as stack:
        for module in (calculators, catalogs, commands, vo_protocols):
            stack.enter_context(mock.patch.object(module, "datetime", _FixedDatetime))
        yield


def _catalog(folder: Path):
    from astrotwo.core.catalogs import read_table

    path = folder / "pleiadi.xml"
    path.write_bytes(VOTABLE.encode("utf-8"))
    table = read_table(path)
    # provenienza fissa: il percorso assoluto della cartella temporanea cambia da un sistema all'altro
    return dataclasses.replace(table, source="pleiadi.xml", origin="pleiadi.xml", retrieved_at=FIXED_NOW,
                               file_modified=FIXED_NOW)


def write_case(folder: Path) -> dict[str, Path]:
    """Scrive tutti i file del caso fisso in ``folder``; nome → percorso."""
    from astrotwo.analysis.profile_export import export_profile
    from astrotwo.core.catalogs import save_subset
    from astrotwo.core.commands import Command, RequestedBy, Session, default_registry
    from astrotwo.core.moc import build_moc, write_moc
    from astrotwo.core.vo_protocols import export_table

    out = folder / "out"
    out.mkdir()
    files: dict[str, Path] = {}
    with fixed_clock(), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        table = _catalog(folder)
        for fmt, name in (("csv", "catalog.csv"), ("ecsv", "catalog.ecsv"), ("votable", "catalog.xml")):
            files[name] = export_table(table, out / name, fmt).path
        files["subset.xml"] = save_subset(table, [True, False, True, False], out / "subset.xml")
        moc = build_moc([table], order_max=10)
        for fmt, name in (("fits", "moc.fits"), ("json", "moc.json"), ("ascii", "moc.txt")):
            files[name] = write_moc(moc, out / name, fmt).path
        profile = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        for fmt, name in (("ecsv", "profile.ecsv"), ("sed_votable", "sed.xml")):
            files[name] = export_profile(profile, out / name, fmt).path
        session = Session(default_registry(cache=None))
        session.created_at = FIXED_NOW.isoformat()
        session.run(Command("calc.convert_units", 1, {"value": 5007.0, "from_unit": "Angstrom", "to_unit": "nm"},
                            RequestedBy("menu")))  # un numero float64 scritto in JSON: stessa forma ovunque
        session.save(out / "session.astrotwo", app_version="fingerprint")
        files["session.astrotwo"] = out / "session.astrotwo"
    return files


def fingerprints() -> dict:
    with tempfile.TemporaryDirectory(prefix="astrotwo-fingerprints-") as tmp:
        files = write_case(Path(tmp))
        data = {name: path.read_bytes() for name, path in sorted(files.items())}
    return {"system": platform.system(), "files": {n: hashlib.sha256(b).hexdigest() for n, b in data.items()},
            "sizes": {n: len(b) for n, b in data.items()}}


def compare(paths: list[Path]) -> list[str]:
    """Differenze tra i JSON delle impronte di più sistemi: una riga per file diverso o mancante (vuota = uguali)."""
    runs = {}
    for path in paths:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        runs[f"{data.get('system', '?')} ({Path(path).name})"] = data["files"]
    names = sorted(set().union(*(set(files) for files in runs.values())))
    problems = []
    for name in names:
        values = {run: files.get(name, "mancante") for run, files in runs.items()}
        if len(set(values.values())) != 1:
            problems.append(f"{name}: " + ", ".join(f"{run} {value[:12]}" for run, value in sorted(values.items())))
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, help="file JSON delle impronte (altrimenti sullo schermo)")
    parser.add_argument("--compare", type=Path, nargs="+", metavar="JSON",
                        help="confronta i JSON delle impronte di più sistemi: uscita 1 se un file è diverso")
    args = parser.parse_args(argv)
    if args.compare:
        if len(args.compare) < 2:
            parser.error("--compare vuole almeno due file")
        problems = compare(args.compare)
        for line in problems:
            print(f"DIVERSO {line}")
        print(f"{len(args.compare)} sistemi: " + ("impronte uguali" if not problems else f"{len(problems)} file diversi"))
        return 1 if problems else 0
    text = json.dumps(fingerprints(), indent=1, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_bytes(text.encode("utf-8"))
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
