# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Catalogo dei messaggi dei moduli: codice → testo inglese e italiano (D40-3, D40-5, D40-6).

Specifica: ``mdfiles/40-ui-finestra-principale.md`` §3.7.1 e §3.7.2 (stato ``approvato``).

Modulo **neutro**: nessuna dipendenza da altri pacchetti di AstroTwo né da Qt; lo importano ``ui/`` e ``ai/``. I
moduli scientifici (10–19) e il ``05`` **non** lo importano: restituiscono solo codice e ``params`` (regola d'oro
n. 1: nessun numero nasce da un testo scritto altrove).

Una voce per codice: testo generale ``en``/``it``, parametri attesi (nome, tipo, ``external``) e, per i codici
sollevati per ragioni diverse (D40-6), sotto-voci scelte dal parametro riservato ``reason`` (identificatore
stabile, mai inserito nel testo). I segnaposto ``{nome}`` si riempiono **solo per sostituzione** del valore così com'è:
nessun arrotondamento, nessuna conversione, nessuna formattazione locale (punto decimale sempre).
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

__all__ = [
    "LANGUAGES",
    "PARAM_TYPES",
    "MAX_MESSAGE_DEPTH",
    "NO_TRANSLATION",
    "Param",
    "Variant",
    "Entry",
    "CATALOG",
    "entry_for",
    "has_message",
    "uses_catalog",
    "external_params",
    "message_params",
    "message_text",
    "placeholders",
    "validate_params",
]

LOG = logging.getLogger("astrotwo.messages")

LANGUAGES = ("en", "it")

#: Tipi dei parametri (forme JSON): ``quantity`` = ``{"value": numero, "unit": testo}``.
PARAM_TYPES = ("string", "number", "integer", "boolean", "quantity", "list", "object", "message", "messages")

#: Profondità massima dei messaggi annidati (D40-7): livelli sotto il messaggio di primo livello; oltre, il solo codice.
MAX_MESSAGE_DEPTH = 3

#: Nota dei messaggi senza voce nel catalogo (§3.7.2).
NO_TRANSLATION = {"en": "(no translation)", "it": "(nessuna traduzione)"}

#: Parametro riservato: sceglie la sotto-voce (D40-6); non si inserisce nel testo.
REASON = "reason"

#: Segnaposto ``{nome}``; ``{{`` e ``}}`` sono le graffe scritte nel testo (es. ``${{...}}`` per ``${...}``).
_PLACEHOLDER = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}")
_TYPE_ABBREVIATIONS = {"str": "string", "num": "number", "int": "integer", "bool": "boolean", "qty": "quantity",
                       "list": "list", "obj": "object", "msg": "message", "msgs": "messages"}


@dataclass(frozen=True)
class Param:
    """Parametro atteso di un messaggio; ``external``: testo di terzi, inserito tale e quale senza tradurlo."""

    name: str
    type: str = "string"
    external: bool = False


@dataclass(frozen=True)
class Variant:
    """Sotto-voce scelta da ``reason`` (D40-6): testi propri e parametri propri (quelli della voce se non diversi)."""

    en: str
    it: str
    params: tuple[Param, ...]


@dataclass(frozen=True)
class Entry:
    """Voce del catalogo (§3.7.1): ``code``, testi ``en``/``it``, parametri attesi, eventuali sotto-voci."""

    code: str
    en: str
    it: str
    params: tuple[Param, ...] = ()
    variants: Mapping[str, Variant] = field(default_factory=dict)

    def text(self, lang: str) -> str:
        return self.it if lang == "it" else self.en


#: Il catalogo: una sola tabella, riempita da ``_add`` in fondo al file.
CATALOG: dict[str, Entry] = {}


def _params(spec: str) -> tuple[Param, ...]:
    """``"nome[:tipo][!]"`` separati da spazi (``!`` = testo esterno); tipo: str, num, int, bool, qty, list, obj, msg
    (``msg`` = messaggio annidato di AstroTwo, ``msgs`` = elenco di messaggi annidati, D40-7)."""
    out = []
    for token in spec.split():
        external = token.endswith("!")
        name, _, kind = token.rstrip("!").partition(":")
        out.append(Param(name, _TYPE_ABBREVIATIONS[kind or "str"], external))
    return tuple(out)


def _add(code: str, en: str, it: str, params: str = "", **variants: tuple) -> None:
    """Aggiunge una voce; ``variants``: ``reason=(en, it)`` o ``reason=(en, it, "parametri")``.

    Una sotto-voce senza elenco proprio ha i parametri della voce; con l'elenco ha esattamente quelli.
    """
    if code in CATALOG:
        raise ValueError(f"codice {code} già presente nel catalogo")
    general = _params(params)
    built = {reason: Variant(item[0], item[1], _params(item[2]) if len(item) > 2 else general)
             for reason, item in variants.items()}
    CATALOG[code] = Entry(code, en, it, general, built)


def _extend(code: str, **variants: tuple) -> None:
    """Aggiunge sotto-voci a una voce già nel catalogo (codice condiviso tra moduli, D40-6): ``reason=(en, it[, params])``."""
    entry = CATALOG[code]
    for reason, item in variants.items():
        if reason in entry.variants:
            raise ValueError(f"{code}: ragione {reason} già presente")
        entry.variants[reason] = Variant(item[0], item[1], _params(item[2]) if len(item) > 2 else entry.params)


def entry_for(code: str) -> Entry | None:
    return CATALOG.get(code)


def has_message(code: str) -> bool:
    return code in CATALOG


def placeholders(text: str) -> frozenset[str]:
    """Nomi dei segnaposto ``{nome}`` di un testo."""
    return frozenset(name for name in _PLACEHOLDER.findall(text) if name)


def _is_quantity(value: object) -> bool:
    return isinstance(value, Mapping) and set(value) == {"value", "unit"}


def _render(value: object) -> str:
    """Valore inserito così com'è: testo tale e quale, numeri nella loro forma JSON, quantità = valore, spazio, unità."""
    if isinstance(value, str):
        return value
    if _is_quantity(value):
        return f"{_render(value['value'])} {_render(value['unit'])}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_render(v) for v in value) if value else "—"  # elenco vuoto: trattino
    return json.dumps(value, ensure_ascii=False)


def _is_message(value: object) -> bool:
    """Messaggio annidato (D40-7): ``{"code", "params", "text"}``, con ``params`` e ``text`` facoltativi."""
    return (isinstance(value, Mapping) and isinstance(value.get("code"), str) and set(value) <= {"code", "params", "text"}
            and isinstance(value.get("params") or {}, Mapping) and isinstance(value.get("text", ""), str))


def _is_messages(value: object) -> bool:
    """Elenco di messaggi annidati (D40-7)."""
    return isinstance(value, (list, tuple)) and all(_is_message(v) for v in value)


def _render_message(value: Mapping, name: str, lang: str, mask_external: bool, depth: int) -> str:
    """Messaggio annidato reso in modo ricorsivo; oltre ``MAX_MESSAGE_DEPTH`` il solo codice; senza voce (o di un
    modulo non convertito) il testo originale con la nota, ``<nome>`` se i parametri esterni sono mascherati."""
    code, params, text = value["code"], value.get("params") or {}, value.get("text")
    if depth > MAX_MESSAGE_DEPTH:
        return code
    entry = CATALOG.get(code)
    if entry is None or not _from_catalog_source(entry, params):
        return f"<{name}>" if mask_external else _fallback(code, text, lang)
    return message_text(code, params, lang, mask_external=mask_external, _depth=depth)


def _selected(entry: Entry, params: Mapping[str, object]) -> tuple[str, str, tuple[Param, ...]]:
    variant = entry.variants.get(params.get(REASON)) if isinstance(params.get(REASON), str) else None
    if variant is not None:
        return variant.en, variant.it, variant.params
    return entry.en, entry.it, entry.params


def message_text(code: str, params: Mapping[str, object] | None, lang: str, *, text: str | None = None,
                 mask_external: bool = False, _depth: int = 0) -> str:
    """Testo del messaggio ``code`` con ``params`` nella lingua ``lang`` (``en`` o ``it``).

    ``text``: testo originale del modulo, usato come ripiego (§3.7.2): codice senza voce, oppure messaggio senza
    ``params`` per una voce che ne richiede (sessioni scritte prima di D40-3); in tal caso si aggiunge la nota
    "(no translation)" / "(nessuna traduzione)". Un parametro atteso ma assente lascia il segnaposto ``{nome}`` e
    scrive una voce di log. ``mask_external``: i parametri ``external`` si sostituiscono con ``<nome>`` (testo
    consegnato all'IA, dove il testo esterno viaggia solo nei parametri, marcato come tale). I parametri di tipo
    ``message`` (D40-7) si rendono in modo ricorsivo, nella stessa lingua, fino a ``MAX_MESSAGE_DEPTH`` livelli.
    """
    lang = lang if lang in LANGUAGES else "en"
    params = {} if params is None else params
    entry = CATALOG.get(code)
    if entry is None:
        return _fallback(code, text, lang)
    en, it, declared = _selected(entry, params)
    if text is not None and not _from_catalog_source(entry, params):
        return _fallback(code, text, lang)
    external = {p.name for p in declared if p.external}
    nested = {p.name for p in declared if p.type == "message"}
    nested_list = {p.name for p in declared if p.type == "messages"}

    def fill(match: re.Match) -> str:
        name = match.group(1)
        if name is None:  # graffa scritta nel testo
            return match.group(0)[0]
        if name not in params:
            LOG.warning("messaggio %s: parametro %r assente", code, name)
            return match.group(0)
        if mask_external and name in external:
            return f"<{name}>"
        if name in nested and _is_message(params[name]):
            return _render_message(params[name], name, lang, mask_external, _depth + 1)
        if name in nested_list and _is_messages(params[name]):
            return "; ".join(_render_message(v, name, lang, mask_external, _depth + 1) for v in params[name]) or "—"
        return _render(params[name])

    return _PLACEHOLDER.sub(fill, it if lang == "it" else en)


def _from_catalog_source(entry: Entry, params: Mapping[str, object]) -> bool:
    """Falso per un messaggio senza ``params`` il cui codice ne richiede (parametri o ragione): viene da chi non è
    ancora convertito (altro modulo, interfaccia o sessione scritta prima di D40-3) e vale il testo originale."""
    return bool(params) or not (entry.variants or any(p.name != REASON for p in entry.params))


def uses_catalog(code: str, params: Mapping[str, object] | None) -> bool:
    """Vero se il testo del messaggio è quello del catalogo (voce presente, origine convertita, ``params`` conformi)."""
    entry = CATALOG.get(code)
    params = {} if params is None else params
    return entry is not None and _from_catalog_source(entry, params) and not validate_params(code, params)


def message_params(code: str, params: Mapping[str, object] | None) -> frozenset[str]:
    """Nomi dei parametri di tipo ``message`` o ``messages`` (messaggi annidati, D40-7), secondo la voce scelta."""
    entry = CATALOG.get(code)
    if entry is None:
        return frozenset()
    return frozenset(p.name for p in _selected(entry, {} if params is None else params)[2]
                     if p.type in ("message", "messages"))


def external_params(code: str, params: Mapping[str, object] | None) -> frozenset[str]:
    """Nomi dei parametri ``external`` (testo di terzi) del messaggio, secondo la voce o la sotto-voce scelta."""
    entry = CATALOG.get(code)
    if entry is None:
        return frozenset()
    return frozenset(p.name for p in _selected(entry, {} if params is None else params)[2] if p.external)


def _fallback(code: str, text: str | None, lang: str) -> str:
    """Codice senza voce: testo originale (o il codice) con la nota; mai una traduzione inventata (§3.7.2)."""
    return f"{code if text is None else text} {NO_TRANSLATION[lang]}"


_TYPE_CHECK = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "quantity": _is_quantity,
    "list": lambda v: isinstance(v, (list, tuple)),
    "object": lambda v: isinstance(v, Mapping),
    "message": _is_message,
    "messages": _is_messages,
}


def validate_params(code: str, params: Mapping[str, object] | None, _depth: int = 0) -> list[str]:
    """Problemi di ``params`` rispetto alla voce (mancanti, non dichiarati, di tipo sbagliato); vuoto se a posto.

    I messaggi annidati (D40-7) si controllano a loro volta, se hanno voce e ``params``; più profondi di
    ``MAX_MESSAGE_DEPTH`` sono un problema."""
    entry = CATALOG.get(code)
    if entry is None:
        return [f"{code}: nessuna voce nel catalogo"]
    params = {} if params is None else params
    _, _, declared = _selected(entry, params)
    expected = {p.name: p for p in declared}
    problems = []
    reason = params.get(REASON)
    if reason is not None and reason not in entry.variants:
        problems.append(f"{code}: reason {reason!r} senza sotto-voce")
    for name, param in expected.items():
        if name not in params:
            problems.append(f"{code}: parametro {name} assente")
        elif not _TYPE_CHECK[param.type](params[name]):
            problems.append(f"{code}: parametro {name} non è {param.type}: {params[name]!r}")
        elif param.type == "message":
            problems.extend(_validate_nested(code, name, params[name], _depth + 1))
        elif param.type == "messages":
            for item in params[name]:
                problems.extend(_validate_nested(code, name, item, _depth + 1))
    for name in params:
        if name not in expected and name != REASON:
            problems.append(f"{code}: parametro {name} non dichiarato")
    return problems


def _validate_nested(code: str, name: str, value: Mapping, depth: int) -> list[str]:
    """Problemi di un messaggio annidato: troppo profondo, o con voce e ``params`` non conformi. Senza voce, o di un
    modulo non convertito (senza ``params``), vale il testo originale e non c'è nulla da controllare."""
    if depth > MAX_MESSAGE_DEPTH:
        return [f"{code}: parametro {name} annidato oltre {MAX_MESSAGE_DEPTH} livelli"]
    entry = CATALOG.get(value["code"])
    params = value.get("params") or {}
    if entry is None or not _from_catalog_source(entry, params):
        return [] if value.get("text") else [f"{code}: parametro {name} senza voce né testo originale"]
    return [f"{code}.{name}: {p}" for p in validate_params(value["code"], params, depth)]


# --------------------------------------------------------------------------
# Voci del catalogo, per modulo (sprint 8b: 10, 11, 12)
# --------------------------------------------------------------------------


# --- Modulo 10: coordinate e WCS (``core/coordinates_wcs.py``) ---

_add("PIXEL_CONVENTION_UNKNOWN",
     "Pixel convention '{value}' is not allowed; allowed: {allowed}.",
     "Convenzione dei pixel '{value}' non ammessa; ammesse: {allowed}.", "value allowed:list")
_add("FRAME_UNSUPPORTED",
     "Frame '{frame}' is not supported; supported frames: {supported}.",
     "Frame '{frame}' non supportato; frame supportati: {supported}.", "frame supported:list",
     no_attribute=("Frame '{frame}' has no attribute {attribute}.",
                   "Il frame '{frame}' non ha l'attributo {attribute}.", "frame attribute"),
     conversion_failed=("Conversion {from_frame} → {to_frame} cannot be performed: {detail}",
                        "Conversione {from_frame} → {to_frame} non eseguibile: {detail}",
                        "from_frame to_frame detail!"),
     equatorial_required=("Propagation with pm_ra_cosdec/pm_dec needs an equatorial frame, not '{frame}'.",
                          "La propagazione con pm_ra_cosdec/pm_dec richiede un frame equatoriale, non '{frame}'.",
                          "frame"),
     not_for_view=("Frame '{frame}' is not allowed for a view; allowed: {allowed}.",
                   "Frame '{frame}' non ammesso per una vista; ammessi: {allowed}.", "frame allowed:list"),
     differs_from_coordinates=("Frame '{frame}' differs from the frame of the coordinates ({coordinates_frame}): "
                               "no conversion is done.",
                               "Il frame '{frame}' è diverso da quello delle coordinate ({coordinates_frame}): "
                               "nessuna conversione.", "frame coordinates_frame"),
     frame_required=("A frame is required when values are given.", "Con values serve il frame.", ""))
_add("EPOCH_REQUIRED",
     "An epoch is required: the epoch is never assumed.",
     "Serve un'epoca: l'epoca non si assume mai.",
     invalid_value=("{argument} '{value}' is not valid: use a Time object with a declared scale, a Julian year "
                    "(e.g. 2000.0) or an epoch such as 'J2000.0'/'B1950.0'.",
                    "{argument} '{value}' non valido: usare un oggetto Time con scala dichiarata, un anno giuliano "
                    "(es. 2000.0) o un'epoca come 'J2000.0'/'B1950.0'.", "argument value"),
     explicit_required=("Frame '{frame}' requires an explicit {attribute}: the epoch is never assumed.",
                        "Il frame '{frame}' richiede {attribute} esplicito: l'epoca non si assume mai.",
                        "frame attribute"),
     frame_default=("Frame '{frame}' has the default {attribute} of Astropy: the epoch is never assumed.",
                    "Il frame '{frame}' ha {attribute} di default di Astropy: l'epoca non si assume mai.",
                    "frame attribute"),
     not_time=("The epoch must be a Time object.", "L'epoca deve essere un oggetto Time.", ""),
     origin_unknown=("The origin epoch of the position is not known: the epoch is never assumed.",
                     "L'epoca di origine della posizione non è nota: l'epoca non si assume mai.", ""),
     missing_for_propagation=("{argument} is missing: it is needed for the propagation.",
                              "{argument} manca: serve per la propagazione.", "argument"),
     target_missing=("The target epoch is missing.", "Manca l'epoca di arrivo.", ""))
_add("COORD_UNIT_MISSING",
     "A value has no usable unit.", "Un valore non ha un'unità utilizzabile.",
     no_unit=("{argument} has no unit: no angle without a unit.",
              "{argument} senza unità: nessun angolo senza unità.", "argument"),
     not_angular=("{argument} is in unit {unit}, which is not angular.",
                  "{argument} in unità {unit}, che non è angolare.", "argument unit"),
     skycoord_required=("A SkyCoord with units and frame is required.",
                        "Serve un SkyCoord con unità e frame.", ""),
     skyframe_required=("{argument} must be a SkyFrame.", "{argument} deve essere uno SkyFrame.", "argument"),
     single_skyframe_required=("{argument} must be a SkyFrame with a single point.",
                               "{argument} deve essere uno SkyFrame con un solo punto.", "argument"),
     column_no_unit=("SIMBAD column '{column}' has no unit.", "La colonna SIMBAD '{column}' non ha unità.",
                     "column"),
     coordinates_required=("SkyFrame or SkyCoord coordinates are required.",
                           "Servono coordinate SkyFrame o SkyCoord.", ""),
     coords_or_values=("Give either coords or values (with frame and axis).",
                       "Dare coords oppure values (con frame e axis).", ""),
     axis_required=("With values, axis = 'lon' or 'lat' is required.",
                    "Con values serve axis = 'lon' o 'lat'.", ""))
_add("COORD_OUT_OF_RANGE",
     "A coordinate is out of range.", "Una coordinata è fuori intervallo.",
     not_finite=("The coordinates are not finite.", "Le coordinate non sono finite.", ""),
     latitude_range=("Latitude outside [-90°, +90°]: {values}.", "Latitudine fuori da [-90°, +90°]: {values}.",
                     "values:qty"),
     longitude_range=("Longitude outside [0°, 360°): {values}.", "Longitudine fuori da [0°, 360°): {values}.",
                      "values:qty"),
     parallax_not_positive=("The parallax is not positive: the distance is undefined.",
                            "La parallasse non è positiva: la distanza non è definita.", ""),
     fov_threshold_positive=("The field of view and the threshold must be positive.",
                             "Il campo di vista e la soglia devono essere positivi.", ""))
_add("NAME_NOT_FOUND",
     "'{name}' was not found in SIMBAD.", "'{name}' non trovato in SIMBAD.", "name",
     empty_name=("The name is empty.", "Il nome è vuoto.", ""),
     source_unsupported=("Source '{source}' is not provided: the only source is 'simbad'.",
                         "La fonte '{source}' non è prevista: l'unica fonte è 'simbad'.", "source"),
     ambiguous=("'{name}' is ambiguous in SIMBAD: no name was resolved approximately.",
                "'{name}' è ambiguo in SIMBAD: nessun nome risolto approssimativamente.", "name"),
     no_coordinates=("'{name}' is in SIMBAD but has no coordinates.",
                     "'{name}' è in SIMBAD ma senza coordinate.", "name"))
_add("NET_TIMEOUT",
     "{service} is not reachable for '{target}' (timeout {connect} connection, {read} read): {detail}",
     "{service} non raggiungibile per '{target}' (timeout {connect} connessione, {read} lettura): {detail}",
     "service target connect:qty read:qty detail!",
     url=("{url} is not reachable (timeout {connect} connection, {read} read): {detail}",
          "{url} non raggiungibile (timeout {connect} connessione, {read} lettura): {detail}",
          "url connect:qty read:qty detail!"))
_add("COORD_FORMAT_INVALID", "Sexagesimal angles cannot be read: {detail}",
     "Angoli sessagesimali non leggibili: {detail}", "detail!")
_add("PROPAGATION_MODE_CONFLICT",
     "proper_motion_only=True does not use parallax or radial velocity: do not pass them.",
     "proper_motion_only=True non usa parallasse né velocità radiale: non passarle.")
_add("WCS_INVALID",
     "The WCS is not valid.", "La WCS non è valida.",
     singular_matrix=("The pixel scale matrix is singular or not finite.",
                      "La matrice di scala dei pixel è singolare o non finita.", ""),
     not_coherent=("The WCS is not coherent: round trip at the centre beyond {tolerance}.",
                   "La WCS non è coerente: andata e ritorno al centro oltre {tolerance}.", "tolerance:qty"),
     cd_all_zero=("The CD matrix is all zero: the solution is not defined.",
                  "La matrice CD è tutta nulla: soluzione non definita.", ""),
     not_constructible=("The WCS cannot be built: {detail}", "WCS non costruibile: {detail}", "detail!"),
     pixel_shape_required=("pixel_shape (nx, ny) is required and must be positive.",
                           "pixel_shape (nx, ny) è obbligatorio e positivo.", ""),
     east_left_required=("east_left (direction of right ascension) must be declared: True or False.",
                         "east_left (verso dell'ascensione retta) va dichiarato: True o False.", ""),
     scale_not_positive=("The scale is not positive.", "La scala non è positiva.", ""),
     no_valid_pixels=("No pixel of the image has valid celestial coordinates.",
                      "Nessun pixel dell'immagine ha coordinate celesti valide.", ""),
     method_unknown=("Method '{method}' is not provided; methods: {allowed}.",
                     "Metodo '{method}' non previsto; metodi: {allowed}.", "method allowed:list"))
_add("WCS_MISSING",
     "No usable WCS.", "Nessuna WCS utilizzabile.",
     header_required=("A FITS header is required.", "Serve un header FITS.", ""),
     no_celestial_wcs=("The header does not contain a celestial WCS.",
                       "L'header non contiene una WCS celeste.", ""),
     not_celestial=("The WCS is not celestial.", "La WCS non è celeste.", ""),
     wcs_required=("A WCS is required (astropy.wcs.WCS or WcsSolution).",
                   "Serve una WCS (astropy.wcs.WCS o WcsSolution).", ""),
     cutout_center=("Cutout centred on celestial coordinates: the image has no WCS.",
                    "Taglio con centro in coordinate celesti: l'immagine non ha WCS.", ""),
     cutout_size=("Cutout side in angular units: the image has no WCS.",
                  "Lato del taglio in unità angolari: l'immagine non ha WCS.", ""),
     contours_sky=("Contours in celestial coordinates: the image has no WCS.",
                   "Contorni in coordinate celesti: l'immagine non ha WCS.", ""),
     resampling=("{operation}: resampling needs the astrometric calibration ({origin}).",
                 "{operation}: il ricampionamento richiede la calibrazione ({origin}).", "operation origin"),
     reference=("The reference must be an image with a WCS.", "Il riferimento deve essere un'immagine con WCS.", ""),
     rgb=("RGB: {origin} has no WCS, resampling needs the astrometric calibration.",
          "RGB: {origin} non ha WCS, il ricampionamento richiede la calibrazione.", "origin"),
     external_unavailable=("External calibration ({source}) is not available: {cause}",
                           "Calibrazione esterna ({source}) non disponibile: {cause}", "source cause!"),
     external_no_header=("External calibration ({source}) is not available: no header.",
                         "Calibrazione esterna ({source}) non disponibile: nessuna intestazione.", "source"),
     hhh_unreadable=("{name} cannot be read: {detail}", "{name} non leggibile: {detail}", "name detail!"),
     no_calibration=("No astrometric calibration: the image is a pixel grid.",
                     "Nessuna calibrazione astrometrica: l'immagine è una griglia di pixel.", ""),
     calibration_invalid_header=("The calibration ({kind}) was discarded: it is not a valid FITS header.",
                                 "Calibrazione ({kind}) scartata: non è un'intestazione FITS valida.", "kind"),
     calibration_size_differs=("The calibration ({kind}) was discarded: NAXIS1/NAXIS2 = {naxis1}/{naxis2}, image "
                               "{nx}×{ny}.",
                               "Calibrazione ({kind}) scartata: NAXIS1/NAXIS2 = {naxis1}/{naxis2}, immagine "
                               "{nx}×{ny}.", "kind naxis1 naxis2 nx:int ny:int"),
     celestial_axes=("The celestial axes {celestial_axes} are not the two useful axes {useful_axes}.",
                     "Gli assi celesti {celestial_axes} non sono i due assi utili {useful_axes}.",
                     "celestial_axes:list useful_axes:list"),
     image_without_wcs=("{origin}: no WCS, no position on the sky.",
                        "{origin}: nessuna WCS, nessuna posizione sul cielo.", "origin"))
_add("WCS_LEGACY_UNSUPPORTED",
     "The historical {legacy} solution is not translated by the library.",
     "La soluzione storica {legacy} non è tradotta dalla libreria.", "legacy",
     library_failed=("The historical {legacy} solution is not supported by the library: {detail}",
                     "Soluzione storica {legacy} non supportata dalla libreria: {detail}", "legacy detail!"))
_add("PROJECTION_UNSUPPORTED",
     "Projection '{projection}' is not supported; supported: {supported}.",
     "Proiezione '{projection}' non supportata; supportate: {supported}.", "projection supported:list",
     not_for_view_ncp=("{projection} is not allowed for a view: it is the historical form of SIN.",
                       "{projection} non ammessa per una vista: è la forma storica di SIN.", "projection"),
     not_for_view_zpn=("{projection} is not allowed for a view: it requires the PV2_m coefficients.",
                       "{projection} non ammessa per una vista: richiede i coefficienti PV2_m.", "projection"),
     not_for_view=("Projection '{projection}' is not allowed for a view; allowed: {allowed}.",
                   "Proiezione '{projection}' non ammessa per una vista; ammesse: {allowed}.",
                   "projection allowed:list"))
_add("PROJECTION_PARAMETERS_MISSING",
     "ZPN requires the explicit PV2_m coefficients: they are not fitted and not assumed.",
     "ZPN richiede i coefficienti PV2_m espliciti: non si adattano e non si assumono.")
_add("CALIB_INCONSISTENT",
     "At the centre of the field the solution departs from the TAN by {deviation} "
     "(limit {factor} × TAN RMS = {limit}).",
     "Al centro del campo la soluzione si scosta dalla TAN di {deviation} "
     "(limite {factor} × RMS TAN = {limit}).", "deviation:qty factor:num limit:qty")
_add("CALIB_TOO_FEW_STARS",
     "{n_stars} stars given, minimum {minimum} for projection {projection}.",
     "{n_stars} stelle date, minimo {minimum} per la proiezione {projection}.", "n_stars:int minimum:int projection",
     count_mismatch=("The number of pixel positions ({pixel_positions}) differs from the number of sky positions "
                     "({sky_positions}).",
                     "Il numero di posizioni pixel ({pixel_positions}) è diverso da quello delle posizioni "
                     "celesti ({sky_positions}).", "pixel_positions:int sky_positions:int"))
_add("CALIB_FIT_FAILED", "The fit did not succeed: {detail}", "Adattamento non riuscito: {detail}", "detail!")
_add("CALIB_RESIDUALS_TOO_LARGE",
     "RMS {rms} (threshold {rms_threshold}), maximum {maximum} (threshold {maximum_threshold}); worst stars "
     "(index): {worst_indices}, residuals: {worst_residuals}.",
     "RMS {rms} (soglia {rms_threshold}), massimo {maximum} (soglia {maximum_threshold}); stelle peggiori "
     "(indice): {worst_indices}, residui: {worst_residuals}.",
     "rms:qty rms_threshold:qty maximum:qty maximum_threshold:qty worst_indices:list worst_residuals:qty")
_add("GRID_SPACING_INVALID",
     "The grid spacing is not valid.", "Il passo della griglia non è valido.",
     no_angular_unit=("{argument} has no angular unit.", "{argument} senza unità angolare.", "argument"),
     out_of_range=("{argument} must be in (0°, 360°]; given {value}.",
                   "{argument} deve essere in (0°, 360°]; dato {value}.", "argument value:qty"),
     target_lines=("target_lines must be an integer ≥ 1.", "target_lines deve essere un intero ≥ 1.", ""),
     both_or_none=("Give both spacings or none (automatic choice).",
                   "Dare entrambi i passi oppure nessuno (scelta automatica).", ""),
     samples=("At least 2 samples per line are needed; given {samples_per_line}.",
              "Servono almeno 2 campioni per linea; dati {samples_per_line}.", "samples_per_line:int"))
_add("VIEW_PARAMETERS_INVALID",
     "The view parameters are not valid.", "I parametri della vista non sono validi.",
     shape=("shape must be (rows, columns), integers ≥ 1; given {shape}.",
            "shape deve essere (righe, colonne), interi ≥ 1; dato {shape}.", "shape"),
     scale_unit=("scale must be an angle per pixel with a unit (e.g. 1 * u.arcsec).",
                 "scale deve essere un angolo per pixel con unità (es. 1 * u.arcsec).", ""),
     scale_positive=("scale must be positive and finite.", "scale deve essere positiva e finita.", ""),
     center_skyframe=("center must be a SkyFrame (coordinates with frame and unit).",
                      "center deve essere uno SkyFrame (coordinate con frame e unità).", ""),
     base_exclusive=("With base, projection, frame and tangent_point are not given.",
                     "Con base non si danno projection, frame né tangent_point.", ""),
     projection_required=("Without base, projection is required.", "Senza base serve projection.", ""),
     tangent_skyframe=("tangent_point must be a SkyFrame.", "tangent_point deve essere uno SkyFrame.", ""),
     center_outside_projection=("The centre falls outside the projection of the base.",
                                "Il centro cade fuori dalla proiezione della base.", ""),
     geometry_required=("A ViewGeometry from make_view_wcs is required.",
                        "Serve una ViewGeometry di make_view_wcs.", ""),
     max_bar_pixels=("max_bar_pixels must be an integer ≥ 1.", "max_bar_pixels deve essere un intero ≥ 1.", ""))
_add("FORMAT_PRECISION_INVALID",
     "The precision is not valid.", "La precisione non è valida.",
     decimal_needs_angle=("In decimal style the precision must be an angle, not {unit}.",
                          "Nello stile decimal la precisione è un angolo, non {unit}.", "unit"),
     ra_unit=("The precision of the right ascension needs a time or angular unit, not {unit}.",
              "La precisione dell'ascensione retta richiede un'unità di tempo o angolare, non {unit}.", "unit"),
     unit_unsuitable=("Unit {unit} is not suitable for the precision of the axis '{axis}'.",
                      "L'unità {unit} non è adatta alla precisione dell'asse '{axis}'.", "axis unit"),
     not_positive=("The precision must be positive.", "La precisione deve essere positiva.", ""),
     style_unknown=("Unknown style '{style}'; styles: {allowed}.", "Stile '{style}' sconosciuto; stili: {allowed}.",
                    "style allowed:list"),
     separators_unknown=("Unknown separators '{separators}'; separators: {allowed}.",
                         "Separatori '{separators}' sconosciuti; separatori: {allowed}.",
                         "separators allowed:list"),
     no_unit=("The precision must have a unit (e.g. 10 * u.arcmin).",
              "La precisione deve avere un'unità (es. 10 * u.arcmin).", ""))
_add("NORTH_UNDEFINED",
     "The north direction is not defined.", "La direzione del nord non è definita.",
     center_outside=("The centre of the window is outside the projection.",
                     "Il centro della finestra è fuori dalla proiezione.", ""),
     pole_near=("The pole of frame '{frame}' is within δ = {delta} of the centre.",
                "Il polo del frame '{frame}' è a meno di δ = {delta} dal centro.", "frame delta:qty"),
     direction_outside=("The direction is outside the projection.", "La direzione è fuori dalla proiezione.", ""))
_add("SCALE_BAR_TOO_LONG",
     "Even {step} is longer than {max_bar_pixels} pixels of the window.",
     "Anche {step} supera {max_bar_pixels} pixel della finestra.", "step:qty max_bar_pixels:int")
_add("OUT_OF_FIELD", "Some points are outside the field of the image.",
     "Alcuni punti sono fuori dal campo dell'immagine.")


# --- Modulo 11: immagini e FITS (``core/images_fits.py``) ---

_add("FITS_UNREADABLE",
     "The FITS file cannot be read: {path}", "Il file FITS non è leggibile: {path}", "path",
     file_unreadable=("The file cannot be read: {path} ({detail})", "File non leggibile: {path} ({detail})",
                      "path detail!"),
     fits_unreadable=("The FITS cannot be read: {path} ({detail})", "FITS non leggibile: {path} ({detail})",
                      "path detail!"),
     file_missing=("The file does not exist: {path}", "File inesistente: {path}", "path"),
     data_unreadable=("{path}: the data cannot be read ({detail})", "{path}: dati non leggibili ({detail})",
                      "path detail!"))
_add("FORMAT_UNSUPPORTED",
     "Format not recognised; supported formats: {supported}.",
     "Formato non riconosciuto; formati supportati: {supported}.", "supported:list",
     gzip_unreadable=("The gzip file cannot be read: {detail}", "File gzip non leggibile: {detail}", "detail!"))
_add("HDU_CHOICE_REQUIRED",
     "More than one HDU can be opened: say which one.", "Più HDU possono essere aperte: indicare quale.",
     rgb=("{path}: {count} HDUs with 3 planes, say which one.", "{path}: {count} HDU con 3 piani, indicare quale.",
          "path count:int"),
     images=("{path}: {count} image HDUs, say which one to open: {hdus}",
             "{path}: {count} HDU immagine, indicare quale aprire: {hdus}", "path count:int hdus:list"))
_add("HDU_NOT_IMAGE",
     "The HDU is not an image.", "L'HDU non è un'immagine.",
     no_such_hdu=("HDU '{hdu}' does not exist.", "L'HDU '{hdu}' non esiste.", "hdu"),
     no_image_hdu=("{path}: no image HDU.", "{path}: nessuna HDU immagine.", "path"),
     no_such_hdu_listed=("HDU '{hdu}' does not exist; image HDUs: {hdus}",
                         "L'HDU '{hdu}' non esiste; HDU immagine: {hdus}", "hdu hdus:list"),
     not_an_image=("HDU '{hdu}' is not an image; image HDUs: {hdus}",
                   "L'HDU '{hdu}' non è un'immagine; HDU immagine: {hdus}", "hdu hdus:list"))
_add("CUBE_NOT_SUPPORTED",
     "Cubes are not handled here.", "I cubi non si trattano qui.",
     only_cubes=("{path}: only cubes (3 or more useful axes): they go to module 23.",
                 "{path}: solo cubi (3 o più assi utili): vanno al modulo 23.", "path"),
     hdu_is_cube=("HDU '{hdu}': cube (3 or more useful axes), module 23.",
                  "HDU '{hdu}': cubo (3 o più assi utili), modulo 23.", "hdu"))
_add("RGB_INPUT_INVALID",
     "The RGB input is not valid.", "L'ingresso RGB non è valido.",
     no_rgb_hdu=("{path}: no HDU with 3 planes for rgb=True.", "{path}: nessuna HDU con 3 piani per rgb=True.",
                 "path"),
     hdu_not_rgb=("HDU '{hdu}': rgb=True needs exactly 3 planes.", "HDU '{hdu}': rgb=True richiede esattamente 3 piani.",
                  "hdu"),
     monochrome_required=("{operation}: a monochrome image is required.", "{operation}: serve un'immagine monocroma.",
                          "operation"),
     monochrome_images_required=("Monochrome images (FitsImage) are required.",
                                 "Servono immagini monocrome (FitsImage).", ""),
     mode_unknown=("Mode '{mode}': allowed are 'rgb' and 'rgb_diff'.", "Modalità '{mode}': ammesse 'rgb' e 'rgb_diff'.",
                   "mode"),
     image_count=("{count} images for {mode}: 2 or 3 are needed (2 for rgb_diff).",
                  "{count} immagini per {mode}: servono 2 o 3 (2 per rgb_diff).", "count:int mode"),
     wavelengths=("wavelengths: one wavelength (Quantity) per image.",
                  "wavelengths: una lunghezza d'onda (Quantity) per immagine.", ""),
     display_required=("rgb: (vmin, vmax, transfer function) are needed for each component.",
                       "rgb: servono (vmin, vmax, funzione di trasferimento) per ogni componente.", ""))
_add("CUTOUT_OUT_OF_RANGE",
     "The cutout is outside the image.", "Il taglio è fuori dall'immagine.",
     region=("Region x {x0}:{x1}, y {y0}:{y1} is outside the image {nx}×{ny}.",
             "La regione x {x0}:{x1}, y {y0}:{y1} è fuori dall'immagine {nx}×{ny}.",
             "x0:int x1:int y0:int y1:int nx:int ny:int"),
     outside=("The cutout is entirely outside the image (centre {center}).",
              "Il taglio è del tutto fuori dall'immagine (centro {center}).", "center"),
     invalid=("The cutout is not valid (centre {center}): {detail}", "Taglio non valido (centro {center}): {detail}",
              "center detail!"))
_add("IMAGE_SHAPE_MISMATCH",
     "The images are not on the same grid: resample first.",
     "Le immagini non sono sulla stessa griglia: ricampionare prima.",
     planes=("Planes on different grids: {shapes}; resample first (P7).",
             "Piani di griglie diverse: {shapes}; ricampionare prima (P7).", "shapes:list"),
     sizes=("Different sizes {shape_a} and {shape_b}: resample first (P7).",
            "Dimensioni diverse {shape_a} e {shape_b}: ricampionare prima (P7).", "shape_a shape_b"),
     grids=("Different grids (WCS): resample first (P7).", "Griglie (WCS) diverse: ricampionare prima (P7).", ""))
_add("UNIT_MISMATCH",
     "The units differ.", "Le unità sono diverse.",
     operands=("Different units: {unit_a} and {unit_b}.", "Unità diverse: {unit_a} e {unit_b}.", "unit_a unit_b"),
     rgb_diff=("rgb_diff: different units {unit_a} and {unit_b}.", "rgb_diff: unità diverse {unit_a} e {unit_b}.",
               "unit_a unit_b"),
     mosaic=("Mosaic: different units {units}.", "Mosaico: unità diverse {units}.", "units:list"))
_add("OPERATION_UNSUPPORTED",
     "The operation is not supported.", "L'operazione non è supportata.",
     color_image=("{operation}: colour images are for presentation only.",
                  "{operation}: le immagini a colori sono solo di presentazione.", "operation"),
     flip_distortion=("Flipping a WCS with distortions (SIP, TPD, tables) is not supported.",
                      "La specchiatura di un WCS con distorsioni (SIP, TPD, tabelle) non è supportata.", ""),
     operation_unknown=("Operation '{operation}' is not provided; list: {allowed}.",
                        "Operazione '{operation}' non prevista; elenco: {allowed}.", "operation allowed:list"),
     operand_required=("{operation}: an image or a constant is required.",
                       "{operation}: serve un'immagine o una costante.", "operation"),
     kernel_required=("convolve: an astropy.convolution kernel (Kernel2D) is required.",
                      "convolve: serve un kernel di astropy.convolution (Kernel2D).", ""),
     no_operands=("{operation} takes no operands.", "{operation} non ha operandi.", "operation"),
     normalization_undefined=("Normalisation is not defined: mean of the finite pixels = {mean}.",
                              "Normalizzazione non definita: media dei pixel finiti = {mean}.", "mean:num"),
     resampling_method_unknown=("Resampling method '{method}' is not provided; methods: {allowed}.",
                                "Metodo di ricampionamento '{method}' non previsto; metodi: {allowed}.",
                                "method allowed:list"),
     build_method=("Method '{method}' is not provided; allowed: {allowed} (flux is not available on the HEALPix "
                   "grid of the tiles).",
                   "Metodo '{method}' non previsto; ammessi: {allowed} (flux non disponibile sulla griglia HEALPix "
                   "dei tile).", "method allowed:list"),
     build_color_image=("{origin}: colour image, for presentation only.",
                        "{origin}: immagine a colori, solo presentazione.", "origin"))
_add("DISPLAY_OPTION_UNKNOWN",
     "{option} '{value}' is not allowed; allowed: {allowed}.",
     "{option} '{value}' non ammesso; ammessi: {allowed}.", "option value allowed:list")
_add("DISPLAY_METHOD_UNKNOWN",
     "Unknown method '{method}' (allowed: {allowed}).", "Metodo '{method}' sconosciuto (ammessi: {allowed}).",
     "method allowed:list")
_add("DISPLAY_LIMITS_UNDEFINED",
     "No display limits can be proposed.", "Nessun limite di visualizzazione può essere proposto.",
     no_finite_pixels=("No finite pixel: no limits proposed.", "Nessun pixel finito: nessun limite proposto.", ""),
     constant=("Constant image (value {value}): no limits proposed, the user chooses them.",
               "Immagine costante (valore {value}): nessun limite proposto, li sceglie l'utente.", "value:num"))
_add("MEMORY_LIMIT_EXCEEDED",
     "{operation}: about {needed} are needed, above the operation limit of {limit} (D11-11); use a cutout, a region "
     "or higher thresholds.",
     "{operation}: servono circa {needed}, oltre il limite delle operazioni di {limit} (D11-11); usare un taglio, "
     "una regione o soglie più alte.", "operation needed:qty limit:qty",
     build_hips=("build_hips: about {needed} are needed, above the operation limit of {limit} (D11-11).",
                 "build_hips: servono circa {needed}, oltre il limite delle operazioni di {limit} (D11-11).",
                 "needed:qty limit:qty"))
_add("PREVIEW_NOT_MEASURABLE",
     "{operation}: the image is open at two levels and the data in memory are only the preview (step "
     "{preview_step}); use read_region or a cutout on the original pixels.",
     "{operation}: l'immagine è aperta a due livelli e i dati in memoria sono solo l'anteprima (passo "
     "{preview_step}); usare read_region o un taglio sui pixel originali.", "operation preview_step:int",
     build_hips=("{origin}: the image is open at two levels and only the preview is in memory.",
                 "{origin}: aperta a due livelli, in memoria c'è solo l'anteprima.", "origin"))
_add("COMPRESSION_UNSUPPORTED",
     "{path}: compression {compression} cannot be read ({detail})",
     "{path}: compressione {compression} non leggibile ({detail})", "path compression detail!")
_add("IMAGE_UNREADABLE",
     "{path}: the image cannot be decoded ({detail})", "{path}: immagine non decodificabile ({detail})",
     "path detail!")
_add("PIXEL_RAW_UNAVAILABLE",
     "The raw pixel value is not available.", "Il valore grezzo del pixel non è disponibile.",
     not_fits=("{format} image: no raw FITS value.", "Immagine {format}: nessun valore grezzo FITS.", "format"),
     color_image=("Colour image: presentation only.", "Immagine a colori: solo presentazione.", ""),
     derived=("Derived image ({history}): the pixels are no longer those of the file.",
              "Immagine derivata ({history}): i pixel non sono più quelli del file.", "history:list"),
     position=("Position ({x}, {y}): integer indices inside the image {nx}×{ny} (numpy convention) are needed.",
               "Posizione ({x}, {y}): servono indici interi dentro l'immagine {nx}×{ny} (convenzione numpy).",
               "x y nx:int ny:int"),
     unreadable=("{origin}: the raw value cannot be read ({detail})",
                 "{origin}: valore grezzo non leggibile ({detail})", "origin detail!"))
_add("CENTROID_OUT_OF_IMAGE",
     "The window or annulus is outside the image {nx}×{ny}.", "La finestra o la corona è fuori dall'immagine {nx}×{ny}.",
     "nx:int ny:int",
     window_and_annulus=("Window x {x0}..{x1}, y {y0}..{y1} or annulus of radius {radius} is outside the image "
                         "{nx}×{ny}.",
                         "La finestra x {x0}..{x1}, y {y0}..{y1} o la corona di raggio {radius} è fuori "
                         "dall'immagine {nx}×{ny}.", "x0:int x1:int y0:int y1:int radius:qty nx:int ny:int"))
_add("CENTROID_UNDEFINED",
     "The centroid is not defined.", "Il centroide non è definito.",
     non_finite_window=("Non-finite pixels in the centroid window.", "Pixel non finiti nella finestra del centroide.",
                        ""),
     no_background_pixels=("No finite pixel in the background annulus.",
                           "Nessun pixel finito nella corona del fondo.", ""),
     no_flux=("The sum of the weights is ≤ 0 after background subtraction: no star in the window.",
              "La somma dei pesi è ≤ 0 dopo la sottrazione del fondo: nessuna stella nella finestra.", ""))
_add("EXTERNAL_CALIBRATION_IGNORED",
     "External calibration ({source}) ignored: the image has its own.",
     "Calibrazione esterna ({source}) ignorata: l'immagine ha la propria.", "source")
_add("EXTERNAL_CALIBRATION_USED",
     "External astrometric calibration: {source}", "Calibrazione astrometrica esterna: {source}", "source")
_add("STRATEGY",
     "{strategy}: the image is opened with this strategy because of its size.",
     "{strategy}: l'immagine è aperta con questa strategia per la sua dimensione.", "strategy",
     compressed=("{strategy}: compressed file of {size} decompressed, above {limit}.",
                 "{strategy}: file compresso di {size} decompressi, oltre {limit}.", "strategy size:qty limit:qty"),
     scaled_keywords=("{strategy}: {size}, memmap impossible with {keywords} (astropy.io.fits).",
                      "{strategy}: {size}, memmap impossibile con {keywords} (astropy.io.fits).",
                      "strategy size:qty keywords:list"),
     over_memory=("{strategy}: {size}, above {limit}: read from disk on demand.",
                  "{strategy}: {size}, oltre {limit}: letti dal disco su richiesta.", "strategy size:qty limit:qty"),
     over_two_level=("{strategy}: {size}, above {limit}.", "{strategy}: {size}, oltre {limit}.",
                     "strategy size:qty limit:qty"))
_add("AXES_DROPPED",
     "FITS axes of length 1 removed: {axes}.", "Assi FITS di lunghezza 1 tolti: {axes}.", "axes:list")
_add("NONFINITE_PIXELS",
     "Non-finite pixels.", "Pixel non finiti.",
     excluded=("Non-finite pixels (NaN/inf): excluded from display and measurements, never replaced.",
               "Pixel non finiti (NaN/inf): esclusi da display e misure, mai sostituiti.", ""),
     operation_result=("{operation}: the result has non-finite pixels (e.g. division by zero).",
                       "{operation}: il risultato ha pixel non finiti (es. divisione per zero).", "operation"))
_add("ALPHA_DROPPED", "Alpha channel of mode {mode} discarded.", "Canale alfa del modo {mode} scartato.", "mode")
_add("FRAMES", "{frames} frames: the first was read.", "{frames} fotogrammi: letto il primo.", "frames:int")
_add("HHH_IGNORED", "{name} ignored: the calibration in the file comment applies.",
     "{name} ignorato: vale la calibrazione nel commento del file.", "name")
_add("HHH_WCS_DIFFERS",
     "{name} describes a WCS different from the one in the comment (used): {differences}",
     "{name} descrive un WCS diverso da quello del commento (usato): {differences}", "name differences")
_add("FROM_CACHE",
     "Copy from the cache.", "Copia dalla cache.",
     network_unavailable=("Network not available ({error}): copy from the cache.",
                          "Rete non disponibile ({error}): copia in cache.", "error"),
     cached_url=("Copy of the URL from the cache, downloaded on {retrieved_at}.",
                 "Copia in cache dell'URL, scaricata il {retrieved_at}.", "retrieved_at"),
     cached_tile=("Copy of {url} from the cache, downloaded on {retrieved_at}.",
                  "Copia in cache di {url}, scaricata il {retrieved_at}.", "url retrieved_at"))
_add("UNIT_UNKNOWN",
     "The unit of the result cannot be determined from {unit_a} and {unit_b}.",
     "Unità del risultato non determinabile da {unit_a} e {unit_b}.", "unit_a unit_b")
_add("CUTOUT_TRIMMED",
     "Cutout trimmed to the intersection with the image: {shape} instead of {requested_shape}.",
     "Taglio ridotto all'intersezione con l'immagine: {shape} invece di {requested_shape}.", "shape requested_shape")


# --- Modulo 12: HiPS (``core/hips.py``) ---
# Le voci già presenti per altri moduli (NET_TIMEOUT, WCS_MISSING, OPERATION_UNSUPPORTED, PREVIEW_NOT_MEASURABLE,
# MEMORY_LIMIT_EXCEEDED, FROM_CACHE) hanno qui le loro sotto-voci aggiunte sopra. Testi esterni (``!``): righe del
# file properties, risposte dei servizi, diagnosi annidate di altri moduli (``mdfiles/12-core-hips.md`` §10).

_add("HIPS_NOT_A_SERVICE",
     "The address is not a HiPS service.", "L'indirizzo non è un servizio HiPS.",
     bad_line=("{source}: line {line} is not in the form 'key = value' of the HiPS 1.0 standard: {content}",
               "{source}: riga {line} non è nella forma 'chiave = valore' dello standard HiPS 1.0: {content}",
               "source line:int content!"),
     no_properties=("{source}: no HiPS property.", "{source}: nessuna proprietà HiPS.", "source"),
     service_error=("{url}: {cause}; it is not a HiPS service.", "{url}: {cause}; non è un servizio HiPS.",
                    "url cause:msg"),
     not_utf8=("{url}: the response is not UTF-8, so it is not a HiPS properties file ({detail}).",
               "{url}: risposta non UTF-8, non è un file properties HiPS ({detail}).", "url detail!"),
     no_mandatory_keys=("{url}: none of the mandatory keys of the HiPS 1.0 standard; it is not a HiPS service.",
                        "{url}: nessuna delle chiavi obbligatorie dello standard HiPS 1.0; non è un servizio HiPS.",
                        "url"),
     no_service_url=("{hips_id}: the collection has no HiPS service (hips_service_url missing in the MocServer).",
                     "{hips_id}: la collezione non ha un servizio HiPS (hips_service_url assente nel MocServer).",
                     "hips_id"))
_add("HIPS_METADATA_INVALID",
     "The HiPS metadata are not valid; nothing was added.",
     "I metadati HiPS non sono validi; nessuna voce aggiunta.",
     missing=("{source}: {field} is missing (mandatory key of the HiPS 1.0 standard); nothing was added.",
              "{source}: {field} mancante (chiave obbligatoria dello standard HiPS 1.0); nessuna voce aggiunta.",
              "source field"),
     not_integer=("{source}: {field} '{value}' is not an integer; nothing was added.",
                  "{source}: {field} '{value}' non è un intero; nessuna voce aggiunta.", "source field value!"),
     out_of_range=("{source}: {field} {value} is outside [{low}, {high}]; nothing was added.",
                   "{source}: {field} {value} fuori da [{low}, {high}]; nessuna voce aggiunta.",
                   "source field value:int low:int high:int"),
     below_minimum=("{source}: {field} {value} is below the minimum {low}; nothing was added.",
                    "{source}: {field} {value} sotto il minimo {low}; nessuna voce aggiunta.",
                    "source field value:int low:int"),
     not_number=("{source}: {field} '{value}' is not a number; nothing was added.",
                 "{source}: {field} '{value}' non è un numero; nessuna voce aggiunta.", "source field value!"),
     release_date=("{source}: hips_release_date '{value}' is not in the ISO 8601 form YYYY-mm-ddTHH:MMZ; nothing "
                   "was added.",
                   "{source}: hips_release_date '{value}' non è nella forma ISO 8601 YYYY-mm-ddTHH:MMZ; nessuna "
                   "voce aggiunta.", "source value!"),
     product_unknown=("{source}: dataproduct_type '{value}' is not provided by the HiPS 1.0 standard ({allowed}); "
                      "nothing was added.",
                      "{source}: dataproduct_type '{value}' non previsto dallo standard HiPS 1.0 ({allowed}); "
                      "nessuna voce aggiunta.", "source value! allowed:list"),
     tile_format=("{source}: hips_tile_format '{formats}': for {product} the allowed formats are {allowed}; nothing "
                  "was added.",
                  "{source}: hips_tile_format '{formats}': per {product} ammessi {allowed}; nessuna voce aggiunta.",
                  "source formats! product allowed:list"),
     tile_width_not_power_of_two=("{source}: hips_tile_width {width} is not a power of 2; nothing was added.",
                                  "{source}: hips_tile_width {width} non è una potenza di 2; nessuna voce aggiunta.",
                                  "source width:int"),
     cube_depth_missing=("{source}: hips_cube_depth is missing (mandatory for cubes, HiPS 1.0 standard); nothing "
                         "was added.",
                         "{source}: hips_cube_depth mancante (obbligatoria per i cubi, standard HiPS 1.0); nessuna "
                         "voce aggiunta.", "source"),
     cube_first_frame=("{source}: hips_cube_firstframe {first} is beyond the depth {depth}; nothing was added.",
                       "{source}: hips_cube_firstframe {first} oltre la profondità {depth}; nessuna voce aggiunta.",
                       "source first:int depth:int"),
     metadata_xml_unavailable=("{url}: {cause}; metadata.xml is required for HiPS catalogues (standard §4.4.3).",
                               "{url}: {cause}; metadata.xml è richiesto per i cataloghi HiPS (standard §4.4.3).",
                               "url cause:msg"),
     metadata_xml_unreadable=("{url}: the VOTable cannot be read ({detail}).",
                              "{url}: VOTable non leggibile ({detail}).", "url detail!"))
_add("HIPS_UNKNOWN",
     "The HiPS identifier '{hips_id}' is unknown.", "L'identificativo HiPS '{hips_id}' è sconosciuto.", "hips_id",
     mocserver=("The identifier '{hips_id}' is unknown to the MocServer.",
                "L'identificativo '{hips_id}' è sconosciuto al MocServer.", "hips_id"),
     not_listed=("The survey '{hips_id}' is not in the list; known: {known}.",
                 "Il survey '{hips_id}' non è in elenco; noti: {known}.", "hips_id known:list"),
     not_listed_empty=("The survey '{hips_id}' is not in the list; the list is empty.",
                       "Il survey '{hips_id}' non è in elenco; l'elenco è vuoto.", "hips_id"))
_add("HEALPIX_ORDER_INVALID",
     "HEALPix order {value}: an integer in [0, {high}] is required.",
     "Ordine HEALPix {value}: serve un intero in [0, {high}].", "value high:int",
     service_maximum=("Order {value} (service maximum {high}): an integer in [0, {high}] is required.",
                      "Ordine {value} (massimo del servizio {high}): serve un intero in [0, {high}].",
                      "value high:int"),
     tile_width=("Order {value} (with tiles of {tile_width} pixels): an integer in [0, {high}] is required.",
                 "Ordine {value} (con tile da {tile_width} pixel): serve un intero in [0, {high}].",
                 "value high:int tile_width:int"),
     plus_tile_bits=("Order {order} + log2({width}) is beyond {maximum}.",
                     "Ordine {order} + log2({width}) oltre {maximum}.", "order:int width:int maximum:int"))
_add("HEALPIX_INDEX_INVALID",
     "Index {index} at order {order}: an integer in [0, {maximum}] is required.",
     "Indice {index} all'ordine {order}: serve un intero in [0, {maximum}].", "index order:int maximum:int")
_add("HIPS_FRAME_UNSUPPORTED",
     "The hips_frame '{frame}' is not supported.", "Il hips_frame '{frame}' non è supportato.", "frame",
     ecliptic=("hips_frame '{frame}': the HiPS 1.0 standard does not say which ecliptic (D12-7: not supported until "
               "verified on a real HiPS).",
               "hips_frame '{frame}': lo standard HiPS 1.0 non precisa quale eclittica (D12-7: non supportato "
               "finché non è verificato su un HiPS reale).", "frame"),
     planetary=("hips_frame '{frame}': planetary frame; planetary positions arrive with module 19.",
                "hips_frame '{frame}': frame planetario: le posizioni planetarie arrivano con il modulo 19.",
                "frame"),
     moc_planetary=("{hips_id}: body {body}; the IVOA MOC is ICRS, the coverage of planetary HiPS comes with "
                    "module 19.",
                    "{hips_id}: corpo {body}; il MOC IVOA è ICRS, copertura dei HiPS planetari con il modulo 19.",
                    "hips_id body"),
     coverage_planetary=("{hips_id}: body {body}; the coverage of planetary HiPS comes with module 19.",
                         "{hips_id}: corpo {body}; copertura dei HiPS planetari con il modulo 19.", "hips_id body"))
_add("REGION_INVALID",
     "The region is not valid.", "La regione non è valida.",
     radius=("Radius {radius}: an angle with a unit in (0°, 180°] is required.",
             "Raggio {radius}: serve un angolo con unità in (0°, 180°].", "radius"),
     center_not_single=("The centre of the field must be a single position.",
                        "Il centro del campo è una sola posizione.", ""),
     conversion_center=("Centre of the field: {detail}", "Centro del campo: {detail}", "detail:msg"),
     conversion_positions=("Positions: {detail}", "Posizioni: {detail}", "detail:msg"),
     conversion_window=("Pixels of the window: {detail}", "Pixel della finestra: {detail}", "detail:msg"))
_add("HIPS_OUT_OF_COVERAGE",
     "Outside the coverage of the survey: no tile.", "Fuori dalla copertura del survey: nessun tile.",
     field=("The field is outside the coverage of the service ({outside} tiles outside): no tile.",
            "Campo fuori dalla copertura del servizio ({outside} tile fuori): nessun tile.", "outside:int"),
     tile=("{hips_id}: tile {index} at order {order} is outside the coverage of the service; no tile.",
           "{hips_id}: tile {index} all'ordine {order} fuori dalla copertura del servizio; nessun tile.",
           "hips_id index:int order:int"))
_add("HIPS_TYPE_MISMATCH",
     "The operation does not apply to this type of HiPS.", "L'operazione non vale per questo tipo di HiPS.",
     catalog_no_pixels=("{hips_id}: catalogues have no pixels.", "{hips_id}: i cataloghi non hanno pixel.",
                        "hips_id"),
     catalog_tiles=("{hips_id}: catalogue HiPS, the tiles are read as tables.",
                    "{hips_id}: HiPS catalogo, i tile si leggono come tabelle.", "hips_id"),
     not_a_cube=("{hips_id}: not a HiPS cube ({dataproduct_type}).",
                 "{hips_id}: non è un cubo HiPS ({dataproduct_type}).", "hips_id dataproduct_type"),
     not_a_catalog=("{hips_id}: not a HiPS catalogue ({dataproduct_type}).",
                    "{hips_id}: non è un catalogo HiPS ({dataproduct_type}).", "hips_id dataproduct_type"))
_add("SERVICE_ERROR",
     "The service answered with an error.", "Il servizio ha risposto con un errore.",
     http_status=("{url}: HTTP response {status} {status_text}", "{url}: risposta HTTP {status} {status_text}",
                  "url status:int status_text!"),
     unreadable_response=("{url}: the response cannot be read ({detail}).", "{url}: risposta non leggibile ({detail}).",
                          "url detail!"))
_add("HIPS_FORMAT_UNAVAILABLE",
     "{hips_id}: format '{format}' is not offered; formats: {offered}.",
     "{hips_id}: formato '{format}' non offerto; formati {offered}.", "hips_id format offered:list")
_add("HIPS_TILE_MISSING",
     "{url}: tile not provided by the service (HTTP 404; the standard allows partial trees and omitted low orders).",
     "{url}: tile non fornito dal servizio (HTTP 404; lo standard ammette alberi parziali e ordini bassi omessi).",
     "url")
_add("HIPS_BAD_TILE",
     "The tile is corrupt.", "Il tile è corrotto.",
     tile_corrupt=("{url}: tile corrupt even after a new request ({problem}).",
                   "{url}: tile corrotto anche dopo una nuova richiesta ({problem}).", "url problem:msg"),
     file_corrupt=("{url}: file not valid even after a new request ({problem}).",
                   "{url}: file non valido anche dopo una nuova richiesta ({problem}).", "url problem:msg"),
     value_not_conformant=("{hips_id}: value '{value}' of column {column} does not conform to type {datatype} "
                           "({detail}).",
                           "{hips_id}: valore '{value}' della colonna {column} non conforme al tipo {datatype} "
                           "({detail}).", "hips_id value! column! datatype! detail!"))
_add("HIPS_CUBE_PLANE_INVALID",
     "The plane of the cube does not exist.", "Il piano del cubo non esiste.",
     not_a_cube=("{hips_id}: not a cube, no plane {plane}.", "{hips_id}: non è un cubo, nessun piano {plane}.",
                 "hips_id plane"),
     out_of_range=("{hips_id}: plane {plane} does not exist; available planes 0–{last_plane} ({depth}).",
                   "{hips_id}: piano {plane} inesistente; piani disponibili 0–{last_plane} ({depth}).",
                   "hips_id plane depth:int last_plane:int"))
_add("HIPS_PIXEL_UNAVAILABLE",
     "The pixel value is not available.", "Il valore del pixel non è disponibile.",
     not_fits=("{url}: the pixel value is read only from FITS tiles, not from a {format} tile (copy for display).",
               "{url}: il valore del pixel si legge solo dai tile FITS, non da un tile {format} (copia per la "
               "visualizzazione).", "url format"),
     no_fits_tiles=("{hips_id}: no FITS tiles (formats {formats}); the pixel value is not available.",
                    "{hips_id}: nessun tile FITS (formati {formats}); il valore del pixel non è disponibile.",
                    "hips_id formats:list"))
_add("HIPS_OUT_OF_TILE",
     "The position is outside the given tile.", "La posizione è fuori dal tile dato.",
     positions=("{count} positions outside tile {index} (order {order}).",
                "{count} posizioni fuori dal tile {index} (ordine {order}).", "count:int index:int order:int"),
     order_mismatch=("Tile at order {tile_order}, sampling at order {sampling_order}.",
                     "Tile all'ordine {tile_order}, campionamento all'ordine {sampling_order}.",
                     "tile_order:int sampling_order:int"),
     no_window_pixels=("Tile {index} contains no pixel of the window.",
                       "Il tile {index} non contiene pixel della finestra.", "index:int"))
_add("MOCSERVER_UNAVAILABLE",
     "The MocServer is not reachable.", "Il MocServer non è raggiungibile.",
     resolve=("The MocServer is not reachable to resolve '{hips_id}': {cause}",
              "MocServer non raggiungibile per risolvere '{hips_id}': {cause}", "hips_id cause:msg"),
     index=("The MocServer is not reachable and there is no local copy of the collections: {cause}",
            "MocServer non raggiungibile e nessuna copia locale delle collezioni: {cause}", "cause:msg"),
     coverage=("Coverage of {hips_id}: {cause}", "Copertura di {hips_id}: {cause}", "hips_id cause:msg"),
     local_copy=("The MocServer is not reachable: local copy of the collections of {retrieved_at}.",
                 "MocServer non raggiungibile: copia locale delle collezioni del {retrieved_at}.", "retrieved_at"))
_add("HIPS_DISPLAY_REQUIRED",
     "PNG/JPEG tiles: (vmin, vmax, transfer function) must be given explicitly.",
     "Tile PNG/JPEG: servono (vmin, vmax, funzione di trasferimento) espliciti.")
_add("HIPS_DISPLAY_INVALID",
     "The display parameters are not valid.", "I parametri di visualizzazione non sono validi.",
     stretch=("Transfer function '{stretch}': allowed {allowed} (histeq depends on the tile).",
              "Funzione di trasferimento '{stretch}': ammesse {allowed} (histeq dipende dal tile).",
              "stretch allowed:list"),
     limits=("vmin < vmax is required, both finite.", "Serve vmin < vmax, entrambi finiti.", ""))
_add("HIPS_DISPLAY_UNKNOWN",  # sollevato dal visualizzatore del 41 (messaggi propri del 41: sprint 8e)
     "The colour limits of the survey are not known: FITS tiles are not drawn.",
     "Limiti di colore del survey non noti: i tile FITS non si disegnano.",
     no_limits=("The colour limits of the survey are not known: FITS tiles are not drawn.",
                "Limiti di colore del survey non noti: i tile FITS non si disegnano.", ""),
     reopen=("{hips_id}: the colour limits of the survey are not known, FITS tiles are not drawn; reopen the survey "
             "giving vmin and vmax.",
             "{hips_id}: limiti di colore del survey non noti, i tile FITS non si disegnano; riaprire il survey "
             "indicando vmin e vmax.", "hips_id"))
_add("HIPS_EMPTY",
     "No valid pixel was resampled: no tile written.", "Nessun pixel valido ricampionato: nessun tile scritto.")

# Avvisi
_add("BODY_UNKNOWN",
     "The body cannot be derived: the data open on their own.",
     "Corpo non ricavabile: il dato si apre da solo.",
     no_hips_body=("{source}: hips_frame '{frame}' is not celestial and there is no hips_body: the body cannot be "
                   "derived, the data open on their own.",
                   "{source}: hips_frame '{frame}' non celeste e senza hips_body: corpo non ricavabile, il dato si "
                   "apre da solo.", "source frame"),
     body_differs=("{source}: hips_frame '{frame}' and hips_body '{body}' differ: the body cannot be derived, the "
                   "data open on their own.",
                   "{source}: hips_frame '{frame}' e hips_body '{body}' diversi: corpo non ricavabile, il dato si "
                   "apre da solo.", "source frame body"))
_add("HIPS_BODY_DRAFT",
     "{source}: body '{body}' from hips_body, defined in the HiPS 2.0 Working Draft (2026-05-01), a version that is "
     "not yet an IVOA recommendation.",
     "{source}: corpo '{body}' da hips_body, definito nel Working Draft HiPS 2.0 (2026-05-01), versione non ancora "
     "raccomandazione IVOA.", "source body")
_add("BODY_UNSUPPORTED",
     "{source}: {detail} (name table of module 19, D12-6): the data open on their own.",
     "{source}: {detail} (tabella dei nomi del 19, D12-6): il dato si apre da solo.", "source detail!")
_add("BODY_NORMALIZED",
     "{source}: hips_body '{body}' → '{canonical}' (name table of module 19, D12-6).",
     "{source}: hips_body '{body}' → '{canonical}' (tabella dei nomi del modulo 19, D12-6).",
     "source body canonical")
_add("HIPS_DEFAULT_TILE_WIDTH",
     "{source}: hips_tile_width is missing, {width} pixels (default of the HiPS 1.0 standard).",
     "{source}: hips_tile_width assente, {width} pixel (default dello standard HiPS 1.0).", "source width:int")
_add("HIPS_VERSION_UNKNOWN",
     "{source}: hips_version '{version}'; the HiPS 1.0 standard writes '{standard}': properties read according to "
     "HiPS 1.0.",
     "{source}: hips_version '{version}'; lo standard HiPS 1.0 scrive '{standard}': proprietà lette secondo "
     "HiPS 1.0.", "source version standard")
_add("HIPS_ID_MISMATCH",
     "Requested identifier '{requested}', creator_did of the service '{service_id}': the service's one applies.",
     "Identificativo richiesto '{requested}', creator_did del servizio '{service_id}': vale quello del servizio.",
     "requested service_id")
_add("HIPS_ALREADY_LISTED",
     "{hips_id} is already in the list (read from {origin} on {retrieved_at}); refresh=True to read it again.",
     "{hips_id} già in elenco (letto da {origin} il {retrieved_at}); refresh=True per rileggerlo.",
     "hips_id origin retrieved_at")
_add("HIPS_COVERAGE_NOT_CHECKED",
     "hips_frame '{frame}': the MOC of the service is in ICRS, coverage filter not applied.",
     "hips_frame '{frame}': il MOC del servizio è in ICRS, filtro di copertura non applicato.", "frame")
_add("HIPS_RESOLUTION_LIMIT",
     "{hips_id}: requested resolution {resolution} is beyond that of the service; maximum order {max_order}.",
     "{hips_id}: risoluzione richiesta {resolution} oltre quella del servizio; ordine massimo {max_order}.",
     "hips_id resolution:qty max_order:int")
_add("HIPS_TILE_DISCARDED",
     "A corrupt tile was discarded.", "Un tile corrotto è stato scartato.",
     cache_corrupt=("The cached copy of {url} is corrupt ({problem}): discarded, new request.",
                    "Copia in cache di {url} corrotta ({problem}): scartata, nuova richiesta.", "url problem:msg"),
     tile_corrupt=("{url}: tile corrupt ({problem}), discarded.", "{url}: tile corrotto ({problem}), scartato.",
                   "url problem:msg"),
     cache_invalid=("The cached copy of {url} is not valid ({problem}): new request.",
                    "Copia in cache di {url} non valida ({problem}): nuova richiesta.", "url problem:msg"),
     file_invalid=("{url}: file not valid ({problem}), discarded.", "{url}: file non valido ({problem}), scartato.",
                   "url problem:msg"))
_add("HIPS_TILE_PROBLEM",  # diagnosi, solo come messaggio annidato (D40-7) di HIPS_BAD_TILE e HIPS_TILE_DISCARDED
     "The tile or file has a problem.", "Il tile o il file ha un problema.",
     no_data=("no data in the FITS", "nessun dato nel FITS", ""),
     fits_unreadable=("FITS not readable ({detail})", "FITS non leggibile ({detail})", "detail!"),
     size_mismatch=("size {shape} instead of {width}×{width}", "dimensione {shape} invece di {width}×{width}",
                    "shape:list width:int"),
     format_mismatch=("format {found} instead of {expected}", "formato {found} invece di {expected}",
                      "found expected"),
     image_unreadable=("image not readable ({detail})", "immagine non leggibile ({detail})", "detail!"),
     not_utf8=("not UTF-8 ({detail})", "non UTF-8 ({detail})", "detail!"),
     no_header=("no header row", "nessuna riga di intestazione", ""),
     columns_mismatch=("columns {header} differ from metadata.xml {expected}",
                       "colonne {header} diverse da metadata.xml {expected}", "header! expected!"),
     bad_row=("row {line}: {fields} fields instead of {expected}", "riga {line}: {fields} campi invece di {expected}",
              "line:int fields:int expected:int"))
_add("HIPS_COVERAGE_UNKNOWN",
     "The coverage is not known.", "Copertura non nota.",
     moc_missing=("{url}: MOC of the service is missing (optional for the standard); coverage not known.",
                  "{url}: MOC del servizio assente (facoltativo per lo standard); copertura non nota.", "url"),
     unavailable=("{hips_id}: coverage not available ({cause_code}: {cause}).",
                  "{hips_id}: copertura non disponibile ({cause_code}: {cause}).", "hips_id cause_code cause:msg"))
_add("HIPS_COVERAGE_FROM_MOCSERVER",
     "{hips_id}: coverage from the MocServer ({url}), the service does not provide Moc.fits.",
     "{hips_id}: copertura dal MocServer ({url}), il servizio non fornisce Moc.fits.", "hips_id url")
_add("HIPS_DEFAULT_SURVEY",
     "Default survey {survey} (D12-3).", "Survey di default {survey} (D12-3).", "survey")
_add("HIPS_CUBE_UNIT_UNKNOWN",
     "The unit of the cube axis is not known: axis without unit.", "Unità dell'asse del cubo ignota: asse senza unità.",
     not_fits_unit=("{source}: data_cube_bunit3 '{unit}' is not a FITS unit: axis without unit.",
                    "{source}: data_cube_bunit3 '{unit}' non è un'unità FITS: asse senza unità.", "source unit"),
     missing=("{source}: data_cube_bunit3 is missing: axis without unit.",
              "{source}: data_cube_bunit3 assente: asse senza unità.", "source"))
_add("HIPS_CUBE_AXIS_INCOMPLETE",
     "{source}: incomplete data_cube_* keys, physical axis not computed.",
     "{source}: chiavi data_cube_* incomplete, asse fisico non calcolato.", "source")
_add("HIPS_UNIT_MIXED",
     "Different units among the images ({units}): BUNIT not written.",
     "Unità diverse tra le immagini ({units}): BUNIT non scritto.", "units:list")
_add("HIPS_ALLSKY_NOT_WRITTEN",
     "Allsky file not written (optional in the standard; D12-8).",
     "File Allsky non scritto (facoltativo nello standard; D12-8).")


# --- Modulo 13: cataloghi e tabelle (``core/catalogs.py``) ---
# Codici condivisi con altri moduli: sotto-voci aggiunte alla voce esistente (``_extend``).

_extend("FORMAT_UNSUPPORTED",
        url_via_vo=("Tables from a URL go through module 14 (P6).", "Le tabelle da URL passano dal modulo 14 (P6).", ""),
        format_not_text=("format '{format}': allowed {allowed}.", "format '{format}': ammessi {allowed}.",
                         "format allowed:list"),
        xml_root=("{path}: XML with root '{root}'; formats: {formats}.",
                  "{path}: XML con radice '{root}'; formati: {formats}.", "path root! formats:list"),
        binary=("{path}: binary file not recognised; formats: {formats}.",
                "{path}: file binario non riconosciuto; formati: {formats}.", "path formats:list"),
        no_table=("{path}: no table in the file.", "{path}: nessuna tabella nel file.", "path"))
_extend("MEMORY_LIMIT_EXCEEDED",
        read_file=("Reading {path}: about {needed} are needed, above the operation limit of {limit}.",
                   "Lettura di {path}: servono circa {needed}, oltre il limite delle operazioni di {limit}.",
                   "path needed:qty limit:qty"),
        loaded_table=("Table {path}: about {needed} are needed, above the operation limit of {limit}.",
                      "Tabella {path}: servono circa {needed}, oltre il limite delle operazioni di {limit}.",
                      "path needed:qty limit:qty"),
        linked_data=("Linked data {url}: about {needed} are needed, above the operation limit of {limit}.",
                     "Dati collegati {url}: servono circa {needed}, oltre il limite delle operazioni di {limit}.",
                     "url! needed:qty limit:qty"),
        subset=("Subset: about {needed} are needed, above the operation limit of {limit}.",
                "Sottoinsieme: servono circa {needed}, oltre il limite delle operazioni di {limit}.",
                "needed:qty limit:qty"),
        calculated_column=("Calculated column '{name}': about {needed} are needed, above the operation limit of "
                           "{limit}.",
                           "Colonna calcolata '{name}': servono circa {needed}, oltre il limite delle operazioni di "
                           "{limit}.", "name needed:qty limit:qty"))
_extend("REGION_INVALID",
        radius_not_angle=("Radius {radius}: an angle with a unit is required.",
                          "Raggio {radius}: serve un angolo con unità.", "radius"),
        radius_range=("Radius {radius}: allowed in (0°, 180°].", "Raggio {radius}: ammesso in (0°, 180°].",
                      "radius:qty"))
_extend("BODY_UNKNOWN",
        table_body=("The body cannot be derived: the data are not overlaid or combined with others.",
                    "Corpo non ricavabile: il dato non si sovrappone né si combina con altri.", ""))
_extend("COORD_UNIT_MISSING",
        column_unit_required=("Column '{column}' has no unit: indicate unit (angular).",
                              "Colonna '{column}' senza unità: indicare unit (angolare).", "column!"),
        column_not_angular=("Column '{column}' is in unit {unit}, which is not angular.",
                            "Colonna '{column}' in unità {unit}, non angolare.", "column! unit!"))

_add("TABLE_UNREADABLE",
     "The table cannot be read.", "La tabella non è leggibile.",
     file_unreadable=("File not readable: {path} ({detail}).", "File non leggibile: {path} ({detail}).",
                      "path detail!"),
     votable_unreadable=("{path}: VOTable not readable ({detail}).", "{path}: VOTable non leggibile ({detail}).",
                         "path detail!"),
     table_unreadable=("{path}: {format} table not readable ({detail}).",
                       "{path}: tabella {format} non leggibile ({detail}).", "path format detail!"))
_add("FORMAT_AMBIGUOUS",
     "{path}: delimited text cannot be classified (rule of §3): indicate format ({formats}).",
     "{path}: testo delimitato non classificabile (regola di §3): indicare format ({formats}).", "path formats:list")
_add("FORMAT_DECLARED",
     "Format {format} indicated by the user, no recognition.",
     "Formato {format} indicato dall'utente, nessun riconoscimento.", "format")
_add("UNIT_UNRECOGNIZED",
     "Column '{column}': unit '{unit}' is not valid in FITS nor in VOUnit, not converted.",
     "Colonna '{column}': unità '{unit}' non valida in FITS né in VOUnit, non convertita.", "column! unit!")
_add("UNIT_DECLARED",
     "Column '{column}': unit {unit} declared by the user.", "Colonna '{column}': unità {unit} dichiarata dall'utente.",
     "column! unit")
_add("NO_COORD_COLUMNS",
     "There are no usable position columns.", "Non ci sono colonne di posizione utilizzabili.",
     not_found=("No position column from UCD or metadata: confirm with confirm_position_columns (suggestions from "
                "suggest_position_columns).",
                "Nessuna colonna di posizione da UCD o metadati: confermare con confirm_position_columns "
                "(suggerimenti da suggest_position_columns).", ""),
     multiple_pairs=("More pairs {lon_ucd}/{lat_ucd} without a single meta.main: no choice.",
                     "Più coppie {lon_ucd}/{lat_ucd} senza un'unica meta.main: nessuna scelta.", "lon_ucd lat_ucd"),
     column_missing=("Column '{column}' does not exist.", "La colonna '{column}' non esiste.", "column"),
     required=("No position column: confirm them first.", "Nessuna colonna di posizione: confermarle prima.", ""),
     schema_ambiguous=("Catalogue '{name}': no unique {ucd} column in the UCDs of TAP_SCHEMA (candidates, "
                       "pos.eq.ra: {candidates_ra}; pos.eq.dec: {candidates_dec}): region not applicable.",
                       "Catalogo '{name}': nessuna colonna {ucd} univoca negli UCD di TAP_SCHEMA (candidate, "
                       "pos.eq.ra: {candidates_ra}; pos.eq.dec: {candidates_dec}): regione non applicabile.",
                       "name ucd candidates_ra:list! candidates_dec:list!"),
     column_name_invalid=("Catalogue '{name}': column name not allowed '{column}'.",
                          "Catalogo '{name}': nome di colonna non ammesso '{column}'.", "name column!"))
_add("POSITIONS_FROM_MANGO",
     "Columns {lon}/{lat}: system {system} from the utype of the IVOA MANGO model ({utype}).",
     "Colonne {lon}/{lat}: sistema {system} dall'utype del modello IVOA MANGO ({utype}).",
     "lon! lat! system utype!",
     with_epoch=("Columns {lon}/{lat}: system {system}, epoch {epoch} from the utype of the IVOA MANGO model "
                 "({utype}).",
                 "Colonne {lon}/{lat}: sistema {system}, epoca {epoch} dall'utype del modello IVOA MANGO ({utype}).",
                 "lon! lat! system epoch! utype!"))
_add("FRAME_UNKNOWN",
     "The reference system is not known.", "Il sistema di riferimento non è noto.",
     undeclared=("Columns '{lon}'/'{lat}': reference system not declared.",
                 "Colonne '{lon}'/'{lat}': sistema di riferimento non dichiarato.", "lon! lat!"),
     ambiguous=("Columns '{lon}'/'{lat}': reference system not declared or not unique ({system}).",
                "Colonne '{lon}'/'{lat}': sistema di riferimento non dichiarato o non univoco ({system}).",
                "lon! lat! system!"),
     unsupported=("Frame '{frame}' is not supported; frames: {supported}.",
                  "Frame '{frame}' non supportato; frame: {supported}.", "frame supported:list"),
     positions_undeclared=("The reference system of the position columns is not declared.",
                           "Sistema delle colonne di posizione non dichiarato.", ""),
     service_undeclared=("Catalogue '{name}': the service does not declare the system of columns {lon}/{lat} with a "
                         "COOSYS ({system}): region not applicable.",
                         "Catalogo '{name}': il servizio non dichiara il sistema delle colonne {lon}/{lat} con un "
                         "COOSYS ({system}): regione non applicabile.", "name lon! lat! system!"),
     service_no_coosys=("Catalogue '{name}': the service does not declare the system of columns {lon}/{lat} with a "
                        "COOSYS (none): region not applicable.",
                        "Catalogo '{name}': il servizio non dichiara il sistema delle colonne {lon}/{lat} con un "
                        "COOSYS (nessuno): regione non applicabile.", "name lon! lat!"),
     no_equinox=("Catalogue '{name}': system {system} without equinox.",
                 "Catalogo '{name}': sistema {system} senza equinozio.", "name system!"))
_add("ECSV_POSITIONS_INVALID",
     "The A2POSITIONS metadata are not usable.", "I metadati A2POSITIONS non sono utilizzabili.",
     unusable=("A2POSITIONS metadata not usable: {meta}.", "Metadati A2POSITIONS non utilizzabili: {meta}.", "meta!"),
     differs=("A2POSITIONS ({lon}/{lat}) differs from the UCD columns ({ucd_lon}/{ucd_lat}): no choice.",
              "A2POSITIONS ({lon}/{lat}) diverso dalle colonne degli UCD ({ucd_lon}/{ucd_lat}): nessuna scelta.",
              "lon! lat! ucd_lon! ucd_lat!"))
_add("POSITIONS_FROM_ECSV",
     "Columns {lon}/{lat}, system {frame} from the ECSV metadata written by AstroTwo.",
     "Colonne {lon}/{lat}, sistema {frame} dai metadati ECSV scritti da AstroTwo.", "lon! lat! frame",
     equinox=("Columns {lon}/{lat}, system {frame} equinox {equinox} from the ECSV metadata written by AstroTwo.",
              "Colonne {lon}/{lat}, sistema {frame} equinozio {equinox} dai metadati ECSV scritti da AstroTwo.",
              "lon! lat! frame equinox!"),
     epoch=("Columns {lon}/{lat}, system {frame} epoch {epoch} from the ECSV metadata written by AstroTwo.",
            "Colonne {lon}/{lat}, sistema {frame} epoca {epoch} dai metadati ECSV scritti da AstroTwo.",
            "lon! lat! frame epoch!"),
     equinox_epoch=("Columns {lon}/{lat}, system {frame} equinox {equinox} epoch {epoch} from the ECSV metadata "
                    "written by AstroTwo.",
                    "Colonne {lon}/{lat}, sistema {frame} equinozio {equinox} epoca {epoch} dai metadati ECSV "
                    "scritti da AstroTwo.", "lon! lat! frame equinox! epoch!"))
_add("EPOCH_FROM_METADATA",
     "Columns {lon}/{lat}: epoch {epoch} declared in the metadata ({system}) kept after the confirmation (same "
     "columns and system).",
     "Colonne {lon}/{lat}: epoca {epoch} dichiarata nei metadati ({system}) conservata dopo la conferma (stesse "
     "colonne e sistema).", "lon! lat! epoch! system!")
_add("TABLE_TOO_LARGE",
     "{path}: {rows} rows, above the limit of {max_rows}.", "{path}: {rows} righe, oltre il tetto di {max_rows}.",
     "path rows:int max_rows:int")
_add("TABLE_CHOICE_REQUIRED",
     "Say which table to open.", "Indicare quale tabella aprire.",
     several=("{path}: more tables, indicate table ({tables}).", "{path}: più tabelle, indicare table ({tables}).",
              "path tables:list!"),
     missing=("{path}: table '{table}' does not exist ({tables}).", "{path}: tabella '{table}' inesistente ({tables}).",
              "path table tables:list!"))

_add("COLUMN_TYPE_UNSUPPORTED",
     "The column type is not supported for this operation.", "Il tipo di colonna non è supportato per l'operazione.",
     position_not_numeric=("Column '{column}' of type {dtype}: numeric values are required.",
                           "Colonna '{column}' di tipo {dtype}: servono valori numerici.", "column! dtype"),
     not_numeric=("Column '{column}' of type {dtype}: a numeric column is required.",
                  "Colonna '{column}' di tipo {dtype}: serve una colonna numerica.", "column! dtype"),
     column_missing=("Column '{column}' does not exist.", "La colonna '{column}' non esiste.", "column"),
     bins_required=("Histogram: bins is required (number or edges).", "Istogramma: bins obbligatorio (numero o bordi).",
                    ""),
     bins_invalid=("bins {bins}: a positive integer or increasing edges are required.",
                   "bins {bins}: serve un intero positivo o bordi crescenti.", "bins"),
     bins_edges=("bins: strictly increasing edges, at least two.", "bins: bordi strettamente crescenti, almeno due.",
                 ""),
     record_out_of_range=("Record {index} is outside 0…{last}.", "Record {index} fuori da 0…{last}.",
                          "index last:int"),
     selection_mask=("Selection: a boolean mask of {rows} values is required.",
                     "Selezione: serve una maschera booleana di {rows} valori.", "rows:int"),
     argument_column_missing=("{argument}: column '{column}' does not exist.",
                              "{argument}: la colonna '{column}' non esiste.", "argument column"),
     argument_not_numeric=("{argument}: column '{column}' is not numeric.",
                           "{argument}: la colonna '{column}' non è numerica.", "argument column!"),
     number_needed=("Column '{column}' of type {dtype}: a number is required.",
                    "Colonna '{column}' di tipo {dtype}: serve un numero.", "column! dtype"))
_add("PROPER_MOTION_MISSING",
     "The proper-motion columns are missing.", "Mancano le colonne del moto proprio.",
     column_missing=("{argument}: column '{column}' does not exist.", "{argument}: la colonna '{column}' non esiste.",
                     "argument column"),
     cosdec_required=("pm_ra_includes_cosdec is required (True or False): never assumed.",
                      "pm_ra_includes_cosdec obbligatorio (True o False): mai assunto.", ""))
_add("UNIT_INCOMPATIBLE",
     "The units are not compatible.", "Le unità non sono compatibili.",
     argument_unit=("{argument}: column '{column}' is in unit {unit}, {required} is required.",
                    "{argument}: colonna '{column}' in unità {unit}, serve {required}.",
                    "argument column! unit! required"),
     calculated_unrecognized=("Column '{column}': unit '{unit}' not recognised, no computation with unknown units.",
                              "Colonna '{column}': unità '{unit}' non riconosciuta, nessun calcolo con unità ignote.",
                              "column! unit!"),
     calculated_column=("Calculated column '{name}': {detail}", "Colonna calcolata '{name}': {detail}",
                        "name detail!"))
_add("COLUMN_NAME_EXISTS",
     "The column name is already present.", "Il nome della colonna è già presente.",
     propagation_columns=("Columns already present: {columns}.", "Colonne già presenti: {columns}.",
                          "columns:list!"),
     name_exists=("Column '{column}' already present: no overwriting.",
                  "Colonna '{column}' già presente: nessuna sovrascrittura.", "column!"))
_add("EPOCH_INVALID",
     "The epoch is not valid.", "L'epoca non è valida.",
     source_in_metadata=("The origin epoch is already in the metadata: source_epoch is not used.",
                         "L'epoca di origine è già nei metadati: source_epoch non si usa.", ""),
     several_epoch_columns=("More columns with UCD time.epoch {columns}: no choice.",
                            "Più colonne con UCD time.epoch {columns}: nessuna scelta.", "columns:list!"),
     epoch_column_unit=("Epoch column '{column}' is in unit {unit}: Julian years are required; otherwise "
                        "source_epoch.",
                        "Colonna d'epoca '{column}' in unità {unit}: servono anni giuliani; altrimenti source_epoch.",
                        "column! unit!"),
     source_missing=("The origin epoch is not in the metadata: indicate source_epoch (never assumed).",
                     "Epoca di origine non nei metadati: indicare source_epoch (mai assunta).", ""),
     target_required=("The target epoch is required.", "L'epoca di arrivo è obbligatoria.", ""),
     scale_required=("scale is required: a non-zero time interval (e.g. 1000 * u.yr).",
                     "scale obbligatoria: un intervallo di tempo non nullo (es. 1000 * u.yr).", ""),
     display_type=("display_positions: image_or_epoch of type {type} is not recognised (image with WCS, WCS of "
                   "module 10, epoch or None): no epoch assumed.",
                   "display_positions: image_or_epoch di tipo {type} non riconosciuto (immagine con WCS, WCS del 10, "
                   "epoca o None): nessuna epoca assunta.", "type"),
     time_objects=("start and end must be Time objects with a declared scale.",
                   "start ed end devono essere oggetti Time con scala dichiarata.", ""),
     empty_interval=("Empty interval: start > end.", "Intervallo vuoto: start > end.", ""),
     timesys_conflict=("Format and scale are already in the TIMESYS: do not pass them.",
                       "Formato e scala sono già nel TIMESYS: non si passano.", ""),
     timescale_unsupported=("Scale '{scale}' of the TIMESYS is not supported.",
                            "Scala '{scale}' del TIMESYS non supportata.", "scale!"),
     timeorigin_invalid=("timeorigin '{origin}' is not valid.", "timeorigin '{origin}' non valido.", "origin!"),
     timeorigin_units=("Column '{column}': with timeorigin, times with units are required.",
                       "Colonna '{column}': con timeorigin servono tempi con unità.", "column"),
     timesys_no_origin=("Column '{column}': TIMESYS without timeorigin and values not in years.",
                        "Colonna '{column}': TIMESYS senza timeorigin e valori non in anni.", "column"),
     format_scale_required=("Column '{column}' has no TIMESYS: time_format and scale are required (never assumed).",
                            "Colonna '{column}' senza TIMESYS: time_format e scale obbligatori (mai assunti).",
                            "column"),
     values_unreadable=("Column '{column}': values not readable as {time_format} ({detail}).",
                        "Colonna '{column}': valori non leggibili come {time_format} ({detail}).",
                        "column time_format detail!"))

_SEARCH_AT = " (character {position}): {expression}"
_SEARCH_AT_IT = " (carattere {position}): {expression}"


def _at(en: str, it: str, params: str = "") -> tuple[str, str, str]:
    """Sotto-voce di un'espressione con la posizione: ``(en, it, parametri)`` con ``position`` ed ``expression``."""
    return en + _SEARCH_AT, it + _SEARCH_AT_IT, ("position:int expression " + params).strip()


_add("EXPRESSION_INVALID",
     "The expression is not valid.", "L'espressione non è valida.",
     unclosed_name=_at("column name ${{...}} without '}}'", "nome di colonna ${{...}} senza '}}'"),
     unclosed_string=_at("string without closing quotes", "stringa senza virgolette di chiusura"),
     unexpected_symbol=_at("symbol '{symbol}' not provided", "simbolo '{symbol}' non previsto", "symbol"),
     expected_token=_at("expected {expected}, found '{found}'", "atteso {expected}, trovato '{found}'",
                        "expected found"),
     expected_token_end=_at("expected {expected}, found the end", "atteso {expected}, trovata la fine", "expected"),
     unexpected_token=_at("unexpected symbol '{found}'", "simbolo inatteso '{found}'", "found"),
     column_missing=_at("column '{column}' does not exist", "colonna '{column}' inesistente", "column"),
     abs_needs_column=_at("a column is needed after '|'", "dopo '|' serve una colonna"),
     no_text_columns=_at("text to search, but the table has no text columns",
                         "testo da cercare, ma la tabella non ha colonne di testo"),
     term_expected=_at("a term was expected, found '{found}'", "atteso un termine, trovato '{found}'", "found"),
     term_expected_end=_at("a term was expected, found the end", "atteso un termine, trovata la fine"),
     value_needed=_at("a value is needed after the operator", "dopo l'operatore serve un valore"),
     number_needed=_at("numeric column '{column}': a number is required", "colonna numerica '{column}': serve un numero",
                       "column!"),
     abs_text=_at("|{column}|: the absolute value only applies to numeric columns",
                  "|{column}|: il valore assoluto vale solo per le colonne numeriche", "column!"),
     text_operators=_at("text column '{column}': only = and != are allowed",
                        "colonna di testo '{column}': ammessi solo = e !=", "column!"),
     not_comparable=_at("column '{column}' of type {dtype} cannot be compared",
                        "colonna '{column}' di tipo {dtype} non confrontabile", "column! dtype"),
     empty=_at("empty expression", "espressione vuota"),
     not_string=("The expression must be a string.", "L'espressione deve essere una stringa.", "position:int"),
     prefix_needs_selection=("prefix '{prefix}': the current selection (selection) is required.",
                             "prefisso '{prefix}': serve la selezione corrente (selection).",
                             "position:int prefix"),
     selection_shape=("selection: a mask of {rows} values is required.",
                      "selection: serve una maschera di {rows} valori.", "position:int rows:int"))
_add("COLUMN_EXPRESSION_INVALID",
     "The column expression is not valid.", "L'espressione di colonna non è valida.",
     name_required=("The name of the column is required.", "Nome della colonna obbligatorio.", "position:int"),
     decimals_invalid=("decimals {decimals}: an integer ≥ 0 is required.", "decimals {decimals}: intero ≥ 0.",
                       "position:int decimals"),
     empty=("Empty expression.", "Espressione vuota.", "position:int"),
     power=_at("'**' not provided: the power is written '^'", "'**' non previsto: la potenza si scrive '^'"),
     unclosed_reference=_at("reference ${{...}} without '}}'", "riferimento ${{...}} senza '}}'"),
     column_missing=_at("column '{column}' does not exist", "colonna '{column}' inesistente", "column"),
     syntax=_at("invalid syntax", "sintassi non valida"),
     name_unknown=_at("name '{name}' not provided (columns as ${{name}}; constants {constants})",
                      "nome '{name}' non previsto (colonne come ${{nome}}; costanti {constants})",
                      "name constants:list"),
     function_unknown=_at("function '{function}' not provided", "funzione '{function}' non prevista", "function"),
     arity=_at("{function}: wrong number of arguments", "{function}: numero di argomenti errato", "function"),
     starred=_at("arguments with '*' not provided", "argomenti con '*' non previsti"),
     construct=_at("construct {construct} not provided", "costrutto {construct} non previsto", "construct"))
_add("PLOT_RULE_INVALID",
     "The drawing rule is not valid.", "La regola di disegno non è valida.",
     not_plotrule=("Rule {rule}: a PlotRule is required.", "Regola {rule}: serve un PlotRule.", "rule:int"),
     shape_unknown=("Rule {rule}: shape '{shape}' is not in the list ({allowed}).",
                    "Regola {rule}: forma '{shape}' fuori elenco ({allowed}).", "rule:int shape allowed:list"),
     color_invalid=("Rule {rule}: colour '{color}': #RRGGBB is required.",
                    "Regola {rule}: colore '{color}': serve #RRGGBB.", "rule:int color"),
     size_column=("Rule {rule}: size: numeric column '{column}' does not exist.",
                  "Regola {rule}: dimensione: colonna numerica '{column}' inesistente.", "rule:int column"),
     size_range=("Rule {rule}: size: vmin < vmax is required, both finite.",
                 "Regola {rule}: dimensione: serve vmin < vmax, entrambi finiti.", "rule:int"),
     size_positive=("Rule {rule}: size: size_min and size_max must be positive.",
                    "Regola {rule}: dimensione: size_min e size_max devono essere positivi.", "rule:int"),
     size_invalid=("Rule {rule}: size {size}: a positive number or a SizeScale is required.",
                   "Regola {rule}: dimensione {size}: serve un numero positivo o una SizeScale.", "rule:int size"),
     selection_prefix=("Rule {rule}: the selection of a rule does not allow the prefixes + and -.",
                       "Regola {rule}: la selezione di una regola non ammette i prefissi + e -.", "rule:int"))
_add("FILE_EXISTS", "{path}: already exists; use overwrite=True.", "{path}: esiste già; usare overwrite=True.", "path")
_add("INPLACE",
     "The given table was modified in place.", "La tabella data è stata modificata in posto.",
     subset=("Subset: {kept} records out of {total}: given table modified in place (inplace=True).",
             "Sottoinsieme: {kept} record su {total}: tabella data modificata in posto (inplace=True).",
             "kept:int total:int"),
     calculated=("Calculated column '{name}' = {expression}: given table modified.",
                 "Colonna calcolata '{name}' = {expression}: tabella data modificata.", "name! expression"),
     calculated_unit=("Calculated column '{name}' = {expression} [{unit}]: given table modified.",
                      "Colonna calcolata '{name}' = {expression} [{unit}]: tabella data modificata.",
                      "name! expression unit"))
_add("PROPER_MOTION_ROW_MISSING",
     "{missing} rows without proper motion (or position or epoch): propagated position missing, a null proper "
     "motion is never assumed.",
     "{missing} righe senza moto proprio (o posizione o epoca): posizione propagata mancante, mai moto proprio nullo "
     "assunto.", "missing:int")

_add("XML_UNSAFE",
     "{path}: dangerous XML construct ({construct}), nothing loaded.",
     "{path}: costrutto XML pericoloso ({construct}), nulla caricato.", "path construct")
_add("ASTRORES_UNREADABLE",
     "The ASTRORES file cannot be read.", "Il file ASTRORES non è leggibile.",
     xml_unreadable=("{path}: XML not readable ({detail}).", "{path}: XML non leggibile ({detail}).", "path detail!"),
     root_unexpected=("{path}: root '{root}', ASTRO expected.", "{path}: radice '{root}', attesa ASTRO.",
                      "path root!"),
     no_data=("{path}: DATA without CSV, TABLEDATA or LINK.", "{path}: DATA senza CSV, TABLEDATA o LINK.", "path"),
     row_fields=("{path}: row {row} with {values} values for {fields} fields.",
                 "{path}: riga {row} con {values} valori per {fields} campi.",
                 "path row:int values:int fields:int"),
     no_fields=("{path}: table {index} without FIELD.", "{path}: tabella {index} senza FIELD.", "path index:int"),
     duplicate_field=("{path}: two fields with the same name '{name}'.",
                      "{path}: due campi con lo stesso nome '{name}'.", "path name!"),
     link_no_content_type=("{path}: LINK without content-type: the format of the linked data cannot be guessed "
                           "(D13-17).",
                           "{path}: LINK senza content-type: il formato dei dati collegati non si indovina (D13-17).",
                           "path"),
     link_type_not_read=("{path}: LINK with content-type '{content_type}' not read; allowed: {allowed} (D13-17).",
                         "{path}: LINK con content-type '{content_type}' non letto; ammessi: {allowed} (D13-17).",
                         "path content_type! allowed:list"),
     link_header_absent=("{path}: LINK '{content_type}': the CSV reader of the module needs the row of column names "
                         "(header=absent, RFC 4180).",
                         "{path}: LINK '{content_type}': il lettore CSV del modulo vuole la riga dei nomi delle "
                         "colonne (header=absent, RFC 4180).", "path content_type!"),
     link_gref=("{path}: LINK with gref (GLU system): only LINKs with href are read (D13-17).",
                "{path}: LINK con gref (sistema GLU): si leggono solo i LINK con href (D13-17).", "path"),
     link_action=("{path}: LINK with action: only LINKs with href are read (D13-17).",
                  "{path}: LINK con action: si leggono solo i LINK con href (D13-17).", "path"),
     link_no_address=("{path}: LINK with no address: only LINKs with href are read (D13-17).",
                      "{path}: LINK con nessun indirizzo: si leggono solo i LINK con href (D13-17).", "path"),
     link_href_invalid=("{path}: LINK href '{href}': an http(s) URL is required (relative only in a document "
                        "downloaded from a URL).",
                        "{path}: LINK href '{href}': serve un URL http(s) (relativo solo in un documento scaricato da "
                        "URL).", "path href!"),
     link_needs_network=("{path}: data in an external LINK ({url}): the network and the cache of module 14 are "
                         "needed, use load_table (D13-17).",
                         "{path}: dati in un LINK esterno ({url}): servono la rete e la cache del modulo 14, usare "
                         "load_table (D13-17).", "path url!"),
     link_unreadable=("{path}: linked data {url} not readable as {format} (declared content-type): {cause}",
                      "{path}: dati collegati {url} non leggibili come {format} (content-type dichiarato): {cause}",
                      "path url! format cause:msg"),
     link_data_error=("{path}: linked data {url} not readable as {format} (declared content-type): {detail}",
                      "{path}: dati collegati {url} non leggibili come {format} (content-type dichiarato): {detail}",
                      "path url! format detail!"),
     link_conflict=("{path}: FIELD and linked data {url} do not match: {problems}",
                    "{path}: FIELD e dati collegati {url} non coincidono: {problems}",
                    "path url! problems:msgs"))
_add("ASTRORES_LINK_PROBLEM",  # diagnosi, solo come messaggio annidato (D40-7) di ASTRORES_UNREADABLE link_conflict
     "A FIELD and the linked data differ.", "Un FIELD e i dati collegati differiscono.",
     columns=("columns {linked} instead of the FIELDs {fields}", "colonne {linked} invece dei FIELD {fields}",
              "linked! fields!"),
     unit=("{name}: unit '{field_unit}' in the FIELD and '{linked_unit}' in the linked data",
           "{name}: unità '{field_unit}' nel FIELD e '{linked_unit}' nei dati collegati",
           "name! field_unit! linked_unit!"),
     ucd=("{name}: UCD '{field_ucd}' in the FIELD and '{linked_ucd}' in the linked data",
          "{name}: UCD '{field_ucd}' nel FIELD e '{linked_ucd}' nei dati collegati", "name! field_ucd! linked_ucd!"),
     numeric=("{name}: numeric FIELD ({datatype}) but linked data of type {dtype}",
              "{name}: FIELD numerico ({datatype}) ma dati collegati di tipo {dtype}", "name! datatype dtype"),
     boolean=("{name}: boolean FIELD but linked data of type {dtype}",
              "{name}: FIELD booleano ma dati collegati di tipo {dtype}", "name! dtype"))
_add("ASTRORES_LINK",
     "Data read from the LINK {url} as {format} (declared content-type '{content_type}').",
     "Dati letti dal LINK {url} come {format} (content-type dichiarato '{content_type}').",
     "url! format content_type!")
_add("ASTRORES_TYPE_MISMATCH",
     "The ASTRORES data differ from the declared type.", "I dati ASTRORES differiscono dal tipo dichiarato.",
     sexagesimal_hours=("Field '{field}': declared {datatype} but the data are sexagesimal; converted to degrees "
                        "(hours) with module 10, original text in '{text_column}'.",
                        "Campo '{field}': dichiarato {datatype} ma i dati sono sessagesimali; convertiti in gradi "
                        "(ore) con il modulo 10, testo originale in '{text_column}'.",
                        "field! datatype text_column!"),
     sexagesimal_degrees=("Field '{field}': declared {datatype} but the data are sexagesimal; converted to degrees "
                          "(degrees) with module 10, original text in '{text_column}'.",
                          "Campo '{field}': dichiarato {datatype} ma i dati sono sessagesimali; convertiti in gradi "
                          "(gradi) con il modulo 10, testo originale in '{text_column}'.",
                          "field! datatype text_column!"),
     not_numeric=("Field '{field}': declared {datatype} but the data are not numeric; read as text.",
                  "Campo '{field}': dichiarato {datatype} ma i dati non sono numerici; letto come testo.",
                  "field! datatype"),
     not_boolean=("Field '{field}': declared L but the data are not boolean; text.",
                  "Campo '{field}': dichiarato L ma i dati non sono booleani; testo.", "field!"))
_add("UCD1_TRANSLATED",
     "Field '{field}': UCD1 '{original}' translated into '{translated}' (IVOA recommendation on UCDs, §3.1 and "
     "appendix A).",
     "Campo '{field}': UCD1 '{original}' tradotto in '{translated}' (raccomandazione IVOA sugli UCD, §3.1 e "
     "appendice A).", "field! original! translated")
_add("ASTRORES_NONCONFORMING_REF",
     "Field '{field}': ref '{ref}' is not an IDREF (DTD): accepted as '{accepted}'.",
     "Campo '{field}': ref '{ref}' non è un IDREF (DTD): accettato come '{accepted}'.", "field! ref! accepted!")
_add("UCD1_NOT_TRANSLATED",
     "UCD1 outside the IVOA recommendation, not translated (D13-14b) in the fields {fields}: position columns to be "
     "confirmed with confirm_position_columns.",
     "UCD1 fuori dalla raccomandazione IVOA, non tradotti (D13-14b) nei campi {fields}: colonne di posizione da "
     "confermare con confirm_position_columns.", "fields:list!")

_add("CATALOG_UNKNOWN",
     "The catalogue is not known.", "Il catalogo non è noto.",
     invalid_id=("Catalogue identifier not valid: {catalog_id}.", "Identificativo di catalogo non valido: {catalog_id}.",
                 "catalog_id"),
     no_columns=("Catalogue '{name}' not found on {server}: no column in TAP_SCHEMA (the identifier of a table is "
                 "needed, e.g. \"I/355/gaiadr3\").",
                 "Catalogo '{name}' non trovato su {server}: nessuna colonna in TAP_SCHEMA (serve l'identificativo di "
                 "una tabella, es. \"I/355/gaiadr3\").", "name server"),
     no_columns_candidates=("Catalogue '{name}' not found on {server}: no column in TAP_SCHEMA (the identifier of a "
                            "table is needed, e.g. \"I/355/gaiadr3\"); tables of {server} that start with '{name}': "
                            "{candidates}.",
                            "Catalogo '{name}' non trovato su {server}: nessuna colonna in TAP_SCHEMA (serve "
                            "l'identificativo di una tabella, es. \"I/355/gaiadr3\"); tabelle di {server} che "
                            "cominciano con '{name}': {candidates}.", "name server candidates:list!"),
     no_columns_candidates_limited=("Catalogue '{name}' not found on {server}: no column in TAP_SCHEMA (the "
                                    "identifier of a table is needed, e.g. \"I/355/gaiadr3\"); tables of {server} "
                                    "that start with '{name}': {candidates} (list limited to {max_candidates}).",
                                    "Catalogo '{name}' non trovato su {server}: nessuna colonna in TAP_SCHEMA (serve "
                                    "l'identificativo di una tabella, es. \"I/355/gaiadr3\"); tabelle di {server} "
                                    "che cominciano con '{name}': {candidates} (elenco limitato a "
                                    "{max_candidates}).", "name server candidates:list! max_candidates:int"),
     not_found=("Catalogue '{catalog_id}' not found on {server}: {detail}",
                "Catalogo '{catalog_id}' non trovato su {server}: {detail}", "catalog_id server detail!"),
     not_found_candidates=("Catalogue '{catalog_id}' not found on {server}: {detail}; tables of {server} that start "
                           "with '{catalog_id}': {candidates}.",
                           "Catalogo '{catalog_id}' non trovato su {server}: {detail}; tabelle di {server} che "
                           "cominciano con '{catalog_id}': {candidates}.",
                           "catalog_id server detail! candidates:list!"),
     not_found_candidates_limited=("Catalogue '{catalog_id}' not found on {server}: {detail}; tables of {server} "
                                   "that start with '{catalog_id}': {candidates} (list limited to "
                                   "{max_candidates}).",
                                   "Catalogo '{catalog_id}' non trovato su {server}: {detail}; tabelle di {server} "
                                   "che cominciano con '{catalog_id}': {candidates} (elenco limitato a "
                                   "{max_candidates}).",
                                   "catalog_id server detail! candidates:list! max_candidates:int"))
_add("REGION_REQUIRED",
     "Catalogue '{catalog_id}': more than {max_rows} rows ({declared}); indicate a region with the "
     "region=(centre, radius) parameter, or allow_partial=True for the first rows.",
     "Catalogo '{catalog_id}': più di {max_rows} righe ({declared}); indicare una regione con il parametro "
     "region=(centro, raggio), oppure allow_partial=True per le prime righe.", "catalog_id max_rows:int declared:msg")
_add("REGION_TOO_LARGE",
     "Catalogue '{catalog_id}': more than {max_rows} rows in the region ({declared}); reduce the radius or use "
     "allow_partial=True.",
     "Catalogo '{catalog_id}': più di {max_rows} righe nella regione ({declared}); ridurre il raggio o usare "
     "allow_partial=True.", "catalog_id max_rows:int declared:msg")
_add("REGION",
     "Region: circle of radius {radius} around ({center_lon}, {center_lat}) in the system of the columns "
     "{lon}/{lat} ({system}, epoch of the positions not declared, from the service metadata; centre converted with "
     "module 10).",
     "Regione: cerchio di raggio {radius} attorno a ({center_lon}, {center_lat}) nel sistema delle colonne "
     "{lon}/{lat} ({system}, epoca delle posizioni non dichiarata, dai metadati del servizio; centro convertito con il "
     "modulo 10).", "lon! lat! system! center_lon:qty center_lat:qty radius:qty",
     equinox=("Region: circle of radius {radius} around ({center_lon}, {center_lat}) in the system of the columns "
              "{lon}/{lat} ({system} equinox {equinox}, epoch of the positions not declared, from the service "
              "metadata; centre converted with module 10).",
              "Regione: cerchio di raggio {radius} attorno a ({center_lon}, {center_lat}) nel sistema delle colonne "
              "{lon}/{lat} ({system} equinozio {equinox}, epoca delle posizioni non dichiarata, dai metadati del "
              "servizio; centro convertito con il modulo 10).",
              "lon! lat! system! equinox! center_lon:qty center_lat:qty radius:qty"),
     epoch=("Region: circle of radius {radius} around ({center_lon}, {center_lat}) in the system of the columns "
            "{lon}/{lat} ({system}, epoch of the positions {epoch}, from the service metadata; centre converted with "
            "module 10).",
            "Regione: cerchio di raggio {radius} attorno a ({center_lon}, {center_lat}) nel sistema delle colonne "
            "{lon}/{lat} ({system}, epoca delle posizioni {epoch}, dai metadati del servizio; centro convertito con il "
            "modulo 10).", "lon! lat! system! epoch! center_lon:qty center_lat:qty radius:qty"),
     equinox_epoch=("Region: circle of radius {radius} around ({center_lon}, {center_lat}) in the system of the "
                    "columns {lon}/{lat} ({system} equinox {equinox}, epoch of the positions {epoch}, from the "
                    "service metadata; centre converted with module 10).",
                    "Regione: cerchio di raggio {radius} attorno a ({center_lon}, {center_lat}) nel sistema delle "
                    "colonne {lon}/{lat} ({system} equinozio {equinox}, epoca delle posizioni {epoch}, dai metadati "
                    "del servizio; centro convertito con il modulo 10).",
                    "lon! lat! system! equinox! epoch! center_lon:qty center_lat:qty radius:qty"))
_add("PARTIAL_CATALOG",
     "allow_partial=True: only the first {max_rows} rows returned by the service, not the whole catalogue "
     "{catalog_id}.",
     "allow_partial=True: solo le prime {max_rows} righe restituite dal servizio, non tutto il catalogo "
     "{catalog_id}.", "max_rows:int catalog_id",
     in_region=("allow_partial=True: only the first {max_rows} rows returned by the service, not the whole "
                "catalogue {catalog_id} in the region.",
                "allow_partial=True: solo le prime {max_rows} righe restituite dal servizio, non tutto il catalogo "
                "{catalog_id} nella regione.", "max_rows:int catalog_id"))
_add("COLLECTION_SKIPPED",
     "Non-VizieR records excluded from the tree: {ids}", "Record non VizieR esclusi dall'albero: {ids}", "ids:list!",
     more=("Non-VizieR records excluded from the tree: {ids} …", "Record non VizieR esclusi dall'albero: {ids} …",
           "ids:list!"))
_add("POPULARITY_INVALID",
     "{count} records with a non-integer vizier_popularity: treated as absent.",
     "{count} record con vizier_popularity non intera: trattati come assenti.", "count:int")
_add("POPULARITY_MISSING",
     "{count} collections without vizier_popularity: after the others, in natural order.",
     "{count} collezioni senza vizier_popularity: dopo le altre, in ordine naturale.", "count:int")

# --- Modulo 14 (protocolli VO, sprint 8d) ----------------------------------------------------------------------
_ASYNC_HINT_EN = " — for long queries use tap_query(..., mode='async')"
_ASYNC_HINT_IT = " — per le interrogazioni lunghe usare tap_query(..., mode='async')"
_add("VOTABLE_INVALID",
     "The VOTable is not valid.", "Il VOTable non è valido.",
     not_votable=("{path}: not a VOTable ({cause})", "{path}: non è un VOTable ({cause})", "path cause:msg"),
     other_format=("{path}: not a VOTable (recognised content: {format})",
                   "{path}: non è un VOTable (contenuto riconosciuto: {format})", "path format"),
     malformed=("{path}: malformed VOTable ({cause})", "{path}: VOTable malformato ({cause})", "path cause:msg"),
     unreadable_response=("{url}: the response cannot be read as a VOTable ({detail})",
                          "{url}: risposta non leggibile come VOTable ({detail})", "url detail!"),
     datalink_columns=("{url}: DataLink document without the columns {missing}",
                       "{url}: documento DataLink senza le colonne {missing}", "url missing:list"),
     photometry_columns=("{url}: response without the columns {missing}", "{url}: risposta senza le colonne {missing}",
                         "url missing:list"))
_add("EXPORT_FORMAT_UNSUPPORTED",
     "Format '{format}': allowed {allowed}", "Formato '{format}': ammessi {allowed}", "format allowed:list")
_extend("NET_TIMEOUT",
        url_sync_tap=("{url} is not reachable (timeout {connect} connection, {read} read): {detail}"
                      + _ASYNC_HINT_EN,
                      "{url} non raggiungibile (timeout {connect} connessione, {read} lettura): {detail}"
                      + _ASYNC_HINT_IT, "url connect:qty read:qty detail!"),
        async_deadline=("{url}: maximum wait of {timeout} exceeded (phase {phase}); job aborted",
                        "{url}: attesa massima di {timeout} superata (fase {phase}); lavoro interrotto",
                        "url timeout:qty phase"))
_add("AUTH_REQUIRED",
     "{url}: the service asks for authentication (HTTP {status}); at level 1 only public services.",
     "{url}: il servizio chiede autenticazione (HTTP {status}); nel livello 1 solo servizi pubblici.",
     "url status:int")
_extend("SERVICE_ERROR",
        http_message=("{url}: HTTP {status}: {message}", "{url}: HTTP {status}: {message}", "url status:int message!"),
        http_message_async_hint=("{url}: HTTP {status}: {message}" + _ASYNC_HINT_EN,
                                 "{url}: HTTP {status}: {message}" + _ASYNC_HINT_IT, "url status:int message!"),
        http_no_votable=("{url}: HTTP response {status} without a VOTable",
                         "{url}: risposta HTTP {status} senza VOTable", "url status:int"),
        service_rejected=("{url}: the service rejected the request: {detail}",
                          "{url}: il servizio ha rifiutato la richiesta: {detail}", "url detail!"),
        request_failed=("{url}: {detail}", "{url}: {detail}", "url detail!"),
        job_phase=("{url}: job ended in phase {phase}", "{url}: lavoro terminato in fase {phase}", "url phase"),
        job_result_status=("{uri}: HTTP response {status}", "{uri}: risposta HTTP {status}", "uri status:int"),
        descriptor_missing=("Descriptor '{service_def}' is missing from the DataLink document.",
                            "Descrittore '{service_def}' assente dal documento DataLink.", "service_def!"),
        simbad_no_units=("SIMBAD: coordinates without a unit in the response.",
                         "SIMBAD: coordinate senza unità nella risposta.", ""))
_add("ADQL_INVALID",
     "The ADQL is not valid.", "L'ADQL non è valida.",
     empty=("ADQL is empty (character {position})", "ADQL vuota (carattere {position})", "position:int"),
     not_select=("The ADQL must start with SELECT (character {position})",
                 "L'ADQL deve iniziare con SELECT (carattere {position})", "position:int"),
     unmatched_close=("Closing parenthesis without an opening one (character {position})",
                      "Parentesi chiusa senza apertura (carattere {position})", "position:int"),
     unclosed_quote=("Quote {quote} not closed (character {position})",
                     "Virgoletta {quote} non chiusa (carattere {position})", "quote position:int"),
     unclosed_paren=("Opening parenthesis not closed (character {position})",
                     "Parentesi aperta non chiusa (carattere {position})", "position:int"),
     service_rejected=("{url}: the service rejected the request: {detail}",
                       "{url}: il servizio ha rifiutato la richiesta: {detail}", "url detail!"),
     service_rejected_async_hint=("{url}: the service rejected the request: {detail}" + _ASYNC_HINT_EN,
                                  "{url}: il servizio ha rifiutato la richiesta: {detail}" + _ASYNC_HINT_IT,
                                  "url detail!"))
_add("MAX_ROWS_INVALID",
     "max_rows = {value}: allowed integers from 1 to {maximum} (row cap of module 13).",
     "max_rows = {value}: ammessi gli interi da 1 a {maximum} (tetto di righe del modulo 13).", "value maximum:int")
_add("MAX_SEP_INVALID",
     "max_distance {distance}: the XMatch service accepts (0, {maximum}].",
     "max_distance {distance}: il servizio XMatch ammette (0, {maximum}].", "distance:qty maximum:qty")
_add("SERVER_UNKNOWN",
     "The server is not known.", "Il server non è noto.",
     wrong_protocol=("The entry '{service}' is a {found} service, not {wanted}.",
                     "La voce '{service}' è un servizio {found}, non {wanted}.", "service found wanted"),
     not_listed=("Server '{server}' is not in the list (entries: {known}).",
                 "Server '{server}' non in elenco (voci: {known}).", "server known:list"),
     not_personal=("'{server}' is not a personal server.", "'{server}' non è un server personale.", "server"))
_extend("TABLE_TOO_LARGE",
        upload=("Uploaded tables of {total}, above the limit of {limit} of the XMatch service.",
                "Tabelle caricate di {total}, oltre il limite di {limit} del servizio XMatch.", "total:qty limit:qty"))
_add("SIA_INVALID",
     "Invalid SIA response: {cause}", "Risposta SIA non valida: {cause}", "cause:msg")
_add("SSA_INVALID",
     "The spectrum or the SSA response is not valid.", "Lo spettro o la risposta SSA non sono validi.",
     axes_dm=("{origin}: spectral axis or flux not recognisable (utype of the Spectrum DM, one column per axis); "
              "columns: {columns}",
              "{origin}: asse spettrale o flusso non riconoscibili (utype dello Spectrum DM, una sola colonna per "
              "asse); colonne: {columns}", "origin columns:list!"),
     axes_dm_ucd=("{origin}: spectral axis or flux not recognisable (utype of the Spectrum DM or UCD "
                  "(em.*, phot.flux*), one column per axis); columns: {columns}",
                  "{origin}: asse spettrale o flusso non riconoscibili (utype dello Spectrum DM o UCD (em.*, "
                  "phot.flux*), una sola colonna per asse); colonne: {columns}", "origin columns:list!"),
     no_unit=("{origin}: column '{column}' without a valid unit.", "{origin}: colonna '{column}' senza unità valida.",
              "origin column!"),
     no_access_column=("The ssa_search result has no access column (utype ssa:Access.Reference or UCD "
                       "meta.ref.url).",
                       "Il risultato di ssa_search non ha la colonna di accesso (utype ssa:Access.Reference o UCD "
                       "meta.ref.url).", ""),
     unreadable=("{url}: spectrum not readable ({cause})", "{url}: spettro non leggibile ({cause})", "url cause:msg"),
     format=("{url}: format {format} (allowed: VOTable Spectrum DM and FITS)",
             "{url}: formato {format} (ammessi VOTable Spectrum DM e FITS)", "url format"))
_add("IDHA_UNREADABLE",
     "The IDHA file cannot be read.", "Il file IDHA non è leggibile.",
     xml_error=("{path}: file not readable as XML ({detail})", "{path}: file non leggibile come XML ({detail})",
                "path detail!"),
     format_unknown=("{path}: IDHA format not readable: no public documentation of the format (D14-9 point 13); "
                     "use SIA or SIA2",
                     "{path}: formato IDHA non leggibile: nessuna documentazione pubblica del formato (D14-9 punto "
                     "13); usare SIA o SIA2", "path"))
_add("SAMP_UNAVAILABLE",
     "No SAMP hub is available.", "Nessun hub SAMP disponibile.",
     no_hub=("No SAMP hub is active and starting one failed ({detail}); the other VO functions remain available.",
             "Nessun hub SAMP attivo e avvio del proprio non riuscito ({detail}); le altre funzioni VO restano "
             "disponibili.", "detail!"),
     not_connected=("Not connected to a SAMP hub: call connect().",
                    "Non collegato a un hub SAMP: chiamare connect().", ""))
_add("SAMP_UNSUPPORTED_TYPE",
     "The SAMP message type is not supported.", "Il tipo di messaggio SAMP non è supportato.",
     type=("Type '{mtype}' is not supported; supported: {supported}.",
           "Tipo '{mtype}' non supportato; supportati: {supported}.", "mtype supported:list"),
     no_handler=("No function registered for {mtype}.", "Nessuna funzione registrata per {mtype}.", "mtype"))
_add("SAMP_NO_PEER",
     "No SAMP client is connected.", "Nessun client SAMP collegato.",
     recipient=("'{recipient}' is not connected or does not accept {mtype}.",
                "'{recipient}' non è collegato o non accetta {mtype}.", "recipient mtype"),
     none=("No connected program accepts {mtype}.", "Nessun programma collegato accetta {mtype}.", "mtype"))
_add("ROW_LIMIT_EXCEEDED",
     "The result exceeds the row limit.", "Il risultato supera il limite di righe.",
     cut=("Received {received} rows, the first {max_rows} returned (max_rows = {max_rows}).",
          "Ricevute {received} righe, restituite le prime {max_rows} (max_rows = {max_rows}).",
          "received:int max_rows:int"),
     service_overflow=("The service truncated the result to {received} rows (max_rows = {max_rows}, status "
                       "OVERFLOW).",
                       "Il servizio ha troncato il risultato a {received} righe (max_rows = {max_rows}, stato "
                       "OVERFLOW).", "received:int max_rows:int"))
_add("CSV_UNITS_NOT_SAVED",
     "Plain CSV does not save the column units: to keep them export to ecsv (D14-10).",
     "Il CSV semplice non salva le unità delle colonne: per conservarle esportare in ecsv (D14-10).")
_add("SIA_NO_RESULT", "No image for the given criteria.", "Nessuna immagine per i criteri dati.")
_add("SSA_NO_RESULT", "No spectrum for the given criteria.", "Nessuno spettro per i criteri dati.")
_extend("FROM_CACHE",
        cached_origin=("Copy of {origin} from the cache, downloaded on {retrieved_at}.",
                       "Copia in cache di {origin}, scaricata il {retrieved_at}.", "origin retrieved_at"),
        network_cached=("Network not available ({error}): copy from the cache of {retrieved_at}.",
                        "Rete non disponibile ({error}): copia in cache del {retrieved_at}.",
                        "error! retrieved_at"),
        cached_since=("Copy from the cache of {retrieved_at}.", "Copia in cache del {retrieved_at}.",
                      "retrieved_at"))
_extend("BODY_UNKNOWN",
        spectrum_without_candidate=("The body cannot be derived: spectrum loaded from a URL without the ssa_search "
                                    "candidate.",
                                    "Corpo non ricavabile: spettro caricato da URL senza il candidato di "
                                    "ssa_search.", ""))
_extend("FORMAT_DECLARED",
        recognized_differs=("Declared format '{declared}', recognised from the content: {recognized}.",
                            "Formato dichiarato '{declared}', riconosciuto dal contenuto: {recognized}.",
                            "declared! recognized"))
_add("ASTRORES_LINK_SOURCE",
     "Linked data of the ASTRORES file.", "Dati collegati del file ASTRORES.",
     cached=("Linked data {url}: copy from the cache of {retrieved_at}.",
             "Dati collegati {url}: copia in cache del {retrieved_at}.", "url retrieved_at"),
     downloaded=("Linked data {url}: downloaded on {retrieved_at}.",
                 "Dati collegati {url}: scaricati il {retrieved_at}.", "url retrieved_at"))
_add("SIMBAD_NO_OBJECT",
     "No SIMBAD object within {radius}.", "Nessun oggetto SIMBAD entro {radius}.", "radius:qty")
_add("SIMBAD_SYSTEM_UNKNOWN",
     "Band {band}: system code '{code}' is not documented by SIMBAD, system not declared.",
     "Banda {band}: codice di sistema '{code}' non documentato da SIMBAD, sistema non dichiarato.", "band! code!")
_add("SIMBAD_SYSTEM_UNDECLARED",
     "Bands without a system declared by SIMBAD: {bands}", "Bande senza sistema dichiarato da SIMBAD: {bands}",
     "bands:list!")
_add("SIMBAD_NBREF_MISSING",
     "Number of citations missing for all the objects: the closest one was chosen.",
     "Numero di citazioni assente per tutti gli oggetti: scelto il più vicino.")
_add("SIMBAD_TIE",
     "{count} objects with the same number of citations ({nbref}): the closest to the centre chosen, {main_id} at "
     "{separation}.",
     "{count} oggetti con lo stesso numero di citazioni ({nbref}): scelto il più vicino al centro, {main_id} a "
     "{separation}.", "count:int nbref:int main_id! separation:qty",
     nbref_missing=("{count} objects without a number of citations: the closest to the centre chosen, {main_id} at "
                    "{separation}.",
                    "{count} oggetti senza numero di citazioni: scelto il più vicino al centro, {main_id} a "
                    "{separation}.", "count:int main_id! separation:qty"))
_add("SIMBAD_NO_MAGNITUDE",
     "No magnitude in SIMBAD for {main_id}.", "Nessuna magnitudine in SIMBAD per {main_id}.", "main_id!")

# --- Modulo 16 (MOC, sprint 8d) --------------------------------------------------------------------------------
_extend("HEALPIX_ORDER_INVALID",
        moc_order=("{what} {value}: an integer in [0, {limit}] is required (IVOA MOC 2.0 standard), no default.",
                   "{what} {value}: serve un intero in [0, {limit}] (standard IVOA MOC 2.0), senza default.",
                   "what value limit:int"),
        map_too_large=("order {order}: a map of {cells} cells is above the limit of this function (order "
                       "{maximum}).",
                       "order {order}: mappa di {cells} celle oltre il limite di questa funzione (ordine "
                       "{maximum}).", "order:int cells:int maximum:int"))
_extend("BODY_UNKNOWN",
        moc_without_body=("MOC {kind} without a body: a MOC without a body is an error.",
                          "MOC {kind} senza corpo (body): un MOC senza corpo è un errore.", "kind"),
        no_moc=("{what}: the body cannot be derived, no MOC.", "{what}: corpo non ricavabile, nessun MOC.", "what"),
        no_filter=("Table {origin}: the body cannot be derived, no filter.",
                   "Tabella {origin}: corpo non ricavabile, nessun filtro.", "origin"))
_add("BODY_MISMATCH",
     "The bodies differ.", "I corpi sono diversi.",
     mixed_operation=("{op} on a mixed MOC {body}: it can be forced only with force_body=True (cited in the "
                      "result).",
                      "{op} su un MOC misto {body}: forzabile solo con force_body=True (citato nel risultato).",
                      "op body"),
     different_bodies=("Different bodies or mixed MOC: {body} and {other}; it can be forced only with "
                       "force_body=True (cited in the result).",
                       "Corpi diversi o MOC misto: {body} e {other}; forzabile solo con force_body=True (citato nel "
                       "risultato).", "body other"),
     table_vs_moc=("Different bodies: table {table_body}, MOC {moc_body}; it can be forced only with "
                   "force_body=True (cited in the result).",
                   "Corpi diversi: tabella {table_body}, MOC {moc_body}; forzabile solo con force_body=True (citato "
                   "nel risultato).", "table_body moc_body"))
_add("MOC_TYPE_MISMATCH",
     "The MOC type does not fit the operation.", "Il tipo di MOC non va bene per l'operazione.",
     operation=("Operation between a {kind} MOC and a {other} MOC: different types (different units).",
                "Operazione tra un MOC {kind} e un MOC {other}: tipi diversi (unità diverse).", "kind other"),
     contains_positions=("contains on positions: a spatial MOC is required, not {kind}.",
                         "contains su posizioni: serve un MOC spaziale, non {kind}.", "kind"),
     contains_times=("contains_times: a temporal MOC is required, not {kind}.",
                     "contains_times: serve un MOC temporale, non {kind}.", "kind"),
     space_during=("space_during: a space-time MOC and a temporal MOC are required.",
                   "space_during: servono un MOC spazio-temporale e un MOC temporale.", ""),
     time_within=("time_within: a space-time MOC and a spatial MOC are required.",
                  "time_within: servono un MOC spazio-temporale e un MOC spaziale.", ""),
     file=("{path}: {found} MOC in the file, {requested} requested.",
           "{path}: MOC {found} nel file, richiesto {requested}.", "path found requested"),
     filter=("Position filter with a {kind} MOC: a spatial MOC is required.",
             "Filtro di posizioni con un MOC {kind}: serve un MOC spaziale.", "kind"),
     grid_within=("healpix_grid: within must be a spatial MOC.", "healpix_grid: within deve essere un MOC spaziale.",
                  ""),
     mocserver_filter=("Spatial filter of the MocServer with a {kind} MOC.",
                       "Filtro spaziale del MocServer con un MOC {kind}.", "kind"),
     build_moc=("build_moc: {kind} MOC, spatial MOCs expected.", "build_moc: MOC {kind}, attesi MOC spaziali.",
                "kind"))
_add("MOC_UNREADABLE",
     "The MOC cannot be read.", "Il MOC non è leggibile.",
     read_error=("{path}: MOC not readable ({detail})", "{path}: MOC non leggibile ({detail})", "path detail!"),
     no_binary_table=("{path}: MOC not readable (no binary table)", "{path}: MOC non leggibile (nessuna tabella "
                      "binaria)", "path"),
     mixed_without_bodies=("{path}: MOC not readable (A2BODY='mixed' without A2BODIES with at least two bodies)",
                           "{path}: MOC non leggibile (A2BODY='mixed' senza A2BODIES con almeno due corpi)", "path"),
     body_empty=("{path}: MOC not readable (A2BODY is empty)", "{path}: MOC non leggibile (A2BODY vuoto)", "path"),
     mocdim=("{path}: MOC not readable (MOCDIM '{value}' not provided by the standard)",
             "{path}: MOC non leggibile (MOCDIM '{value}' non previsto dallo standard)", "path value!"),
     coordsys=("{path}: MOC not readable (COORDSYS '{value}': the standard requires 'C' (ICRS))",
               "{path}: MOC non leggibile (COORDSYS '{value}': lo standard prevede 'C' (ICRS))", "path value!"),
     mocpy_error=("{path}: MOC not readable ({detail})", "{path}: MOC non leggibile ({detail})", "path detail!"),
     json_syntax=("{path}: MOC not readable ({detail})", "{path}: MOC non leggibile ({detail})", "path detail!"),
     json_cells=("{path}: MOC not readable (JSON: {{\"order\": [integer indices], ...}} expected)",
                 "{path}: MOC non leggibile (JSON: atteso {{\"ordine\": [indici interi], ...}})", "path"),
     json_st_list=("{path}: MOC not readable (JSON of a space-time MOC: a list of {{\"t\": …}} and {{\"s\": …}} "
                   "expected)",
                   "{path}: MOC non leggibile (JSON di un MOC spazio-temporale: attesa una lista di {{\"t\": …}} e "
                   "{{\"s\": …}})", "path"),
     empty_text=("{path}: MOC not readable (empty text)", "{path}: MOC non leggibile (testo vuoto)", "path"),
     not_utf8=("{path}: MOC not readable ({detail})", "{path}: MOC non leggibile ({detail})", "path detail!"))
_add("MOC_VERSION_UNSUPPORTED",
     "The MOC version is not supported.", "La versione del MOC non è supportata.",
     unsupported=("{path}: MOC version '{version}' not supported; read: {supported}",
                  "{path}: versione MOC '{version}' non supportata; lette: {supported}",
                  "path version! supported:list"),
     unsupported_2_1=("{path}: MOC version '2.1' not supported; read: {supported} (D16-6: no 2.1 version among the "
                      "IVOA documents, not even as a Working Draft or Proposed Recommendation, check of "
                      "2026-10-12)",
                      "{path}: versione MOC '2.1' non supportata; lette: {supported} (D16-6: nessuna versione 2.1 "
                      "tra i documenti IVOA, nemmeno come Working Draft o Proposed Recommendation, verifica del "
                      "2026-10-12)", "path supported:list"),
     timesys=("{path}: TIMESYS '{value}'; the 2.0 standard requires TCB (earlier temporal MOCs, STMOC Note 2019, are "
              "not read)",
              "{path}: TIMESYS '{value}'; lo standard 2.0 prevede TCB (i MOC temporali precedenti, Note STMOC 2019, "
              "non sono letti)", "path value!"))
_add("MOC_TYPE_REQUIRED",
     "The MOC type must be given.", "Il tipo del MOC va indicato.",
     json=("{path}: JSON without the \"s\"/\"t\" prefix: the type is determined by the context (standard 2.0); give "
           "it with kind='space' or kind='time'.",
           "{path}: JSON senza prefisso \"s\"/\"t\": il tipo si determina dal contesto d'uso (standard 2.0); "
           "indicarlo con kind='space' o kind='time'.", "path"),
     ascii=("{path}: text without the t/s prefix: the type is determined by the context (standard 2.0); give it "
            "with kind='space' or kind='time'.",
            "{path}: testo senza prefisso t/s: il tipo si determina dal contesto d'uso (standard 2.0); indicarlo "
            "con kind='space' o kind='time'.", "path"))
_add("MOC_BODY_UNSUPPORTED",
     "The body is not supported for this MOC.", "Il corpo non è supportato per questo MOC.",
     format=("MOC of the body {body}: the body cannot be declared in {format}; non-celestial MOCs are written only in "
             "FITS with the A2BODY keyword.",
             "MOC del corpo {body}: in {format} il corpo non si può dichiarare; i MOC non celesti si scrivono solo "
             "in FITS con la parola chiave A2BODY.", "body format"),
     not_celestial=("{what}: body '{body}'; spatial MOCs are in ICRS (sky only).",
                    "{what}: corpo '{body}'; i MOC spaziali sono in ICRS (solo cielo).", "what body"))
_extend("REGION_INVALID",
        conversion=("{what}: {cause}", "{what}: {cause}", "what cause:msg"),
        not_finite=("{what}: coordinates not finite.", "{what}: coordinate non finite.", "what"),
        polygon_vertices=("Polygon with {count} vertices: at least 3 are required.",
                          "Poligono con {count} vertici: ne servono almeno 3.", "count:int"),
        polygon_mocpy=("Polygon not valid for mocpy: {detail}", "Poligono non valido per mocpy: {detail}", "detail!"))
_extend("NO_COORD_COLUMNS",
        no_positions=("{what} ({origin}): no position column (module 13).",
                      "{what} ({origin}): nessuna colonna di posizione (modulo 13).", "what origin"),
        no_angular_unit=("{what}: columns {lon}/{lat} without an angular unit.",
                         "{what}: colonne {lon}/{lat} senza unità angolare.", "what lon! lat!"))
_extend("FRAME_UNKNOWN",
        columns_without_frame=("{what}: columns {lon}/{lat} without a declared reference system.",
                               "{what}: colonne {lon}/{lat} senza sistema dichiarato.", "what lon! lat!"))
_extend("PREVIEW_NOT_MEASURABLE",
        moc_from_image=("MOC from an image: the image is open at two levels and the data in memory are only the "
                        "preview.",
                        "MOC da immagine: l'immagine è aperta a due livelli e i dati in memoria sono solo "
                        "l'anteprima.", ""))
_add("GRID_TOO_LARGE",
     "The grid is too large.", "La griglia è troppo grande.",
     full_sky=("All-sky grid at order {order}: {cells} cells, above {maximum}; give within=MOC.",
               "Griglia di tutto il cielo all'ordine {order}: {cells} celle, oltre {maximum}; indicare within=MOC.",
               "order:int cells:int maximum:int"),
     within=("Grid of {cells} cells above {maximum}.", "Griglia di {cells} celle oltre {maximum}.",
             "cells:int maximum:int"))
_add("TIME_RANGE_INVALID",
     "The times are not valid.", "I tempi non sono validi.",
     not_finite=("{what}: times not finite.", "{what}: istanti non finiti.", "what"),
     before_jd0=("{what}: times before JD 0, outside the temporal MOCs (standard 2.0).",
                 "{what}: istanti prima di JD 0, fuori dai MOC temporali (standard 2.0).", "what"),
     different_counts=("Start and end with different numbers of values.",
                       "Inizio e fine con numeri di valori diversi.", ""),
     end_before_start=("Interval with the end before the start.", "Intervallo con fine prima dell'inizio.", ""),
     counts_mismatch=("{times} times and {positions} positions: one position per observation is required.",
                      "{times} tempi e {positions} posizioni: serve una posizione per osservazione.",
                      "times:int positions:int"),
     invalid_intervals=("Intervals not valid (different numbers or end before the start).",
                        "Intervalli non validi (numeri diversi o fine prima dell'inizio).", ""))
_add("PROBABILITY_MAP_INVALID",
     "The probability map is not valid.", "La mappa di probabilità non è valida.",
     read_error=("{path}: probability map not valid ({detail})", "{path}: mappa di probabilità non valida "
                 "({detail})", "path detail!"),
     no_table=("{path}: probability map not valid (no binary table)",
               "{path}: mappa di probabilità non valida (nessuna tabella binaria)", "path"),
     coordsys=("{path}: probability map not valid (COORDSYS '{value}': 'C' (equatorial, ICRS) is required)",
               "{path}: mappa di probabilità non valida (COORDSYS '{value}': serve 'C' (equatoriale, ICRS))",
               "path value!"),
     density_unit=("{path}: probability map not valid (PROBDENSITY with unit {unit}: a density per steradian is "
                   "required)",
                   "{path}: mappa di probabilità non valida (PROBDENSITY con unità {unit}: serve una densità per "
                   "steradiante)", "path unit!"),
     ordering=("{path}: probability map not valid (ORDERING '{value}': RING or NESTED is required)",
               "{path}: mappa di probabilità non valida (ORDERING '{value}': serve RING o NESTED)", "path value!"),
     nside=("{path}: probability map not valid (NSIDE {nside} and {values} values are not consistent)",
            "{path}: mappa di probabilità non valida (NSIDE {nside} e {values} valori non coerenti)",
            "path nside:int values:int"),
     no_columns=("{path}: probability map not valid (expected the columns PROB (flat map) or UNIQ and PROBDENSITY "
                 "(multi-order))",
                 "{path}: mappa di probabilità non valida (attese le colonne PROB (mappa piatta) o UNIQ e "
                 "PROBDENSITY (multi-ordine))", "path"),
     bad_uniq=("{path}: probability map not valid (invalid UNIQ cells)",
               "{path}: mappa di probabilità non valida (celle UNIQ non valide)", "path"))
_add("PROBABILITY_OUT_OF_RANGE",
     "A probability is out of range.", "Una probabilità è fuori intervallo.",
     cell_probability=("{path}: probability per cell outside [0, 1].", "{path}: probabilità per cella fuori da "
                       "[0, 1].", "path"),
     density=("{path}: probability densities negative or not finite.",
              "{path}: densità di probabilità negative o non finite.", "path"),
     cell_over_one=("{path}: probability per cell above 1.", "{path}: probabilità per cella oltre 1.", "path"),
     level=("Credibility level {level}: allowed in (0, 1].", "Livello di credibilità {level}: ammesso in (0, 1].",
            "level"))
_add("PROBABILITY_SUM_INVALID",
     "{path}: sum of the probabilities {total}, 1 expected within {tolerance} relative.",
     "{path}: somma delle probabilità {total}, attesa 1 entro {tolerance} relativo.",
     "path total:num tolerance:num")
_extend("MOCSERVER_UNAVAILABLE",
        filter=("The MocServer is not reachable, no spatial filter: {cause}",
                "MocServer non raggiungibile, nessun filtro spaziale: {cause}", "cause:msg"))
_extend("SERVICE_ERROR",
        mocserver_response=("{url}: the response cannot be read ({detail}): '{body}'",
                            "{url}: risposta non leggibile ({detail}): '{body}'", "url detail! body!"))
_add("BODY_FORCED",
     "The operation between different bodies was forced.", "Operazione tra corpi diversi forzata.",
     mixed=("{op} on a mixed MOC forced: bodies {bodies}.", "{op} su un MOC misto forzata: corpi {bodies}.",
            "op bodies:list"),
     forced=("Operation forced between {body} and {other}; the result has a mixed body ({bodies}).",
             "Operazione forzata tra {body} e {other}; il risultato ha corpo misto ({bodies}).",
             "body other bodies:list"),
     within=("Bodies forced: {body} and {other}.", "Corpi forzati: {body} e {other}.", "body other"),
     filter=("Filter between different bodies forced: table {table_body}, MOC {moc_body}.",
             "Filtro tra corpi diversi forzato: tabella {table_body}, MOC {moc_body}.", "table_body moc_body"))
_add("MOC_EMPTY",
     "Empty MOC.", "MOC vuoto.",
     plain=("Empty MOC.", "MOC vuoto.", ""),
     operation=("The result of {op} is empty.", "Risultato di {op} vuoto.", "op"),
     source=("{origin}: empty MOC.", "{origin}: MOC vuoto.", "origin"))
_add("MOC_VERSION_ASSUMED",
     "{path}: MOCVERS missing, version {version} assumed.", "{path}: MOCVERS assente, versione {version}.",
     "path version")
_add("MOC_NONSTANDARD_EXTENSION",
     "Non-standard extension of the IVOA MOC 2.0 format (D19-7).",
     "Estensione non standard del formato IVOA MOC 2.0 (D19-7).",
     read=("{path}: body {body} from the AstroTwo keyword {keyword}, a non-standard extension of the IVOA MOC 2.0 "
           "format (D19-7).",
           "{path}: corpo {body} dalla parola chiave {keyword} di AstroTwo, estensione non standard del formato "
           "IVOA MOC 2.0 (D19-7).", "path body keyword"),
     write=("{path}: body {body} written in the AstroTwo keyword {keyword}, a non-standard extension of the IVOA "
            "MOC 2.0 format (D19-7); COORDSYS stays 'C' as the format requires: a reader without the extension "
            "sees a celestial MOC.",
            "{path}: corpo {body} scritto nella parola chiave {keyword} di AstroTwo, estensione non standard del "
            "formato IVOA MOC 2.0 (D19-7); COORDSYS resta 'C' come richiesto dal formato: un lettore senza "
            "l'estensione vede un MOC celeste.", "path body keyword"))
_add("ROWS_EXCLUDED",
     "{count} rows without a position excluded.", "{count} righe senza posizione escluse.", "count:int",
     never_selected=("{count} rows without a position: never selected.",
                     "{count} righe senza posizione: mai selezionate.", "count:int"))
_add("VALUES_EXCLUDED",
     "{count} rows with {column} missing excluded.", "{count} righe con {column} mancante escluse.",
     "count:int column!")
_add("POINTS_OUTSIDE_PROJECTION",
     "{count} sampling points without a position on the sky (outside the projection) excluded.",
     "{count} punti di campionamento senza posizione sul cielo (fuori dalla proiezione) esclusi.", "count:int")
_add("ORDER_DEGRADED",
     "Map at order {map_order}: region brought to order {order} by excess (larger cells containing the region).",
     "Mappa all'ordine {map_order}: regione portata all'ordine {order} per eccesso (celle più grandi che "
     "contengono la regione).", "map_order:int order:int")
_add("CREDIBLE_PROBABILITY",
     "Probability contained in the region: {probability}.", "Probabilità contenuta nella regione: {probability}.",
     "probability:num")
_extend("FROM_CACHE",
        cached_converted=("Copy of {origin} from the cache, downloaded on {retrieved_at}, stored as IVOA FITS "
                          "(original {original_format}).",
                          "Copia in cache di {origin}, scaricata il {retrieved_at}, conservata in FITS IVOA "
                          "(originale {original_format}).", "origin retrieved_at original_format"))
