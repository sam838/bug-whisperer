"""Kane's voice: turn Kane CLI's step remarks into Kane speaking in the first person.

Kane logs steps like 'click: Clicking Book appointment button' or
'type: Type "{{secrets.user.account1_password}}" into "Password"'. On the website, Kane is the
detective, so each step reads as Kane telling you what it did: "I clicked Book appointment."
Credentials stay as placeholders ("the test password"), never real values.
"""

from __future__ import annotations

import re

_PREFIX = re.compile(r"^(?P<kind>[a-z_]+):\s*(?:(?:PRIMARY|SECONDARY):\s*)?(?P<rest>.*)$", re.S)
_QUOTED = re.compile(r'"([^"]+)"')
_SECRETS = [
    (re.compile(r"\{\{(?:secrets\.user\.)?account(\d)_password\}\}"), "the test password"),
    (re.compile(r"\{\{(?:global\.)?account(\d)_email\}\}"), "the test email"),
    (re.compile(r"\{\{(?:global\.|secrets\.user\.)?([a-z0-9_]+)\}\}"), r"the \1"),
]
# Kane's own bookkeeping: true, but not something a detective would say out loud.
_SKIP = re.compile(r"^(queued plan|ANALYZE\(|Step \d+$|Waiting for the next step|wait \d+ ?ms)", re.I)


_ICONS = re.compile(r"[-\U000f0000-\U000fffff​-‏️]")  # icon-font glyphs


def _clean(text: str) -> str:
    for pattern, replacement in _SECRETS:
        text = pattern.sub(replacement, text)
    text = _ICONS.sub("", text)  # buttons labelled with icon fonts show up as boxes otherwise
    return re.sub(r"\s{2,}", " ", text).strip().rstrip(".")


def _quoted(text: str) -> list[str]:
    return [_clean(q) for q in _QUOTED.findall(text)]


def speak(remark: str | None) -> str | None:
    """One Kane step remark → one first-person sentence, or None if it's bookkeeping."""
    if not remark:
        return None
    match = _PREFIX.match(remark.strip())
    kind, rest = (match["kind"], match["rest"]) if match else ("", remark.strip())
    if _SKIP.match(rest):
        return None
    rest = _SELECTOR.sub("", rest)  # Kane's element locators ('; role=button; text=...')
    q = _quoted(rest)
    lower = rest.lower()

    if kind == "navigate":
        url = re.search(r"https?://\S+", rest)
        if url:
            return f"I went to {url.group(0).rstrip('.')}."
        return f"I went to {_clean(re.sub(r'^(go|going|navigate|navigating)\s+to\s+', '', rest, flags=re.I))}."
    if kind in ("press", "key", "keyboard") or re.match(r"^press\s", rest, re.I):
        return f"I pressed {_clean(re.sub(r'^(press(ing)?)\s+', '', rest, flags=re.I))}."
    if kind in ("type", "fill"):
        if len(q) >= 2:
            return f"I typed {q[0]} into {q[1]}."
        return f"I {_clean(re.sub(r'^(typing|entering)\s+', 'typed ', rest, flags=re.I))}."
    if kind == "select":
        if len(q) >= 2:
            return f"I picked {q[0]} in {q[1]}."
        return f"I {_clean(re.sub(r'^selecting\s+', 'picked ', rest, flags=re.I))}."
    if kind == "click":
        if q:
            return f"I clicked {q[0]}."
        target = re.sub(r"^(clicking|click(ed)?)\s+(on\s+)?(the\s+)?", "", rest, flags=re.I)
        return f"I clicked {_clean(target)}."
    if kind == "assert":
        return f"I checked: {_clean(rest)}."
    if kind == "analyze":
        return f"I looked closely: {_clean(rest)}."
    if kind == "wait":
        if "load" in lower or "result" in lower or "confirm" in lower or "verify" in lower:
            return "I waited to see what the page did."
        return None
    if kind == "scroll" or lower.startswith("scroll"):
        return "I scrolled the page."
    text = _clean(re.sub(r"^[a-z_]+:\s*", "", rest))
    first, _, others = text.partition(" ")
    verb = _PAST.get(first.lower())
    if verb:  # 'move keyboard focus to …' → 'I moved keyboard focus to …'
        return f"I {verb} {others}." if others else f"I {verb}."
    return (text[:1].upper() + text[1:] + ".") if text else None


_SELECTOR = re.compile(r";\s*(role|text|name|label|placeholder|testid|css|xpath)\s*=.*$", re.I | re.S)
_PAST = {"move": "moved", "focus": "focused", "hover": "hovered over", "open": "opened",
         "close": "closed", "check": "checked", "uncheck": "unchecked", "submit": "submitted",
         "upload": "uploaded", "drag": "dragged", "clear": "cleared", "go": "went", "find": "found"}
