from datetime import timedelta

from django.utils import timezone
from rest_framework import serializers

from .models import Location, Report, Review, Usage
from .moderation import contains_banned_words


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = ('id', 'location', 'type', 'tags', 'free_text', 'created_at')
        read_only_fields = ('id', 'location', 'created_at')

    def validate_tags(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError('tags는 문자열 배열이어야 합니다.')
        if not all(isinstance(tag, str) for tag in value):
            raise serializers.ValidationError('tags의 각 항목은 문자열이어야 합니다.')
        return value

    def validate_free_text(self, value):
        if contains_banned_words(value):
            raise serializers.ValidationError('부적절한 표현이 포함되어 있어 등록할 수 없습니다.')
        return value

    def validate(self, attrs):
        tags = attrs.get('tags') or []
        free_text = (attrs.get('free_text') or '').strip()
        if not tags and not free_text:
            raise serializers.ValidationError('태그를 하나 이상 고르거나 의견을 입력해주세요.')
        return attrs


class ReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Report
        fields = ('id', 'location', 'reason', 'status', 'created_at')
        read_only_fields = ('id', 'location', 'status', 'created_at')

    def validate_reason(self, value):
        if contains_banned_words(value):
            raise serializers.ValidationError('부적절한 표현이 포함되어 있어 등록할 수 없습니다.')
        return value


class LocationListSerializer(serializers.ModelSerializer):
    """지도 화면용 목록 응답. 리뷰 본문 없이 집계만 내려준다."""

    photo = serializers.ImageField(read_only=True, use_url=True)
    up_count = serializers.IntegerField(read_only=True)
    down_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Location
        fields = (
            'id', 'lat', 'lng', 'building_name', 'address', 'photo', 'detail_text',
            'source', 'status', 'up_count', 'down_count', 'created_at',
        )


class LocationDetailSerializer(LocationListSerializer):
    """상세 화면용. 해당 위치의 리뷰 목록을 함께 내려준다."""

    reviews = ReviewSerializer(many=True, read_only=True)

    class Meta(LocationListSerializer.Meta):
        fields = LocationListSerializer.Meta.fields + ('reviews',)


class LocationCreateSerializer(serializers.ModelSerializer):
    """사용자 등록용. source/status는 서버가 정한다."""

    class Meta:
        model = Location
        fields = (
            'id', 'lat', 'lng', 'building_name', 'address', 'photo', 'detail_text',
            'source', 'status', 'created_at',
        )
        read_only_fields = ('id', 'source', 'status', 'created_at')
        # 사진과 상세 설명은 둘 다 선택. 등록 문턱을 낮추는 쪽을 택했다.
        # 대신 사용자 등록은 항상 '운영진 확인 전' 상태로 들어가고(create 참고),
        # 지도에서 노란 마커와 주의 안내로 구분되므로 검증 없이 신뢰되지는 않는다.
        # 사진이 있으면 AI 검증을 거치고, 없으면 그 단계를 건너뛴다.
        extra_kwargs = {
            'photo': {'required': False, 'allow_null': True},
            'detail_text': {'required': False, 'allow_blank': True},
        }

    def validate_building_name(self, value):
        if contains_banned_words(value):
            raise serializers.ValidationError('부적절한 표현이 포함되어 있어 등록할 수 없습니다.')
        return value

    def validate_detail_text(self, value):
        if contains_banned_words(value):
            raise serializers.ValidationError('부적절한 표현이 포함되어 있어 등록할 수 없습니다.')
        return value

    def validate_lat(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError('위도는 -90 ~ 90 사이여야 합니다.')
        return value

    def validate_lng(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError('경도는 -180 ~ 180 사이여야 합니다.')
        return value

    def create(self, validated_data):
        validated_data['source'] = Location.Source.USER
        validated_data['status'] = Location.Status.UNCONFIRMED
        return super().create(validated_data)


class ReliabilitySerializer(serializers.Serializer):
    """GET /api/locations/{id}/reliability/ 응답 형태 (문서화용)."""

    score = serializers.ChoiceField(choices=['high', 'medium', 'low'])
    summary = serializers.CharField()


# 너무 오래된 기록은 습관 통계에 의미가 없고, 오타로 연도를 잘못 넣은 경우를 걸러준다.
MAX_USAGE_BACKDATE_DAYS = 365

# 기기 시계가 서버보다 조금 빠를 수 있어 미래 판정에 여유를 둔다.
USAGE_FUTURE_TOLERANCE = timedelta(minutes=5)


class UsageSerializer(serializers.ModelSerializer):
    """'여기서 씻었어요' 기록.

    used_at은 생략하면 지금 시각이 된다. 컵을 씻고 한참 뒤에 기록하는 경우가 있어
    지나간 날짜·시간도 직접 넣을 수 있게 열어둔다.
    """

    location_name = serializers.CharField(source='location.building_name', read_only=True)

    class Meta:
        model = Usage
        fields = ('id', 'location', 'location_name', 'used_at', 'note')
        read_only_fields = ('id', 'location', 'location_name')

    def validate_note(self, value):
        # 리뷰·신고와 같은 기준으로 거른다. 개인 기록이라도 화면에 그대로 나오는 값이다.
        if contains_banned_words(value):
            raise serializers.ValidationError('부적절한 표현이 포함되어 있어 등록할 수 없습니다.')
        return value.strip()

    def validate_used_at(self, value):
        now = timezone.now()
        if value > now + USAGE_FUTURE_TOLERANCE:
            raise serializers.ValidationError('아직 오지 않은 시각은 기록할 수 없습니다.')
        if value < now - timedelta(days=MAX_USAGE_BACKDATE_DAYS):
            raise serializers.ValidationError('1년보다 오래된 기록은 남길 수 없습니다.')
        return value
