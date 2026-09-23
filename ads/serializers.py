from rest_framework import serializers

from .models import PRICE_MAX, PRICE_MIN, Ad, Author


class AuthorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Author
        fields = ["id", "name"]


class AdSerializer(serializers.ModelSerializer):
    title = serializers.CharField(max_length=120)
    description = serializers.CharField(max_length=5000)
    price = serializers.DecimalField(
        max_digits=11,
        decimal_places=2,
        min_value=PRICE_MIN,
        max_value=PRICE_MAX,
    )
    status = serializers.ChoiceField(choices=Ad.Status.choices, required=False)
    author = AuthorSerializer(read_only=True)
    author_id = serializers.PrimaryKeyRelatedField(
        source="author", queryset=Author.objects.all(), write_only=True
    )
    expires_at = serializers.DateTimeField(required=False, allow_null=True)

    class Meta:
        model = Ad
        fields = [
            "id",
            "title",
            "description",
            "price",
            "status",
            "author",
            "author_id",
            "expires_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
