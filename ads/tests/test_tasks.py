from datetime import timedelta

import pytest
from django.conf import settings
from django.utils import timezone

from ads.models import Ad
from ads.tasks import archive_expired_ads

pytestmark = pytest.mark.django_db


class TestArchiveExpiredAds:
    def test_archives_expired_published_ads(self, make_ad):
        now = timezone.now()
        expired = make_ad(status=Ad.Status.PUBLISHED, expires_at=now - timedelta(minutes=1))

        assert archive_expired_ads() == 1

        expired.refresh_from_db()
        assert expired.status == Ad.Status.ARCHIVED

    def test_expires_at_equal_now_is_archived(self, make_ad, monkeypatch):
        now = timezone.now()
        ad = make_ad(status=Ad.Status.PUBLISHED, expires_at=now)
        monkeypatch.setattr("ads.tasks.timezone.now", lambda: now)

        assert archive_expired_ads() == 1
        ad.refresh_from_db()
        assert ad.status == Ad.Status.ARCHIVED

    def test_future_expires_at_stays_published(self, make_ad):
        ad = make_ad(status=Ad.Status.PUBLISHED, expires_at=timezone.now() + timedelta(hours=1))

        assert archive_expired_ads() == 0
        ad.refresh_from_db()
        assert ad.status == Ad.Status.PUBLISHED

    def test_without_expires_at_stays_published(self, make_ad):
        ad = make_ad(status=Ad.Status.PUBLISHED, expires_at=None)

        assert archive_expired_ads() == 0
        ad.refresh_from_db()
        assert ad.status == Ad.Status.PUBLISHED

    @pytest.mark.parametrize("status", [Ad.Status.DRAFT, Ad.Status.ARCHIVED])
    def test_non_published_ads_untouched(self, make_ad, status):
        ad = make_ad(status=status, expires_at=timezone.now() - timedelta(days=1))
        old_updated_at = ad.updated_at

        assert archive_expired_ads() == 0
        ad.refresh_from_db()
        assert ad.status == status
        assert ad.updated_at == old_updated_at

    def test_updates_updated_at(self, make_ad):
        ad = make_ad(status=Ad.Status.PUBLISHED, expires_at=timezone.now() - timedelta(days=1))
        old_updated_at = ad.updated_at

        archive_expired_ads()

        ad.refresh_from_db()
        assert ad.updated_at > old_updated_at

    def test_repeated_run_is_safe(self, make_ad):
        past = timezone.now() - timedelta(minutes=5)
        ads = [make_ad(status=Ad.Status.PUBLISHED, expires_at=past) for _ in range(3)]

        assert archive_expired_ads() == 3
        updated_at = {a.pk: Ad.objects.get(pk=a.pk).updated_at for a in ads}

        assert archive_expired_ads() == 0
        for ad in ads:
            ad.refresh_from_db()
            assert ad.status == Ad.Status.ARCHIVED
            assert ad.updated_at == updated_at[ad.pk]

    def test_republished_expired_ad_is_archived_again(self, make_ad):
        ad = make_ad(status=Ad.Status.PUBLISHED, expires_at=timezone.now() - timedelta(minutes=1))
        archive_expired_ads()
        Ad.objects.filter(pk=ad.pk).update(status=Ad.Status.PUBLISHED)

        assert archive_expired_ads() == 1

    def test_task_runs_via_celery_apply(self, make_ad):
        make_ad(status=Ad.Status.PUBLISHED, expires_at=timezone.now() - timedelta(minutes=1))

        result = archive_expired_ads.apply()

        assert result.successful()
        assert result.result == 1

    def test_beat_schedule_runs_every_minute(self):
        entry = settings.CELERY_BEAT_SCHEDULE["archive-expired-ads"]
        assert entry["task"] == "ads.tasks.archive_expired_ads"
        assert entry["schedule"] == 60.0


class TestExpiresAtApi:
    def test_create_with_expires_at(self, api_client, ad_payload):
        response = api_client.post(
            "/api/ads/",
            {**ad_payload, "status": "published", "expires_at": "2030-01-01T12:00:00Z"},
            format="json",
        )

        assert response.status_code == 201
        assert response.json()["expires_at"] == "2030-01-01T12:00:00Z"

    def test_expires_at_can_be_cleared(self, api_client, make_ad):
        ad = make_ad(expires_at=timezone.now())

        response = api_client.patch(f"/api/ads/{ad.id}/", {"expires_at": None}, format="json")

        assert response.status_code == 200
        assert response.json()["expires_at"] is None

    def test_invalid_expires_at(self, api_client, ad_payload):
        response = api_client.post(
            "/api/ads/", {**ad_payload, "expires_at": "not-a-date"}, format="json"
        )

        assert response.status_code == 400
        assert "expires_at" in response.json()

    def test_expired_ad_disappears_from_list(self, api_client, make_ad):
        make_ad(status=Ad.Status.PUBLISHED, expires_at=timezone.now() - timedelta(seconds=1))
        assert len(api_client.get("/api/ads/").json()) == 1

        archive_expired_ads()

        assert api_client.get("/api/ads/").json() == []
        assert len(api_client.get("/api/ads/", {"status": "archived"}).json()) == 1
