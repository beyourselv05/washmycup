from django.db.models import Count, Q
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Location, Review, Usage
from .serializers import (
    LocationCreateSerializer,
    LocationDetailSerializer,
    LocationListSerializer,
    ReportSerializer,
    ReviewSerializer,
    UsageSerializer,
)
from .services import build_usage_report, initialize_reliability, verify_location_photo
from .stats import build_usage_stats


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
        # 백그라운드 워커가 돌기 전까지 reliability 필드가 비어있지 않도록 즉시 채워둔다.
        initialize_reliability(location)
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
        # Gemini는 여기서 절대 호출하지 않는다 — 백그라운드 워커(update_reliability)가
        # 미리 계산해둔 값을 읽기만 하므로 동시접속자가 많아도 응답이 항상 즉시 나온다.
        location = self.get_object()
        return Response({
            'score': location.reliability_score,
            'summary': location.reliability_summary,
            'aspects': location.reliability_aspects,
            'notes': location.reliability_notes,
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

    @action(detail=True, methods=['post'], url_path='usages')
    def usages(self, request, pk=None):
        """'여기서 씻었어요'를 눌렀을 때 사용 기록을 남긴다.

        used_at을 함께 보내면 지나간 시각으로 기록한다. 없으면 지금 시각.
        """
        location = self.get_object()

        serializer = UsageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        usage = serializer.save(location=location)

        data = UsageSerializer(usage).data
        # 앱이 곧바로 "n번째 기록이에요"를 보여줄 수 있게 누적 횟수를 함께 준다.
        # id도 함께 나가므로 앱에서 '실행 취소'로 되돌릴 수 있다.
        data['total_count'] = Usage.objects.count()
        return Response(data, status=status.HTTP_201_CREATED)


class UsageViewSet(mixins.ListModelMixin,
                   mixins.DestroyModelMixin,
                   viewsets.GenericViewSet):
    """사용 기록 목록/삭제.

    잘못 누른 기록을 되돌릴 수 있어야 해서 삭제를 연다.
    기록은 되돌릴 수 없으면 부담스러워서 아예 안 누르게 된다.
    """

    serializer_class = UsageSerializer

    def get_queryset(self):
        return Usage.objects.select_related('location').all()

    @action(detail=False, methods=['get'], url_path='notes')
    def notes(self, request):
        """전에 직접 적었던 '상황' 문구를 최근 순으로 돌려준다.

        고정 선택지를 주는 대신, 본인이 쓴 말을 다시 쓰기 쉽게 하려는 것이다.
        두 번째 기록부터는 대부분 한 번 탭으로 끝난다.
        """
        seen = []
        for note in (Usage.objects.exclude(note='')
                     .order_by('-used_at')
                     .values_list('note', flat=True)[:200]):
            if note not in seen:
                seen.append(note)
            if len(seen) >= 8:
                break
        return Response(seen)


class UsageReportView(APIView):
    """GET /api/me/report/ — 내 사용 기록으로 만든 개인 리포트.

    통계는 stats.py가 실제 기록으로 계산하고, 문장만 AI가 붙인다.
    ?refresh=1 을 붙이면 캐시를 건너뛰고 문구를 다시 만든다.
    """

    def get(self, request):
        usages = list(Usage.objects.select_related('location').all())
        stats = build_usage_stats(usages)

        # 기록이 하나 늘면 캐시 키가 바뀌도록 최신 기록 id를 함께 넘긴다.
        # 정렬이 used_at 기준이라 첫 항목이 곧 최신 id는 아니므로 max로 잡는다.
        latest_usage_id = max((usage.id for usage in usages), default=0)
        refresh = request.query_params.get('refresh') == '1'

        report = build_usage_report(stats, latest_usage_id, use_cache=not refresh)
        return Response(report)
