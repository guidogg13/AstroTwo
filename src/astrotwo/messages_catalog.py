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
    "NO_TRANSLATION",
    "Param",
    "Variant",
    "Entry",
    "CATALOG",
    "entry_for",
    "has_message",
    "uses_catalog",
    "external_params",
    "message_text",
    "placeholders",
    "validate_params",
]

LOG = logging.getLogger("astrotwo.messages")

LANGUAGES = ("en", "it")

#: Tipi dei parametri (forme JSON): ``quantity`` = ``{"value": numero, "unit": testo}``.
PARAM_TYPES = ("string", "number", "integer", "boolean", "quantity", "list", "object")

#: Nota dei messaggi senza voce nel catalogo (§3.7.2).
NO_TRANSLATION = {"en": "(no translation)", "it": "(nessuna traduzione)"}

#: Parametro riservato: sceglie la sotto-voce (D40-6); non si inserisce nel testo.
REASON = "reason"

_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_TYPE_ABBREVIATIONS = {"str": "string", "num": "number", "int": "integer", "bool": "boolean", "qty": "quantity",
                       "list": "list", "obj": "object"}


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
    """``"nome[:tipo][!]"`` separati da spazi (``!`` = testo esterno); tipo: str, num, int, bool, qty, list, obj."""
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


def entry_for(code: str) -> Entry | None:
    return CATALOG.get(code)


def has_message(code: str) -> bool:
    return code in CATALOG


def placeholders(text: str) -> frozenset[str]:
    """Nomi dei segnaposto ``{nome}`` di un testo."""
    return frozenset(_PLACEHOLDER.findall(text))


def _is_quantity(value: object) -> bool:
    return isinstance(value, Mapping) and set(value) == {"value", "unit"}


def _render(value: object) -> str:
    """Valore inserito così com'è: testo tale e quale, numeri nella loro forma JSON, quantità = valore, spazio, unità."""
    if isinstance(value, str):
        return value
    if _is_quantity(value):
        return f"{_render(value['value'])} {_render(value['unit'])}"
    if isinstance(value, (list, tuple)):
        return ", ".join(_render(v) for v in value)
    return json.dumps(value, ensure_ascii=False)


def _selected(entry: Entry, params: Mapping[str, object]) -> tuple[str, str, tuple[Param, ...]]:
    variant = entry.variants.get(params.get(REASON)) if isinstance(params.get(REASON), str) else None
    if variant is not None:
        return variant.en, variant.it, variant.params
    return entry.en, entry.it, entry.params


def message_text(code: str, params: Mapping[str, object] | None, lang: str, *, text: str | None = None,
                 mask_external: bool = False) -> str:
    """Testo del messaggio ``code`` con ``params`` nella lingua ``lang`` (``en`` o ``it``).

    ``text``: testo originale del modulo, usato come ripiego (§3.7.2): codice senza voce, oppure messaggio senza
    ``params`` per una voce che ne richiede (sessioni scritte prima di D40-3); in tal caso si aggiunge la nota
    "(no translation)" / "(nessuna traduzione)". Un parametro atteso ma assente lascia il segnaposto ``{nome}`` e
    scrive una voce di log. ``mask_external``: i parametri ``external`` si sostituiscono con ``<nome>`` (testo
    consegnato all'IA, dove il testo esterno viaggia solo nei parametri, marcato come tale).
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

    def fill(match: re.Match) -> str:
        name = match.group(1)
        if name not in params:
            LOG.warning("messaggio %s: parametro %r assente", code, name)
            return match.group(0)
        if mask_external and name in external:
            return f"<{name}>"
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
}


def validate_params(code: str, params: Mapping[str, object] | None) -> list[str]:
    """Problemi di ``params`` rispetto alla voce (mancanti, non dichiarati, di tipo sbagliato); vuoto se a posto."""
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
    for name in params:
        if name not in expected and name != REASON:
            problems.append(f"{code}: parametro {name} non dichiarato")
    return problems


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
                     "celestial_axes:list useful_axes:list"))
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
                                "method allowed:list"))
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
     "una regione o soglie più alte.", "operation needed:qty limit:qty")
_add("PREVIEW_NOT_MEASURABLE",
     "{operation}: the image is open at two levels and the data in memory are only the preview (step "
     "{preview_step}); use read_region or a cutout on the original pixels.",
     "{operation}: l'immagine è aperta a due livelli e i dati in memoria sono solo l'anteprima (passo "
     "{preview_step}); usare read_region o un taglio sui pixel originali.", "operation preview_step:int")
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
                 "Copia in cache dell'URL, scaricata il {retrieved_at}.", "retrieved_at"))
_add("UNIT_UNKNOWN",
     "The unit of the result cannot be determined from {unit_a} and {unit_b}.",
     "Unità del risultato non determinabile da {unit_a} e {unit_b}.", "unit_a unit_b")
_add("CUTOUT_TRIMMED",
     "Cutout trimmed to the intersection with the image: {shape} instead of {requested_shape}.",
     "Taglio ridotto all'intersezione con l'immagine: {shape} invece di {requested_shape}.", "shape requested_shape")
