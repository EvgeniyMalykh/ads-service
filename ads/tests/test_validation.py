import pytest

from ads.models import Ad

pytestmark = pytest.mark.django_db

LIST_URL = "/api/ads/"


def post(client, payload):
    return client.post(LIST_URL, payload, format="json")


class TestRequiredFields:
    @pytest.mark.parametrize("field", ["title", "description", "price", "author_id"])
    def test_missing_required_field(self, api_client, ad_payload, field):
        ad_payload.pop(field)

        response = post(api_client, ad_payload)

        assert response.status_code == 400
        assert field in response.json()
        assert not Ad.objects.exists()

    def test_empty_body(self, api_client):
        response = post(api_client, {})

        assert response.status_code == 400
        assert set(response.json()) == {"title", "description", "price", "author_id"}

    @pytest.mark.parametrize("field", ["title", "description"])
    @pytest.mark.parametrize("value", ["", "   ", "\t\n "])
    def test_blank_strings_rejected(self, api_client, ad_payload, field, value):
        response = post(api_client, {**ad_payload, field: value})

        assert response.status_code == 400
        assert field in response.json()

    @pytest.mark.parametrize("field", ["title", "description", "price", "author_id", "status"])
    def test_null_rejected(self, api_client, ad_payload, field):
        response = post(api_client, {**ad_payload, field: None})

        assert response.status_code == 400
        assert field in response.json()

    def test_title_max_length(self, api_client, ad_payload):
        assert post(api_client, {**ad_payload, "title": "a" * 120}).status_code == 201

        response = post(api_client, {**ad_payload, "title": "a" * 121})
        assert response.status_code == 400
        assert "title" in response.json()

    def test_description_max_length(self, api_client, ad_payload):
        assert post(api_client, {**ad_payload, "description": "a" * 5000}).status_code == 201

        response = post(api_client, {**ad_payload, "description": "a" * 5001})
        assert response.status_code == 400
        assert "description" in response.json()

    def test_blank_title_rejected_on_patch(self, api_client, make_ad):
        ad = make_ad()

        response = api_client.patch(f"/api/ads/{ad.id}/", {"title": "  "}, format="json")

        assert response.status_code == 400
        assert "title" in response.json()


class TestPrice:
    @pytest.mark.parametrize("price", ["0", "0.00", "0.01", "999999999.99", 100, "12.3"])
    def test_valid_prices(self, api_client, ad_payload, price):
        assert post(api_client, {**ad_payload, "price": price}).status_code == 201

    @pytest.mark.parametrize(
        "price",
        [
            "-0.01",
            "-1",
            "1000000000",
            "999999999.999",
            "10.123",
            "abc",
            "",
            True,
            "NaN",
            "Infinity",
            [],
            {},
        ],
    )
    def test_invalid_prices(self, api_client, ad_payload, price):
        response = post(api_client, {**ad_payload, "price": price})

        assert response.status_code == 400
        assert "price" in response.json()

    def test_invalid_price_on_patch(self, api_client, make_ad):
        ad = make_ad()

        response = api_client.patch(f"/api/ads/{ad.id}/", {"price": "-5"}, format="json")

        assert response.status_code == 400
        assert "price" in response.json()


class TestStatus:
    @pytest.mark.parametrize("status", ["deleted", "PUBLISHED", "", 1])
    def test_invalid_status_on_create(self, api_client, ad_payload, status):
        response = post(api_client, {**ad_payload, "status": status})

        assert response.status_code == 400
        assert "status" in response.json()

    def test_invalid_status_on_patch(self, api_client, make_ad):
        ad = make_ad()

        response = api_client.patch(f"/api/ads/{ad.id}/", {"status": "sold"}, format="json")

        assert response.status_code == 400
        assert "status" in response.json()
        ad.refresh_from_db()
        assert ad.status == Ad.Status.DRAFT


class TestAuthor:
    def test_unknown_author_on_create(self, api_client, ad_payload):
        response = post(api_client, {**ad_payload, "author_id": 999_999})

        assert response.status_code == 400
        assert "author_id" in response.json()

    @pytest.mark.parametrize("value", ["abc", [], 1.5])
    def test_invalid_author_type(self, api_client, ad_payload, value):
        response = post(api_client, {**ad_payload, "author_id": value})

        assert response.status_code == 400
        assert "author_id" in response.json()

    def test_unknown_author_on_patch(self, api_client, make_ad):
        ad = make_ad()

        response = api_client.patch(f"/api/ads/{ad.id}/", {"author_id": 999_999}, format="json")

        assert response.status_code == 400
        assert "author_id" in response.json()


class TestRequestFormat:
    def test_invalid_json(self, api_client):
        response = api_client.post(LIST_URL, "{bad json", content_type="application/json")

        assert response.status_code == 400
        assert "detail" in response.json()

    def test_unsupported_media_type(self, api_client):
        response = api_client.post(LIST_URL, "title=x", content_type="text/plain")

        assert response.status_code == 415
