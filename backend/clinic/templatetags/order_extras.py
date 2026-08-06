"""Small template helpers for the ordering forms."""
from django import template

register = template.Library()


@register.filter
def dictkey(mapping, key):
    """Look up ``mapping[key]`` from a template, tolerating anything odd.

    Item rows are plain dicts whose columns vary per form, so the template
    needs to read a value by a key it only knows at render time.
    """
    try:
        return mapping.get(key, "")
    except Exception:
        return ""
