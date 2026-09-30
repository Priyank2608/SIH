"""Layer 7 — single, consistent output-escape choke point.

Every user-supplied string that reaches a rendering context (ReportLab PDF
paragraphs, HTML views, JSON error surfaces) is passed through `escape_text`
here first, so escaping is correct in one place instead of N places. The PDF
report builder routes all user text through this function; the frontend's
React-by-default rendering is the browser-side counterpart.
"""
from xml.sax.saxutils import escape as _xml_escape


def escape_text(value) -> str:
    """Escape a user-supplied value for safe inclusion in markup contexts
    (ReportLab paragraphs use an HTML-ish mini-language, hence XML escaping).

    Never raises: None becomes '', non-strings are coerced via str().
    """
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return _xml_escape(value, entities={
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    })
