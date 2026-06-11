def pet(request):
    """Sidebar pet widget — cached state, never worth an error page."""
    from .pet import pet_state

    try:
        return {"atlas_pet": pet_state()}
    except Exception:
        return {"atlas_pet": None}


def assistant(request):
    """Props for the assistant island (mounted globally in base.html)."""
    from django.urls import reverse

    try:
        return {"assistant_props": {"contextUrl": reverse("core:assistant_context")}}
    except Exception:  # URL not wired yet (e.g. partial deploys) — island simply won't mount
        return {"assistant_props": {"contextUrl": ""}}
