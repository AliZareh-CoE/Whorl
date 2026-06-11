def pet(request):
    """Sidebar pet widget — cached state, never worth an error page."""
    from .pet import pet_state

    try:
        return {"atlas_pet": pet_state()}
    except Exception:
        return {"atlas_pet": None}
