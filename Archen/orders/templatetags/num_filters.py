# Custom numeric filters for templates in the orders app.
# Comments must be in English as per project guideline.

from django import template

register = template.Library()


@register.filter(name="to_english_digits")
def to_english_digits(value: object) -> str:
    """Convert Persian/Arabic-Indic digits to ASCII 0-9.

    This ensures serials and other identifiers render in English digits
    regardless of locale or fonts. Non-digit characters are preserved.
    """
    s = str(value or "")
    out_chars = []
    for ch in s:
        code = ord(ch)
        # Persian digits U+06F0..U+06F9
        if 0x06F0 <= code <= 0x06F9:
            out_chars.append(chr(code - 0x06F0 + ord("0")))
            continue
        # Arabic-Indic digits U+0660..U+0669
        if 0x0660 <= code <= 0x0669:
            out_chars.append(chr(code - 0x0660 + ord("0")))
            continue
        out_chars.append(ch)
    return "".join(out_chars)

