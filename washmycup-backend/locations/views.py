from django.db.models import Count, Q
from rest_framework import mixins, serializers, status, viewsets
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
from .services import build_reliability_report, verify_location_photo


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
        self.check_photo(serializer.validated_data.get('photo'))
        location = serializer.save()
        # 응답은 목록과 같은 형태로 맞춰, 앱이 그대로 지도에 마커를 추가할 수 있게 한다.
        location = self.get_queryset().get(pk=location.pk)
        output = LocationListSerializer(location, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def check_photo(self, photo):
        """세척 설비와 무관한 사진이면 등록을 막는다.

        판단이 확실할 때만 거절하고, 검증 자체가 실패하면 통과시킨다.
        (services.verify_location_photo 참고)
        """
        if not photo:
            return

        photo.seek(0)
        image_bytes = photo.read()
        photo.seek(0)  # 이어서 저장해야 하므로 스트림을 되돌려 둔다.

        result = verify_location_photo(image_bytes, getattr(photo, 'content_type', None))
        if result['ok']:
            return

        reason = result['reason'] or '세척 설비가 보이지 않습니다.'
        raise serializers.ValidationError({
            'photo': [f'{reason} 세척기가 나온 사진으로 다시 올려주세요.'],
        })

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
        location = self.get_object()
        refresh = request.query_params.get('refresh') == '1'
        report = build_reliability_report(location, use_cache=not refresh)
        return Response(report)

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
