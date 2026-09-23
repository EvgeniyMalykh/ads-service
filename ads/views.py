from django.http import Http404, JsonResponse
from rest_framework import mixins, viewsets
from rest_framework.exceptions import NotFound

from .filters import AdListQuerySerializer
from .models import Ad
from .serializers import AdSerializer


class AdViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """CRUD объявлений. PUT намеренно отключён — обновление только через PATCH."""

    serializer_class = AdSerializer
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        queryset = Ad.objects.select_related("author").order_by("-created_at", "-id")
        if self.action != "list":
            # Детальная ручка отдаёт объявление в любом статусе.
            return queryset

        params = AdListQuerySerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        queryset = queryset.filter(status=params.validated_data["status"])
        search = params.validated_data.get("search")
        if search:
            queryset = queryset.filter(title__icontains=search)
        return queryset

    def get_object(self):
        try:
            return super().get_object()
        except Http404 as exc:
            raise NotFound(f"Объявление с id={self.kwargs['pk']} не найдено.") from exc


def not_found(request, exception=None):
    return JsonResponse(
        {"detail": "Ресурс не найден."}, status=404, json_dumps_params={"ensure_ascii": False}
    )


def server_error(request):
    return JsonResponse(
        {"detail": "Внутренняя ошибка сервера."},
        status=500,
        json_dumps_params={"ensure_ascii": False},
    )
