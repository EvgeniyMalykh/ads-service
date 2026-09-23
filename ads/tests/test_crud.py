from decimal import Decimal

import pytest

from ads.models import Ad

pytestmark = pytest.mark.django_db

LIST_URL = "/api/ads/"


def detail_url(ad_id) -> str:
    return f"/api/ads/{ad_id}/"


class TestCreate:
    def test_create_returns_201_and_object(self, api_client, ad_payload, author):
        response = api_client.post(LIST_URL, ad_payload, format="json")

        assert response.status_code == 201
        data = response.json()
        assert set(data) == {
            "id",
            "title",
            "description",
            "price",
            "status",
            "author",
            "expires_at",
            "created_at",
            "updated_at",
        }
        assert data["title"] == "Велосипед"
        assert data["price"] == "15000.50"
        assert data["author"] == {"id": author.id, "name": author.name}
        assert data["expires_at"] is None
        assert Ad.objects.filter(pk=data["id"]).exists()

    def test_default_status_is_draft(self, api_client, ad_payload):
        response = api_client.post(LIST_URL, ad_payload, format="json")

        assert response.status_code == 201
        assert response.json()["status"] == "draft"
        assert Ad.objects.get().status == Ad.Status.DRAFT

    @pytest.mark.parametrize("status", ["draft", "published", "archived"])
    def test_status_can_be_set_on_create(self, api_client, ad_payload, status):
        response = api_client.post(LIST_URL, {**ad_payload, "status": status}, format="json")

        assert response.status_code == 201
        assert response.json()["status"] == status

    def test_read_only_fields_are_ignored(self, api_client, ad_payload):
        payload = {
            **ad_payload,
            "id": 999_999,
            "created_at": "2000-01-01T00:00:00Z",
            "updated_at": "2000-01-01T00:00:00Z",
        }
        response = api_client.post(LIST_URL, payload, format="json")

        assert response.status_code == 201
        data = response.json()
        assert data["id"] != 999_999
        assert not data["created_at"].startswith("2000")
        assert not data["updated_at"].startswith("2000")

    def test_price_accepts_number(self, api_client, ad_payload):
        response = api_client.post(LIST_URL, {**ad_payload, "price": 10.5}, format="json")

        assert response.status_code == 201
        assert Ad.objects.get().price == Decimal("10.50")


class TestRetrieve:
    @pytest.mark.parametrize("status", ["draft", "published", "archived"])
    def test_retrieve_in_any_status(self, api_client, make_ad, author, status):
        ad = make_ad(status=status)

        response = api_client.get(detail_url(ad.id))

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == ad.id
        assert data["status"] == status
        assert data["author"] == {"id": author.id, "name": author.name}

    def test_missing_id_returns_404(self, api_client):
        response = api_client.get(detail_url(123456))

        assert response.status_code == 404
        assert "detail" in response.json()

    def test_non_integer_id_returns_404(self, api_client):
        response = api_client.get(detail_url("abc"))

        assert response.status_code == 404


class TestPartialUpdate:
    def test_patch_updates_only_passed_fields(self, api_client, make_ad):
        ad = make_ad(title="Старый", description="Старое описание", price="10.00")
        old_updated_at = ad.updated_at

        response = api_client.patch(detail_url(ad.id), {"title": "Новый"}, format="json")

        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Новый"
        assert data["description"] == "Старое описание"
        assert data["price"] == "10.00"
        assert data["status"] == "draft"
        ad.refresh_from_db()
        assert ad.title == "Новый"
        assert ad.updated_at > old_updated_at

    def test_patch_without_author_keeps_author(self, api_client, make_ad, author):
        ad = make_ad()

        response = api_client.patch(detail_url(ad.id), {"price": "1.00"}, format="json")

        assert response.status_code == 200
        assert response.json()["author"]["id"] == author.id

    def test_patch_changes_author(self, api_client, make_ad, other_author):
        ad = make_ad()

        response = api_client.patch(
            detail_url(ad.id), {"author_id": other_author.id}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["author"] == {"id": other_author.id, "name": other_author.name}

    @pytest.mark.parametrize(
        ("start", "target"),
        [
            ("draft", "published"),
            ("published", "archived"),
            ("archived", "draft"),
            ("archived", "published"),
            ("published", "draft"),
        ],
    )
    def test_any_status_transition_allowed(self, api_client, make_ad, start, target):
        ad = make_ad(status=start)

        response = api_client.patch(detail_url(ad.id), {"status": target}, format="json")

        assert response.status_code == 200
        assert response.json()["status"] == target

    def test_patch_missing_id_returns_404(self, api_client):
        response = api_client.patch(detail_url(123456), {"title": "x"}, format="json")

        assert response.status_code == 404

    def test_put_is_not_allowed(self, api_client, make_ad, ad_payload):
        ad = make_ad()

        response = api_client.put(detail_url(ad.id), ad_payload, format="json")

        assert response.status_code == 405


class TestDelete:
    def test_delete_returns_204_without_body(self, api_client, make_ad):
        ad = make_ad()

        response = api_client.delete(detail_url(ad.id))

        assert response.status_code == 204
        assert response.content == b""
        assert not Ad.objects.filter(pk=ad.id).exists()

    def test_deleted_ad_returns_404(self, api_client, make_ad):
        ad = make_ad()
        api_client.delete(detail_url(ad.id))

        assert api_client.get(detail_url(ad.id)).status_code == 404
        assert api_client.patch(detail_url(ad.id), {"title": "x"}).status_code == 404
        assert api_client.delete(detail_url(ad.id)).status_code == 404

    def test_delete_missing_id_returns_404(self, api_client):
        assert api_client.delete(detail_url(123456)).status_code == 404
