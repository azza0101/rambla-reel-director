"""Shared typography rules for editable Resolve highlight titles."""


def wrap_textplus_text(text: str, *, max_chars: int = 11) -> str:
    """Wrap highlighted copy at word boundaries for vertical-safe titles."""
    if max_chars < 1:
        raise ValueError('max_chars must be positive')
    words = str(text or '').split()
    if not words:
        return ''
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = current + ' ' + word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return '\n'.join(lines)
