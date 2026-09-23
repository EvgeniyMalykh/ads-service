from rest_framework import serializers

from .models import Ad


class AdListQuerySerializer(serializers.Serializer):
    """Валидация query-параметров списка объявлений.

    status — один из draft/published/archived (по умолчанию published);
    пустое или неизвестное значение — ошибка 400.
    search — подстрока для регистронезависимого поиска по title.
    """

    status = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)
    search = serializers.CharField(required=False, allow_blank=True, trim_whitespace=False)

    def validate_status(self, value: str) -> str:
        if value not in Ad.Status.values:
            allowed = ", ".join(Ad.Status.values)
            raise serializers.ValidationError(
                f"Недопустимое значение «{value}». Допустимые значения: {allowed}."
            )
        return value

    def validate(self, attrs: dict) -> dict:
        attrs.setdefault("status", Ad.Status.PUBLISHED)
        return attrs
