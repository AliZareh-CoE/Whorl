import pytest
from django.contrib.auth.models import User
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _clean_cache():
    """Keep Django's cache from leaking state (heatmap, login throttle) across tests."""
    cache.clear()
    yield


@pytest.fixture
def owner(db):
    return User.objects.create_superuser("owner", password="pw")


@pytest.fixture
def client_logged_in(client, owner):
    client.force_login(owner)
    return client
