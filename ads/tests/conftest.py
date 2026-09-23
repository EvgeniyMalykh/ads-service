import pytest
from rest_framework.test import APIClient

from ads.models import Ad, Author


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def author(db) -> Author:
    return Author.objects.create(name="Иван Петров")


@pytest.fixture
def other_author(db) -> Author:
    return Author.objects.create(name="Мария Смирнова")


@pytest.fixture
def ad_payload(author) -> dict:
    return {
        "title": "Велосипед",
        "description": "Горный велосипед, почти новый",
        "price": "15000.50",
        "author_id": author.id,
    }


@pytest.fixture
def make_ad(author):
    def _make_ad(**kwargs) -> Ad:
        defaults = {
            "title": "Объявление",
            "description": "Описание",
            "price": "100.00",
            "author": author,
        }
        defaults.update(kwargs)
        return Ad.objects.create(**defaults)

    return _make_ad
