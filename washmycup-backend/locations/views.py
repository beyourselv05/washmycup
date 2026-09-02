from django.db.models import Count, Q
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from .models import Location, Review
from .serializers import (
    LocationCreateSerializer,
    LocationDetailSerializer,
    LocationListSerializer,
    ReportSerializer,
    ReviewSerializer,
)
from .services import initialize_reliability


class LocationViewSet(mixins.ListModelMixin,
                      mixins.CreateModelMixin,
                      mixins.RetrieveModelMixin,
                      viewsets.GenericViewSet):
    """세척기 위치 목록/등록/상세 + 리뷰·신고·AI 신뢰도 엔드포인트."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        queryset = (
            Location.objects
            .exclude(status=Location.Status.REMOVED)
            .annotate(
                up_count=Count('reviews', filter=Q(reviews__type=Review.Type.UP)),
                down_count=Count('reviews', filter=Q(reviews__type=Review.Type.DOWN)),
            )
            .order_by('-created_at')
        )
        if self.action == 'retrieve':
            queryset = queryset.prefetch_related('reviews')
        return queryset

    def get_serializer_class(self):
        if self.action == 'create':
            return LocationCreateSerializer
        if self.action == 'retrieve':
            return LocationDetailSerializer
        return LocationListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        location = serializer.save()
        # 백그라운드 워커가 돌기 전까지 reliability 필드가 비어있지 않도록 즉시 채워둔다.
        initialize_reliability(location)
        # 응답은 목록과 같은 형태로 맞춰, 앱이 그대로 지도에 마커를 추가할 수 있게 한다.
        location = self.get_queryset().get(pk=location.pk)
        output = LocationListSerializer(location, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get', 'post'], url_path='reviews')
    def reviews(self, request, pk=None):
        location = self.get_object()

        if request.method == 'GET':
            serializer = ReviewSerializer(location.reviews.all(), many=True)
            return Response(serializer.data)

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(location=location)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='reliability')
    def reliability(self, request, pk=None):
        # Gemini는 여기서 절대 호출하지 않는다 — 백그라운드 워커(update_reliability)가
        # 미리 계산해둔 값을 읽기만 하므로 동시접속자가 많아도 응답이 항상 즉시 나온다.
        location = self.get_object()
        return Response({
            'score': location.reliability_score,
            'summary': location.reliability_summary,
            'updated_at': location.reliability_updated_at,
        })

    @action(detail=True, methods=['post'], url_path='report')
    def report(self, request, pk=None):
        location = self.get_object()
        serializer = ReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(location=location)

        # 신고가 들어오면 관리자가 확인할 때까지 지도에 '검토중'으로 표시한다.
        if location.status != Location.Status.REVIEWING:
            location.status = Location.Status.REVIEWING
            location.save(update_fields=['status'])

        return Response(serializer.data, status=status.HTTP_201_CREATED)
