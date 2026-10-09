from django.conf.urls.static import static
from django.conf import settings
from django.urls import include, path


urlpatterns = [
    path(
        "api/v1/",
        include("presentation.api.urls")
    ),
]


if settings.DEBUG:
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )
