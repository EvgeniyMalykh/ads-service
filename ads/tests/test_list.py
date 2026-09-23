from datetime import timedelta

import pytest
from django.utils import timezone

from ads.models import Ad

pytestmark = pytest.mark.django_db

LIST_URL = "/api/ads/"


def ids(response) -> list[int]:
    return [item["id"] for item in response.json()]


class TestDefaultVisibility:
    def test_list_returns_array_of_published_by_default(self, api_client, make_ad, author):
        published = make_ad(status=Ad.Status.PUBLISHED)
        make_ad(status=Ad.Status.DRAFT)
        make_ad(status=Ad.Status.ARCHIVED)

        response = api_client.get(LIST_URL)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert ids(response) == [published.id]
        assert data[0]["author"] == {"id": author.id, "name": author.name}

    def test_empty_list(self, api_client):
        response = api_client.get(LIST_URL)

        assert response.status_code == 200
        assert response.json() == []

    def test_publish_via_patch_makes_ad_visible(self, api_client, ad_payload):
        ad_id = api_client.post(LIST_URL, ad_payload, format="json").json()["id"]
        assert ad_id not in ids(api_client.get(LIST_URL))

        response = api_client.patch(f"/api/ads/{ad_id}/", {"status": "published"}, format="json")

        assert response.status_code == 200
        assert ids(api_client.get(LIST_URL)) == [ad_id]

    def test_archive_via_patch_hides_ad(self, api_client, make_ad):
        ad = make_ad(status=Ad.Status.PUBLISHED)

        api_client.patch(f"/api/ads/{ad.id}/", {"status": "archived"}, format="json")

        assert api_client.get(LIST_URL).json() == []


class TestStatusFilter:
    @pytest.mark.parametrize("status", ["draft", "published", "archived"])
    def test_filter_by_status(self, api_client, make_ad, status):
        expected = {s: make_ad(status=s).id for s in Ad.Status.values}

        response = api_client.get(LIST_URL, {"status": status})

        assert response.status_code == 200
        assert ids(response) == [expected[status]]

    @pytest.mark.parametrize("status", ["deleted", "PUBLISHED", "", "all"])
    def test_invalid_status_filter_returns_400(self, api_client, status):
        response = api_client.get(LIST_URL, {"status": status})

        assert response.status_code == 400
        assert "status" in response.json()


class TestSearch:
    def test_search_substring_case_insensitive(self, api_client, make_ad):
        bike = make_ad(title="Горный ВЕЛОСИПЕД", status=Ad.Status.PUBLISHED)
        kids_bike = make_ad(title="детский велосипед", status=Ad.Status.PUBLISHED)
        make_ad(title="Самокат", status=Ad.Status.PUBLISHED)

        response = api_client.get(LIST_URL, {"search": "ВелоСип"})

        assert response.status_code == 200
        assert set(ids(response)) == {bike.id, kids_bike.id}

    def test_search_only_in_title(self, api_client, make_ad):
        make_ad(title="Самокат", description="не велосипед", status=Ad.Status.PUBLISHED)

        assert api_client.get(LIST_URL, {"search": "велосипед"}).json() == []

    def test_search_latin_case_insensitive(self, api_client, make_ad):
        ad = make_ad(title="iPhone 15 Pro", status=Ad.Status.PUBLISHED)

        assert ids(api_client.get(LIST_URL, {"search": "IPHONE"})) == [ad.id]

    def test_search_special_characters_are_literal(self, api_client, make_ad):
        ad = make_ad(title="Скидка 50% на всё", status=Ad.Status.PUBLISHED)
        make_ad(title="Скидка 50 рублей", status=Ad.Status.PUBLISHED)

        assert ids(api_client.get(LIST_URL, {"search": "50%"})) == [ad.id]
        assert api_client.get(LIST_URL, {"search": "_"}).json() == []

    def test_empty_search_returns_all(self, api_client, make_ad):
        make_ad(status=Ad.Status.PUBLISHED)
        make_ad(status=Ad.Status.PUBLISHED)

        assert len(api_client.get(LIST_URL, {"search": ""}).json()) == 2

    def test_search_uses_default_published_status(self, api_client, make_ad):
        published = make_ad(title="Велосипед", status=Ad.Status.PUBLISHED)
        make_ad(title="Велосипед", status=Ad.Status.DRAFT)

        assert ids(api_client.get(LIST_URL, {"search": "велосипед"})) == [published.id]


class TestCombinedFilters:
    def test_status_and_search_together(self, api_client, make_ad):
        draft_bike = make_ad(title="Велосипед", status=Ad.Status.DRAFT)
        make_ad(title="Велосипед", status=Ad.Status.PUBLISHED)
        make_ad(title="Самокат", status=Ad.Status.DRAFT)

        response = api_client.get(LIST_URL, {"status": "draft", "search": "велос"})

        assert response.status_code == 200
        assert ids(response) == [draft_bike.id]

    def test_invalid_status_with_search_returns_400(self, api_client):
        response = api_client.get(LIST_URL, {"status": "bad", "search": "x"})

        assert response.status_code == 400


class TestOrdering:
    def test_newest_first(self, api_client, make_ad):
        now = timezone.now()
        old = make_ad(status=Ad.Status.PUBLISHED)
        new = make_ad(status=Ad.Status.PUBLISHED)
        middle = make_ad(status=Ad.Status.PUBLISHED)
        Ad.objects.filter(pk=old.pk).update(created_at=now - timedelta(days=2))
        Ad.objects.filter(pk=middle.pk).update(created_at=now - timedelta(days=1))
        Ad.objects.filter(pk=new.pk).update(created_at=now)

        assert ids(api_client.get(LIST_URL)) == [new.id, middle.id, old.id]

    def test_same_created_at_ordered_by_id_desc(self, api_client, make_ad):
        same_time = timezone.now()
        ads = [make_ad(status=Ad.Status.PUBLISHED) for _ in range(3)]
        Ad.objects.filter(pk__in=[a.pk for a in ads]).update(created_at=same_time)
        older = make_ad(status=Ad.Status.PUBLISHED)
        Ad.objects.filter(pk=older.pk).update(created_at=same_time - timedelta(seconds=1))

        expected = sorted((a.id for a in ads), reverse=True) + [older.id]
        assert ids(api_client.get(LIST_URL)) == expected

    def test_ordering_with_filters(self, api_client, make_ad):
        now = timezone.now()
        first = make_ad(title="Велосипед 1", status=Ad.Status.DRAFT)
        second = make_ad(title="Велосипед 2", status=Ad.Status.DRAFT)
        Ad.objects.filter(pk=first.pk).update(created_at=now)
        Ad.objects.filter(pk=second.pk).update(created_at=now - timedelta(hours=1))

        response = api_client.get(LIST_URL, {"status": "draft", "search": "велосипед"})

        assert ids(response) == [first.id, second.id]
