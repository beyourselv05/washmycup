"""URL configuration for the CupPit backend."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('locations.urls')),
]

if settings.DEBUG:
    # 개발 중에는 업로드된 세척기 사진을 Django가 직접 서빙한다.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
