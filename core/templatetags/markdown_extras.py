import markdown as md
import nh3
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="markdownify")
def markdownify(text):
    if not text:
        return ""
    html = md.markdown(text, extensions=["fenced_code", "tables"])
    return mark_safe(nh3.clean(html))  # noqa: S308 — nh3 sanitizes the HTML


@register.filter(name="mentions")
def mentions(text):
    """Turn [[Note Title]] and @cite-key into markdown links; pipe into markdownify."""
    from core.mentions import resolve_mentions

    return resolve_mentions(text)
