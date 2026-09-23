from django.urls import include, path

urlpatterns = [
    path("api/", include("ads.urls")),
]

handler404 = "ads.views.not_found"
handler500 = "ads.views.server_error"
