"""Controls: how a piece declares its settings, and how incoming values are made safe.

A piece lists its controls (sliders, choices, toggles). The front end draws its panel from
`describe(controls)`; whatever values come back go through `resolve`, which always returns a
complete and valid set of settings, so the drawing code never has to check its inputs.
"""
import math
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Slider:
    name: str
    label: str
    min: float
    max: float
    step: float
    default: float
    unit: str = ""


@dataclass(frozen=True)
class Choice:
    name: str
    label: str
    options: tuple[str, ...]
    default: str


@dataclass(frozen=True)
class Toggle:
    name: str
    label: str
    default: bool


TOGGLE_WORDS = {"on": True, "true": True, "off": False, "false": False}


def _slider_value(control: Slider, raw):
    """Parse a number, clamp it to [min, max], and make it an int when the step is whole."""
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = float(control.default)
    if not math.isfinite(value):
        value = float(control.default)
    value = min(max(value, control.min), control.max)
    if float(control.step).is_integer():
        return int(round(value))
    return value


def _choice_value(control: Choice, raw):
    return raw if raw in control.options else control.default


def _toggle_value(control: Toggle, raw):
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str) and raw.lower() in TOGGLE_WORDS:
        return TOGGLE_WORDS[raw.lower()]
    return control.default


def resolve(controls: list, values: dict | None) -> dict:
    """A complete, valid settings dict keyed by control name.

    Missing or unreadable values fall back to the control's default; keys that no control
    declares are dropped. Values that are not a dict at all (a list or a number from an old
    file or stale browser storage) count as empty, so every setting takes its default.
    """
    if not isinstance(values, dict):
        values = {}
    settings = {}
    for control in controls:
        raw = values.get(control.name, control.default)
        if isinstance(control, Slider):
            settings[control.name] = _slider_value(control, raw)
        elif isinstance(control, Choice):
            settings[control.name] = _choice_value(control, raw)
        elif isinstance(control, Toggle):
            settings[control.name] = _toggle_value(control, raw)
        else:
            raise TypeError(f"unknown control: {control!r}")
    return settings


KINDS = {Slider: "slider", Choice: "choice", Toggle: "toggle"}


def describe(controls: list) -> list[dict]:
    """The controls as plain JSON-ready dicts: {"kind": "slider"|"choice"|"toggle", ...fields}."""
    described = []
    for control in controls:
        if type(control) not in KINDS:
            raise TypeError(f"unknown control: {control!r}")
        fields = asdict(control)
        if "options" in fields:
            fields["options"] = list(fields["options"])
        described.append({"kind": KINDS[type(control)], **fields})
    return described
