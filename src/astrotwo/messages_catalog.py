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
     service_error=("{url}: {detail}; it is not a HiPS service.", "{url}: {detail}; non è un servizio HiPS.",
                    "url detail!"),
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
     metadata_xml_unavailable=("{url}: {detail}; metadata.xml is required for HiPS catalogues (standard §4.4.3).",
                               "{url}: {detail}; metadata.xml è richiesto per i cataloghi HiPS (standard §4.4.3).",
                               "url detail!"),
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
     conversion_center=("Centre of the field: {detail}", "Centro del campo: {detail}", "detail!"),
     conversion_positions=("Positions: {detail}", "Posizioni: {detail}", "detail!"),
     conversion_window=("Pixels of the window: {detail}", "Pixel della finestra: {detail}", "detail!"))
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
                   "{url}: tile corrotto anche dopo una nuova richiesta ({problem}).", "url problem!"),
     file_corrupt=("{url}: file not valid even after a new request ({problem}).",
                   "{url}: file non valido anche dopo una nuova richiesta ({problem}).", "url problem!"),
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
     resolve=("The MocServer is not reachable to resolve '{hips_id}': {detail}",
              "MocServer non raggiungibile per risolvere '{hips_id}': {detail}", "hips_id detail!"),
     index=("The MocServer is not reachable and there is no local copy of the collections: {detail}",
            "MocServer non raggiungibile e nessuna copia locale delle collezioni: {detail}", "detail!"),
     coverage=("Coverage of {hips_id}: {detail}", "Copertura di {hips_id}: {detail}", "hips_id detail!"),
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
                    "Copia in cache di {url} corrotta ({problem}): scartata, nuova richiesta.", "url problem!"),
     tile_corrupt=("{url}: tile corrupt ({problem}), discarded.", "{url}: tile corrotto ({problem}), scartato.",
                   "url problem!"),
     cache_invalid=("The cached copy of {url} is not valid ({problem}): new request.",
                    "Copia in cache di {url} non valida ({problem}): nuova richiesta.", "url problem!"),
     file_invalid=("{url}: file not valid ({problem}), discarded.", "{url}: file non valido ({problem}), scartato.",
                   "url problem!"))
_add("HIPS_COVERAGE_UNKNOWN",
     "The coverage is not known.", "Copertura non nota.",
     moc_missing=("{url}: MOC of the service is missing (optional for the standard); coverage not known.",
                  "{url}: MOC del servizio assente (facoltativo per lo standard); copertura non nota.", "url"),
     unavailable=("{hips_id}: coverage not available ({cause_code}: {cause}).",
                  "{hips_id}: copertura non disponibile ({cause_code}: {cause}).", "hips_id cause_code cause!"))
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
