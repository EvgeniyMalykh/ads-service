from rest_framework.routers import DefaultRouter

from .views import AdViewSet

router = DefaultRouter(trailing_slash=True)
router.include_root_view = False
router.register("ads", AdViewSet, basename="ad")

urlpatterns = router.urls
