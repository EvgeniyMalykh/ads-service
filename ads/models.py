from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

PRICE_MIN = Decimal("0")
PRICE_MAX = Decimal("999999999.99")


class Author(models.Model):
    name = models.CharField("имя", max_length=120)

    class Meta:
        verbose_name = "автор"
        verbose_name_plural = "авторы"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(name__regex=r"^\s*$"),
                name="author_name_not_blank",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class AdStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    PUBLISHED = "published", "Опубликовано"
    ARCHIVED = "archived", "В архиве"


class Ad(models.Model):
    Status = AdStatus

    title = models.CharField("заголовок", max_length=120)
    description = models.CharField("описание", max_length=5000)
    price = models.DecimalField(
        "цена, ₽",
        max_digits=11,
        decimal_places=2,
        validators=[MinValueValidator(PRICE_MIN), MaxValueValidator(PRICE_MAX)],
    )
    status = models.CharField("статус", max_length=16, choices=Status.choices, default=Status.DRAFT)
    author = models.ForeignKey(
        Author, on_delete=models.PROTECT, related_name="ads", verbose_name="автор"
    )
    expires_at = models.DateTimeField("окончание публикации", null=True, blank=True)
    created_at = models.DateTimeField("создано", auto_now_add=True)
    updated_at = models.DateTimeField("изменено", auto_now=True)

    class Meta:
        verbose_name = "объявление"
        verbose_name_plural = "объявления"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "-created_at", "-id"], name="ad_status_created_idx"),
            models.Index(fields=["status", "expires_at"], name="ad_status_expires_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(price__gte=PRICE_MIN) & models.Q(price__lte=PRICE_MAX),
                name="ad_price_range",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=AdStatus.values),
                name="ad_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(title__regex=r"^\s*$"),
                name="ad_title_not_blank",
            ),
            models.CheckConstraint(
                condition=~models.Q(description__regex=r"^\s*$"),
                name="ad_description_not_blank",
            ),
        ]

    def __str__(self) -> str:
        return self.title
