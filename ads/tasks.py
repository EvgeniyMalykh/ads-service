from celery import shared_task
from django.utils import timezone

from .models import Ad


@shared_task(name="ads.tasks.archive_expired_ads")
def archive_expired_ads() -> int:
    """Переводит опубликованные объявления с истёкшим expires_at в архив.

    Операция идемпотентна: один UPDATE с условием status=published, поэтому
    повторный или параллельный запуск не меняет уже архивированные записи.
    Возвращает количество архивированных объявлений.
    """
    now = timezone.now()
    return Ad.objects.filter(
        status=Ad.Status.PUBLISHED,
        expires_at__isnull=False,
        expires_at__lte=now,
    ).update(status=Ad.Status.ARCHIVED, updated_at=now)
