from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class MatchSpec:
    class_: str | None = None
    title: str | None = None
    initial_class: str | None = None
    initial_title: str | None = None
    tag: str | None = None
    fullscreen: bool | None = None

    def is_empty(self) -> bool:
        return all(
            v is None
            for v in (
                self.class_,
                self.title,
                self.initial_class,
                self.initial_title,
                self.tag,
                self.fullscreen,
            )
        )


@dataclass
class Rule:
    name: str
    match: MatchSpec = field(default_factory=MatchSpec)
    float: bool | None = None
    pin: bool | None = None
    center: bool | None = None
    workspace: str | None = None
    opacity: str | None = None
    size: str | None = None
    fullscreen_state: str | None = None
    no_blur: bool | None = None
    raw_extras: list[str] = field(default_factory=list)

    def summary(self) -> str:
        bits: list[str] = []
        m = self.match
        if m.class_:
            bits.append(f"class={m.class_}")
        if m.title:
            bits.append(f"title={m.title}")
        if m.initial_class:
            bits.append(f"initialClass={m.initial_class}")
        if m.initial_title:
            bits.append(f"initialTitle={m.initial_title}")
        if m.tag:
            bits.append(f"tag={m.tag}")
        if m.fullscreen is not None:
            bits.append(f"fullscreen={'true' if m.fullscreen else 'false'}")
        props: list[str] = []
        if self.float is not None:
            props.append(f"float={'on' if self.float else 'off'}")
        if self.pin is not None:
            props.append(f"pin={'on' if self.pin else 'off'}")
        if self.center is not None:
            props.append(f"center={'on' if self.center else 'off'}")
        if self.workspace:
            props.append(f"workspace={self.workspace}")
        if self.opacity:
            props.append(f"opacity={self.opacity}")
        if self.size:
            props.append(f"size={self.size}")
        if self.fullscreen_state is not None:
            props.append(f"fullscreen={self.fullscreen_state}")
        if self.no_blur:
            props.append("no_blur=on")
        match_part = ", ".join(bits) or "<no match>"
        prop_part = ", ".join(props) or "<no props>"
        return f"{match_part}  \u2192  {prop_part}"


# ---------------------------------------------------------------------------
# Matching helpers
# ---------------------------------------------------------------------------

def exact_pattern(value: str) -> str:
    """Turn a literal window class/title into an anchored exact-match regex."""
    return f"^({re.escape(value)})$"


# ---------------------------------------------------------------------------
# Serialization (block form only)
# ---------------------------------------------------------------------------

def serialize_rule(rule: Rule) -> str:
    lines = ["windowrule {", f"    name = {rule.name}"]
    m = rule.match
    if m.class_ is not None:
        lines.append(f"    match:class = {m.class_}")
    if m.title is not None:
        lines.append(f"    match:title = {m.title}")
    if m.initial_class is not None:
        lines.append(f"    match:initial_class = {m.initial_class}")
    if m.initial_title is not None:
        lines.append(f"    match:initial_title = {m.initial_title}")
    if m.tag is not None:
        lines.append(f"    match:tag = {m.tag}")
    if m.fullscreen is not None:
        lines.append(f"    match:fullscreen = {'true' if m.fullscreen else 'false'}")

    if rule.float is not None:
        lines.append(f"    float = {'on' if rule.float else 'off'}")
    if rule.pin is not None:
        lines.append(f"    pin = {'on' if rule.pin else 'off'}")
    if rule.center is not None:
        lines.append(f"    center = {'on' if rule.center else 'off'}")
    if rule.workspace:
        lines.append(f"    workspace = {rule.workspace}")
    if rule.opacity:
        lines.append(f"    opacity = {rule.opacity}")
    if rule.size:
        lines.append(f"    size = {rule.size}")
    if rule.fullscreen_state is not None:
        lines.append(f"    fullscreen = {rule.fullscreen_state}")
    if rule.no_blur:
        lines.append("    no_blur = on")

    for extra in rule.raw_extras:
        lines.append(f"    {extra}")

    lines.append("}")
    return "\n".join(lines)


def serialize_rules(rules: Iterable[Rule]) -> str:
    return "\n\n".join(serialize_rule(r) for r in rules) + ("\n" if rules else "")


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

_KNOWN_MATCH_KEYS = {
    "match:class": "class_",
    "match:title": "title",
    "match:initialClass": "initial_class",
    "match:initial_class": "initial_class",
    "match:initialTitle": "initial_title",
    "match:initial_title": "initial_title",
    "match:tag": "tag",
}


def _truthy(val: str) -> bool | None:
    v = val.strip().lower()
    if v in ("on", "true", "1", "yes"):
        return True
    if v in ("off", "false", "0", "no"):
        return False
    return None


def _apply_kv(rule: Rule, key: str, val: str) -> None:
    key = key.strip()
    val = val.strip()
    if key in _KNOWN_MATCH_KEYS:
        setattr(rule.match, _KNOWN_MATCH_KEYS[key], val)
        return
    if key == "match:fullscreen":
        t = _truthy(val)
        rule.match.fullscreen = t if t is not None else None
        return
    if key == "name":
        rule.name = val
        return
    if key == "float":
        t = _truthy(val)
        if t is not None:
            rule.float = t
            return
    if key == "pin":
        t = _truthy(val)
        if t is not None:
            rule.pin = t
            return
    if key == "center":
        t = _truthy(val)
        if t is not None:
            rule.center = t
            return
    if key == "workspace":
        rule.workspace = val
        return
    if key == "opacity":
        rule.opacity = val
        return
    if key == "size":
        rule.size = val
        return
    if key == "fullscreen":
        rule.fullscreen_state = val
        return
    if key == "no_blur":
        t = _truthy(val)
        if t is not None:
            rule.no_blur = t
            return
    rule.raw_extras.append(f"{key} = {val}")


def parse_rules(text: str) -> list[Rule]:
    """Parse a stream of `windowrule { ... }` blocks. Lines outside blocks are ignored."""
    rules: list[Rule] = []
    current: Rule | None = None
    depth = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if current is None:
            if not line or line.startswith("#"):
                continue
            if line.startswith("windowrule") and "{" in line:
                current = Rule(name="")
                depth = line.count("{") - line.count("}")
                if depth <= 0:
                    current = None
            continue
        # inside a block
        depth += line.count("{") - line.count("}")
        if line == "}" or depth <= 0:
            rules.append(current)
            current = None
            depth = 0
            continue
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, val = line.partition("=")
            _apply_kv(current, key, val)
    return rules
