# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Guido Ratti
"""Registro degli strumenti esposti all'IA (livello 3).

Specifica: ``mdfiles/32-ia-registro-strumenti.md`` (stato ``approvato``).

Uno strumento = un comando del 05 dall'elenco chiuso ``EXPOSED_COMMANDS``: nome, descrizione e schema vengono da
``export_schema`` del 05 (ridotto al sottoinsieme accettato dai provider), gli argomenti si validano con il 05
come quelli dell'utente e il risultato inviato al modello è ridotto (≤ 50 elementi, ≤ 20 kB, nessun numero
accorciato), con i testi esterni marcati come dati e i nomi dei file senza cartelle. Il modulo non calcola,
non esegue comandi (coda del 40, tramite il 35) e non usa Qt.
"""

from __future__ import annotations

import copy
import functools
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from astrotwo.messages_catalog import (
    LAYER_CONTEXT,
    MAX_MESSAGE_DEPTH,
    external_params,
    message_params,
    message_text,
    uses_catalog,
)
from astrotwo.core.commands import (
    PHYSICAL_TYPES,
    Command,
    CommandError,
    CommandRegistry,
    CommandResult,
    RequestedBy,
    WorkspaceState,
)

__all__ = [
    "EXPOSED_COMMANDS",
    "EXTERNAL_FIELDS",
    "ASTROTWO_FIELDS",
    "ASTROTWO_MESSAGE_CODES",
    "MAX_ITEMS",
    "MAX_RESULT_BYTES",
    "MAX_EXTERNAL_CHARS",
    "SOURCE_ONCE",
    "TOOL_NAME_PATTERN",
    "Confirmation",
    "ToolCallOutcome",
    "ToolRegistry",
    "ToolRegistryError",
    "external_source",
    "string_paths",
]

#: Elenco esplicito e chiuso (32 §3.2): (comando del 05, nome dello strumento). La corrispondenza inversa si fa con
#: questa tabella, mai con una sostituzione di testo (§3.4 punto 1).
EXPOSED_COMMANDS: tuple[tuple[str, str], ...] = (
    ("view.go_to", "view__go_to"),
    ("view.set_center", "view__set_center"),
    ("view.set_zoom", "view__set_zoom"),
    ("view.set_grid", "view__set_grid"),
    ("view.set_overlays", "view__set_overlays"),
    ("hips.set_survey", "hips__set_survey"),
    ("catalog.load_region", "catalog__load_region"),
    ("catalog.select", "catalog__select"),
    ("catalog.set_style", "catalog__set_style"),
    ("measure.distance", "measure__distance"),
    ("calc.evaluate_expression", "calc__evaluate_expression"),
    ("calc.convert_units", "calc__convert_units"),
    ("calc.convert_pixel_value", "calc__convert_pixel_value"),
    ("calc.calculate_coordinates", "calc__calculate_coordinates"),
    ("calc.convert_time", "calc__convert_time"),
    ("layer.set_visible", "layer__set_visible"),
    ("layer.set_opacity", "layer__set_opacity"),
    ("coords.resolve_name", "coords__resolve_name"),
    ("catalog.search", "catalog__search"),
    ("catalog.describe", "catalog__describe"),
    ("catalog.rows", "catalog__rows"),
    ("layer.list", "layer__list"),
)

#: Nomi accettati da entrambi i provider (§3.4 punto 1).
TOOL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

MAX_ITEMS = 50  # righe di una tabella o elementi di un elenco (§3.7)
MAX_RESULT_BYTES = 20 * 1024  # JSON in UTF-8 (§3.7)
MAX_EXTERNAL_CHARS = 500  # ogni testo esterno (§3.6)

#: Comandi con la fonte dei testi esterni scritta una volta in testa al risultato (``external_source``) invece che
#: in ogni campo (decisione del proprietario del 2026-10-22: tutti i testi esterni del risultato hanno quella fonte).
SOURCE_ONCE = frozenset({"catalog.rows"})

# --------------------------------------------------------------------------
# Testi esterni (§3.6, decisione del proprietario del 2026-10-22: "entrambe le liste")
#
# Percorsi nel risultato: chiavi separate da ".", "[]" per gli elementi di un elenco; nei modelli solo ``*`` è
# speciale e vale qualunque testo, anche più livelli. Si cerca prima in EXTERNAL_FIELDS, poi in ASTROTWO_FIELDS; una
# stringa che non è in nessuno dei due è testo esterno (nel dubbio, esterno) e il test T12 la segnala.
# --------------------------------------------------------------------------

_VIEW = ("values.base", "values.base_layer", "values.base_scale.unit", "values.base_scale_method", "values.center.*",
         "values.compass.*", "values.field_*", "values.frame", "values.projection", "values.scale.unit",
         "values.grid.*", "values.grid_frame", "values.notes[]", "values.pixel_grid.*", "values.wcs_problem.*",
         "values.interpreted_as", "values.overlays.*", "values.cursor_frame", "values.layer")
# valori di resolve_name del 10 (``coords.resolve_name``; dentro ``resolved`` per ``view.go_to``)
_RESOLVED_ASTROTWO = ("name", "position.*", "source", "service", "origin", "retrieved_at", "notes[]")
_RESOLVED_EXTERNAL = ("main_id", "coo_bibcode")
# valori di un catalogo caricato (``_catalog_values`` del 05)
_CATALOG_ASTROTWO = ("values.layer", "values.body", "values.positions.frame", "values.positions.source",
                     "values.source", "values.provenance", "values.style.*")
_CATALOG_EXTERNAL = ("values.columns[]", "values.positions.lon", "values.positions.lat", "values.positions.epoch",
                     "values.positions.equinox")
# un record di record_view del 13: nome, valore, unità, UCD vengono dal file o dal servizio
_RECORD = ("name", "value", "value[]", "unit", "unit_unrecognized", "ucd")

EXTERNAL_FIELDS: dict[str, tuple[str, ...]] = {
    "view.go_to": tuple(f"values.resolved.{f}" for f in _RESOLVED_EXTERNAL),
    "hips.set_survey": ("values.title", "values.hips_id", "values.frame", "values.tile_formats[]",
                        "values.display.unit"),
    "catalog.load_region": _CATALOG_EXTERNAL,
    "catalog.select": ("values.source.name.*", "values.source.catalog.name",
                       *(f"values.source.record[].{f}" for f in _RECORD)),
    "coords.resolve_name": tuple(f"values.{f}" for f in _RESOLVED_EXTERNAL),
    "catalog.describe": (*_CATALOG_EXTERNAL, "values.epoch", "values.columns[].name", "values.columns[].unit",
                         "values.columns[].ucd", "values.columns[].description"),
    "catalog.rows": ("values.sort.column", *(f"values.rows[].values[].{f}" for f in _RECORD)),
    "layer.list": ("values.layers[].name", "values.layers[].columns.*", "values.layers[].sort.column",
                   "values.layers[].display.unit"),
}

#: Campi comuni a tutti i comandi: provenienza scritta dai moduli (origine = URL configurato o nome del file).
_COMMON_ASTROTWO = ("provenance[].origin", "provenance[].retrieved_at", "provenance[].source",
                    "provenance[].library", "provenance[].file")

ASTROTWO_FIELDS: dict[str, tuple[str, ...]] = {
    "view.go_to": (*_VIEW, *(f"values.resolved.{f}" for f in _RESOLVED_ASTROTWO)),
    "view.set_center": _VIEW,
    "view.set_zoom": _VIEW,
    "view.set_grid": _VIEW,
    "view.set_overlays": _VIEW,
    "hips.set_survey": ("values.layer", "values.replaced[]", "values.base_url", "values.server", "values.servers[]",
                        "values.body",
                        "values.display.limits_source", "values.display.palette", "values.display.stretch"),
    "catalog.load_region": _CATALOG_ASTROTWO,
    "catalog.select": ("values.layer", "values.source.position.*", "values.source.position_reason",
                       "values.source.position_reason_code",
                       "values.source.catalog.layer", "values.source.catalog.source", "values.source.catalog.origin",
                       "values.source.catalog.retrieved_at"),
    "catalog.set_style": ("values.layer", "values.style.*"),
    "measure.distance": ("values.distance.unit", "values.frame", "values.layer", "values.notes[]",
                         "values.points[].*"),
    "calc.evaluate_expression": ("values.*",),
    "calc.convert_units": ("values.*",),
    "calc.convert_pixel_value": ("values.*",),
    "calc.calculate_coordinates": ("values.*",),
    "calc.convert_time": ("values.*",),
    "layer.set_visible": ("values.layer",),
    "layer.set_opacity": ("values.layer",),
    "coords.resolve_name": tuple(f"values.{f}" for f in _RESOLVED_ASTROTWO),
    "catalog.search": ("values.layer", "values.expression"),
    "catalog.describe": (*_CATALOG_ASTROTWO, "values.columns[].dtype", "values.origin", "values.retrieved_at"),
    "catalog.rows": ("values.layer", "values.order", "values.sort.direction"),
    "layer.list": ("values.layers[].id", "values.layers[].kind", "values.layers[].source",
                   "values.layers[].display.limits_source", "values.layers[].display.palette",
                   "values.layers[].display.stretch", "values.layers[].style.*", "values.layers[].sort.direction"),
}

#: Codici di avvisi ed errori il cui testo è scritto solo da AstroTwo (05 e moduli, senza testo di terzi); gli altri
#: testi sono esterni (un servizio può scrivere nel messaggio).
ASTROTWO_MESSAGE_CODES = frozenset({
    "COMMAND_PARAMETER_INVALID", "COMMAND_UNKNOWN", "COMMAND_VERSION_UNSUPPORTED", "COMMAND_CANCELLED",
    "LAYER_UNKNOWN", "VIEW_UNDEFINED", "OUT_OF_SKY", "NO_WCS", "WCS_MISSING", "HIPS_DISPLAY_LIMITS_UNDEFINED",
    "TABLE_SORT_UNSUPPORTED", "REGION", "HIPS_COVERAGE_UNKNOWN",
})

# Percorsi assoluti dentro un testo (privacy, §3.7): "/a/b…", "~/…", "file:///…", non dentro un URL
# ("https://h/p") né in una divisione ("10 /2"): servono almeno due elementi dopo "/" (o "~/" e uno).
_SEGMENT = r"[^\s/'\"()\[\]{},;]+"
_ABSOLUTE_PATH = re.compile(rf"(?<![\w:/.~-])(?:file://)?(?:~(?:/{_SEGMENT})+|(?:/{_SEGMENT}){{2,}})/?")

_FLAG_TEXT = (("confirm", "Requires user confirmation."), ("read_only", "Read-only."),
              ("network", "Uses the network."))

#: Esempio di unità per grandezza fisica nella descrizione dei parametri ``quantity`` (§3.4 punto 3).
_UNIT_EXAMPLES = {"angle": "arcmin", "angular velocity": "mas/yr", "length": "nm", "frequency": "GHz",
                  "speed": "km/s", "time": "s"}


class ToolRegistryError(Exception):
    """Errore di §10 con codice, testo ed eventuale parametro; ``model_result`` è il JSON per il modello."""

    def __init__(self, code: str, message: str, *, params: Mapping[str, object] | None = None,
                 parameter: str | None = None, tool: str | None = None, command: str | None = None,
                 valid_tools: tuple[str, ...] | None = None) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.params = dict(params or {})  # valori JSON del messaggio (D40-3, 32 §10.1)
        self.parameter = parameter
        self.tool = tool
        self.command = command
        self.valid_tools = valid_tools

    def model_result(self) -> dict:
        # Stesso trattamento degli errori dei comandi (§3.7): testo inglese del catalogo, testi esterni marcati.
        marker = _Marker(None, self.command or "", self.tool or self.command or "")
        error = marker.message({"code": self.code, "params": dict(self.params), "text": self.message})
        if not error.get("params"):
            error.pop("params", None)
        if self.parameter is not None:
            error["parameter"] = self.parameter
        if self.valid_tools is not None:
            error["valid_tools"] = list(self.valid_tools)  # §3.5 punto 2: il modello si corregge senza indovinare
        return {"contains_external_text": marker.found,
                "command": {"number": None, "name": self.command, "tool": self.tool, "status": "not_executed"},
                "error": error}


@dataclass(frozen=True)
class Confirmation:
    """Esito di ``needs_confirmation``: se serve, perché, se vale "Conferma per questa conversazione" (§3.5, §3.6)."""

    required: bool
    reasons: tuple[str, ...] = ()
    after_external_text: bool = False
    external_source: str | None = None
    conversation_allowed: bool = True  # falso dopo un testo esterno (§3.6)


@dataclass
class ToolCallOutcome:
    """Esito di una chiamata (§7): risultato per il modello, numero ``#n`` se eseguito, errore, conferma."""

    call_id: str
    tool: str
    model_result: dict
    command: Command | None = None
    number: int | None = None
    error_code: str | None = None
    confirmation: Confirmation | None = None
    confirmed: str | None = None  # "yes", "no", "conversation" (risposta dell'utente), None se non chiesta
    external_text: bool = False  # il risultato conteneva testo esterno
    full_result: CommandResult | None = field(default=None, repr=False)  # risultato completo del 05 (per il 34)

    @property
    def is_error(self) -> bool:
        return self.error_code is not None


def string_paths(value: object, path: str = ""):
    """Coppie (percorso, stringa) di un JSON, con la sintassi dei percorsi di §3.6."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            yield from string_paths(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for item in value:
            yield from string_paths(item, f"{path}[]")
    elif isinstance(value, str):
        yield path, value


def _file_name(text: str) -> str:
    """Testo con ogni percorso assoluto ridotto al nome del file (privacy, §3.7)."""
    return _ABSOLUTE_PATH.sub(lambda m: m.group(0).rstrip("/").rsplit("/", 1)[-1] or "/", text)


def _private(value: object) -> object:
    """Copia JSON senza cartelle nei testi e senza chiavi ``sha256`` (§3.7)."""
    if isinstance(value, Mapping):
        return {str(k): _private(v) for k, v in value.items() if k != "sha256"}
    if isinstance(value, list):
        return [_private(v) for v in value]
    if isinstance(value, str):
        return _file_name(value)
    return value


@functools.cache
def _pattern(text: str) -> re.Pattern:
    """Modello di percorso: solo ``*`` è speciale (vale anche per più livelli); ``[]`` è testo."""
    return re.compile(".*".join(re.escape(part) for part in text.split("*")))


def _matches(path: str, patterns: Sequence[str]) -> bool:
    return any(_pattern(p).fullmatch(path) for p in patterns)


# --------------------------------------------------------------------------
# Riduzione dello schema del 05 (§3.4 punto 3)
# --------------------------------------------------------------------------

_KEPT = ("type", "properties", "required", "enum", "minimum", "maximum", "items", "description", "default")


def _note(schema: dict, text: str) -> None:
    schema["description"] = f"{schema['description']} {text}".strip() if schema.get("description") else text


def _quantity_text(s: Mapping) -> str:
    kinds = list(s.get("x-physical-type", ()))
    example = _UNIT_EXAMPLES.get(kinds[0], str(PHYSICAL_TYPES.get(kinds[0], ""))) if kinds else ""
    text = (f"Physical quantity ({' or '.join(kinds)}): value with unit, e.g. "
            f"{{\"value\": 10, \"unit\": \"{example}\"}}.")
    low, high, unit = s.get("x-minimum"), s.get("x-maximum"), s.get("x-range-unit")
    if low is not None or high is not None:
        parts = []
        if low is not None:
            parts.append(f"{'>' if s.get('x-exclusive-minimum') else '≥'} {low!r}")
        if high is not None:
            parts.append(f"≤ {high!r}")
        text += f" Range: {' and '.join(parts)}{f' {unit}' if unit else ''}."
    return text


def _reduce(schema: Mapping) -> dict:
    """Schema nel sottoinsieme di §3.4: le altre parole diventano tipi più larghi o testo della descrizione."""
    s = dict(schema)
    if "anyOf" in s:
        options = [o for o in s.pop("anyOf")]
        nullable = {"type": "null"} in options
        options = [o for o in options if o != {"type": "null"}]
        if len(options) == 1:
            out = _reduce({**options[0], **{k: v for k, v in s.items() if k != "anyOf"}})
            if nullable:
                _nullable(out)
            return out
        out = _merge(options, nullable)
        for key in ("description", "default"):
            if key in s:
                out[key] = s[key]
        _note(out, _forms_text(options))
        return out
    out: dict = {}
    if "const" in s:
        out["enum"] = [s["const"]]
    for key in _KEPT:
        if key not in s:
            continue
        if key == "properties":
            out[key] = {name: _reduce(sub) for name, sub in s[key].items()}
        elif key == "items":
            out[key] = _reduce(s[key])
        else:
            out[key] = copy.deepcopy(s[key])
    if "x-physical-type" in s:
        _note(out, _quantity_text(s))
    if "exclusiveMinimum" in s:
        out["minimum"] = s["exclusiveMinimum"]
        _note(out, f"(exclusive: must be greater than {s['exclusiveMinimum']!r})")
    if "pattern" in s:
        _note(out, f"(pattern {s['pattern']})")
    if "maxItems" in s:
        _note(out, f"(at most {s['maxItems']} items)")
    if "x-layer-kinds" in s:
        _note(out, f"(layer of kind: {', '.join(s['x-layer-kinds'])})")
    if "x-rule" in s:
        _note(out, f"(rule: {s['x-rule']})")
    return out


def _nullable(out: dict) -> None:
    if "enum" in out:
        if None not in out["enum"]:
            out["enum"] = [*out["enum"], None]
    elif "type" in out:
        types = out["type"] if isinstance(out["type"], list) else [out["type"]]
        if "null" not in types:
            out["type"] = [*types, "null"]


def _merge(options: Sequence[Mapping], nullable: bool) -> dict:
    """Unione di più forme (es. tempi: stringa "J2000.0" oppure oggetto): tipi uniti, proprietà dell'oggetto."""
    types: list[str] = []
    out: dict = {}
    for option in options:
        reduced = _reduce(option)
        t = reduced.get("type")
        for name in (t if isinstance(t, list) else [t] if t else []):
            if name not in types:
                types.append(name)
        if "properties" in reduced:
            out["properties"] = reduced["properties"]
            out["required"] = reduced.get("required", [])
    if nullable:
        types.append("null")
    out["type"] = types
    return out


def _forms_text(options: Sequence[Mapping]) -> str:
    forms = []
    for option in options:
        if option.get("type") == "string" and "pattern" in option:
            forms.append(f"a string matching {option['pattern']} (e.g. \"J2000.0\")")
        elif option.get("type") == "object":
            forms.append(f"an object with {', '.join(option.get('properties', {}))}")
        elif option.get("type") == "array":
            size = option.get("minItems") if option.get("minItems") == option.get("maxItems") else None
            item = option.get("items", {}).get("type", "value")
            forms.append(f"an array of {size} {item}s" if size else f"an array of {item}s")
        elif set(option) == {"type"} and isinstance(option["type"], str):
            forms.append(f"a {option['type']}")
        else:
            forms.append(json.dumps(option, ensure_ascii=False))
    return f"(one of: {'; '.join(forms)})"


# --------------------------------------------------------------------------
# Registro degli strumenti
# --------------------------------------------------------------------------


class ToolRegistry:
    """Strumenti per il provider dal ``CommandRegistry`` del 05 (§7)."""

    def __init__(self, registry: CommandRegistry, exposed: Sequence[tuple[str, str]] = EXPOSED_COMMANDS) -> None:
        self.registry = registry
        self._by_tool: dict[str, str] = {}
        self._by_command: dict[str, str] = {}
        for command, tool in exposed:
            if not TOOL_NAME_PATTERN.fullmatch(tool) or tool != command.replace(".", "__"):
                raise ToolRegistryError("TOOL_NAME_INVALID", f"nome dello strumento {tool!r} non valido per "
                                        f"{command}", params={"reason": "pattern", "tool": tool, "command": command},
                                        tool=tool, command=command)
            if tool in self._by_tool or command in self._by_command:
                raise ToolRegistryError("TOOL_NAME_INVALID", f"strumento o comando ripetuto: {tool} ({command})",
                                        params={"reason": "repeated", "tool": tool, "command": command},
                                        tool=tool, command=command)
            try:
                registry.spec(command)
            except CommandError:
                raise ToolRegistryError("TOOL_NAME_INVALID", f"{command} non è un comando registrato del 05",
                                        params={"reason": "not_registered", "command": command},
                                        tool=tool, command=command) from None
            self._by_tool[tool] = command
            self._by_command[command] = tool
        # §3.4 punto 4: schema ricalcolato all'avvio da export_schema, nessuna copia scritta a mano
        schema = registry.export_schema(list(self._by_command))
        self._schema = {c["name"]: c for c in schema["commands"]}

    # --- strumenti per il provider (§3.4) ---------------------------------------------------

    def tools(self) -> list[dict]:
        """Strumenti nell'ordine di §3.2: ``name``, ``description``, ``input_schema`` (forma del ``ToolDefinition``)."""
        out = []
        for command, tool in self._by_command.items():
            entry = self._schema[command]
            flags = entry["flags"]
            lines = [text for key, text in _FLAG_TEXT if flags.get(key)]
            description = entry["description"] + (f"\n{' '.join(lines)}" if lines else "")
            out.append({"name": tool, "description": description, "input_schema": _reduce(entry["parameters"])})
        return out

    def tool_definitions(self):
        """Gli strumenti come ``ToolDefinition`` del 30."""
        from astrotwo.ai.provider_adapter import ToolDefinition

        return [ToolDefinition(t["name"], t["description"], t["input_schema"]) for t in self.tools()]

    def valid_tools(self) -> tuple[str, ...]:
        """Nomi degli strumenti esposti, in ordine alfabetico (risultato di ``TOOL_NOT_EXPOSED``, §3.5)."""
        return tuple(sorted(self._by_tool))

    def command_name(self, tool: str) -> str | None:
        return self._by_tool.get(tool)

    def tool_name(self, command: str) -> str | None:
        return self._by_command.get(command)

    # --- chiamata (§3.5) ------------------------------------------------------------------

    def command_for(self, tool: str, arguments: str, requested_by: RequestedBy,
                    state: WorkspaceState | None = None) -> Command:
        """Comando validato dal 05 come quelli dell'utente; errori come ``ToolRegistryError`` per il modello."""
        name = self._by_tool.get(tool)
        if name is None:
            raise ToolRegistryError("TOOL_NOT_EXPOSED", f"tool {tool!r} does not exist or is not exposed: use one of "
                                    "valid_tools (names with '__')", params={"tool": tool}, tool=tool,
                                    valid_tools=self.valid_tools())
        text = arguments if isinstance(arguments, str) else ""
        try:
            params = json.loads(text) if text.strip() else {}  # nessun argomento: alcuni provider mandano ""
        except ValueError as exc:
            raise ToolRegistryError("TOOL_ARGUMENTS_INVALID", f"arguments are not valid JSON: {exc}",
                                    params={"reason": "not_json", "detail": str(exc)}, tool=tool,
                                    command=name) from None
        if not isinstance(params, dict):
            raise ToolRegistryError("TOOL_ARGUMENTS_INVALID", "arguments must be a JSON object",
                                    params={"reason": "not_object"}, tool=tool, command=name)
        spec = self.registry.spec(name)
        try:
            return self.registry.validate(Command(name, spec.version, params, requested_by), state)
        except CommandError as exc:
            raise ToolRegistryError(exc.code, exc.message, params=exc.params, parameter=exc.details.get("parameter"),
                                    tool=tool, command=name) from None

    def needs_confirmation(self, command: Command, after_external_text: bool = False,
                           external_source: str | None = None) -> Confirmation:
        """Regola di §3.5 (indicatore ``confirm`` del 05) e di §3.6 (dopo un testo esterno)."""
        spec = self.registry.spec(command.name)
        reasons = []
        if spec.confirm:
            if spec.network:
                reasons.append("network")
            if spec.long:
                reasons.append("long")
            if not reasons:
                reasons.append("modifies_layer")
        external = after_external_text and not (spec.read_only and not spec.network)
        if external:
            reasons.append("after_external_text")
        return Confirmation(bool(reasons), tuple(reasons), external, external_source if external else None,
                            conversation_allowed=not external)

    def confirmation_request(self, command: Command, confirmation: Confirmation) -> dict:
        """Scheda per il 44: comando, parametri con unità (file senza cartelle), righe massime, motivi."""
        params = _private(dict(command.parameters))
        return {"command": command.name, "tool": self._by_command.get(command.name), "parameters": params,
                "max_rows": params.get("max_rows"), "reasons": list(confirmation.reasons),
                "external_source": confirmation.external_source,
                "conversation_allowed": confirmation.conversation_allowed}

    @staticmethod
    def not_confirmed(command: Command, tool: str) -> dict:
        return ToolRegistryError("TOOL_NOT_CONFIRMED", "the user did not confirm this command: it was not executed",
                                 tool=tool, command=command.name).model_result()

    # --- risultato per il modello (§3.6, §3.7) --------------------------------------------

    def classify(self, command: str, path: str) -> str:
        """``external``, ``astrotwo`` o ``unclassified`` (che conta come esterno) per un percorso del risultato."""
        if _matches(path, EXTERNAL_FIELDS.get(command, ())):
            return "external"
        if _matches(path, ASTROTWO_FIELDS.get(command, ())) or _matches(path, _COMMON_ASTROTWO):
            return "astrotwo"
        return "unclassified"

    def unclassified(self, command: str, result: CommandResult) -> list[str]:
        """Percorsi delle stringhe dei valori e della provenienza non classificati (T12)."""
        data = {"values": result.to_json()["values"], "provenance": result.to_json()["provenance"]}
        return sorted({p for p, _ in string_paths(_private(data)) if self.classify(command, p) == "unclassified"})

    def reduce_result(self, result: CommandResult, *, command: Command, number: int | None,
                      state: WorkspaceState | None = None) -> dict:
        """JSON per il modello: ``#n``, parametri registrati, valori pieni, testi esterni marcati, limiti fissi."""
        full = result.to_json()
        source = external_source(command, full, state)
        once = command.name in SOURCE_ONCE
        marker = _Marker(self, command.name, source, inline_source=not once)
        values = marker.walk(_private(full["values"]), "values")
        provenance = marker.walk(_private(full["provenance"]), "provenance")
        warnings = [marker.message(w) for w in _private(full["warnings"])]
        error = None if full["error"] is None else marker.message(_private(full["error"]))
        out = {"contains_external_text": marker.found}
        if once and marker.found:
            out["external_source"] = source
        out |= {"command": {"number": number, "name": command.name, "tool": self._by_command.get(command.name),
                           "parameters": _private(dict(command.parameters)), "status": result.status},
               "values": values, "provenance": provenance, "warnings": warnings, "error": error,
               "layers": list(full["layers_created"])}
        cuts: list[dict] = []
        out["values"] = _cut_lists(out["values"], "values", cuts)
        if cuts:
            out["truncated"] = cuts
        return _fit(out)


def external_source(command: Command, full: Mapping, state: WorkspaceState | None) -> str:
    """Fonte dei testi esterni: origine della provenienza, altrimenti sorgente del livello del comando."""
    for item in full.get("provenance", ()):
        if item.get("origin"):
            return _file_name(str(item["origin"]))
    layer_id = command.parameters.get("layer")
    if state is not None and isinstance(layer_id, str):
        layer = state.find(layer_id)
        if layer is not None:
            return _file_name(layer.source or layer.name)
    if command.name == "layer.list":
        return "files and services opened by the user (layer names)"
    return command.name


class _Marker:
    """Sostituisce i testi esterni con ``{"external_text", "source"}`` limitati a 500 caratteri (§3.6); senza
    ``source`` nei campi se la fonte è scritta una volta in testa al risultato (``SOURCE_ONCE``)."""

    def __init__(self, tools: ToolRegistry, command: str, source: str, *, inline_source: bool = True) -> None:
        self.tools, self.command, self.source, self.found = tools, command, source, False
        self.inline_source = inline_source

    def text(self, value: str) -> dict:
        self.found = True
        out = {"external_text": value[:MAX_EXTERNAL_CHARS]}
        if self.inline_source:
            out["source"] = self.source
        if len(value) > MAX_EXTERNAL_CHARS:
            out.update(truncated=True, length=len(value))
        return out

    def walk(self, value: object, path: str) -> object:
        if isinstance(value, dict):
            return {k: self.walk(v, f"{path}.{k}") for k, v in value.items()}
        if isinstance(value, list):
            return [self.walk(v, f"{path}[]") for v in value]
        if isinstance(value, str) and self.tools.classify(self.command, path) != "astrotwo":
            return self.text(value)
        return value

    def nested(self, message: Mapping, depth: int) -> dict:
        """Messaggio annidato (D40-7): come ``message``, ma oltre ``MAX_MESSAGE_DEPTH`` resta il solo codice."""
        if depth > MAX_MESSAGE_DEPTH:
            return {"code": message.get("code")}
        return self.message(message, depth)

    def message(self, message: Mapping, _depth: int = 0) -> dict:
        """Avviso o errore per il modello: codice, ``params`` e testo **inglese** del catalogo (D40-3, 40 §3.7.1).

        Con una voce nel catalogo e ``params`` conformi, il testo lo scrive AstroTwo: i parametri ``external``
        (testi di terzi) viaggiano marcati come testo esterno e nel testo restano ``<nome>``. Altrimenti vale il
        testo originale del modulo, esterno salvo i codici di ``ASTROTWO_MESSAGE_CODES``. I messaggi annidati
        (tipo ``message``, D40-7) sono resi allo stesso modo, in modo ricorsivo fino a ``MAX_MESSAGE_DEPTH``.
        """
        out = dict(message)
        code, params = out.get("code"), out.get("params") or {}
        if isinstance(code, str) and uses_catalog(code, params):
            external = external_params(code, params)
            nested = message_params(code, params)

            def one(key: str, value: object) -> object:
                if key == LAYER_CONTEXT and isinstance(value, Mapping):  # il nome del livello è testo esterno
                    return {**value, "name": self.text(value["name"])}
                if key in external and isinstance(value, str):
                    return self.text(value)
                if key in external and isinstance(value, (list, tuple)):
                    return [self.text(v) if isinstance(v, str) else v for v in value]
                if key in nested and isinstance(value, Mapping):
                    return self.nested(value, _depth + 1)
                if key in nested and isinstance(value, (list, tuple)):
                    return [self.nested(v, _depth + 1) if isinstance(v, Mapping) else v for v in value]
                return value

            out["params"] = {k: one(k, v) for k, v in params.items()}
            out["text"] = message_text(code, params, "en", mask_external=True)
            return out
        if code not in ASTROTWO_MESSAGE_CODES and isinstance(out.get("text"), str):
            out["text"] = self.text(out["text"])
        return out


def _cut_lists(value: object, path: str, cuts: list[dict]) -> object:
    """Al più ``MAX_ITEMS`` elementi per elenco, con totale dichiarato (§3.7)."""
    if isinstance(value, dict):
        return {k: _cut_lists(v, f"{path}.{k}", cuts) for k, v in value.items()}
    if isinstance(value, list):
        if len(value) > MAX_ITEMS:
            cuts.append({"path": path, "total": len(value), "kept": MAX_ITEMS})
            value = value[:MAX_ITEMS]
        return [_cut_lists(v, f"{path}[]", cuts) for v in value]
    return value


def _size(data: object) -> int:
    return len(json.dumps(data, ensure_ascii=False).encode("utf-8"))


def _lists(value: object, path: str):
    """(percorso, elenco) di ogni elenco con più di un elemento, per togliere elementi in coda."""
    if isinstance(value, dict):
        for k, v in value.items():
            yield from _lists(v, f"{path}.{k}")
    elif isinstance(value, list):
        if len(value) > 1:
            yield path, value
        for v in value:
            yield from _lists(v, f"{path}[]")


def _drop_external(value: object) -> object:
    if isinstance(value, dict):
        if "external_text" in value:
            return {"external_text": None, "removed": True} | ({"source": value["source"]} if "source" in value
                                                               else {})
        return {k: _drop_external(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_drop_external(v) for v in value]
    return value


def _fit(out: dict) -> dict:
    """Al più ``MAX_RESULT_BYTES``: prima elementi in coda agli elenchi, poi i testi esterni; mai cifre tolte."""
    if _size(out) <= MAX_RESULT_BYTES:
        return out
    cuts = {c["path"]: c for c in out.get("truncated", [])}
    while _size(out) > MAX_RESULT_BYTES:
        candidates = sorted(_lists(out["values"], "values"), key=lambda pl: _size(pl[1]), reverse=True)
        if not candidates:
            break
        path, items = candidates[0]
        total = cuts[path]["total"] if path in cuts else len(items)
        # togli metà di ciò che eccede, almeno un elemento: poche ripetizioni anche per risultati grandi
        excess = _size(out) - MAX_RESULT_BYTES
        each = max(1, _size(items) // len(items))
        remove = min(len(items) - 1, max(1, excess // each // 2 or 1))
        del items[len(items) - remove:]
        if path in cuts:
            cuts[path]["kept"] = len(items)
        else:
            cuts[path] = {"path": path, "total": total, "kept": len(items)}
        out["truncated"] = list(cuts.values())
    if _size(out) > MAX_RESULT_BYTES:
        out["values"] = _drop_external(out["values"])
        out["removed"] = ["external_text"]
    if _size(out) > MAX_RESULT_BYTES:
        out["over_limit"] = True  # restano solo numeri, unità e testi di AstroTwo: nulla si accorcia
    return out
