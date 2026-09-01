from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import LocationViewSet, UsageReportView, UsageViewSet

router = DefaultRouter()
router.register('locations', LocationViewSet, basename='location')
router.register('usages', UsageViewSet, basename='usage')

urlpatterns = [
    # 로그인이 없는 프로토타입이라 'me'는 이 기기의 기록 전체를 뜻한다.
    path('me/report/', UsageReportView.as_view(), name='usage-report'),
] + router.urls
