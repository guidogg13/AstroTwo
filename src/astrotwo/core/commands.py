# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Registro dei comandi e sessione (livello 1, file generale come il 04).

Specifica: ``mdfiles/05-comandi-sessione.md`` (stato ``approvato``).

Ogni azione dell'interfaccia e ogni richiesta dell'IA diventa un **comando** con nome stabile, versione,
parametri tipizzati con unità (forme JSON del §3.1, D05-4) e risultato strutturato; il registro chiama solo
le funzioni pubbliche dei moduli 04, 10–19 e ne riporta risultati, avvisi ed errori invariati (regola d'oro
n. 1: il 05 non calcola). La sessione salva i comandi, i file con SHA-256 e lo stato finale, mai pixel né
segreti, e si riapre rieseguendo i comandi (regola d'oro n. 6).

Il modulo non usa Qt e non crea thread: coda e thread di lavoro sono del 40 (§3.2).
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import json
import math
import os
import re
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import astropy.units as u
import numpy as np
from astropy.time import Time

__all__ = [
    "PARAMETER_TYPES",
    "COMMAND_CLASSES",
    "REQUESTED_BY_SOURCES",
    "SESSION_SCHEMA_VERSION",
    "SESSION_EXTENSION",
    "CommandError",
    "ParameterSpec",
    "CommandSpec",
    "RequestedBy",
    "Command",
    "ResultMessage",
    "CommandResult",
    "ProgressReport",
    "CancelToken",
    "Layer",
    "ViewState",
    "WorkspaceState",
    "Workspace",
    "ExecutionContext",
    "Outcome",
    "CommandRegistry",
    "HistoryEntry",
    "CommandHistory",
    "ReplayReport",
    "Session",
    "default_registry",
]

#: Elenco chiuso dei tipi dei parametri (§3.1; ``record`` dal 2026-10-17, D05-4).
PARAMETER_TYPES = ("quantity", "sky_position", "pixel_position", "time", "file", "url", "layer_ref", "enum",
                   "number", "integer", "boolean", "string", "list", "record")
#: Classi dei comandi (D05-1).
COMMAND_CLASSES = ("session", "passive", "application")
#: Valori di ``requested_by`` (scelta minore 1 del 2026-10-16).
REQUESTED_BY_SOURCES = ("menu", "keyboard", "mouse", "history", "session", "ai")
#: Versione dello schema del file di sessione (§3.4).
SESSION_SCHEMA_VERSION = 1
#: Estensione del file di sessione (scelta minore 1 del 2026-10-15).
SESSION_EXTENSION = ".astrotwo.json"

#: Unità di riferimento delle grandezze fisiche dichiarabili per un ``quantity`` (equivalenza con astropy).
PHYSICAL_TYPES: dict[str, u.UnitBase] = {
    "angle": u.deg,
    "angular velocity": u.mas / u.yr,
    "length": u.m,
    "frequency": u.Hz,
    "speed": u.km / u.s,
    "time": u.s,
}
_TIME_FORMATS = ("isot", "jd", "mjd", "jyear", "byear")
_TIME_SCALES = ("utc", "tai", "tt", "tdb", "tcb", "tcg", "ut1")
_LAYER_ID = re.compile(r"L[1-9]\d*")
_NAME = re.compile(r"[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*")


def _now() -> str:
    """Istante UTC in ISO 8601 (DC1)."""
    return datetime.now(UTC).isoformat()


class _Required:
    def __repr__(self) -> str:
        return "REQUIRED"


#: Segnaposto: parametro obbligatorio (nessun default).
REQUIRED = _Required()


class CommandError(Exception):
    """Errore del registro o della sessione con l'identificatore della specifica (§10)."""

    def __init__(self, code: str, message: str, *, params: Mapping[str, object] | None = None,
                 **details: object) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.params = dict(params or {})  # valori JSON del messaggio (D40-3); il testo resta del modulo
        self.details = details


def _invalid(where: str, reason: str, message: str, /, **params: object) -> CommandError:
    """``COMMAND_PARAMETER_INVALID`` per il parametro ``where``: ``reason`` sceglie la sotto-voce del catalogo (§10.1)."""
    return CommandError("COMMAND_PARAMETER_INVALID", f"{where}: {message}",
                        params={"reason": reason, "parameter": where, **params}, parameter=where)


def _given(value: object) -> str:
    """Valore ricevuto, in JSON così com'è (per i messaggi: nessuna riformattazione)."""
    return json.dumps(value, ensure_ascii=False, default=str)


def _nested(code: str, text: str, params: Mapping[str, object] | None = None) -> dict:
    """Messaggio annidato (D40-7): codice, ``params`` e testo originale."""
    return {"code": code, "params": _json_params(params), "text": text}


def _nested_items(items) -> list[dict]:
    """Avvisi dei moduli (coppie codice/testo con ``params`` facoltativi) come elenco di messaggi annidati."""
    return [_nested(str(i[0]), str(i[1]), i[2] if len(i) == 3 else getattr(i, "params", None)) for i in items]


# --------------------------------------------------------------------------
# Definizioni dei parametri e dei comandi (§3.1)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ParameterSpec:
    """Definizione di un parametro (o di un campo di un ``record``, D05-4).

    ``default``: ``REQUIRED`` (obbligatorio), ``None`` (facoltativo, ``null`` quando manca) o un valore nella
    forma JSON del tipo, risolto alla registrazione. ``minimum``/``maximum``: per ``number``/``integer`` nel
    numero stesso, per ``quantity`` in ``range_unit``. ``note``: precisazione mostrata con la descrizione (es.
    "nell'unità dell'immagine (BUNIT)").
    """

    name: str
    type: str
    description_en: str
    description_it: str
    default: object = REQUIRED
    physical_type: str | tuple[str, ...] | None = None
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: bool = False
    range_unit: str | None = None
    choices: tuple[str, ...] = ()
    item: ParameterSpec | None = None
    fields: tuple[ParameterSpec, ...] = ()
    max_items: int | None = None
    layer_kinds: tuple[str, ...] = ()
    note: str | None = None

    def __post_init__(self) -> None:
        if self.type not in PARAMETER_TYPES:
            raise ValueError(f"tipo {self.type!r} fuori dall'elenco chiuso {PARAMETER_TYPES}")
        if self.type == "quantity":
            kinds = (self.physical_type,) if isinstance(self.physical_type, str) else self.physical_type
            if not kinds or any(k not in PHYSICAL_TYPES for k in kinds):
                raise ValueError(f"{self.name}: quantity con grandezza fisica dichiarata ({tuple(PHYSICAL_TYPES)})")
        if self.type == "enum" and not self.choices:
            raise ValueError(f"{self.name}: enum senza elenco")
        if self.type == "list" and self.item is None:
            raise ValueError(f"{self.name}: list senza tipo degli elementi")
        if self.type == "record" and not self.fields:
            raise ValueError(f"{self.name}: record senza campi")

    @property
    def required(self) -> bool:
        return self.default is REQUIRED

    @property
    def physical_types(self) -> tuple[str, ...]:
        if self.physical_type is None:
            return ()
        return (self.physical_type,) if isinstance(self.physical_type, str) else tuple(self.physical_type)


def P(name: str, type: str, en: str, it: str, **kw) -> ParameterSpec:  # noqa: N802 - forma compatta
    return ParameterSpec(name, type, en, it, **kw)


@dataclass(frozen=True)
class CommandSpec:
    """Definizione di un comando (§3.1): nome stabile, versione, funzioni chiamate, parametri, indicatori.

    ``executor``: funzione ``(ctx, params) -> Outcome`` che chiama solo funzioni pubbliche dei moduli; ``None``
    per i comandi la cui esecuzione appartiene all'interfaccia (``bound_by``: disegno del 41, impostazioni del
    40), collegata con ``CommandRegistry.bind``.
    """

    name: str
    version: int
    description_en: str
    description_it: str
    functions: tuple[str, ...]
    parameters: tuple[ParameterSpec, ...]
    command_class: str
    executor: Callable | None = None
    network: bool = False
    long: bool = False
    changes_view: bool = False
    read_only: bool = False
    confirm: bool = False
    bound_by: str | None = None
    steps: int | None = None  # passi dichiarati (avanzamento n di m); None = indeterminato

    def __post_init__(self) -> None:
        if not _NAME.fullmatch(self.name):
            raise ValueError(f"nome {self.name!r}: forma dominio.verbo_oggetto in minuscolo")
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 1:
            raise ValueError("versione: intero ≥ 1")
        if self.command_class not in COMMAND_CLASSES:
            raise ValueError(f"classe {self.command_class!r} non in {COMMAND_CLASSES}")
        names = [p.name for p in self.parameters]
        if len(set(names)) != len(names):
            raise ValueError(f"{self.name}: parametri ripetuti")

    def parameter(self, name: str) -> ParameterSpec:
        for p in self.parameters:
            if p.name == name:
                return p
        raise KeyError(name)


# --------------------------------------------------------------------------
# Forme JSON e validazione dei valori (§3.1, D05-4)
# --------------------------------------------------------------------------


def _unit(text: object, path: str) -> u.UnitBase:
    """Unità nel formato FITS o, se non valida lì, VOUnit (D18-2)."""
    if not isinstance(text, str) or not text.strip():
        raise _invalid(path, "unit_missing", "unità mancante: un numero per una grandezza con unità non si accetta senza "
                       "unità")
    for fmt in ("fits", "vounit"):
        try:
            return u.Unit(text, format=fmt)
        except ValueError:
            continue
    raise _invalid(path, "unit_invalid", f"unità {text!r} non valida in FITS né in VOUnit (D18-2)", unit=text)


def _finite_number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise _invalid(path, "not_finite", f"serve un numero finito, non {value!r}", given=_given(value))
    return float(value)


def _check_range(number: float, spec: ParameterSpec, path: str, shown: str, given: Mapping | None = None) -> None:
    """Intervallo del parametro; ``given``: la grandezza ricevuta (``{value, unit}``) se il parametro ne è una."""

    def out(reason: str, op: str, limit: float) -> CommandError:
        suffix = f" {spec.range_unit}" if spec.range_unit else ""
        if given is not None:
            return _invalid(path, reason + "_quantity", f"{shown} fuori intervallo: serve {op} {limit!r}{suffix}",
                            value=dict(given), limit={"value": limit, "unit": spec.range_unit})
        return _invalid(path, reason, f"{shown} fuori intervallo: serve {op} {limit!r}{suffix}",
                        value=number, limit=limit)

    if spec.minimum is not None:
        if number < spec.minimum or (spec.exclusive_minimum and number == spec.minimum):
            raise out("not_above_minimum" if spec.exclusive_minimum else "below_minimum",
                      ">" if spec.exclusive_minimum else "≥", spec.minimum)
    if spec.maximum is not None and number > spec.maximum:
        raise out("above_maximum", "≤", spec.maximum)


def _check_time(value: object, path: str) -> object:
    """Tempo del §3.1: ``"J…"``/``"B…"`` oppure ``{value, format, scale}`` con la scala sempre scritta."""
    if value is None:
        return None
    if isinstance(value, str):
        if value[:1] not in ("J", "B"):
            raise _invalid(path, "epoch_form", f"epoca {value!r}: 'J…'/'B…' oppure {{value, format, scale}}",
                           given=_given(value))
        try:
            Time(value)
        except ValueError as exc:
            raise _invalid(path, "epoch_unreadable", f"epoca {value!r} non leggibile ({exc})", given=_given(value),
                           detail=str(exc)) from exc
        return value
    if not isinstance(value, Mapping) or set(value) != {"value", "format", "scale"}:
        raise _invalid(path, "time_form", "tempo: 'J…'/'B…' oppure {value, format, scale} (scala sempre scritta, DC1)")
    if value["format"] not in _TIME_FORMATS:
        raise _invalid(path, "time_format_unknown", f"formato del tempo {value['format']!r} non in {_TIME_FORMATS}",
                       given=_given(value["format"]), allowed=list(_TIME_FORMATS))
    if value["scale"] not in _TIME_SCALES:
        raise _invalid(path, "time_scale_unknown", f"scala {value['scale']!r} non in {_TIME_SCALES}",
                       given=_given(value["scale"]), allowed=list(_TIME_SCALES))
    raw = value["value"]
    pair = value["format"] == "jd" and isinstance(raw, list) and len(raw) == 2
    if pair:
        for k, part in enumerate(raw):
            _finite_number(part, f"{path}.value[{k}]")
    elif value["format"] == "isot":
        if not isinstance(raw, str):
            raise _invalid(path, "time_isot_text", "tempo isot: testo ISO 8601")
    else:
        _finite_number(raw, f"{path}.value")
    return {"value": list(raw) if pair else raw, "format": value["format"], "scale": value["scale"]}


def _time_value(value: object) -> Time | str | None:
    """Tempo del §3.1 in oggetto ``Time`` (o testo ``J…``/``B…``, letto dal 10)."""
    if value is None or isinstance(value, str):
        return value
    raw = value["value"]
    if value["format"] == "jd" and isinstance(raw, list):
        return Time(float(raw[0]), float(raw[1]), format="jd", scale=value["scale"])
    return Time(raw, format=value["format"], scale=value["scale"])


def time_json(value: object) -> object:
    """Forma JSON di un tempo: epoca ``J…``/``B…`` come testo, altrimenti JD in due parti con la scala."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, Time):
        if value.format in ("jyear_str", "byear_str"):
            return str(value.value)
        return {"value": [float(value.jd1), float(value.jd2)], "format": "jd", "scale": value.scale}
    raise TypeError(f"tempo {value!r}: Time o epoca 'J…'/'B…'")


def time_text(value: object) -> str | None:
    """Tempo scritto per l'interfaccia (DC1, correzione del proprietario del 2026-10-21): ISO 8601 con la scala
    (millesimi solo se non nulli), epoche ``J…``/``B…`` come sono; mai il JD, che resta interno."""
    if value is None or isinstance(value, str):
        return value
    t = _time_value(value) if isinstance(value, Mapping) else value
    if isinstance(t, str):
        return t
    if not isinstance(t, Time):
        raise TypeError(f"tempo {value!r}: Time, epoca 'J…'/'B…' o forma JSON del §3.1")
    if t.format in ("jyear_str", "byear_str"):
        return str(t.value)
    text = t.isot
    return f"{text[:-4] if text.endswith('.000') else text} {t.scale.upper()}"


def quantity_json(q) -> dict | None:
    """Forma JSON di una ``Quantity`` scalare: ``{"value", "unit"}`` con l'unità in FITS o VOUnit."""
    if q is None:
        return None
    q = u.Quantity(q)
    for fmt in ("fits", "vounit"):
        try:
            text = q.unit.to_string(fmt)
            break
        except (ValueError, u.UnitsError):
            continue
    else:
        q = q.to(u.deg) if q.unit.is_equivalent(u.deg) else q.decompose()
        text = q.unit.to_string("fits")
    return {"value": float(q.value), "unit": text}


def sky_json(point) -> dict:
    """Forma JSON di uno ``SkyFrame`` del 10 (§3.1): epoca scritta sempre, valore o ``null`` con il motivo."""
    from astrotwo.core.coordinates_wcs import SkyFrame
    from astropy.coordinates import SkyCoord

    if isinstance(point, SkyCoord):
        point = SkyFrame(coord=point)
    frame = point.coord.frame
    sph = point.coord.spherical
    attrs = frame.frame_attributes
    return {"lon": quantity_json(u.Quantity(sph.lon)), "lat": quantity_json(u.Quantity(sph.lat)),
            "frame": frame.name,
            "equinox": time_json(frame.equinox) if "equinox" in attrs else None,
            "obstime": time_json(frame.obstime) if "obstime" in attrs and frame.obstime is not None else None,
            "epoch": time_json(point.epoch),
            "epoch_reason": None if point.epoch is not None else "epoca delle posizioni non nota (non assunta)"}


def _sha256(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def _normalize(spec: ParameterSpec, value: object, path: str, ws: WorkspaceState | None, *,
               hash_files: bool = True) -> object:
    """Valida un valore nella forma JSON del suo tipo e restituisce la forma registrata (default risolti).

    Controlli di §3.2: tipo, unità convertibile nella grandezza dichiarata, intervallo, elenco chiuso, file
    esistente e leggibile (SHA-256 e dimensione calcolati qui, §3.4), livello esistente (``LAYER_UNKNOWN``).
    """
    if value is None:
        if spec.required:
            raise _invalid(path, "required", "parametro obbligatorio mancante")
        return None
    t = spec.type
    if t == "quantity":
        if not isinstance(value, Mapping) or set(value) != {"value", "unit"}:
            raise _invalid(path, "quantity_form", 'serve {"value": numero, "unit": "unità"}: un numero puro non basta per '
                           "una grandezza con unità")
        number = _finite_number(value["value"], f"{path}.value")
        unit = _unit(value["unit"], f"{path}.unit")
        refs = [PHYSICAL_TYPES[k] for k in spec.physical_types]
        if not any(unit.is_equivalent(ref) for ref in refs):
            raise _invalid(path, "unit_not_convertible", f"unità {value['unit']!r} ({unit.physical_type}) non "
                           f"convertibile in {' o '.join(spec.physical_types)}", unit=value["unit"],
                           physical_type=str(unit.physical_type), expected=list(spec.physical_types))
        if spec.minimum is not None or spec.maximum is not None:
            _check_range(float((number * unit).to_value(u.Unit(spec.range_unit))), spec, path,
                         f"{number!r} {value['unit']}", {"value": number, "unit": value["unit"]})
        return {"value": number, "unit": value["unit"]}
    if t == "sky_position":
        keys = {"lon", "lat", "frame", "equinox", "obstime", "epoch", "epoch_reason"}
        if not isinstance(value, Mapping) or not {"lon", "lat", "frame"} <= set(value) or set(value) - keys:
            raise _invalid(path, "position_form", f"posizione: oggetto con {sorted(keys)}", keys=sorted(keys))
        angle = ParameterSpec("lon", "quantity", "", "", physical_type="angle")
        out = {"lon": _normalize(angle, value["lon"], f"{path}.lon", ws),
               "lat": _normalize(angle, value["lat"], f"{path}.lat", ws)}
        if not isinstance(value["frame"], str) or not value["frame"]:
            raise _invalid(f"{path}.frame", "frame_name", "nome del frame di astropy.coordinates")
        out["frame"] = value["frame"]
        for key in ("equinox", "obstime", "epoch"):
            out[key] = _check_time(value.get(key), f"{path}.{key}")
        reason = value.get("epoch_reason")
        if out["epoch"] is None and (not isinstance(reason, str) or not reason.strip()):
            raise _invalid(f"{path}.epoch", "epoch_reason_missing", "epoca null senza motivo (epoch_reason): l'epoca "
                           "non si assume mai (D10-2)")
        out["epoch_reason"] = reason if out["epoch"] is None else None
        return out
    if t == "time":
        return _check_time(value, path)
    if t == "pixel_position":
        if not isinstance(value, Mapping) or set(value) != {"x", "y", "convention"}:
            raise _invalid(path, "pixel_form", 'serve {"x", "y", "convention"}')
        if value["convention"] != "numpy":
            raise _invalid(f"{path}.convention", "pixel_convention", "nel comando registrato la convenzione è sempre numpy "
                           "(DC7)")
        return {"x": _finite_number(value["x"], f"{path}.x"), "y": _finite_number(value["y"], f"{path}.y"),
                "convention": "numpy"}
    if t == "file":
        if not isinstance(value, Mapping) or "path" not in value or set(value) - {"path", "sha256", "size"}:
            raise _invalid(path, "file_form", 'serve {"path": percorso assoluto}')
        target = value["path"]
        if not isinstance(target, str) or not os.path.isabs(target):
            raise _invalid(path, "path_not_absolute", f"percorso assoluto, non {target!r}", path=_given(target))
        p = Path(target)
        if not p.is_file() or not os.access(p, os.R_OK):
            raise _invalid(path, "file_unreadable", f"file {target!r} inesistente o non leggibile", path=target)
        if not hash_files:
            return dict(value)
        sha, size = _sha256(p)
        return {"path": target, "sha256": sha, "size": size}
    if t == "url":
        if not isinstance(value, str) or not re.match(r"https?://", value):
            raise _invalid(path, "url_form", f"indirizzo http(s), non {value!r}", given=_given(value))
        return value
    if t == "layer_ref":
        if not isinstance(value, str) or not _LAYER_ID.fullmatch(value):
            raise _invalid(path, "layer_form", f"identificativo di livello L<n>, non {value!r}", given=_given(value))
        if ws is not None:
            layer = ws.find(value)
            if layer is None:
                raise CommandError("LAYER_UNKNOWN", f"{path}: livello {value} inesistente o rimosso",
                                   params={"reason": "in_parameter", "parameter": path, "layer": value},
                                   parameter=path)
            if spec.layer_kinds and layer.kind not in spec.layer_kinds:
                raise _invalid(path, "layer_kind", f"livello {value} di tipo {layer.kind}: serve "
                               f"{' o '.join(spec.layer_kinds)}", layer=value, kind=layer.kind,
                               expected=list(spec.layer_kinds))
        return value
    if t == "enum":
        if value not in spec.choices:
            raise _invalid(path, "choice", f"{value!r} non in {list(spec.choices)}", given=_given(value),
                       allowed=list(spec.choices))
        return value
    if t == "number":
        number = _finite_number(value, path)
        _check_range(number, spec, path, repr(number))
        return number
    if t == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            raise _invalid(path, "integer_required", f"serve un intero, non {value!r}", given=_given(value))
        _check_range(value, spec, path, repr(value))
        return value
    if t == "boolean":
        if not isinstance(value, bool):
            raise _invalid(path, "boolean_required", f"serve true o false, non {value!r}", given=_given(value))
        return value
    if t == "string":
        if not isinstance(value, str):
            raise _invalid(path, "string_required", f"serve un testo, non {value!r}", given=_given(value))
        return value
    if t == "list":
        if not isinstance(value, list):
            raise _invalid(path, "list_required", "serve una lista")
        if spec.max_items is not None and len(value) > spec.max_items:
            raise _invalid(path, "list_too_long", f"{len(value)} elementi, al più {spec.max_items}", count=len(value),
                           maximum=spec.max_items)
        return [_normalize(spec.item, v, f"{path}[{k}]", ws, hash_files=hash_files) for k, v in enumerate(value)]
    if t == "record":
        if not isinstance(value, Mapping):
            raise _invalid(path, "record_required", "serve un oggetto JSON (record)")
        names = {f.name for f in spec.fields}
        extra = sorted(set(value) - names)
        if extra:
            raise _invalid(f"{path}.{extra[0]}", "field_unknown", "campo non dichiarato nel record")
        return {f.name: _normalize(f, value.get(f.name, f.default if f.default is not REQUIRED else None),
                                   f"{path}.{f.name}", ws, hash_files=hash_files) for f in spec.fields}
    raise AssertionError(t)  # pragma: no cover - elenco chiuso


def _schema_for(spec: ParameterSpec) -> dict:
    """JSON Schema (draft 2020-12) di un parametro, con unità, grandezza, intervallo e default come annotazioni."""
    t = spec.type
    angle_q = {"type": "object", "properties": {"value": {"type": "number"}, "unit": {"type": "string"}},
               "required": ["value", "unit"], "additionalProperties": False}
    time_s = {"anyOf": [{"type": "string", "pattern": "^[JB]"},
                        {"type": "object", "properties": {
                            "value": {"anyOf": [{"type": "number"}, {"type": "string"},
                                                {"type": "array", "items": {"type": "number"}, "minItems": 2,
                                                 "maxItems": 2}]},
                            "format": {"enum": list(_TIME_FORMATS)}, "scale": {"enum": list(_TIME_SCALES)}},
                         "required": ["value", "format", "scale"], "additionalProperties": False},
                        {"type": "null"}]}
    if t == "quantity":
        s = dict(angle_q)
        s["x-physical-type"] = list(spec.physical_types)
        if spec.minimum is not None:
            s["x-minimum"] = spec.minimum
            s["x-exclusive-minimum"] = spec.exclusive_minimum
        if spec.maximum is not None:
            s["x-maximum"] = spec.maximum
        if spec.range_unit:
            s["x-range-unit"] = spec.range_unit
    elif t == "sky_position":
        s = {"type": "object", "properties": {
            "lon": angle_q, "lat": angle_q, "frame": {"type": "string"}, "equinox": time_s, "obstime": time_s,
            "epoch": time_s, "epoch_reason": {"type": ["string", "null"]}},
            "required": ["lon", "lat", "frame", "epoch", "epoch_reason"], "additionalProperties": False,
            "x-rule": "epoch null richiede epoch_reason (epoca mai assunta)"}
    elif t == "time":
        s = {"anyOf": [x for x in time_s["anyOf"] if x != {"type": "null"}]}
    elif t == "pixel_position":
        s = {"type": "object", "properties": {"x": {"type": "number"}, "y": {"type": "number"},
                                              "convention": {"const": "numpy"}},
             "required": ["x", "y", "convention"], "additionalProperties": False}
    elif t == "file":
        s = {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}
    elif t in ("url", "string"):
        s = {"type": "string"}
    elif t == "layer_ref":
        s = {"type": "string", "pattern": "^L[1-9][0-9]*$"}
        if spec.layer_kinds:
            s["x-layer-kinds"] = list(spec.layer_kinds)
    elif t == "enum":
        s = {"enum": list(spec.choices)}
    elif t in ("number", "integer"):
        s = {"type": t}
        if spec.minimum is not None:
            s["exclusiveMinimum" if spec.exclusive_minimum else "minimum"] = spec.minimum
        if spec.maximum is not None:
            s["maximum"] = spec.maximum
    elif t == "boolean":
        s = {"type": "boolean"}
    elif t == "list":
        s = {"type": "array", "items": _schema_for(spec.item)}
        if spec.max_items is not None:
            s["maxItems"] = spec.max_items
    else:  # record
        s = {"type": "object", "properties": {f.name: _schema_for(f) for f in spec.fields},
             "required": [f.name for f in spec.fields if f.required], "additionalProperties": False}
    s["description"] = spec.description_en + (f" ({spec.note})" if spec.note else "")
    if not spec.required:
        s["default"] = spec.default
        if spec.default is None and t not in ("sky_position",):
            s = {"anyOf": [s, {"type": "null"}], "default": None, "description": s["description"]}
    return s


# --------------------------------------------------------------------------
# Comandi, risultati, avanzamento, annullamento (§3.1, §3.2)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RequestedBy:
    """Chi ha chiesto il comando (§3.1): dato descrittivo, non cambia validazione, esecuzione né risultato."""

    source: str
    conversation: str | None = None
    turn: int | None = None
    call: str | None = None
    profile: str | None = None
    model: str | None = None

    def __post_init__(self) -> None:
        if self.source not in REQUESTED_BY_SOURCES:
            raise ValueError(f"requested_by {self.source!r} non in {REQUESTED_BY_SOURCES}")
        extra = (self.conversation, self.turn, self.call, self.profile, self.model)
        if self.source == "ai":
            if any(v is None for v in extra):
                raise ValueError("requested_by ai: servono conversazione, turno, chiamata, profilo e modello")
        elif any(v is not None for v in extra):
            raise ValueError("conversazione, turno, chiamata, profilo e modello solo per requested_by ai")

    def to_json(self) -> dict:
        out = {"source": self.source}
        if self.source == "ai":
            out.update(conversation=self.conversation, turn=self.turn, call=self.call, profile=self.profile,
                       model=self.model)
        return out

    @classmethod
    def from_json(cls, data: object) -> RequestedBy:
        if isinstance(data, str):
            return cls(data)
        if not isinstance(data, Mapping):
            raise ValueError("requested_by: oggetto JSON")
        return cls(**dict(data))


@dataclass(frozen=True)
class Command:
    """Un comando: nome, versione, parametri nella forma JSON del §3.1 e ``requested_by``.

    Dopo ``CommandRegistry.validate`` i parametri sono completi (default risolti, file con SHA-256).
    """

    name: str
    version: int
    parameters: Mapping[str, object]
    requested_by: RequestedBy = RequestedBy("menu")

    def to_json(self) -> dict:
        return {"name": self.name, "version": self.version, "parameters": copy.deepcopy(dict(self.parameters)),
                "requested_by": self.requested_by.to_json()}

    @classmethod
    def from_json(cls, data: Mapping) -> Command:
        if not isinstance(data, Mapping) or not {"name", "version", "parameters"} <= set(data):
            raise ValueError("comando: oggetto con name, version, parameters")
        return cls(name=data["name"], version=data["version"], parameters=copy.deepcopy(dict(data["parameters"])),
                   requested_by=RequestedBy.from_json(data.get("requested_by", "menu")))


@dataclass(frozen=True)
class ResultMessage:
    """Avviso o errore con codice e testo del modulo (mai riscritti dal 05)."""

    code: str
    text: str
    params: Mapping[str, object] = field(default_factory=dict)  # D40-3: valori JSON, {} se assenti

    def to_json(self) -> dict:
        out = {"code": self.code, "text": self.text}
        if self.params:  # facoltativo: le sessioni scritte prima di D40-3 restano identiche
            out["params"] = copy.deepcopy(dict(self.params))
        return out


@dataclass(frozen=True)
class CommandResult:
    """Risultato strutturato (§3.1): esito, valori con unità, avvisi, errore, provenienza, livelli, istanti."""

    status: str  # ok, error, cancelled
    values: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[ResultMessage, ...] = ()
    error: ResultMessage | None = None
    provenance: tuple[Mapping[str, object], ...] = ()
    layers_created: tuple[str, ...] = ()
    started_at: str = ""
    finished_at: str = ""
    network_fingerprint: tuple[Mapping[str, object], ...] = ()

    def to_json(self) -> dict:
        return {"status": self.status, "values": copy.deepcopy(dict(self.values)),
                "warnings": [w.to_json() for w in self.warnings],
                "error": None if self.error is None else self.error.to_json(),
                "provenance": [dict(p) for p in self.provenance], "layers_created": list(self.layers_created),
                "started_at": self.started_at, "finished_at": self.finished_at,
                "network_fingerprint": [dict(f) for f in self.network_fingerprint]}

    @classmethod
    def from_json(cls, data: Mapping) -> CommandResult:
        return cls(status=data["status"], values=data.get("values", {}),
                   warnings=tuple(ResultMessage(**w) for w in data.get("warnings", ())),
                   error=None if data.get("error") is None else ResultMessage(**data["error"]),
                   provenance=tuple(data.get("provenance", ())), layers_created=tuple(data.get("layers_created", ())),
                   started_at=data.get("started_at", ""), finished_at=data.get("finished_at", ""),
                   network_fingerprint=tuple(data.get("network_fingerprint", ())))


@dataclass(frozen=True)
class ProgressReport:
    """Avanzamento di un comando a più passi (passo n di m); ``total`` None = indeterminato."""

    step: int
    total: int | None
    text: str


class CancelToken:
    """Annullamento cooperativo (§3.2): il 05 lo controlla prima di iniziare e tra i passi."""

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()


# --------------------------------------------------------------------------
# Spazio di lavoro immutabile (§3.2)
# --------------------------------------------------------------------------

LAYER_KINDS = ("image", "hips", "catalog", "moc", "measure")


@dataclass(frozen=True)
class Layer:
    """Un livello: oggetto del modulo (``data``, mai salvato) e stato descrittivo (salvato nella sessione)."""

    id: str
    kind: str
    name: str
    data: object = field(compare=False, repr=False, default=None)
    visible: bool = True
    opacity: float = 1.0
    source: str = ""
    display: Mapping[str, object] | None = None  # immagine: vmin, vmax, stretch, palette, gamma
    style: Mapping[str, object] | None = None  # catalogo: forma, colore, dimensione
    columns: Mapping[str, object] | None = None  # catalogo: colonne di posizione e moto proprio confermate
    selection: tuple[int, ...] = ()
    sort: Mapping[str, object] | None = None  # catalogo: colonna e verso (ordine mostrato, 42)
    force_body: bool = False
    derived: Mapping[str, object] = field(compare=False, repr=False, default_factory=dict)  # piani di disegno

    def state_json(self) -> dict:
        return {"id": self.id, "kind": self.kind, "name": self.name, "visible": self.visible,
                "opacity": self.opacity, "source": self.source,
                "display": None if self.display is None else dict(self.display),
                "style": None if self.style is None else dict(self.style),
                "columns": None if self.columns is None else dict(self.columns),
                "selection": list(self.selection), "sort": None if self.sort is None else dict(self.sort),
                "force_body": self.force_body}


@dataclass(frozen=True)
class ViewState:
    """Vista: centro, scala (angolo per pixel della finestra), proiezione e base, finestra; geometria del 10."""

    center: object = None  # SkyFrame del 10
    scale: u.Quantity | None = None
    projection: str | None = None
    frame: str = "icrs"
    tangent_point: object = None  # SkyFrame del 10 (base creata)
    window: tuple[int, int] | None = None  # (larghezza, altezza) in pixel fisici
    base_layer: str | None = None  # immagine la cui WCS è la base
    geometry: object = field(default=None, compare=False, repr=False)  # ViewGeometry (ricalcolata, non salvata)
    grid_visible: bool = False
    grid_frame: str = "icrs"
    grid: object = field(default=None, compare=False, repr=False)  # GridLines del 10
    compass_visible: bool = True  # nord ed est (41 §3.18)
    scale_bar_visible: bool = True  # barra di scala (41 §3.18)
    compass: object = field(default=None, compare=False, repr=False)  # CompassScaleBar del 10
    coordinate_frame: str = "icrs"
    coordinate_format: str = "sexagesimal"

    def state_json(self) -> dict:
        return {"center": None if self.center is None else sky_json(self.center),
                "scale": quantity_json(self.scale), "projection": self.projection, "frame": self.frame,
                "tangent_point": None if self.tangent_point is None else sky_json(self.tangent_point),
                "window": None if self.window is None else list(self.window), "base_layer": self.base_layer,
                "grid": {"visible": self.grid_visible, "frame": self.grid_frame},
                "overlays": {"compass": self.compass_visible, "scale_bar": self.scale_bar_visible},
                "coordinate_display": {"frame": self.coordinate_frame, "format": self.coordinate_format}}


@dataclass(frozen=True)
class WorkspaceState:
    """Stato intero e immutabile: livelli (ordine di disegno, il primo in basso) e vista."""

    layers: tuple[Layer, ...] = ()
    next_layer: int = 1
    view: ViewState = ViewState()
    catalogs_opened: int = 0  # cataloghi aperti nella sessione: stile iniziale in ordine di apertura (§7)
    mocs_opened: int = 0  # MOC aperti nella sessione: stile iniziale in ordine di apertura (§7, sprint 4f)

    def find(self, layer_id: str) -> Layer | None:
        for layer in self.layers:
            if layer.id == layer_id:
                return layer
        return None

    def layer(self, layer_id: str) -> Layer:
        found = self.find(layer_id)
        if found is None:
            raise CommandError("LAYER_UNKNOWN", f"livello {layer_id} inesistente o rimosso", params={"layer": layer_id})
        return found

    def of_kind(self, kind: str) -> tuple[Layer, ...]:
        return tuple(layer for layer in self.layers if layer.kind == kind)

    def new_layer_id(self) -> tuple[str, WorkspaceState]:
        """Identificativo ``L<n>`` in ordine di creazione, mai riusato (§3.2)."""
        return f"L{self.next_layer}", dataclasses.replace(self, next_layer=self.next_layer + 1)

    def replace_layer(self, layer: Layer) -> WorkspaceState:
        return dataclasses.replace(self, layers=tuple(layer if x.id == layer.id else x for x in self.layers))

    def state_json(self) -> dict:
        """Stato finale descrittivo (§3.4): nessun pixel né contenuto di tabelle."""
        return {"layers": [layer.state_json() for layer in self.layers], "next_layer": self.next_layer,
                "view": self.view.state_json()}


class Workspace:
    """Spazio di lavoro letto dall'interfaccia: ``state`` si sostituisce in un solo passo (lettura sempre intera)."""

    def __init__(self, state: WorkspaceState | None = None) -> None:
        self._state = WorkspaceState() if state is None else state
        self._lock = threading.Lock()

    @property
    def state(self) -> WorkspaceState:
        return self._state

    def _commit(self, state: WorkspaceState) -> None:
        with self._lock:
            self._state = state


# --------------------------------------------------------------------------
# Esecuzione (§3.2)
# --------------------------------------------------------------------------


class _Cancelled(Exception):
    pass


@dataclass
class ExecutionContext:
    """Ciò che riceve l'esecutore di un comando: stato, parametri decodificati, cache, annullamento."""

    registry: CommandRegistry
    spec: CommandSpec
    state: WorkspaceState
    raw: Mapping[str, object]  # parametri registrati (forma JSON)
    cancel: CancelToken
    progress: Callable[[ProgressReport], None] | None
    cache: object = None
    _step: int = 0

    def step(self, text: str) -> None:
        """Passo di un comando a più passi: controlla l'annullamento ed emette l'avanzamento."""
        if self.cancel.cancelled:
            raise _Cancelled()
        self._step += 1
        if self.progress is not None:
            self.progress(ProgressReport(self._step, self.spec.steps, text))


@dataclass
class Outcome:
    """Esito di un esecutore: valori (forma JSON, ogni numero con unità), nuovo stato, avvisi, provenienza."""

    values: dict = field(default_factory=dict)
    state: WorkspaceState | None = None
    warnings: list[ResultMessage] = field(default_factory=list)
    provenance: list[dict] = field(default_factory=list)
    layers_created: list[str] = field(default_factory=list)
    network_fingerprint: list[dict] = field(default_factory=list)
    resolved: dict = field(default_factory=dict)  # valori scelti dal modulo da scrivere nel comando registrato


def _module_error(exc: BaseException) -> ResultMessage | None:
    """Errore di un modulo con codice, testo e ``params`` (``code``/``message``/``params``), invariati (§3.2)."""
    code, message = getattr(exc, "code", None), getattr(exc, "message", None)
    if isinstance(code, str) and isinstance(message, str):
        return ResultMessage(code, message, _json_params(getattr(exc, "params", None)))
    return None


def _command_error_message(exc: CommandError) -> ResultMessage:
    return ResultMessage(exc.code, exc.message, _json_params(exc.params))


def _json_value(value: object) -> object:
    """Valore di ``params`` in forma JSON, senza cambiarne il valore (numpy → tipo nativo, quantità → valore e unità)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Mapping):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    if isinstance(value, u.Quantity):
        if value.isscalar:
            return {"value": float(value.value), "unit": value.unit.to_string()}
        return {"value": [float(v) for v in value.value.ravel()], "unit": value.unit.to_string()}
    if hasattr(value, "tolist"):  # numpy scalare o array
        return _json_value(value.tolist())
    return str(value)


def _json_params(params: Mapping[str, object] | None) -> dict:
    return {} if not params else {str(k): _json_value(v) for k, v in params.items()}


class CommandRegistry:
    """Elenco chiuso delle definizioni; validazione, esecuzione, schema per il 32 (§3.2, §3.5)."""

    def __init__(self, *, cache=None) -> None:
        self._specs: dict[str, CommandSpec] = {}
        self._bound: dict[str, Callable] = {}
        self.cache = cache  # SharedCache del 04 passata ai moduli (None: quella di default dei moduli)

    def register(self, spec: CommandSpec) -> None:
        if spec.name in self._specs:
            raise ValueError(f"comando {spec.name} già registrato")
        self._specs[spec.name] = spec

    def bind(self, name: str, executor: Callable) -> None:
        """Collega l'esecuzione di un comando dell'interfaccia (``bound_by``: 40 o 41)."""
        spec = self.spec(name)
        if spec.bound_by is None:
            raise ValueError(f"{name} è eseguito dal 05, non dall'interfaccia")
        self._bound[name] = executor

    def spec(self, name: str) -> CommandSpec:
        try:
            return self._specs[name]
        except KeyError:
            raise CommandError("COMMAND_UNKNOWN", f"comando {name!r} non registrato", params={"command": name}) from None

    def specs(self) -> tuple[CommandSpec, ...]:
        return tuple(self._specs.values())

    def validate(self, command: Command, workspace: Workspace | WorkspaceState | None = None) -> Command:
        """Comando registrato: parametri validati, default risolti, file con SHA-256; errori di §10."""
        if not isinstance(command, Command):
            raise TypeError("serve un Command")
        spec = self.spec(command.name)
        if command.version != spec.version:
            raise CommandError("COMMAND_VERSION_UNSUPPORTED", f"{command.name} versione {command.version!r} non "
                               f"supportata (registrata: {spec.version})",
                               params={"command": command.name, "version": _given(command.version),
                                       "registered": spec.version}, name=command.name, version=command.version)
        if not isinstance(command.parameters, Mapping):
            raise _invalid(command.name, "parameters_form", "parametri: oggetto JSON")
        extra = sorted(set(command.parameters) - {p.name for p in spec.parameters})
        if extra:
            raise _invalid(extra[0], "parameter_unexpected", f"parametro non previsto da {command.name}",
                           command=command.name)
        ws = workspace.state if isinstance(workspace, Workspace) else workspace
        params = {}
        for p in spec.parameters:
            given = command.parameters.get(p.name, p.default if p.default is not REQUIRED else None)
            params[p.name] = _normalize(p, copy.deepcopy(given), p.name, ws)
        return Command(spec.name, spec.version, params, command.requested_by)

    def execute(self, command: Command, workspace: Workspace, cancel: CancelToken | None = None,
                progress: Callable[[ProgressReport], None] | None = None) -> CommandResult:
        """Valida ed esegue il comando (§7); per il comando registrato da mettere in cronologia: ``run``."""
        return self.run(command, workspace, cancel, progress)[1]

    def run(self, command: Command, workspace: Workspace, cancel: CancelToken | None = None,
            progress: Callable[[ProgressReport], None] | None = None) -> tuple[Command, CommandResult]:
        """Valida ed esegue; restituisce il comando registrato (con i valori scelti dal modulo) e il risultato.

        Le eccezioni dei moduli diventano un risultato ``error`` con codice e testo invariati; con l'annullamento
        il risultato si scarta e lo stato non cambia (``cancelled``).
        """
        cancel = CancelToken() if cancel is None else cancel
        started = _now()
        try:
            registered = self.validate(command, workspace)
        except CommandError as exc:
            return command, CommandResult("error", error=_command_error_message(exc), started_at=started,
                                          finished_at=_now())
        spec = self.spec(registered.name)
        executor = spec.executor if spec.bound_by is None else self._bound.get(spec.name)
        if executor is None:
            return registered, CommandResult("error", error=ResultMessage(
                "COMMAND_UNKNOWN", f"{spec.name}: esecuzione dell'interfaccia ({spec.bound_by}) non collegata",
                {"reason": "not_bound", "command": spec.name, "module": str(spec.bound_by)}),
                started_at=started, finished_at=_now())
        if cancel.cancelled:
            return registered, CommandResult("cancelled", error=ResultMessage(
                "COMMAND_CANCELLED", "comando annullato prima dell'inizio", {"reason": "before_start"}),
                started_at=started, finished_at=_now())
        before = workspace.state
        ctx = ExecutionContext(self, spec, before, registered.parameters, cancel, progress, self.cache)
        if progress is not None and spec.steps is None:
            progress(ProgressReport(0, None, spec.name))
        try:
            outcome = executor(ctx, registered.parameters)
        except _Cancelled:
            outcome = None
        except CommandError as exc:
            return registered, CommandResult("error", error=_command_error_message(exc), started_at=started,
                                             finished_at=_now())
        except Exception as exc:  # noqa: BLE001 - errori dei moduli: codice e testo invariati
            message = _module_error(exc)
            if message is None:
                if isinstance(exc, (TypeError, ValueError)):
                    message = ResultMessage("COMMAND_PARAMETER_INVALID", f"{type(exc).__name__}: {exc}",
                                            {"reason": "module_rejected", "error_type": type(exc).__name__,
                                             "detail": str(exc)})
                else:
                    raise
            return registered, CommandResult("error", error=message, started_at=started, finished_at=_now())
        if outcome is None or cancel.cancelled:
            return registered, CommandResult("cancelled", error=ResultMessage(
                "COMMAND_CANCELLED", "comando annullato: risultato scartato, stato invariato",
                {"reason": "discarded"}),
                started_at=started, finished_at=_now())
        if outcome.resolved:
            registered = Command(registered.name, registered.version, {**registered.parameters, **outcome.resolved},
                                 registered.requested_by)
        if outcome.state is not None and workspace.state is before:
            workspace._commit(outcome.state)
        return registered, CommandResult(
            "ok", values=outcome.values, warnings=tuple(outcome.warnings), provenance=tuple(outcome.provenance),
            layers_created=tuple(outcome.layers_created), started_at=started, finished_at=_now(),
            network_fingerprint=tuple(outcome.network_fingerprint))

    def export_schema(self, names: Sequence[str] | None = None) -> dict:
        """Definizioni come JSON Schema draft 2020-12 (§3.5), con indicatori e schema del risultato."""
        chosen = [self.spec(n) for n in names] if names is not None else list(self._specs.values())
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "title": "AstroTwo commands",
            "commands": [{
                "name": s.name, "version": s.version, "description": s.description_en,
                "parameters": {"type": "object",
                               "properties": {p.name: _schema_for(p) for p in s.parameters},
                               "required": [p.name for p in s.parameters if p.required],
                               "additionalProperties": False},
                "result": _RESULT_SCHEMA,
                "flags": {"read_only": s.read_only, "network": s.network, "long": s.long, "confirm": s.confirm,
                          "changes_view": s.changes_view, "class": s.command_class},
                "functions": list(s.functions),
            } for s in chosen]}


_MESSAGE_SCHEMA = {"type": "object", "properties": {"code": {"type": "string"}, "text": {"type": "string"}},
                   "required": ["code", "text"]}
_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"enum": ["ok", "error", "cancelled"]},
        "values": {"type": "object", "description": "module values; every number with its unit "
                                                    "({value, unit}), frame, epoch and pixel convention"},
        "warnings": {"type": "array", "items": _MESSAGE_SCHEMA},
        "error": {"anyOf": [_MESSAGE_SCHEMA, {"type": "null"}]},
        "provenance": {"type": "array", "items": {"type": "object"}},
        "layers_created": {"type": "array", "items": {"type": "string"}},
        "started_at": {"type": "string", "format": "date-time"},
        "finished_at": {"type": "string", "format": "date-time"},
        "network_fingerprint": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["status", "values", "warnings", "error", "provenance", "layers_created", "started_at",
                 "finished_at"],
}


# --------------------------------------------------------------------------
# Aiuti degli esecutori: decodifica, sovrapposizione, impronte di rete (§3.1, D05-2)
# --------------------------------------------------------------------------


def _q(value: Mapping | None) -> u.Quantity | None:
    """Quantity dalla forma JSON (già validata)."""
    if value is None:
        return None
    for fmt in ("fits", "vounit"):
        try:
            return np.float64(value["value"]) * u.Unit(value["unit"], format=fmt)
        except ValueError:
            continue
    raise AssertionError(value)  # pragma: no cover - validata prima


def _sky(value: Mapping | None):
    """``SkyFrame`` del 10 dalla forma JSON; gli errori del 10 passano invariati (T13)."""
    from astrotwo.core.coordinates_wcs import SkyFrame

    if value is None:
        return None
    return SkyFrame.from_lonlat(_q(value["lon"]), _q(value["lat"]), value["frame"],
                                equinox=_time_value(value.get("equinox")), obstime=_time_value(value.get("obstime")),
                                epoch=_time_value(value.get("epoch")))


def _iso(when) -> str | None:
    return None if when is None else when.isoformat()


def _source(origin: str | None, retrieved_at, from_cache: bool | None, **extra) -> dict:
    out = {"origin": origin, "retrieved_at": _iso(retrieved_at), "from_cache": from_cache}
    out.update(extra)
    return out


def _table_digest(table) -> tuple[str, int]:
    """SHA-256 del contenuto di una tabella restituita dal modulo (colonne, tipi, unità, valori, maschere)."""
    digest = hashlib.sha256()
    for name in table.colnames:
        col = table[name]
        digest.update(f"{name}|{col.dtype}|{col.unit}|".encode())
        data = np.asarray(getattr(col, "data", col))
        if data.dtype.kind == "O":
            digest.update(repr(data.tolist()).encode())
        else:
            digest.update(np.ascontiguousarray(data).tobytes())
        mask = getattr(col, "mask", None)
        if mask is not None:
            digest.update(np.ascontiguousarray(np.asarray(mask)).tobytes())
    return digest.hexdigest(), len(table)


def _fingerprint(sha256: str, origin, retrieved_at, from_cache, rows: int | None = None) -> dict:
    """Impronta dei risultati di rete di un comando (D05-2): contenuto, origine, data, cache, righe."""
    return {"sha256": sha256, "origin": origin, "retrieved_at": _iso(retrieved_at), "from_cache": from_cache,
            "rows": rows}


def _json_digest(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()


def _module_warnings(items) -> list[ResultMessage]:
    """Avvisi dei moduli (codice, testo ed eventuali ``params``) invariati."""
    out = []
    for item in items or ():
        if isinstance(item, (tuple, list)) and len(item) in (2, 3):
            params = item[2] if len(item) == 3 else getattr(item, "params", None)  # ModuleWarning del 10
            out.append(ResultMessage(str(item[0]), str(item[1]), _json_params(params)))
        else:
            out.append(ResultMessage("MODULE_NOTE", str(item), {"note": str(item)}))
    return out


def _warning_json(item) -> dict:
    out = {"code": item[0], "text": item[1]}
    params = _json_params(getattr(item, "params", None))
    if params:
        out["params"] = params
    return out


def _unique_messages(messages: Sequence[ResultMessage]) -> list[ResultMessage]:
    """Messaggi senza ripetizioni (stesso codice e stesso testo), nell'ordine di arrivo."""
    seen: set[tuple[str, str]] = set()
    out = []
    for m in messages:
        if (m.code, m.text) not in seen:
            seen.add((m.code, m.text))
            out.append(m)
    return out


def _overlay(state: WorkspaceState, new_data, force: bool, *, exclude: Sequence[str] = ()) -> list[ResultMessage]:
    """``check_overlay`` del 19 tra il nuovo dato e i livelli visibili (D19-4); BODY_MISMATCH passa invariato."""
    from astrotwo.core.planetary_data import check_overlay

    others = [layer.data for layer in state.layers if layer.visible and layer.id not in exclude
              and layer.kind != "measure" and layer.data is not None]
    check = check_overlay(others + [new_data], force=force)
    return _module_warnings(check.warnings)


def _add_layer(state: WorkspaceState, kind: str, name: str, data, **kw) -> tuple[str, WorkspaceState]:
    layer_id, state = state.new_layer_id()
    layer = Layer(id=layer_id, kind=kind, name=name, data=data, **kw)
    return layer_id, dataclasses.replace(state, layers=state.layers + (layer,))


# --------------------------------------------------------------------------
# Esecutori: immagini (11), HiPS (12), cataloghi (13), MOC (16)
# --------------------------------------------------------------------------


def _display_values(plane, limits=None) -> dict:
    out = {"vmin": float(plane.vmin), "vmax": float(plane.vmax), "stretch": plane.stretch, "palette": plane.palette,
           "gamma": float(plane.gamma)}
    if limits is not None:
        out["suggested_limits"] = {"vmin": float(limits.vmin), "vmax": float(limits.vmax),
                                   "unit": None if limits.unit is None else str(limits.unit), "method": limits.method,
                                   "parameters": {k: (float(v) if isinstance(v, (float, np.floating)) else v)
                                                  for k, v in dict(limits.parameters).items()},
                                   "n_pixels": int(limits.n_pixels), "notes": list(limits.notes)}
    return out


def _image_unit(image) -> str | None:
    return None if image.unit is None else str(image.unit)


def _frame_image(state: WorkspaceState, layer_id: str) -> tuple[WorkspaceState, dict]:
    """L'immagine appena aperta diventa la base della vista e si inquadra intera nella finestra (decisione del
    proprietario del 2026-10-20, 41 §3.2): centro = centro dei pixel dell'immagine (``pixel_to_sky`` del 10), scala =
    scala della base (``make_view_wcs`` del 10) × il rapporto tra l'immagine e la finestra. Senza finestra la vista
    non cambia; senza WCS valido la base è la griglia di pixel (``PixelGridGeometry``)."""
    from astrotwo.core.coordinates_wcs import CoordinatesWcsError, make_view_wcs, pixel_to_sky

    layer = state.layer(layer_id)
    image = layer.data
    view = dataclasses.replace(state.view, base_layer=layer_id)
    framing: dict = {"fitted": False, "problem": None}
    if image.wcs is not None and view.window is not None:
        cols, rows = view.window
        ny, nx = image.shape
        try:
            center = pixel_to_sky(image.wcs, (nx - 1) / 2, (ny - 1) / 2, convention="numpy").coords
            probe = make_view_wcs(center, 1.0 * u.arcsec, (rows, cols), base=image.wcs)
            scale = (probe.base_scale * max(nx / cols, ny / rows)).to(u.deg)
            view = dataclasses.replace(view, center=center, scale=scale)
            framing.update(fitted=True, center=sky_json(center), scale=quantity_json(scale),
                           method="centro dei pixel con pixel_to_sky e scala della base con make_view_wcs (10) × "
                                  "max(colonne immagine / colonne finestra, righe immagine / righe finestra)")
        except CoordinatesWcsError as exc:  # WCS presente ma non utilizzabile: griglia di pixel, nessuna coordinata
            problem = ResultMessage(
                "WCS_INVALID", f"WCS non valido ({exc.code}: {exc}): nessuna coordinata celeste",
                {"reason": "no_celestial_coordinates", "cause_code": exc.code,
                 "cause": _nested(exc.code, exc.message, exc.params)})
            layer = dataclasses.replace(layer, derived={**layer.derived, "wcs_problem": problem})
            state = state.replace_layer(layer)
            framing["problem"] = problem.to_json()
    return dataclasses.replace(state, view=_recompute_view(view, state)), framing


def _exec_image_open(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.images_fits import list_image_hdus, load_image, set_display, suggest_display_limits

    path = p["file"]["path"]
    ctx.step("list_image_hdus")
    hdus = list_image_hdus(path)
    ctx.step("load_image")
    image = load_image(path, hdu=p["hdu"], cache=ctx.cache)
    ctx.step("suggest_display_limits")
    resolved, limits = {}, None
    vmin, vmax = p["vmin"], p["vmax"]
    if vmin is None or vmax is None:
        limits = suggest_display_limits(image)
        vmin = float(limits.vmin) if vmin is None else vmin
        vmax = float(limits.vmax) if vmax is None else vmax
        resolved.update(vmin=vmin, vmax=vmax)  # limiti scelti registrati nel comando (D41-3)
    plane = set_display(image, vmin, vmax, p["gamma"], p["palette"], p["stretch"])
    ctx.step("check_overlay")
    state = ctx.state
    old = [layer.id for layer in state.of_kind("image")]  # al più un'immagine (41 §3.5): sostituisce
    warnings = _overlay(state, image, p["force_body"], exclude=old)
    state = dataclasses.replace(state, layers=tuple(x for x in state.layers if x.id not in old))
    name = Path(path).name + (f"[{image.hdu_index}]" if image.hdu_index else "")
    display = _display_values(plane)
    layer_id, state = _add_layer(state, "image", name, image, source=path, display=display,
                                 force_body=p["force_body"], derived={"plane": plane})
    state, framing = _frame_image(state, layer_id)
    if framing.get("problem") is not None and image.wcs is not None:
        warnings.append(ResultMessage(**framing["problem"]))
    values = {"layer": layer_id, "replaced": old, "hdu_index": image.hdu_index, "hdu_name": image.hdu_name,
              "hdus": [{"index": h.index, "name": h.name, "shape": list(h.shape)} for h in hdus],
              "shape": list(image.data.shape), "unit": _image_unit(image), "wcs": image.wcs is not None,
              "display": _display_values(plane, limits), "provenance": image.provenance, "framing": framing}
    warnings += _module_warnings(image.warnings)
    if image.wcs is None:
        warnings.append(ResultMessage("WCS_MISSING", "immagine senza WCS: griglia di pixel; finché è aperta non si "
                                      "sovrappongono HiPS, cataloghi o MOC (41 §3.5)",
                                      {"reason": "pixel_grid_overlay"}))
    return Outcome(values=values, state=state, warnings=warnings, layers_created=[layer_id], resolved=resolved,
                   provenance=[_source(image.origin, image.retrieved_at, image.from_cache, file=path,
                                       sha256=p["file"]["sha256"])])


def _exec_image_set_display(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.images_fits import set_display

    layer = ctx.state.layer(p["layer"])
    plane = set_display(layer.data, p["vmin"], p["vmax"], p["gamma"], p["palette"], p["stretch"])
    display = _display_values(plane)
    new = dataclasses.replace(layer, display=display, derived={**layer.derived, "plane": plane})
    return Outcome(values={"layer": layer.id, "display": display, "unit": _image_unit(layer.data)},
                   state=ctx.state.replace_layer(new))


#: Ordine massimo del tile su cui si propongono i limiti di colore di un survey FITS (41 §3.7, decisione del
#: proprietario del 2026-10-18): un tile fisso e piccolo, così il risultato non dipende dalla finestra.
DISPLAY_TILE_ORDER = 3


def _survey_display_limits(ctx: ExecutionContext, service, coverage, vmin, vmax) -> tuple[dict, list[ResultMessage]]:
    """Limiti di colore di un survey con tile FITS (41 §3.7): ``vmin``/``vmax`` dati, altrimenti ``hips_pixel_cut``
    del servizio, altrimenti ``suggest_display_limits`` (11) sul tile FITS che contiene ICRS (0°, 0°) — centro della
    vista iniziale — all'ordine ``min(3, ordine massimo)``; se quel tile manca, sul primo tile coperto. Dichiara
    sempre da dove vengono."""
    from astrotwo.core.coordinates_wcs import SkyFrame
    from astrotwo.core.hips import HiPSError, _tile_cells_at, fetch_tile, pixel_values
    from astrotwo.core.images_fits import suggest_display_limits

    base = {"gamma": 1.0, "stretch": "linear", "palette": "gray"}
    warnings: list[ResultMessage] = []
    if vmin is not None and vmax is not None:
        return {**base, "vmin": float(vmin), "vmax": float(vmax), "limits_source": "parametri del comando"}, warnings
    cut = [t for text in service.properties.get("hips_pixel_cut", ()) for t in text.split()]
    try:
        cut_min, cut_max = (float(cut[0]), float(cut[1])) if len(cut) == 2 else (None, None)
    except ValueError:
        cut_min = cut_max = None
    if cut_min is not None and cut_min < cut_max and math.isfinite(cut_min) and math.isfinite(cut_max):
        return ({**base, "vmin": cut_min, "vmax": cut_max,
                 "limits_source": f"hips_pixel_cut del servizio ({service.origin})"}, warnings)
    order = min(DISPLAY_TILE_ORDER, service.order)
    center = SkyFrame.from_lonlat(0.0 * u.deg, 0.0 * u.deg, "icrs")
    tile, where = None, "tile che contiene ICRS (0°, 0°)"
    try:
        index = int(np.ravel(pixel_values(service, center, order=order, cache=ctx.cache).tile_index)[0])
        tile = fetch_tile(service, order, index, format="fits", cache=ctx.cache)
    except HiPSError as exc:
        if exc.code in ("NET_TIMEOUT", "MOCSERVER_UNAVAILABLE"):
            raise
        warnings.append(ResultMessage(
            "HIPS_DISPLAY_FALLBACK", f"{service.hips_id}: il tile di ICRS (0°, 0°) all'ordine {order} non c'è "
            f"({exc.code}); limiti dal primo tile coperto",
            {"hips_id": service.hips_id, "order": order, "cause_code": exc.code}))
    if tile is None:
        if coverage is None:
            raise CommandError("HIPS_DISPLAY_LIMITS_UNDEFINED", f"{service.hips_id}: nessun tile da cui proporre i "
                               "limiti di colore (copertura non nota); indicare vmin e vmax",
                               params={"reason": "coverage_unknown", "hips_id": service.hips_id})
        cells, _ = _tile_cells_at(coverage.moc, order)
        if len(cells) == 0:
            raise CommandError("HIPS_DISPLAY_LIMITS_UNDEFINED", f"{service.hips_id}: copertura vuota; indicare vmin e vmax",
                               params={"reason": "coverage_empty", "hips_id": service.hips_id})
        index = int(np.min(cells))
        tile = fetch_tile(service, order, index, format="fits", cache=ctx.cache)
        where = "primo tile coperto"
    data = tile.data if tile.data.ndim == 2 else tile.data[0]
    limits = suggest_display_limits(data)
    return ({**base, "vmin": float(limits.vmin), "vmax": float(limits.vmax),
             "limits_source": f"{limits.method} sul {where}, ordine {order}, tile {tile.index} ({tile.provenance()})",
             "unit": tile.header.get("BUNIT") if tile.header is not None else None}, warnings)


def _exec_hips_set_survey(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.hips import set_survey

    active = set_survey(p["survey"], cache=ctx.cache)
    service = active.service
    state = ctx.state
    display, resolved, display_warnings = None, {}, []
    if service.tile_formats[:1] == ("fits",) and service.tile_width is not None:
        ctx.step("suggest_display_limits")
        display, display_warnings = _survey_display_limits(ctx, service, active.coverage, p["vmin"], p["vmax"])
        resolved = {"vmin": display["vmin"], "vmax": display["vmax"]}  # limiti scelti registrati nel comando (D41-3)
    old = [layer.id for layer in state.of_kind("hips")]  # uno sfondo HiPS (il survey attivo, 41 §3.5)
    state = dataclasses.replace(state, layers=tuple(x for x in state.layers if x.id not in old))
    layer_id, state = _add_layer(state, "hips", service.title or service.hips_id, service, source=service.base_url,
                                 display=display, derived={"coverage": active.coverage})
    # Lo sfondo va sotto gli altri livelli.
    layers = (state.layers[-1],) + state.layers[:-1]
    state = dataclasses.replace(state, layers=layers)
    props = {k: list(v) for k, v in dict(service.properties).items()}
    values = {"layer": layer_id, "replaced": old, "hips_id": service.hips_id, "title": service.title,
              "base_url": service.base_url, "frame": service.frame, "order": service.order,
              "tile_formats": list(service.tile_formats), "body": service.body,
              "coverage": active.coverage is not None, "display": display}
    return Outcome(values=values, state=state, layers_created=[layer_id], resolved=resolved,
                   # ``active.warnings`` contiene già gli avvisi del servizio: ogni sorgente compare una volta sola
                   warnings=_unique_messages(_module_warnings(active.warnings) + display_warnings),
                   provenance=[_source(service.origin, service.retrieved_at, service.from_cache)],
                   network_fingerprint=[_fingerprint(_json_digest(props), service.origin, service.retrieved_at,
                                                     service.from_cache)])


#: Stile iniziale dei cataloghi (§7, decisione del proprietario del 2026-10-21): tavolozza di Okabe e Ito (2008)
#: senza il nero, sei forme del 13, 8 pixel logici; colore e forma avanzano insieme in ordine di apertura.
CATALOG_COLORS = ("#E69F00", "#56B4E9", "#009E73", "#F0E442", "#0072B2", "#D55E00", "#CC79A7")
CATALOG_SHAPES = ("circle", "square", "diamond", "triangle", "cross", "plus")
CATALOG_SIZE = 8.0


def _initial_style(state: WorkspaceState, table) -> tuple[dict, dict, WorkspaceState]:
    """Stile del ``k``-esimo catalogo aperto, passato da ``set_plot_rules`` del 13 come ``catalog.set_style``."""
    from astrotwo.core.catalogs import PlotRule, set_plot_rules

    k = state.catalogs_opened
    style = {"shape": CATALOG_SHAPES[k % len(CATALOG_SHAPES)], "color": CATALOG_COLORS[k % len(CATALOG_COLORS)],
             "size": CATALOG_SIZE}
    plot = set_plot_rules(table, [PlotRule(**style)])
    return style, {"plot_style": plot}, dataclasses.replace(state, catalogs_opened=k + 1)


#: Stile iniziale dei MOC (§7, decisione del proprietario del 2026-10-21): la stessa tavolozza in ordine inverso, così
#: il primo MOC e il primo catalogo non hanno lo stesso colore; riempimento = 0,25 × opacità del livello.
MOC_COLORS = CATALOG_COLORS[::-1]
MOC_FILL = 0.25


def catalog_positions(table, rows=None):
    """Posizioni della tabella (colonne di posizione del 13, nel loro frame, con equinozio ed epoca del catalogo come
    li dichiara il 13, mai assunti), senza propagazione (41 §3.8, scelta minore 3).

    Restituisce ``(coords, valid)``: ``valid`` maschera delle righe (tutte o ``rows``) con una posizione leggibile e
    nei limiti, ``coords`` ``SkyFrame`` del 10 delle sole righe valide (``None`` se nessuna). Senza colonne di
    posizione, frame o unità angolare: ``(None, valid tutta False)``."""
    from astrotwo.core.coordinates_wcs import SkyFrame

    t = table.table
    index = np.arange(len(t)) if rows is None else np.asarray(rows, dtype=np.int64)
    pos = table.positions
    valid = np.zeros(index.size, dtype=bool)
    if pos is None or pos.frame is None:
        return None, valid
    values = []
    for name in (pos.lon, pos.lat):
        column = t[name]
        if column.unit is None or not column.unit.is_equivalent(u.deg):
            return None, valid
        data = np.asarray(getattr(column, "data", column), dtype=np.float64)[index]
        mask = np.asarray(getattr(column, "mask", np.zeros(len(t), dtype=bool)), dtype=bool)[index]
        degrees = (data * column.unit).to_value(u.deg)
        valid_ = ~mask & np.isfinite(degrees)
        values.append((degrees, valid_))
    (lon, lon_ok), (lat, lat_ok) = values
    with np.errstate(invalid="ignore"):
        valid = lon_ok & lat_ok & (lon >= 0.0) & (lon < 360.0) & (lat >= -90.0) & (lat <= 90.0)
    if not valid.any():
        return None, valid
    coords = SkyFrame.from_lonlat(lon[valid] * u.deg, lat[valid] * u.deg, pos.frame, equinox=pos.equinox,
                                  epoch=pos.epoch)
    return coords, valid


def _ucd_words(column) -> set[str]:
    return {w.strip().lower() for w in (column.meta.get("ucd") or "").split(";") if w.strip()}


def _source_card(layer: Layer, row: int) -> dict:
    """Scheda della sorgente di ``catalog.select`` con una riga (§7): nome da UCD, posizione della tabella con
    l'epoca del catalogo, catalogo con sorgente e data, ``record_view`` del 13."""
    from astrotwo.core.catalogs import record_view
    from astrotwo.core.coordinates_wcs import SkyFrame

    table = layer.data
    t = table.table
    name_column = next((n for n in t.colnames if {"meta.id", "meta.main"} <= _ucd_words(t[n])), None) or \
        next((n for n in t.colnames if "meta.id" in _ucd_words(t[n])), None)
    name = None
    if name_column is not None:
        value = t[name_column][row]
        if not (np.ma.is_masked(value) or value is None):
            name = (value.decode() if isinstance(value, bytes) else str(value)).strip() or None
    coords, _ = catalog_positions(table, [row])
    position = None if coords is None else sky_json(SkyFrame(coord=coords.coord[0], epoch=coords.epoch))
    code = None if position is not None else ("columns_not_confirmed" if table.positions is None else "row_invalid")
    reason = {None: None, "columns_not_confirmed": "colonne di posizione non confermate (catalog.set_columns)",
              "row_invalid": "posizione mancante o non valida in questa riga"}[code]
    return {"row": row, "name": {"column": name_column, "value": name}, "position": position,
            "position_reason": reason, "position_reason_code": code,
            "catalog": {"layer": layer.id, "name": layer.name, "source": table.source, "origin": table.origin,
                        "retrieved_at": _iso(table.retrieved_at)},
            "record": _jsonable(record_view(table, row))}


def _catalog_values(layer_id: str, table) -> dict:
    pos = table.positions
    return {"layer": layer_id, "rows": len(table.table), "columns": list(table.table.colnames),
            "positions": None if pos is None else {"lon": pos.lon, "lat": pos.lat, "frame": pos.frame,
                                                   "equinox": pos.equinox, "epoch": pos.epoch, "source": pos.source},
            "body": table.body, "source": table.source, "provenance": table.provenance}


def _exec_catalog_open_file(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.catalogs import load_table, suggest_position_columns

    path = p["file"]["path"]
    ctx.step("load_table")
    table = load_table(path, table=p["table"], format=p["format"], cache=ctx.cache)
    ctx.step("suggest_position_columns")
    suggestions = suggest_position_columns(table) if table.positions is None else ()
    ctx.step("check_overlay")
    warnings = _overlay(ctx.state, table, p["force_body"]) if table.body is not None else [ResultMessage(
        "POSITION_COLUMNS_REQUIRED", "colonne di posizione da confermare con catalog.set_columns (mai dai nomi)")]
    style, derived, state = _initial_style(ctx.state, table)
    layer_id, state = _add_layer(state, "catalog", table.table_name or Path(path).name, table, source=path,
                                 force_body=p["force_body"], style=style, derived=derived)
    values = _catalog_values(layer_id, table)
    values["style"] = style
    values["suggestions"] = [{"lon": s.lon, "lat": s.lat, "frame_hint": s.frame_hint, "reason": s.reason,
                              "kind": s.kind} for s in suggestions]
    return Outcome(values=values, state=state, layers_created=[layer_id],
                   warnings=warnings + _module_warnings(table.warnings),
                   provenance=[_source(table.origin, table.retrieved_at, False, file=path,
                                       sha256=p["file"]["sha256"])])


def _exec_catalog_load_region(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.catalogs import load_catalog

    center, radius = _sky(p["center"]), _q(p["radius"])
    ctx.step("load_catalog")
    table = load_catalog(p["catalog"], region=(center, radius), max_rows=p["max_rows"], cache=ctx.cache)
    ctx.step("check_overlay")
    warnings = _overlay(ctx.state, table, p["force_body"])
    style, derived, state = _initial_style(ctx.state, table)
    layer_id, state = _add_layer(state, "catalog", p["catalog"], table, source=table.source,
                                 force_body=p["force_body"], style=style, derived=derived)
    sha, rows = _table_digest(table.table)
    from_cache = bool(getattr(table.request, "from_cache", False)) if table.request is not None else None
    return Outcome(values={**_catalog_values(layer_id, table), "style": style}, state=state,
                   layers_created=[layer_id],
                   warnings=warnings + _module_warnings(table.warnings),
                   provenance=[_source(table.origin, table.retrieved_at, from_cache)],
                   network_fingerprint=[_fingerprint(sha, table.origin, table.retrieved_at, from_cache, rows)])


def _exec_catalog_set_columns(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.catalogs import confirm_position_columns

    layer = ctx.state.layer(p["layer"])
    unit = None if p["unit"] is None else u.Unit(p["unit"])
    table = confirm_position_columns(layer.data, p["lon"], p["lat"], p["frame"], equinox=_time_value(p["equinox"]),
                                     unit=unit)
    columns = {k: p[k] for k in ("lon", "lat", "frame", "equinox", "unit", "pm_ra", "pm_dec",
                                 "pm_ra_includes_cosdec", "parallax", "radial_velocity")}
    new = dataclasses.replace(layer, data=table, columns=columns)
    return Outcome(values=_catalog_values(layer.id, table), state=ctx.state.replace_layer(new))


def _exec_catalog_set_style(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.catalogs import PlotRule, set_plot_rules

    layer = ctx.state.layer(p["layer"])
    style = set_plot_rules(layer.data, [PlotRule(shape=p["shape"], color=p["color"], size=p["size"])])
    data = {"shape": p["shape"], "color": p["color"], "size": p["size"]}
    new = dataclasses.replace(layer, style=data, derived={**layer.derived, "plot_style": style})
    return Outcome(values={"layer": layer.id, "style": data, "drawn": [int(c) for c in style.counts],
                           "not_selected": int(style.not_selected)}, state=ctx.state.replace_layer(new))


def _exec_catalog_select(ctx: ExecutionContext, p: Mapping) -> Outcome:
    layer = ctx.state.layer(p["layer"])
    n = len(layer.data.table)
    bad = [r for r in p["rows"] if not 0 <= r < n]
    if bad:
        raise _invalid("rows", "rows_out_of_range", f"righe {bad[:5]} fuori da 0…{n - 1}", rows=bad[:5], last=n - 1)
    rows = tuple(dict.fromkeys(p["rows"]))
    card = _source_card(layer, rows[0]) if len(rows) == 1 else None
    return Outcome(values={"layer": layer.id, "selected": list(rows), "source": card},
                   state=ctx.state.replace_layer(dataclasses.replace(layer, selection=rows)))


def shown_order(table, sort: Mapping | None) -> np.ndarray:
    """Ordine delle righe mostrate (42 §3, D8): ``numpy.argsort`` stabile, valori mancanti in fondo."""
    n = len(table)
    if sort is None:
        return np.arange(n)
    col = table[sort["column"]]
    data = np.asarray(getattr(col, "data", col))
    if data.ndim != 1:
        raise CommandError("TABLE_SORT_UNSUPPORTED", f"colonna {sort['column']!r} non ordinabile (array per riga)",
                           params={"reason": "array_column", "column": sort["column"]})
    mask = np.asarray(getattr(col, "mask", np.zeros(n, dtype=bool)), dtype=bool)
    if data.dtype.kind == "f":
        mask = mask | ~np.isfinite(data)
    present = np.flatnonzero(~mask)
    try:
        order = present[np.argsort(data[present], kind="stable")]
    except TypeError as exc:
        raise CommandError("TABLE_SORT_UNSUPPORTED", f"colonna {sort['column']!r} non ordinabile ({exc})",
                           params={"reason": "not_sortable", "column": sort["column"], "detail": str(exc)}) from exc
    if sort["direction"] == "descending":
        # Stabile anche al contrario: a pari valore resta l'ordine originale.
        values = data[order]
        groups = np.split(order, np.flatnonzero(values[1:] != values[:-1]) + 1) if len(order) else []
        order = np.concatenate(groups[::-1]) if groups else order
    return np.concatenate([order, np.flatnonzero(mask)])


def _exec_table_sort(ctx: ExecutionContext, p: Mapping) -> Outcome:
    layer = ctx.state.layer(p["layer"])
    if p["column"] not in layer.data.table.colnames:
        raise _invalid("column", "column_unknown", f"colonna {p['column']!r} non nella tabella", column=p["column"])
    sort = {"column": p["column"], "direction": p["direction"]}
    shown_order(layer.data.table, sort)  # controlla che la colonna sia ordinabile
    return Outcome(values={"layer": layer.id, "sort": sort},
                   state=ctx.state.replace_layer(dataclasses.replace(layer, sort=sort)))


def _exec_moc_open(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.moc import read_moc

    path = p["file"]["path"]
    moc = read_moc(path, cache=ctx.cache)
    warnings = _overlay(ctx.state, moc, p["force_body"])
    m = ctx.state.mocs_opened
    style = {"color": MOC_COLORS[m % len(MOC_COLORS)], "fill": MOC_FILL}
    layer_id, state = _add_layer(dataclasses.replace(ctx.state, mocs_opened=m + 1), "moc", Path(path).name, moc,
                                 source=path, force_body=p["force_body"], style=style)
    values = {"layer": layer_id, "kind": moc.kind, "version": moc.version, "body": moc.body,
              "provenance": moc.provenance, "style": style}
    return Outcome(values=values, state=state, layers_created=[layer_id],
                   warnings=warnings + _module_warnings(moc.warnings),
                   provenance=[_source(moc.origin, None, False, file=path, sha256=p["file"]["sha256"])])


# --------------------------------------------------------------------------
# Esecutori: vista (10), griglia, livelli, misure (17), letture passive
# --------------------------------------------------------------------------

#: Scarto di ±10 % attorno alla soglia di 30° (41 §3.3, D10-9): valori fissi dichiarati, non calcoli.
_TO_AIT_THRESHOLD = 33.0 * u.deg
_TO_TAN_THRESHOLD = 27.0 * u.deg


@dataclass(frozen=True)
class PixelGridGeometry:
    """Geometria di un'immagine senza WCS valido (41 §3.5): griglia di pixel inquadrata intera nella finestra.

    Solo pixel (convenzione numpy, indice da 0, DC7): nessuna coordinata celeste, nessun campo, nessuna scala in
    angolo. Pixel della base = ``origin + (x, y) / factor`` per il pixel ``(x, y)`` della finestra, come
    ``ViewGeometry`` del 10.
    """

    shape: tuple[int, int]  # (righe, colonne) della finestra
    image_shape: tuple[int, int]  # (righe, colonne) dell'immagine
    factor: float
    origin: tuple[float, float]
    problem: ResultMessage  # motivo (codice, testo, params) per cui mancano le coordinate

    def window_to_base(self, x, y) -> tuple[np.ndarray, np.ndarray]:
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        return self.origin[0] + x / self.factor, self.origin[1] + y / self.factor

    def base_to_window(self, bx, by) -> tuple[np.ndarray, np.ndarray]:
        bx = np.asarray(bx, dtype=np.float64)
        by = np.asarray(by, dtype=np.float64)
        return (bx - self.origin[0]) * self.factor, (by - self.origin[1]) * self.factor


def _wcs_problem(layer) -> ResultMessage | None:
    """Perché un'immagine non ha coordinate celesti (WCS assente o non valido), o ``None`` se ce l'ha."""
    image = layer.data
    if image.wcs is None:
        causes = [w for w in image.warnings if w[0] in ("WCS_MISSING", "WCS_INVALID")]
        reasons = "; ".join(w[1] for w in causes)
        text = "WCS assente o non valido: nessuna coordinata celeste" + (f" ({reasons})" if reasons else "")
        if not causes:
            return ResultMessage("WCS_INVALID", text, {"reason": "absent"})
        return ResultMessage("WCS_INVALID", text, {"reason": "absent_with_reasons", "reasons": _nested_items(causes)})
    return layer.derived.get("wcs_problem")


def _pixel_grid(layer, window: tuple[int, int], problem: ResultMessage) -> PixelGridGeometry:
    cols, rows = window
    ny, nx = layer.data.shape
    factor = min(cols / nx, rows / ny)
    origin = ((nx - 1) / 2 - (cols - 1) / 2 / factor, (ny - 1) / 2 - (rows - 1) / 2 / factor)
    return PixelGridGeometry((rows, cols), (ny, nx), factor, origin, problem)


def _recompute_view(view: ViewState, state: WorkspaceState, info: dict | None = None) -> ViewState:
    """Nuova ``ViewGeometry`` con ``make_view_wcs`` del 10 (41 §3.2): base dell'immagine o base creata.

    Base creata: proiezione con ``choose_projection`` (soglia 33° in ``TAN``, 27° in ``AIT``), ricreata con il
    punto di tangenza al centro quando la proiezione cambia o il punto di tangenza esce dalla finestra.
    """
    from astrotwo.core.coordinates_wcs import CoordinatesWcsError, choose_projection, make_view_wcs

    info = {} if info is None else info
    base = state.find(view.base_layer) if view.base_layer else None
    if base is None:
        view = dataclasses.replace(view, base_layer=None)
    problem = None if base is None else _wcs_problem(base)
    if problem is not None and view.window is not None:
        # Immagine senza WCS valido: griglia di pixel intera nella finestra, senza coordinate (41 §3.5)
        info["base"] = f"griglia di pixel dell'immagine {base.id} ({problem.code})"
        return dataclasses.replace(view, projection=None, tangent_point=None, grid=None, compass=None,
                                   geometry=_pixel_grid(base, view.window, problem))
    if view.center is None or view.scale is None or view.window is None:
        return dataclasses.replace(view, geometry=None, grid=None, compass=None)
    cols, rows = view.window
    shape = (rows, cols)
    if view.base_layer is not None and problem is None:
        geometry = make_view_wcs(view.center, view.scale, shape, base=base.data.wcs)
        info["base"] = f"WCS dell'immagine {base.id}"
        view = dataclasses.replace(view, projection=geometry.projection, tangent_point=None, geometry=geometry)
    else:
        if view.base_layer is not None:  # immagine senza WCS e finestra non nota: nessuna geometria
            return dataclasses.replace(view, geometry=None, grid=None, compass=None)
        projection = view.projection or "TAN"
        outside = False
        try:
            geometry = make_view_wcs(view.center, view.scale, shape, projection=projection, frame=view.frame,
                                     tangent_point=view.tangent_point)
        except CoordinatesWcsError as exc:
            if exc.code != "VIEW_PARAMETERS_INVALID" or view.tangent_point is None:
                raise
            # Il nuovo centro non ha posto nella proiezione della base attuale (es. una ``TAN`` centrata su Sirius
            # non rappresenta M31, a più di 90°): si ricrea la base con il punto di tangenza al centro (41 §3.2). Se
            # il motivo era un altro (scala, finestra) lo stesso errore si ripresenta qui sotto.
            outside = True
            geometry = make_view_wcs(view.center, view.scale, shape, projection=projection, frame=view.frame)
        choice = choose_projection(2 * geometry.field_radius,
                                   threshold=_TO_AIT_THRESHOLD if projection == "TAN" else _TO_TAN_THRESHOLD)
        tx, ty = geometry.sky_to_window(geometry.tangent_point)
        inside = bool(-0.5 <= float(tx) < cols - 0.5 and -0.5 <= float(ty) < rows - 0.5)
        recreated = outside or choice.projection != projection or not inside or view.tangent_point is None
        if recreated:
            geometry = make_view_wcs(view.center, view.scale, shape, projection=choice.projection, frame=view.frame)
        info["base"] = "base creata" + (" (ricreata con il punto di tangenza al centro)" if recreated else "")
        info["projection_choice"] = {"projection": choice.projection,
                                     "field_of_view": quantity_json(choice.field_of_view),
                                     "threshold": quantity_json(choice.threshold),
                                     "threshold_source": choice.threshold_source}
        view = dataclasses.replace(view, projection=geometry.projection, tangent_point=geometry.tangent_point,
                                   geometry=geometry)
    return _with_overlays(view)


def _with_overlays(view: ViewState) -> ViewState:
    return _with_compass(_with_grid(view))


def _with_compass(view: ViewState) -> ViewState:
    """Nord, est e barra di scala del 10 sulla geometria corrente, nel frame della griglia se è visibile, altrimenti
    ICRS (41 §3.18); non calcolati se né l'indicatore né la barra sono accesi."""
    from astrotwo.core.coordinates_wcs import compass_and_scale_bar

    if (view.geometry is None or isinstance(view.geometry, PixelGridGeometry)
            or not (view.compass_visible or view.scale_bar_visible)):
        return dataclasses.replace(view, compass=None)
    frame = view.grid_frame if view.grid_visible else "icrs"
    return dataclasses.replace(view, compass=compass_and_scale_bar(view.geometry, frame=frame))


def _with_grid(view: ViewState) -> ViewState:
    from astrotwo.core.coordinates_wcs import choose_grid_spacing, compute_grid_lines

    if not view.grid_visible or view.geometry is None or isinstance(view.geometry, PixelGridGeometry):
        return dataclasses.replace(view, grid=None)
    w = view.geometry.visible_wcs
    spacing = choose_grid_spacing(w, frame=view.grid_frame)
    lines = compute_grid_lines(w, frame=view.grid_frame, lon_spacing=spacing.lon_spacing,
                               lat_spacing=spacing.lat_spacing)
    return dataclasses.replace(view, grid=lines)


def _view_values(view: ViewState, info: dict) -> dict:
    g = view.geometry
    out = {"center": None if view.center is None else sky_json(view.center), "scale": quantity_json(view.scale),
           "projection": view.projection, "frame": view.frame, "base_layer": view.base_layer,
           "window": None if view.window is None else {"width": view.window[0], "height": view.window[1]}}
    if isinstance(g, PixelGridGeometry):
        out.update(pixel_grid={"image_shape": list(g.image_shape), "factor": g.factor, "origin": list(g.origin)},
                   wcs_problem=g.problem.to_json(), **info)
    elif g is not None:
        out.update(field_radius=quantity_json(g.field_radius), field_radius_method=g.field_radius_method,
                   field_of_view=quantity_json(2 * g.field_radius),
                   field_of_view_method="2 × field_radius della ViewGeometry del 10 (diametro del cerchio che "
                                        "contiene la finestra disegnata)",
                   base_scale=quantity_json(g.base_scale), base_scale_method=g.base_scale_method,
                   notes=list(g.notes), **info)
    if view.compass is not None:
        c = view.compass
        out["compass"] = {"frame": c.frame_name, "north": None if c.north is None else list(c.north),
                          "east": None if c.east is None else list(c.east), "bar_pixels": c.bar_pixels,
                          "bar_label": c.label, "local_only": c.local_only,
                          "warnings": [_warning_json(w) for w in c.warnings], "method": c.method}
    if view.grid is not None:
        out["grid"] = {"frame": view.grid.frame_name, "lon_spacing": quantity_json(view.grid.lon_spacing),
                       "lat_spacing": quantity_json(view.grid.lat_spacing), "lines": len(view.grid.lines)}
    return out


def _window(p: Mapping) -> tuple[int, int] | None:
    w = p.get("window")
    return None if w is None else (w["width"], w["height"])


def _apply_view(ctx: ExecutionContext, **changes) -> Outcome:
    info: dict = {}
    view = _recompute_view(dataclasses.replace(ctx.state.view, **changes), ctx.state, info)
    return Outcome(values=_view_values(view, info), state=dataclasses.replace(ctx.state, view=view))


def _exec_view_set_center(ctx: ExecutionContext, p: Mapping) -> Outcome:
    return _apply_view(ctx, center=_sky(p["position"]), window=_window(p) or ctx.state.view.window)


def _exec_view_set_zoom(ctx: ExecutionContext, p: Mapping) -> Outcome:
    return _apply_view(ctx, scale=_q(p["scale"]).to(u.deg), window=_window(p) or ctx.state.view.window)


_DECIMAL = r"[+-]?(?:\d+\.?\d*|\.\d+)"
_DECIMAL_PAIR = re.compile(rf"\s*({_DECIMAL})\s*[,\s]\s*({_DECIMAL})\s*")
_SEXA_TOKEN = r"[+-]?\d+(?:\.\d*)?"
_SEXA_COLON_PAIR = re.compile(rf"\s*({_SEXA_TOKEN}:\d+(?::\d+(?:\.\d*)?)?)\s*[,\s]\s*([+-]?\d+:\d+(?::\d+(?:\.\d*)?)?)\s*")
_SEXA_SPACE_PAIR = re.compile(r"\s*(\d+\s+\d+\s+\d+(?:\.\d*)?)\s*[,\s]\s*([+-]?\d+\s+\d+\s+\d+(?:\.\d*)?)\s*")


def _parse_go_to(text: str, frame: str):
    """Coordinate scritte nel campo "Vai a" (40 §3.4) con ``parse_sexagesimal`` del 10, o ``None`` per un nome.

    Coppia decimale = gradi; coppia sessagesimale (``h:m:s ±d:m:s`` o ``h m s ±d m s``) = longitudine in ore
    nei frame equatoriali, in gradi negli altri; frame quello delle coordinate mostrate; epoca non nota
    (non assunta).
    """
    from astrotwo.core.coordinates_wcs import SkyFrame, parse_sexagesimal

    decimal = _DECIMAL_PAIR.fullmatch(text)
    if decimal:
        lon, lat = (np.float64(float(v)) * u.deg for v in decimal.groups())
        how = "coppia decimale in gradi"
    else:
        sexa = _SEXA_COLON_PAIR.fullmatch(text) or _SEXA_SPACE_PAIR.fullmatch(text)
        if not sexa:
            return None, None
        hours = frame in ("icrs", "fk5", "fk4")
        lon = parse_sexagesimal(sexa.group(1), hours=hours)[0]
        lat = parse_sexagesimal(sexa.group(2), hours=False)[0]
        how = f"sessagesimale con parse_sexagesimal del 10 (longitudine in {'ore' if hours else 'gradi'})"
    return SkyFrame.from_lonlat(lon, lat, frame), how


def _exec_view_go_to(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.coordinates_wcs import convert_coordinates, resolve_name

    text = p["text"]
    point, how = _parse_go_to(text, ctx.state.view.coordinate_frame)
    extra, provenance, fingerprint = {}, [], []
    if point is None:
        resolved = resolve_name(text, cache=ctx.cache)
        point = resolved.coords
        extra = {"resolved": _resolved_values(resolved)}
        provenance = [_source(resolved.origin, resolved.retrieved_at, resolved.from_cache, source=resolved.source)]
        fingerprint = [_fingerprint(_json_digest(extra["resolved"]["position"]), resolved.origin,
                                    resolved.retrieved_at, resolved.from_cache)]
        how = f"nome risolto con resolve_name del 10 ({resolved.source})"
    else:
        point = convert_coordinates(point, "icrs")
    outcome = _apply_view(ctx, center=point, window=_window(p) or ctx.state.view.window)
    outcome.values.update(interpreted_as=how, **extra)
    outcome.provenance, outcome.network_fingerprint = provenance, fingerprint
    return outcome


def _exec_view_set_grid(ctx: ExecutionContext, p: Mapping) -> Outcome:
    view = _with_overlays(dataclasses.replace(ctx.state.view, grid_visible=p["visible"], grid_frame=p["frame"]))
    return Outcome(values=_view_values(view, {}) | {"grid_visible": p["visible"], "grid_frame": p["frame"]},
                   state=dataclasses.replace(ctx.state, view=view))


def _exec_view_set_overlays(ctx: ExecutionContext, p: Mapping) -> Outcome:
    view = _with_compass(dataclasses.replace(ctx.state.view, compass_visible=p["compass"],
                                             scale_bar_visible=p["scale_bar"]))
    return Outcome(values=_view_values(view, {}) | {"compass_visible": p["compass"], "scale_bar_visible": p["scale_bar"]},
                   state=dataclasses.replace(ctx.state, view=view))


def _exec_view_set_coordinate_display(ctx: ExecutionContext, p: Mapping) -> Outcome:
    view = dataclasses.replace(ctx.state.view, coordinate_frame=p["frame"], coordinate_format=p["format"])
    return Outcome(values={"frame": p["frame"], "format": p["format"]},
                   state=dataclasses.replace(ctx.state, view=view))


def _exec_layer_set_visible(ctx: ExecutionContext, p: Mapping) -> Outcome:
    layer = ctx.state.layer(p["layer"])
    warnings = []
    if p["visible"] and not layer.visible and layer.kind != "measure":
        warnings = _overlay(ctx.state, layer.data, p["force_body"], exclude=[layer.id])
    new = dataclasses.replace(layer, visible=p["visible"], force_body=layer.force_body or p["force_body"])
    return Outcome(values={"layer": layer.id, "visible": p["visible"]}, state=ctx.state.replace_layer(new),
                   warnings=warnings)


def _exec_layer_set_opacity(ctx: ExecutionContext, p: Mapping) -> Outcome:
    layer = ctx.state.layer(p["layer"])
    new = dataclasses.replace(layer, opacity=p["opacity"])
    return Outcome(values={"layer": layer.id, "opacity": p["opacity"]}, state=ctx.state.replace_layer(new))


def _exec_layer_move(ctx: ExecutionContext, p: Mapping) -> Outcome:
    layer = ctx.state.layer(p["layer"])
    rest = [x for x in ctx.state.layers if x.id != layer.id]
    if p["position"] > len(rest):
        raise _invalid("position", "position_beyond", f"posizione {p['position']} oltre l'ultimo livello ({len(rest)})",
                       position=p["position"], count=len(rest))
    rest.insert(p["position"], layer)
    state = dataclasses.replace(ctx.state, layers=tuple(rest))
    return Outcome(values={"layer": layer.id, "order": [x.id for x in rest]}, state=state)


def _exec_layer_remove(ctx: ExecutionContext, p: Mapping) -> Outcome:
    layer = ctx.state.layer(p["layer"])
    state = dataclasses.replace(ctx.state, layers=tuple(x for x in ctx.state.layers if x.id != layer.id))
    values = {"layer": layer.id, "order": [x.id for x in state.layers]}
    if ctx.state.view.base_layer == layer.id:
        info: dict = {}
        view = _recompute_view(dataclasses.replace(state.view, base_layer=None, projection=None, tangent_point=None),
                               state, info)
        state = dataclasses.replace(state, view=view)
        values["view"] = _view_values(view, info)
    return Outcome(values=values, state=state)


def _exec_measure_distance(ctx: ExecutionContext, p: Mapping) -> Outcome:
    """Due forme (05 §7): pixel di un'immagine (``layer``, ``p1``, ``p2``) o posizioni celesti (``sky1``, ``sky2``)."""
    from astrotwo.core.coordinates_wcs import convert_pixel_convention, pixel_to_sky
    from astrotwo.core.images_fits import star_centroid
    from astrotwo.core.measures import angular_distance

    pixel_form = [name for name in ("layer", "p1", "p2") if p[name] is not None]
    sky_form = [name for name in ("sky1", "sky2") if p[name] is not None]
    if bool(pixel_form) == bool(sky_form):
        raise _invalid("layer", "distance_form", "serve una sola forma: (layer, p1, p2) per i pixel di un'immagine "
                       "oppure (sky1, sky2) per due posizioni celesti")
    if sky_form:
        if len(sky_form) != 2:
            raise _invalid("sky2" if "sky1" in sky_form else "sky1", "sky_form_incomplete",
                           "la forma cielo vuole sky1 e sky2")
        if p["snap"]:
            raise _invalid("snap", "snap_needs_pixels",
                           "l'aggancio al centroide vuole i pixel di un'immagine (layer, p1, p2)")
        points = [(None, None, _sky(p[name]), None) for name in ("sky1", "sky2")]
        centroids: list = []
        source, name = None, "distance"
    else:
        if len(pixel_form) != 3:
            missing = [x for x in ("layer", "p1", "p2") if x not in pixel_form]
            raise _invalid(missing[0], "pixel_form_incomplete", "la forma pixel vuole layer, p1 e p2")
        layer = ctx.state.layer(p["layer"])
        image = layer.data
        if image.wcs is None:
            raise CommandError("NO_WCS", f"livello {layer.id}: immagine senza WCS, distanza angolare non misurabile",
                               params={"reason": "distance", "layer": layer.id})
        if p["snap"] and p["box_size"] is None:
            raise _invalid("box_size", "box_size_required",
                           "con l'aggancio al centroide serve box_size (intero dispari ≥ 3)")
        points, centroids = [], []
        for name in ("p1", "p2"):
            x, y = p[name]["x"], p[name]["y"]
            if p["snap"]:
                c = star_centroid(image, (x, y), p["box_size"])
                x, y = float(c.x), float(c.y)
                centroids.append({"point": name, "x": x, "y": y, "convention": c.convention,
                                  "background": float(c.background), "annulus_inner": float(c.annulus_inner),
                                  "annulus_outer": float(c.annulus_outer), "provenance": c.provenance})
            sky = pixel_to_sky(image.wcs, x, y, convention="numpy").coords
            fits = convert_pixel_convention(x, y, "numpy", "fits")
            points.append((x, y, sky, (float(np.ravel(fits.x)[0]), float(np.ravel(fits.y)[0]))))
        source, name = layer.id, f"distance {layer.id}"
    distance = angular_distance(points[0][2], points[1][2], p["unit"])
    values = {"distance": quantity_json(distance.value), "frame": distance.report.frame,
              "points": [{"pixel_numpy": None if x is None else {"x": x, "y": y},
                          "pixel_fits": None if fits is None else {"x": fits[0], "y": fits[1]},
                          "sky": sky_json(s)} for x, y, s, fits in points],
              "centroids": centroids, "notes": list(distance.report.notes)}
    layer_id, state = _add_layer(ctx.state, "measure", name, distance, source=source, derived={"values": values})
    values["layer"] = layer_id
    return Outcome(values=values, state=state, layers_created=[layer_id])


def _cursor_point(ctx: ExecutionContext, p: Mapping):
    """Pixel della base sotto il mouse e cielo (``None`` su una griglia di pixel: nessuna coordinata inventata)."""
    from astrotwo.core.coordinates_wcs import pixel_to_sky

    g = ctx.state.view.geometry
    if g is None:
        raise CommandError("VIEW_UNDEFINED", "vista senza centro, scala o finestra: nessuna geometria del 10",
                           params={"reason": "geometry"})
    bx, by = g.window_to_base(p["position"]["x"], p["position"]["y"])
    bx, by = float(bx), float(by)
    if isinstance(g, PixelGridGeometry):
        return bx, by, None
    sky = pixel_to_sky(g.base, bx, by, convention="numpy")
    return bx, by, sky


def _exec_cursor_read(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.coordinates_wcs import (
        CoordinatesWcsError, PixelPosition, convert_coordinates, convert_pixel_convention)
    from astrotwo.core.measures import UNDECLARED_UNIT, read_pixel

    bx, by, sky = _cursor_point(ctx, p)
    values: dict = {"base_pixel": {"x": bx, "y": by, "convention": "numpy"}}
    warnings: list[ResultMessage] = []
    if sky is None:
        # Griglia di pixel: nessuna coordinata celeste (41 §3.5); il motivo va nel risultato e nel messaggio
        problem = ctx.state.view.geometry.problem
        values["sky"] = None
        values["wcs_problem"] = problem.to_json()
        warnings.append(problem)
        finite = False
    else:
        finite = bool(np.all(np.isfinite([sky.coords.lon.to_value(u.deg), sky.coords.lat.to_value(u.deg)])))
        # Cielo nel sistema scelto per le coordinate mostrate (``view.set_coordinate_display``, 41 §3.11), con
        # l'epoca dichiarata dal 10; il valore del pixel si legge sempre dalla posizione nel frame della base. Se la
        # conversione richiede un'epoca che l'intestazione non dà (EPOCH_REQUIRED) l'epoca non si assume: si
        # mostrano le coordinate nel frame dell'immagine con l'avviso del 10.
        shown = sky.coords
        if finite:
            try:
                shown = convert_coordinates(sky.coords, ctx.state.view.coordinate_frame)
            except CoordinatesWcsError as exc:
                warnings.append(ResultMessage(exc.code, f"{exc}; coordinate nel frame dell'immagine",
                                              _json_params(getattr(exc, "params", None))))
        values["sky"] = sky_json(shown) if finite else None
        if not finite:
            warnings.append(ResultMessage("OUT_OF_SKY", "fuori dal cielo: il punto non ha coordinate nella proiezione",
                                          {"reason": "point"}))
    base = ctx.state.find(ctx.state.view.base_layer) if ctx.state.view.base_layer else None
    if base is not None:
        try:
            reading = read_pixel(base.data, PixelPosition(x=np.float64(bx), y=np.float64(by), convention="numpy"))
            fits = convert_pixel_convention(reading.x, reading.y, "numpy", "fits")
            values["pixel"] = {"layer": base.id, "value": float(reading.value),
                               "unit": None if reading.unit is None else str(reading.unit),
                               "unit_label": reading.unit_label, "unit_declared": reading.unit_label != UNDECLARED_UNIT,
                               "fits": {"x": int(np.ravel(fits.x)[0]), "y": int(np.ravel(fits.y)[0])}}
        except Exception as exc:  # noqa: BLE001 - "nessun dato" con il messaggio del modulo
            message = _module_error(exc)
            if message is None:
                raise
            warnings.append(message)
    elif finite:
        hips = [x for x in ctx.state.of_kind("hips") if x.visible]
        if hips and "fits" in hips[0].data.tile_formats:
            from astrotwo.core.hips import pixel_values
            try:
                read = pixel_values(hips[0].data, sky.coords, order=p["order"], cache=ctx.cache)
                from astropy_healpix import nside_to_pixel_resolution

                # Risoluzione del pixel HiPS letto: lato medio della cella HEALPix all'ordine + log2(larghezza del
                # tile) (``astropy-healpix``); a ordini bassi non è il pixel originale del survey.
                nside = 2 ** (read.order + hips[0].data.tile_width.bit_length() - 1)
                values["pixel"] = {"layer": hips[0].id, "value": float(np.ravel(read.values)[0]),
                                   "unit": None if read.unit is None else str(read.unit), "order": read.order,
                                   "resolution": quantity_json(nside_to_pixel_resolution(nside).to(u.arcsec)),
                                   "survey_order": hips[0].data.order}
                warnings += _module_warnings(read.warnings)
            except Exception as exc:  # noqa: BLE001
                message = _module_error(exc)
                if message is None:
                    raise
                warnings.append(message)
    return Outcome(values=values, warnings=warnings + ([] if sky is None else _module_warnings(sky.warnings)))


def _exec_simbad_pointer(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.vo_protocols import simbad_pointer

    _, _, sky = _cursor_point(ctx, p)
    if sky is None:
        problem = ctx.state.view.geometry.problem
        raise CommandError(problem.code, problem.text, params=problem.params)
    found = simbad_pointer(sky.coords, _q(p["radius"]), cache=ctx.cache)
    obj = found.object
    values = {"position": sky_json(sky.coords), "object": None if obj is None else {
        "main_id": obj.main_id, "otype": obj.otype, "position": sky_json(obj.coords), "nbref": obj.nbref,
        "separation": quantity_json(obj.separation),
        "magnitudes": [_jsonable(dataclasses.asdict(m)) for m in obj.magnitudes]}}
    req = found.request
    return Outcome(values=values, warnings=_module_warnings(found.warnings),
                   provenance=[_source(getattr(req, "url", found.source), getattr(req, "retrieved_at", None),
                                       getattr(req, "from_cache", None))])


# --------------------------------------------------------------------------
# Esecutori: comandi di sola lettura per l'assistente (dal 2026-10-16) e cache
# --------------------------------------------------------------------------


def _jsonable(value: object) -> object:
    """Valori dei moduli in forma JSON: ogni ``Quantity`` con la sua unità, tempi con la scala."""
    if isinstance(value, u.Quantity):
        return quantity_json(value) if value.isscalar else {"value": value.value.tolist(), "unit": str(value.unit)}
    if isinstance(value, Time):
        return time_json(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (np.floating, float)):
        v = float(value)
        return v if math.isfinite(v) else None
    if isinstance(value, np.ndarray):
        return [_jsonable(v) for v in value.tolist()]
    if isinstance(value, Mapping):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if value is None or isinstance(value, (str, int)):
        return value
    if isinstance(value, np.ma.core.MaskedConstant):
        return None
    return str(value)


def _resolved_values(resolved) -> dict:
    return {"name": resolved.name, "main_id": resolved.main_id, "position": sky_json(resolved.coords),
            "source": resolved.source, "origin": resolved.origin, "retrieved_at": _iso(resolved.retrieved_at),
            "from_cache": resolved.from_cache, "coo_err_maj": quantity_json(resolved.coo_err_maj),
            "coo_err_min": quantity_json(resolved.coo_err_min), "coo_err_angle": quantity_json(resolved.coo_err_angle),
            "coo_bibcode": resolved.coo_bibcode, "notes": list(resolved.notes)}


def _exec_coords_resolve_name(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.coordinates_wcs import resolve_name

    resolved = resolve_name(p["name"], cache=ctx.cache)
    values = _resolved_values(resolved)
    return Outcome(values=values,
                   provenance=[_source(resolved.origin, resolved.retrieved_at, resolved.from_cache,
                                       source=resolved.source)],
                   network_fingerprint=[_fingerprint(_json_digest(values["position"]), resolved.origin,
                                                     resolved.retrieved_at, resolved.from_cache)])


def _exec_catalog_search(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.catalogs import search

    layer = ctx.state.layer(p["layer"])
    mask = np.asarray(search(layer.data, p["expression"], case_sensitive=p["case_sensitive"]), dtype=bool)
    rows = np.flatnonzero(mask)
    return Outcome(values={"layer": layer.id, "expression": p["expression"], "matching_rows": int(rows.size),
                           "first_rows": [int(r) for r in rows[:50]], "rows_total": int(mask.size)})


def _exec_catalog_describe(ctx: ExecutionContext, p: Mapping) -> Outcome:
    layer = ctx.state.layer(p["layer"])
    table = layer.data
    columns = [{"name": name, "dtype": str(table.table[name].dtype),
                "unit": None if table.table[name].unit is None else str(table.table[name].unit),
                "ucd": table.table[name].meta.get("ucd"), "description": table.table[name].description}
               for name in table.table.colnames]
    values = _catalog_values(layer.id, table)
    values.update(columns=columns, origin=table.origin, retrieved_at=_iso(table.retrieved_at),
                  epoch=None if table.positions is None else table.positions.epoch)
    return Outcome(values=values)


def _exec_catalog_rows(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.catalogs import record_view

    layer = ctx.state.layer(p["layer"])
    table = layer.data
    n = len(table.table)
    order = shown_order(table.table, layer.sort) if p["order"] == "shown" else np.arange(n)
    chosen = order[p["first"]:p["first"] + p["count"]]
    wanted = p["columns"]
    if wanted is not None:
        missing = [c for c in wanted if c not in table.table.colnames]
        if missing:
            raise _invalid("columns", "columns_unknown", f"colonne non nella tabella: {missing}", columns=missing)
    rows = []
    for index in chosen:
        record = record_view(table, int(index))
        if wanted is not None:
            record = [field_ for field_ in record if field_.get("name") in wanted]
        rows.append({"row": int(index), "values": _jsonable(record)})
    return Outcome(values={"layer": layer.id, "rows": rows, "rows_total": n, "order": p["order"],
                           "sort": None if layer.sort is None else dict(layer.sort)})


def _exec_layer_list(ctx: ExecutionContext, p: Mapping) -> Outcome:
    out = []
    for position, layer in enumerate(ctx.state.layers):
        entry = layer.state_json()
        entry["order"] = position
        if layer.kind == "catalog":
            entry["rows"] = len(layer.data.table)
        out.append(entry)
    return Outcome(values={"layers": out})


def _exec_cache_clear(ctx: ExecutionContext, p: Mapping) -> Outcome:
    from astrotwo.core.cache import SharedCache

    cache = ctx.cache if ctx.cache is not None else SharedCache()
    cache.clear(p["module"])
    usage = cache.usage()
    return Outcome(values={"module": p["module"], "total_bytes": {"value": float(usage.total_bytes), "unit": "byte"}})


# --------------------------------------------------------------------------
# Esecutori: calcolatrici del 18 (adattatore run_command, D05-4)
# --------------------------------------------------------------------------


def _calculator_value(result) -> object:
    from astrotwo.core import calculators as calc

    value, unit = result.value, result.unit
    if isinstance(value, calc.TimeRepresentations):
        return {"scale": value.scale, "iso": value.iso, "jd": float(value.jd), "mjd": float(value.mjd),
                "jyear": float(value.jyear), "byear": float(value.byear), "jd1": float(value.jd1),
                "jd2": float(value.jd2)}
    if isinstance(value, calc.PixelValues):
        out = {k: _jsonable(getattr(value, k)) for k in ("raw", "physical", "bzero", "bscale", "blank",
                                                         "color_index", "in_memory", "x", "y")}
        out["fits_position"] = None if value.fits_position is None else list(value.fits_position)
        out["unit"] = str(unit) if isinstance(unit, u.UnitBase) else unit
        return out
    if isinstance(value, calc.CoordinatesOutput):
        reps = [{"position": sky_json(r.position), "lon": {"value": float(r.lon_deg), "unit": "deg"},
                 "lat": {"value": float(r.lat_deg), "unit": "deg"}, "lon_sexagesimal": r.lon_sexagesimal,
                 "lat_sexagesimal": r.lat_sexagesimal, "lon_in_hours": r.lon_in_hours, "text": r.text}
                for r in value.representations]
        off = value.offsets_to
        return {"base": sky_json(value.base), "representations": reps, "offsets_to": None if off is None else {
            "d_lon": quantity_json(off.d_lon), "d_lat": quantity_json(off.d_lat)}}
    if isinstance(value, str):  # data ISO 8601 (convertitore di unità con to_unit iso)
        return {"value": value, "scale": result.scale}
    number = float(value)
    if isinstance(unit, u.UnitBase):
        return quantity_json(number * unit) if unit != u.dimensionless_unscaled else {"value": number, "unit": ""}
    if result.scale is not None:
        return {"value": number, "scale": result.scale}
    return {"value": number, "unit": None, "unit_label": unit}


def _calc_executor(name: str) -> Callable:
    def run(ctx: ExecutionContext, p: Mapping) -> Outcome:
        from astrotwo.core.calculators import run_command

        layers = {}
        if p.get("image") is not None:
            layers[p["image"]] = ctx.state.layer(p["image"]).data
        row = p.get("catalog_row")
        if row is not None:
            layers[row["layer"]] = ctx.state.layer(row["layer"]).data
        result = run_command({"name": name, "version": 1, "parameters": copy.deepcopy(dict(p))}, layers)
        unit = result.unit
        values = {"calculator": result.calculator, "input": result.input, "value": _calculator_value(result),
                  "unit": str(unit) if isinstance(unit, u.UnitBase) else unit, "scale": result.scale,
                  "library": result.library, "notes": list(result.notes),
                  "requested_at": result.requested_at.isoformat(),
                  "iers": None if result.iers is None else result.iers.text}
        return Outcome(values=values, provenance=[{"library": result.library}])
    return run


# --------------------------------------------------------------------------
# Definizioni dei comandi della prima versione dell'interfaccia (§7)
# --------------------------------------------------------------------------

_LAYER_IMAGE = ("image",)
_LAYER_CATALOG = ("catalog",)
_ANGLE = "angle"
_FRAMES_VIEW = ("icrs", "galactic")


def _window_param() -> ParameterSpec:
    return P("window", "record", "Window size in physical pixels.", "Dimensioni della finestra in pixel fisici.",
             default=None, fields=(
                 P("width", "integer", "Width in pixels.", "Larghezza in pixel.", minimum=1),
                 P("height", "integer", "Height in pixels.", "Altezza in pixel.", minimum=1)))


def _force_body() -> ParameterSpec:
    return P("force_body", "boolean", "Force overlaying data of different bodies (cited in the result).",
             "Forza la sovrapposizione di dati di corpi diversi (citata nel risultato).", default=False)


def _layer_param(kinds: tuple[str, ...] = ()) -> ParameterSpec:
    return P("layer", "layer_ref", "Layer identifier (L<n>).", "Identificativo del livello (L<n>).",
             layer_kinds=kinds)



def _calc_specs() -> list[CommandSpec]:
    from astrotwo.core.calculators import EQUIVALENCIES, TIME_FORMATS, TIME_SCALES
    from astrotwo.core.images_fits import STRETCHES

    scale_enum = tuple(TIME_SCALES) + tuple(x.upper() for x in TIME_SCALES)  # maiuscole o minuscole (18 P2)
    angle_q = dict(physical_type=_ANGLE)
    sky = P("to_point", "sky_position", "Point for the offsets towards it.", "Punto verso cui calcolare gli offset.",
            default=None)
    coordinate_input = P(
        "position", "record", "Written coordinates (degrees as quantities or sexagesimal text).",
        "Coordinate scritte (quantità angolari o testo sessagesimale).", default=None, fields=(
            P("lon", "quantity", "Longitude.", "Longitudine.", default=None, **angle_q),
            P("lat", "quantity", "Latitude.", "Latitudine.", default=None, **angle_q),
            P("lon_text", "string", "Sexagesimal longitude.", "Longitudine sessagesimale.", default=None),
            P("lat_text", "string", "Sexagesimal latitude (degrees).", "Latitudine sessagesimale (gradi).",
              default=None),
            P("lon_sexagesimal", "enum", "Unit of the sexagesimal longitude.",
              "Unità della longitudine sessagesimale.", default=None, choices=("hours", "degrees")),
            P("frame", "string", "astropy frame name.", "Nome del frame di astropy."),
            P("equinox", "time", "Equinox (J…/B…).", "Equinozio (J…/B…).", default=None),
            P("obstime", "time", "Observation time (J…/B…).", "Istante di osservazione (J…/B…).", default=None),
            P("epoch", "time", "Epoch of the positions (J…/B…), if known.",
              "Epoca delle posizioni (J…/B…), se nota.", default=None)))
    return [
        CommandSpec("calc.evaluate_expression", 1, "Evaluate an expression of the algebraic calculator.",
                    "Valuta un'espressione della calcolatrice algebrica.", ("18 evaluate_expression",), (
                        P("expression", "string", "Expression (closed grammar).", "Espressione (grammatica chiusa)."),
                        P("max_length", "integer", "Maximum length.", "Lunghezza massima.", default=1000, minimum=1),
                        P("max_depth", "integer", "Maximum nesting.", "Annidamento massimo.", default=50, minimum=1),
                        P("colon_units", "enum", "Unit of all colon sexagesimals.",
                          "Unità di tutti i sessagesimali con i due punti.", default=None,
                          choices=("hours", "degrees")),
                        P("colon_units_each", "list", "Unit of each colon sexagesimal, in text order.",
                          "Unità di ogni sessagesimale con i due punti, nell'ordine del testo.", default=None,
                          item=P("unit", "enum", "", "", choices=("hours", "degrees")))),
                    "session", executor=_calc_executor("calc.evaluate_expression")),
        CommandSpec("calc.convert_units", 1, "Convert a value between units with astropy.units.",
                    "Converte un valore tra unità con astropy.units.", ("18 convert_units",), (
                        P("value", "number", "Value.", "Valore.", default=None),
                        P("value_text", "string", "Expression, sexagesimal angle or ISO 8601 date.",
                          "Espressione, angolo sessagesimale o data ISO 8601.", default=None),
                        P("from_unit", "string", "Source unit (FITS or VOUnit).", "Unità di partenza (FITS o VOUnit).",
                          default=None),
                        P("to_unit", "string", "Target unit or time representation.",
                          "Unità di arrivo o rappresentazione del tempo."),
                        P("equivalency", "enum", "Physical equivalency (only if requested).",
                          "Equivalenza fisica (solo se richiesta).", default=None, choices=tuple(EQUIVALENCIES)),
                        P("reference", "quantity", "Reference (rest) wavelength or frequency.",
                          "Lunghezza d'onda o frequenza di riferimento (a riposo).", default=None,
                          physical_type=("length", "frequency")),
                        P("sexagesimal", "enum", "Unit of a sexagesimal value.", "Unità di un valore sessagesimale.",
                          default=None, choices=("degrees", "hours")),
                        P("scale", "enum", "Time scale of a date.", "Scala di tempo di una data.", default=None,
                          choices=scale_enum),
                        P("target_scale", "enum", "Target time scale.", "Scala di tempo di arrivo.", default=None,
                          choices=scale_enum)),
                    "session", executor=_calc_executor("calc.convert_units")),
        CommandSpec("calc.convert_pixel_value", 1, "Raw ↔ physical pixel value with the FITS rule and colour index.",
                    "Valore grezzo ↔ fisico di un pixel con la regola FITS e indice di colore.",
                    ("18 convert_pixel_value", "17 read_pixel", "11 pixel_scaling", "11 read_raw_pixel",
                     "11 set_display"), (
                        P("raw", "number", "Raw value.", "Valore grezzo.", default=None,
                          note="nell'unità dell'immagine (BUNIT) dopo la regola FITS"),
                        P("physical", "number", "Physical value.", "Valore fisico.", default=None,
                          note="nell'unità dell'immagine (BUNIT)"),
                        P("bzero", "number", "BZERO.", "BZERO.", default=None, note="nell'unità dell'immagine (BUNIT)"),
                        P("bscale", "number", "BSCALE.", "BSCALE.", default=None),
                        P("blank", "integer", "BLANK.", "BLANK.", default=None),
                        P("bunit", "string", "BUNIT.", "BUNIT.", default=None),
                        P("image", "layer_ref", "Image layer (click).", "Livello dell'immagine (clic).", default=None,
                          layer_kinds=_LAYER_IMAGE),
                        P("position", "pixel_position", "Clicked pixel (numpy).", "Pixel cliccato (numpy).",
                          default=None),
                        P("position_sky", "sky_position", "Clicked sky position.", "Posizione celeste cliccata.",
                          default=None),
                        P("display", "record", "Display settings for the colour index.",
                          "Parametri di visualizzazione per l'indice di colore.", default=None, fields=(
                              P("vmin", "number", "vmin.", "vmin.", note="nell'unità dell'immagine (BUNIT)"),
                              P("vmax", "number", "vmax.", "vmax.", note="nell'unità dell'immagine (BUNIT)"),
                              P("gamma", "number", "Gamma.", "Gamma.", default=1.0, minimum=0.0,
                                exclusive_minimum=True),
                              P("stretch", "enum", "Transfer function.", "Funzione di trasferimento.",
                                default="linear", choices=STRETCHES),
                              P("palette", "string", "Palette.", "Palette.", default="gray")))),
                    "session", executor=_calc_executor("calc.convert_pixel_value")),
        CommandSpec("calc.calculate_coordinates", 1, "Coordinates in the requested systems and epochs.",
                    "Coordinate nei sistemi ed epoche richiesti.",
                    ("18 calculate_coordinates", "10 convert_coordinates", "10 propagate_position",
                     "17 apply_offsets", "17 offset_position", "17 angular_offsets"), (
                        coordinate_input,
                        P("catalog_row", "record", "Catalog row (epoch and proper motion from its metadata).",
                          "Riga di catalogo (epoca e moto proprio dai suoi metadati).", default=None, fields=(
                              P("layer", "layer_ref", "Catalog layer.", "Livello del catalogo.",
                                layer_kinds=_LAYER_CATALOG),
                              P("row", "integer", "Row.", "Riga.", minimum=0),
                              P("pm_ra", "string", "Proper motion column (RA).", "Colonna del moto proprio (RA).",
                                default=None),
                              P("pm_dec", "string", "Proper motion column (Dec).", "Colonna del moto proprio (Dec).",
                                default=None),
                              P("pm_ra_includes_cosdec", "boolean", "pm_ra includes cos δ.", "pm_ra include cos δ.",
                                default=None),
                              P("parallax", "string", "Parallax column.", "Colonna della parallasse.", default=None),
                              P("radial_velocity", "string", "Radial velocity column.",
                                "Colonna della velocità radiale.", default=None),
                              P("source_epoch", "time", "Epoch if not in the metadata (J…/B…).",
                                "Epoca se non nei metadati (J…/B…).", default=None))),
                        P("targets", "list", "Requested systems.", "Sistemi richiesti.",
                          item=P("target", "record", "", "", fields=(
                              P("frame", "string", "Frame.", "Frame."),
                              P("equinox", "time", "Equinox (J…/B…).", "Equinozio (J…/B…).", default=None),
                              P("obstime", "time", "Observation time (J…/B…).", "Istante (J…/B…).",
                                default=None)))),
                        P("epoch", "time", "Target epoch (J…/B…).", "Epoca di arrivo (J…/B…).", default=None),
                        P("motion", "record", "Proper motion.", "Moto proprio.", default=None, fields=(
                            P("pm_ra_cosdec", "quantity", "μα cos δ.", "μα cos δ.", physical_type="angular velocity"),
                            P("pm_dec", "quantity", "μδ.", "μδ.", physical_type="angular velocity"),
                            P("parallax", "quantity", "Parallax.", "Parallasse.", default=None, **angle_q),
                            P("radial_velocity", "quantity", "Radial velocity.", "Velocità radiale.", default=None,
                              physical_type="speed"),
                            P("proper_motion_only", "boolean", "Proper motion only.", "Solo moto proprio.",
                              default=False))),
                        P("offsets", "record", "Offsets Δα cos δ, Δδ.", "Offset Δα cos δ, Δδ.", default=None, fields=(
                            P("d_lon", "quantity", "Δα cos δ.", "Δα cos δ.", **angle_q),
                            P("d_lat", "quantity", "Δδ.", "Δδ.", **angle_q))),
                        P("direction", "record", "Distance and position angle.", "Distanza e angolo di posizione.",
                          default=None, fields=(
                              P("distance", "quantity", "Distance.", "Distanza.", **angle_q),
                              P("position_angle", "quantity", "Position angle (north → east).",
                                "Angolo di posizione (nord → est).", **angle_q))),
                        sky),
                    "session", executor=_calc_executor("calc.calculate_coordinates")),
        CommandSpec("calc.convert_time", 1, "Convert a date between ISO 8601, JD, MJD, Julian and Besselian years.",
                    "Converte una data tra ISO 8601, JD, MJD, anno giuliano e besseliano.", ("18 convert_time",), (
                        P("time_value", "number", "Numeric date (jd, mjd, jyear, byear).",
                          "Data numerica (jd, mjd, jyear, byear).", default=None),
                        P("time_text", "string", "ISO 8601 date.", "Data ISO 8601.", default=None),
                        P("time_format", "enum", "Input format.", "Formato di ingresso.", choices=tuple(TIME_FORMATS)),
                        P("scale", "enum", "Time scale (always declared).", "Scala di tempo (sempre dichiarata).",
                          choices=scale_enum),
                        P("target_scale", "enum", "Target scale.", "Scala di arrivo.", default=None,
                          choices=scale_enum),
                        P("iers_table", "enum", "IERS table for UT1.", "Tabella IERS per UT1.", default="bundled",
                          choices=("bundled", "updated"))),
                    "session", executor=_calc_executor("calc.convert_time")),
    ]


def default_registry(*, cache=None) -> CommandRegistry:
    """Registro con i comandi della prima versione dell'interfaccia (§7), tutti in versione 1."""
    from astrotwo.core.catalogs import FIXED_COLLECTIONS, PLOT_SHAPES
    from astrotwo.core.images_fits import STRETCHES
    from astrotwo.core.vo_protocols import DEFAULT_MAX_ROWS

    # D32-1 (c): gli identificativi del gruppo fisso del 13, letti da lì (05 §7)
    fixed_ids = ", ".join(f'"{c.id}"' for c in FIXED_COLLECTIONS)
    _catalog_id_help_en = ("Identifier of one catalog table, not of a whole collection (a prefix such as \"I/355\" "
                           f"is not a table). Most used: {fixed_ids}.")
    _catalog_id_help_it = ("Identificativo di una tabella di catalogo, non di una collezione intera (un prefisso come "
                           f"\"I/355\" non è una tabella). Più usati: {fixed_ids}.")

    reg = CommandRegistry(cache=cache)
    angle = dict(physical_type=_ANGLE)
    file_p = P("file", "file", "File (absolute path).", "File (percorso assoluto).")
    specs = [
        CommandSpec("image.open", 1, "Open a FITS image as a layer.", "Apre un'immagine FITS come livello.",
                    ("11 list_image_hdus", "11 load_image", "11 suggest_display_limits", "11 set_display",
                     "19 check_overlay", "10 make_view_wcs"), (
                        file_p,
                        P("hdu", "integer", "HDU index (null: the module's choice, written in the result).",
                          "Indice della HDU (null: scelta del modulo, scritta nel risultato).", default=None,
                          minimum=0),
                        P("vmin", "number", "Display minimum (null: zscale, written in the command).",
                          "Minimo di visualizzazione (null: zscale, scritto nel comando).", default=None,
                          note="nell'unità dell'immagine (BUNIT)"),
                        P("vmax", "number", "Display maximum (null: zscale, written in the command).",
                          "Massimo di visualizzazione (null: zscale, scritto nel comando).", default=None,
                          note="nell'unità dell'immagine (BUNIT)"),
                        P("stretch", "enum", "Transfer function.", "Funzione di trasferimento.", default="linear",
                          choices=STRETCHES),
                        P("palette", "string", "Palette.", "Palette.", default="gray"),
                        P("gamma", "number", "Gamma.", "Gamma.", default=1.0, minimum=0.0, exclusive_minimum=True),
                        _force_body()),
                    "session", _exec_image_open, long=True, changes_view=True, confirm=True, steps=4),
        CommandSpec("image.set_display", 1, "Set the display of an image layer.",
                    "Regola la visualizzazione di un'immagine.", ("11 set_display",), (
                        _layer_param(_LAYER_IMAGE),
                        P("vmin", "number", "Minimum.", "Minimo.", note="nell'unità dell'immagine (BUNIT)"),
                        P("vmax", "number", "Maximum.", "Massimo.", note="nell'unità dell'immagine (BUNIT)"),
                        P("stretch", "enum", "Transfer function.", "Funzione di trasferimento.", default="linear",
                          choices=STRETCHES),
                        P("palette", "string", "Palette.", "Palette.", default="gray"),
                        P("gamma", "number", "Gamma.", "Gamma.", default=1.0, minimum=0.0, exclusive_minimum=True)),
                    "session", _exec_image_set_display, confirm=True),
        CommandSpec("hips.set_survey", 1, "Set the HiPS background survey.", "Imposta il survey HiPS di sfondo.",
                    ("12 set_survey", "12 add_hips"), (
                        P("survey", "string", "Survey identifier or base URL (null: default survey of the 12).",
                          "Identificativo o URL di base del survey (null: survey di default del 12).", default=None),
                        P("vmin", "number", "Display minimum for FITS tiles (null: hips_pixel_cut or zscale, written "
                          "in the command).", "Minimo di visualizzazione dei tile FITS (null: hips_pixel_cut o zscale, "
                          "scritto nel comando).", default=None, note="nell'unità del survey (BUNIT)"),
                        P("vmax", "number", "Display maximum for FITS tiles (null: hips_pixel_cut or zscale, written "
                          "in the command).", "Massimo di visualizzazione dei tile FITS (null: hips_pixel_cut o "
                          "zscale, scritto nel comando).", default=None, note="nell'unità del survey (BUNIT)")),
                    "session", _exec_hips_set_survey, network=True, confirm=True),
        CommandSpec("catalog.open_file", 1, "Open a catalog from a file.", "Apre un catalogo da file.",
                    ("13 load_table", "13 suggest_position_columns", "19 check_overlay"), (
                        file_p,
                        P("table", "integer", "Table index in the file.", "Indice della tabella nel file.",
                          default=None, minimum=0),
                        P("format", "string", "File format (null: from the file).", "Formato (null: dal file).",
                          default=None),
                        _force_body()),
                    "session", _exec_catalog_open_file, long=True, confirm=True, steps=3),
        CommandSpec("catalog.load_region", 1, "Load the rows of a catalog in a circular region.",
                    "Carica le righe di un catalogo in una regione circolare.",
                    ("13 load_catalog", "14 tap_query", "19 check_overlay"), (
                        P("catalog", "string", _catalog_id_help_en, _catalog_id_help_it),
                        P("center", "sky_position", "Center of the region.", "Centro della regione."),
                        P("radius", "quantity", "Radius.", "Raggio.", minimum=0.0, exclusive_minimum=True,
                          maximum=180.0, range_unit="deg", **angle),
                        P("max_rows", "integer", "Maximum rows.", "Righe massime.", default=DEFAULT_MAX_ROWS,
                          minimum=1),
                        _force_body()),
                    "session", _exec_catalog_load_region, network=True, long=True, confirm=True, steps=2),
        CommandSpec("catalog.set_columns", 1, "Confirm position (and proper motion) columns.",
                    "Conferma le colonne di posizione (e di moto proprio).", ("13 confirm_position_columns",), (
                        _layer_param(_LAYER_CATALOG),
                        P("lon", "string", "Longitude column.", "Colonna della longitudine."),
                        P("lat", "string", "Latitude column.", "Colonna della latitudine."),
                        P("frame", "string", "Frame.", "Frame."),
                        P("equinox", "time", "Equinox (J…/B…).", "Equinozio (J…/B…).", default=None),
                        P("unit", "string", "Angular unit if the columns have none.",
                          "Unità angolare se le colonne non l'hanno.", default=None),
                        P("pm_ra", "string", "Proper motion column (RA).", "Colonna del moto proprio (RA).",
                          default=None),
                        P("pm_dec", "string", "Proper motion column (Dec).", "Colonna del moto proprio (Dec).",
                          default=None),
                        P("pm_ra_includes_cosdec", "boolean", "pm_ra includes cos δ.", "pm_ra include cos δ.",
                          default=None),
                        P("parallax", "string", "Parallax column.", "Colonna della parallasse.", default=None),
                        P("radial_velocity", "string", "Radial velocity column.", "Colonna della velocità radiale.",
                          default=None)),
                    "session", _exec_catalog_set_columns, confirm=True),
        CommandSpec("catalog.set_style", 1, "Set the drawing style of a catalog.", "Imposta lo stile di disegno.",
                    ("13 set_plot_rules",), (
                        _layer_param(_LAYER_CATALOG),
                        P("shape", "enum", "Symbol shape.", "Forma del simbolo.", choices=PLOT_SHAPES),
                        P("color", "string", "Colour.", "Colore."),
                        P("size", "number", "Size in screen pixels.", "Dimensione in pixel dello schermo.",
                          minimum=0.0, exclusive_minimum=True)),
                    "session", _exec_catalog_set_style, confirm=True),
        CommandSpec("catalog.select", 1, "Select catalog rows.", "Seleziona righe del catalogo.", (), (
                        _layer_param(_LAYER_CATALOG),
                        P("rows", "list", "Row indices.", "Indici delle righe.",
                          item=P("row", "integer", "", "", minimum=0))),
                    "session", _exec_catalog_select),
        CommandSpec("table.sort", 1, "Sort the shown rows of a table.", "Ordina le righe mostrate di una tabella.",
                    (), (
                        _layer_param(_LAYER_CATALOG),
                        P("column", "string", "Column.", "Colonna."),
                        P("direction", "enum", "Direction.", "Verso.", default="ascending",
                          choices=("ascending", "descending"))),
                    "session", _exec_table_sort),
        CommandSpec("moc.open", 1, "Open a MOC.", "Apre un MOC.", ("16 read_moc", "19 check_overlay"),
                    (file_p, _force_body()), "session", _exec_moc_open),
        CommandSpec("view.go_to", 1, "Center the view on a name or written coordinates.",
                    "Centra la vista su un nome o su coordinate scritte.",
                    ("10 resolve_name", "10 parse_sexagesimal", "10 convert_coordinates", "10 make_view_wcs",
                     "10 choose_projection"), (
                        P("text", "string", "Object name or coordinate pair.", "Nome o coppia di coordinate."),
                        _window_param()),
                    "session", _exec_view_go_to, network=True, changes_view=True, confirm=True),
        CommandSpec("view.set_center", 1, "Set the view center.", "Imposta il centro della vista.",
                    ("10 make_view_wcs", "10 choose_projection"), (
                        P("position", "sky_position", "Center.", "Centro."), _window_param()),
                    "session", _exec_view_set_center, changes_view=True),
        CommandSpec("view.set_zoom", 1, "Set the view scale (angle per window pixel).",
                    "Imposta la scala della vista (angolo per pixel della finestra).",
                    ("10 make_view_wcs", "10 choose_projection"), (
                        P("scale", "quantity", "Scale per window pixel.", "Scala per pixel della finestra.",
                          minimum=0.0, exclusive_minimum=True, maximum=180.0, range_unit="deg", **angle),
                        _window_param()),
                    "session", _exec_view_set_zoom, changes_view=True),
        CommandSpec("view.set_grid", 1, "Show or hide the coordinate grid.", "Mostra o nasconde la griglia.",
                    ("10 choose_grid_spacing", "10 compute_grid_lines"), (
                        P("visible", "boolean", "Visible.", "Visibile."),
                        P("frame", "enum", "Grid frame.", "Frame della griglia.", default="icrs",
                          choices=_FRAMES_VIEW)),
                    "session", _exec_view_set_grid, changes_view=True),
        CommandSpec("view.set_overlays", 1, "Show or hide the north/east indicator and the scale bar.",
                    "Mostra o nasconde l'indicatore di nord ed est e la barra di scala.",
                    ("10 compass_and_scale_bar",), (
                        P("compass", "boolean", "North and east indicator.", "Indicatore di nord ed est.",
                          default=True),
                        P("scale_bar", "boolean", "Scale bar.", "Barra di scala.", default=True)),
                    "session", _exec_view_set_overlays, changes_view=True),
        CommandSpec("view.set_coordinate_display", 1, "Frame and format of the shown coordinates.",
                    "Frame e formato delle coordinate mostrate.", (), (
                        P("frame", "enum", "Frame.", "Frame.", choices=_FRAMES_VIEW),
                        P("format", "enum", "Format.", "Formato.", default="sexagesimal",
                          choices=("sexagesimal", "decimal"))),
                    "session", _exec_view_set_coordinate_display),
        CommandSpec("layer.set_visible", 1, "Show or hide a layer.", "Mostra o nasconde un livello.",
                    ("19 check_overlay",), (_layer_param(), P("visible", "boolean", "Visible.", "Visibile."),
                                            _force_body()),
                    "session", _exec_layer_set_visible, confirm=True),
        CommandSpec("layer.set_opacity", 1, "Set the opacity of a layer.", "Imposta l'opacità di un livello.", (), (
                        _layer_param(), P("opacity", "number", "Opacity in [0, 1].", "Opacità in [0, 1].",
                                          minimum=0.0, maximum=1.0)),
                    "session", _exec_layer_set_opacity, confirm=True),
        CommandSpec("layer.move", 1, "Move a layer in the drawing order (0 = bottom).",
                    "Sposta un livello nell'ordine di disegno (0 = in basso).", (), (
                        _layer_param(), P("position", "integer", "New position.", "Nuova posizione.", minimum=0)),
                    "session", _exec_layer_move, confirm=True),
        CommandSpec("layer.remove", 1, "Remove a layer.", "Rimuove un livello.", ("10 make_view_wcs",),
                    (_layer_param(),), "session", _exec_layer_remove, confirm=True),
        CommandSpec("measure.distance", 1, "Angular distance between two pixels of an image.",
                    "Distanza angolare tra due pixel di un'immagine.",
                    ("11 star_centroid", "10 pixel_to_sky", "17 angular_distance"), (
                        P("layer", "layer_ref", "Image layer (pixel form: with p1 and p2).",
                          "Livello dell'immagine (forma pixel: con p1 e p2).", default=None, layer_kinds=_LAYER_IMAGE),
                        P("p1", "pixel_position", "First point (image pixel).", "Primo punto (pixel dell'immagine).",
                          default=None),
                        P("p2", "pixel_position", "Second point.", "Secondo punto.", default=None),
                        P("sky1", "sky_position", "First point (sky form: with sky2, no layer).",
                          "Primo punto (forma cielo: con sky2, senza livello).", default=None),
                        P("sky2", "sky_position", "Second point (sky form).", "Secondo punto (forma cielo).",
                          default=None),
                        P("unit", "string", "Angular unit of the result.", "Unità angolare del risultato.",
                          default="arcsec"),
                        P("snap", "boolean", "Snap to the star centroid.", "Aggancio al centroide.", default=False),
                        P("box_size", "integer", "Centroid box (odd, ≥ 3).", "Finestra del centroide (dispari, ≥ 3).",
                          default=None, minimum=3)),
                    "session", _exec_measure_distance),
        CommandSpec("view.export_png", 1, "Export the view as PNG (drawing of the 41).",
                    "Esporta la vista in PNG (disegno del 41).", ("41 disegno",), (
                        P("path", "string", "Absolute path of the file to write.",
                          "Percorso assoluto del file da scrivere."),),
                    "application", bound_by="41"),
        CommandSpec("cache.clear", 1, "Clear the cache or the part of a module.",
                    "Svuota la cache o la parte di un modulo.", ("04 SharedCache.clear",), (
                        P("module", "string", "Module (null: all).", "Modulo (null: tutta).", default=None),),
                    "application", _exec_cache_clear),
        CommandSpec("prefs.set", 1, "Set an application preference.", "Imposta una preferenza dell'app.",
                    ("40 QSettings",), (
                        P("key", "string", "Preference key.", "Chiave."),
                        P("value", "string", "Value (text form of the 40).", "Valore (forma testuale del 40).")),
                    "application", bound_by="40"),
        CommandSpec("ui.set_tool", 1, "Activate a tool.", "Attiva uno strumento.", ("40",), (
                        P("tool", "string", "Tool.", "Strumento."),), "application", bound_by="40"),
        CommandSpec("ui.set_panel", 1, "Show or hide a panel.", "Mostra o nasconde un pannello.", ("40",), (
                        P("panel", "string", "Panel.", "Pannello."), P("visible", "boolean", "Visible.", "Visibile.")),
                    "application", bound_by="40"),
        CommandSpec("ui.set_fullscreen", 1, "Full screen.", "Schermo intero.", ("40",), (
                        P("enabled", "boolean", "Enabled.", "Attivo."),), "application", bound_by="40"),
        CommandSpec("ui.set_appearance", 1, "Appearance (system, light, dark, red night mode).",
                    "Aspetto (sistema, chiaro, scuro, notte rossa).", ("40",), (
                        P("mode", "enum", "Mode.", "Modalità.", choices=("system", "light", "dark", "night")),),
                    "application", bound_by="40"),
        CommandSpec("cursor.read", 1, "Sky position and pixel value under the cursor.",
                    "Posizione celeste e valore del pixel sotto il cursore.",
                    ("10 pixel_to_sky", "10 convert_pixel_convention", "17 read_pixel", "12 pixel_values"), (
                        P("position", "pixel_position", "Window pixel (numpy).", "Pixel della finestra (numpy)."),
                        P("order", "integer", "HiPS order of the pixel value (null: the survey's deepest).",
                          "Ordine HiPS del valore del pixel (null: il più profondo del survey).", default=None,
                          minimum=0)),
                    "passive", _exec_cursor_read, read_only=True),
        CommandSpec("simbad.pointer", 1, "Most cited SIMBAD object near the cursor.",
                    "Oggetto SIMBAD più citato vicino al cursore.",
                    ("10 pixel_to_sky", "14 simbad_pointer"), (
                        P("position", "pixel_position", "Window pixel (numpy).", "Pixel della finestra (numpy)."),
                        P("radius", "quantity", "Search radius.", "Raggio di ricerca.", minimum=0.0,
                          exclusive_minimum=True, maximum=180.0, range_unit="deg", **angle)),
                    "passive", _exec_simbad_pointer, network=True, read_only=True),
        *_calc_specs(),
        CommandSpec("coords.resolve_name", 1, "Resolve an object name to ICRS coordinates.",
                    "Risolve il nome di un oggetto in coordinate ICRS.", ("10 resolve_name",), (
                        P("name", "string", "Object name.", "Nome dell'oggetto."),),
                    "session", _exec_coords_resolve_name, network=True, read_only=True),
        CommandSpec("catalog.search", 1, "Count the rows matching an expression and give the first 50 indices.",
                    "Conta le righe che soddisfano un'espressione e dà i primi 50 indici.", ("13 search",), (
                        _layer_param(_LAYER_CATALOG),
                        P("expression", "string", "Expression (closed grammar of the 13).",
                          "Espressione (grammatica chiusa del 13)."),
                        P("case_sensitive", "boolean", "Case sensitive.", "Maiuscole distinte.", default=False)),
                    "session", _exec_catalog_search, read_only=True),
        CommandSpec("catalog.describe", 1, "Metadata of a catalog layer.", "Metadati di un catalogo.",
                    ("13 metadati della tabella",), (_layer_param(_LAYER_CATALOG),),
                    "session", _exec_catalog_describe, read_only=True),
        CommandSpec("catalog.rows", 1, "At most 50 rows of a catalog with units.",
                    "Al più 50 righe di un catalogo con le unità.", ("13 record_view",), (
                        _layer_param(_LAYER_CATALOG),
                        P("first", "integer", "First row.", "Prima riga.", default=0, minimum=0),
                        P("count", "integer", "Number of rows (≤ 50).", "Numero di righe (≤ 50).", default=10,
                          minimum=1, maximum=50),
                        P("columns", "list", "Columns (null: all).", "Colonne (null: tutte).", default=None,
                          item=P("column", "string", "", "")),
                        P("order", "enum", "Table order or shown order.", "Ordine della tabella o mostrato.",
                          default="table", choices=("table", "shown"))),
                    "session", _exec_catalog_rows, read_only=True),
        CommandSpec("layer.list", 1, "List the layers of the workspace.", "Elenca i livelli.", (), (),
                    "session", _exec_layer_list, read_only=True),
    ]
    for spec in specs:
        reg.register(spec)
    return reg


# --------------------------------------------------------------------------
# Cronologia e sessione (§3.2, §3.4)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class HistoryEntry:
    """Un comando della cronologia: numero progressivo, classe, comando registrato e risultato."""

    number: int
    command_class: str
    command: Command
    result: CommandResult

    def to_json(self) -> dict:
        return {"number": self.number, "class": self.command_class, "command": self.command.to_json(),
                "result": self.result.to_json()}

    @classmethod
    def from_json(cls, data: Mapping) -> HistoryEntry:
        return cls(number=data["number"], command_class=data["class"], command=Command.from_json(data["command"]),
                   result=CommandResult.from_json(data["result"]))


class CommandHistory:
    """Cronologia dei comandi ``session`` e ``application`` (anche in errore o annullati); mai i ``passive``."""

    def __init__(self) -> None:
        self._entries: list[HistoryEntry] = []
        self._lock = threading.Lock()

    def record(self, spec: CommandSpec, command: Command, result: CommandResult) -> HistoryEntry | None:
        if spec.command_class == "passive":
            return None
        with self._lock:
            entry = HistoryEntry(len(self._entries) + 1, spec.command_class, command, result)
            self._entries.append(entry)
            return entry

    @property
    def entries(self) -> tuple[HistoryEntry, ...]:
        return tuple(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __iter__(self):
        return iter(self.entries)


@dataclass(frozen=True)
class ReplayReport:
    """Esito della riapertura (§3.4): comandi rieseguiti, elencati e non rieseguiti, stop, avvisi."""

    status: str  # ok, stopped, cancelled
    replayed: tuple[int, ...]  # numeri della sessione rieseguiti
    not_replayed: tuple[tuple[int, str, str], ...]  # (numero, nome, motivo): errore, annullato, application
    stop: ResultMessage | None = None
    stop_details: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[ResultMessage, ...] = ()
    warning_details: tuple[Mapping[str, object], ...] = ()


def _file_values(spec: ParameterSpec, value: object):
    """Valori ``file`` (con SHA-256) dentro un parametro, anche in liste e record."""
    if value is None:
        return
    if spec.type == "file":
        yield value
    elif spec.type == "list":
        for v in value:
            yield from _file_values(spec.item, v)
    elif spec.type == "record":
        for f in spec.fields:
            yield from _file_values(f, value.get(f.name))


def _differences(recorded: object, found: object, path: str = "") -> list[dict]:
    """Differenze tra due stati JSON (percorso, registrato, trovato)."""
    if isinstance(recorded, Mapping) and isinstance(found, Mapping):
        out = []
        for key in sorted(set(recorded) | set(found)):
            out += _differences(recorded.get(key), found.get(key), f"{path}.{key}" if path else str(key))
        return out
    if isinstance(recorded, list) and isinstance(found, list) and len(recorded) == len(found):
        out = []
        for k, (a, b) in enumerate(zip(recorded, found)):
            out += _differences(a, b, f"{path}[{k}]")
        return out
    return [] if recorded == found else [{"path": path, "recorded": recorded, "found": found}]


class Session:
    """Sessione: spazio di lavoro, cronologia e registro; ``save``, ``load``, ``replay`` (§3.4).

    Salvare e aprire una sessione non sono comandi della sessione stessa.
    """

    def __init__(self, registry: CommandRegistry, workspace: Workspace | None = None,
                 history: CommandHistory | None = None) -> None:
        self.registry = registry
        self.workspace = Workspace() if workspace is None else workspace
        self.history = CommandHistory() if history is None else history
        self.loaded: dict | None = None  # contenuto del file aperto con load (per replay)
        self.created_at = _now()

    def run(self, command: Command, cancel: CancelToken | None = None,
            progress: Callable[[ProgressReport], None] | None = None) -> CommandResult:
        """Esegue un comando e lo registra in cronologia (non i ``passive``, D05-1)."""
        registered, result = self.registry.run(command, self.workspace, cancel, progress)
        try:
            spec = self.registry.spec(registered.name)
        except CommandError:
            return result  # nome sconosciuto: nessuna definizione, niente cronologia
        self.history.record(spec, registered, result)
        return result

    # --- salvataggio ----------------------------------------------------------------------

    def to_json(self, *, app_version: str, conversations: Sequence[Mapping] | None = None) -> dict:
        """Contenuto del file di sessione: comandi, file con SHA-256, stato finale; nessun pixel né segreto.

        ``conversations`` (blocco facoltativo del 35, solo su richiesta dell'utente) non si rilegge mai per
        rieseguire; i nomi dei file al suo interno sono senza cartelle.
        """
        files: dict[str, dict] = {}
        for entry in self.history:
            try:
                spec = self.registry.spec(entry.command.name)
            except CommandError:
                continue
            for p in spec.parameters:
                for f in _file_values(p, entry.command.parameters.get(p.name)):
                    if "sha256" in f:
                        files[f["path"]] = dict(f)
        data = {"format": "astrotwo-session", "schema_version": SESSION_SCHEMA_VERSION,
                "app_version": app_version, "created_at": self.created_at, "saved_at": _now(),
                "commands": [e.to_json() for e in self.history], "files": list(files.values()),
                "final_state": self.workspace.state.state_json()}
        if conversations is not None:
            text = json.dumps(list(conversations))
            folders = [path for path in files if path in text or str(Path(path).parent) + os.sep in text]
            if folders:
                raise ValueError("blocco conversations con percorsi completi dei file: i nomi vanno senza cartelle "
                                 "(05 §3.4)")
            data["conversations"] = copy.deepcopy(list(conversations))
        return data

    def save(self, path: str | os.PathLike, *, app_version: str,
             conversations: Sequence[Mapping] | None = None) -> None:
        """Scrive il file JSON UTF-8 (numeri con la rappresentazione più breve che si rilegge identica)."""
        target = Path(path)
        payload = json.dumps(self.to_json(app_version=app_version, conversations=conversations), ensure_ascii=False,
                             indent=1, allow_nan=False)
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, target)

    # --- apertura e riesecuzione -------------------------------------------------------------

    @classmethod
    def load(cls, path: str | os.PathLike, registry: CommandRegistry) -> Session:
        """Legge un file di sessione (nessuna esecuzione); errori ``SESSION_INVALID``, ``SESSION_SCHEMA_UNSUPPORTED``."""
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CommandError("SESSION_INVALID", f"file di sessione non leggibile: {exc}",
                               params={"reason": "unreadable", "detail": str(exc)}) from exc
        if not isinstance(data, dict) or data.get("format") != "astrotwo-session" \
                or not isinstance(data.get("schema_version"), int) or not isinstance(data.get("commands"), list):
            raise CommandError("SESSION_INVALID", "file di sessione non valido (format, schema_version, commands)",
                               params={"reason": "structure"})
        if data["schema_version"] > SESSION_SCHEMA_VERSION:
            raise CommandError("SESSION_SCHEMA_UNSUPPORTED", f"schema della sessione {data['schema_version']} più "
                               f"recente di quello dell'app ({SESSION_SCHEMA_VERSION}): nessuna riesecuzione",
                               params={"schema_version": data["schema_version"],
                                       "app_version": SESSION_SCHEMA_VERSION})
        try:
            entries = [HistoryEntry.from_json(e) for e in data["commands"]]
        except (KeyError, TypeError, ValueError) as exc:
            raise CommandError("SESSION_INVALID", f"comando non valido nel file di sessione: {exc}",
                               params={"reason": "command", "detail": str(exc)}) from exc
        session = cls(registry)
        session.loaded = {"data": data, "entries": entries}
        return session

    def replay(self, registry: CommandRegistry | None = None, cancel: CancelToken | None = None,
               progress: Callable[[ProgressReport], None] | None = None) -> ReplayReport:
        """Riesegue in ordine i comandi ``session`` con esito ``ok`` (§3.4), senza chiamare l'IA.

        Stop su file cambiato o mancante, versione non supportata, comando prima ``ok`` ora in errore; avviso
        per dati di rete diversi (la riesecuzione continua, D05-2) e per uno stato finale diverso.
        """
        if self.loaded is None:
            raise ValueError("replay: prima Session.load")
        registry = self.registry if registry is None else registry
        cancel = CancelToken() if cancel is None else cancel
        entries: list[HistoryEntry] = self.loaded["entries"]
        todo = [e for e in entries if e.command_class == "session" and e.result.status == "ok"]
        skipped = tuple((e.number, e.command.name, e.command_class if e.command_class != "session"
                         else e.result.status) for e in entries if e not in todo)
        replayed: list[int] = []
        warnings: list[ResultMessage] = []
        details: list[dict] = []

        def stopped(code: str, message: str, params: Mapping[str, object] | None = None, **info) -> ReplayReport:
            return ReplayReport("stopped", tuple(replayed), skipped, ResultMessage(code, message, _json_params(params)),
                                info, tuple(warnings), tuple(details))

        for k, entry in enumerate(todo, start=1):
            if cancel.cancelled:
                return ReplayReport("cancelled", tuple(replayed), skipped, ResultMessage(
                    "COMMAND_CANCELLED", "riapertura annullata", {"reason": "replay"}), {}, tuple(warnings),
                    tuple(details))
            if progress is not None:
                progress(ProgressReport(k, len(todo), f"#{entry.number} {entry.command.name}"))
            name = entry.command.name
            try:
                spec = registry.spec(name)
            except CommandError as exc:
                return stopped(exc.code, f"#{entry.number}: {exc.message}",
                               {**exc.params, "reason": "in_session", "number": entry.number}, number=entry.number)
            if entry.command.version != spec.version:
                return stopped("COMMAND_VERSION_UNSUPPORTED", f"#{entry.number} {name} versione "
                               f"{entry.command.version} non supportata (registrata: {spec.version})",
                               {"reason": "in_session", "number": entry.number, "command": name,
                                "version": _given(entry.command.version), "registered": spec.version},
                               number=entry.number, name=name, version=entry.command.version)
            for p in spec.parameters:
                for f in _file_values(p, entry.command.parameters.get(p.name)):
                    target = Path(f["path"])
                    if not target.is_file():
                        return stopped("SESSION_FILE_MISSING", f"#{entry.number} {name}: file {f['path']} mancante",
                                       {"number": entry.number, "command": name, "path": f["path"]},
                                       number=entry.number, name=name, file=f["path"])
                    found, _ = _sha256(target)
                    if found != f.get("sha256"):
                        return stopped("SESSION_FILE_CHANGED", f"#{entry.number} {name}: file {f['path']} cambiato "
                                       f"(SHA-256 atteso {f.get('sha256')}, trovato {found})",
                                       {"number": entry.number, "command": name, "path": f["path"],
                                        "expected": f.get("sha256") or "", "found": found},
                                       number=entry.number, name=name, file=f["path"], expected=f.get("sha256"),
                                       found=found)
            registered, result = registry.run(entry.command, self.workspace, cancel)
            self.history.record(spec, registered, result)
            if result.status == "cancelled":
                return ReplayReport("cancelled", tuple(replayed), skipped, result.error, {}, tuple(warnings),
                                    tuple(details))
            if result.status != "ok":
                return stopped("SESSION_REPLAY_FAILED", f"#{entry.number} {name} era ok e ora fallisce: "
                               f"{result.error.code}: {result.error.text}",
                               {"number": entry.number, "command": name,
                                "error": _nested(result.error.code, result.error.text, result.error.params)},
                               number=entry.number, name=name, error=result.error.to_json())
            replayed.append(entry.number)
            before = [dict(f) for f in entry.result.network_fingerprint]
            after = [dict(f) for f in result.network_fingerprint]
            changed = [(a, b) for a, b in zip(before, after) if (a.get("sha256"), a.get("rows")) !=
                       (b.get("sha256"), b.get("rows"))] + ([(None, None)] if len(before) != len(after) else [])
            if changed:
                info = {"number": entry.number, "name": name, "before": before, "after": after}
                pieces = [(f"impronta {a.get('sha256')} → {b.get('sha256')}, origine {a.get('origin')} del "
                           f"{a.get('retrieved_at')} → {b.get('origin')} del {b.get('retrieved_at')}, righe "
                           f"{a.get('rows')} → {b.get('rows')}", a, b) for a, b in changed if a is not None]
                text = "; ".join(piece for piece, _, _ in pieces)
                params = {"number": entry.number, "command": name}
                if pieces:
                    params["changes"] = [_nested("SESSION_FINGERPRINT_CHANGE", piece, {
                        "before_sha256": a.get("sha256") or "", "after_sha256": b.get("sha256") or "",
                        "before_origin": a.get("origin") or "", "before_retrieved_at": a.get("retrieved_at") or "",
                        "after_origin": b.get("origin") or "", "after_retrieved_at": b.get("retrieved_at") or "",
                        "rows_before": _given(a.get("rows")), "rows_after": _given(b.get("rows"))})
                        for piece, a, b in pieces]
                else:
                    params = {"reason": "count_differs", **params}
                warnings.append(ResultMessage("SESSION_NETWORK_DATA_DIFFERS",
                                              f"#{entry.number} {name}: dati di rete diversi da quelli registrati "
                                              f"({text or 'numero di risposte diverso'})", params))
                details.append(info)
        recorded = self.loaded["data"].get("final_state")
        if recorded is not None:
            diff = _differences(recorded, self.workspace.state.state_json())
            if diff:
                shown = [(f"{d['path']}: {d['recorded']!r} → {d['found']!r}", d) for d in diff[:20]]
                warnings.append(ResultMessage(
                    "SESSION_STATE_DIFFERS", "stato finale diverso da quello registrato: "
                    + "; ".join(piece for piece, _ in shown),
                    {"differences": [_nested("SESSION_STATE_DIFFERENCE", piece, {
                        "path": str(d["path"]), "recorded": _given(d["recorded"]), "found": _given(d["found"])})
                        for piece, d in shown]}))
                details.append({"state_differences": diff})
        return ReplayReport("ok", tuple(replayed), skipped, None, {}, tuple(warnings), tuple(details))
