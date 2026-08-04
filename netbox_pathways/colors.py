"""Resolve color names to the hex codes NetBox's core color palette uses.

Innerduct colors were free text originally, and users typed names by
hand ("blue", "slate"). The field now stores a 6-digit hex code, so the
0022 data migration and the CSV import form both need to translate those
names -- and keep accepting them, since operators paste the same
spreadsheets year after year.
"""

import re

from netbox.choices import ColorChoices

# Names the core palette does not carry. "Slate" and "violet" are two of the
# telecom 12-color code; the rest are spellings seen in imported plant data.
_SYNONYMS = {
    "slate": ColorChoices.COLOR_DARK_GREY,
    "violet": ColorChoices.COLOR_PURPLE,
    "magenta": ColorChoices.COLOR_FUCHSIA,
    "silver": ColorChoices.COLOR_LIGHT_GREY,
    "natural": ColorChoices.COLOR_WHITE,
    "clear": ColorChoices.COLOR_WHITE,
}

# Labels first, so a deployment that extends ColorChoices via FIELD_CHOICES
# gets its additions; then the COLOR_* constant names, which stay English
# even where the labels are translated.
_HEX_BY_NAME = {str(label).lower(): value for value, label in ColorChoices.CHOICES}
_HEX_BY_NAME.update(
    {
        name.removeprefix("COLOR_").replace("_", " ").lower(): value
        for name, value in vars(ColorChoices).items()
        if name.startswith("COLOR_")
    }
)
# The palette labels all spell it "grey".
_HEX_BY_NAME.update({name.replace("grey", "gray"): value for name, value in _HEX_BY_NAME.items() if "grey" in name})
_HEX_BY_NAME.update(_SYNONYMS)

_HEX_RE = re.compile(r"^#?([0-9a-f]{3}|[0-9a-f]{6})$")


def color_to_hex(value):
    """Return `value` as a 6-digit lowercase hex code, without the leading '#'.

    Blank input returns blank. A value matching neither a known name nor a
    hex code returns None, leaving the caller to choose between dropping it
    (the migration) and reporting an error (the import form).
    """
    if not value:
        return ""
    text = str(value).strip().lower()
    if not text:
        return ""
    if named := _HEX_BY_NAME.get(text):
        return named
    match = _HEX_RE.match(text)
    if not match:
        return None
    digits = match.group(1)
    return "".join(digit * 2 for digit in digits) if len(digits) == 3 else digits
