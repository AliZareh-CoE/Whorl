import pytest
from django.contrib.auth.models import User


@pytest.fixture
def owner(db):
    return User.objects.create_superuser("owner", password="pw")


@pytest.fixture
def client_logged_in(client, owner):
    client.force_login(owner)
    return client
