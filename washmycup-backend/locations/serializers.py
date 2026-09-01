from rest_framework import serializers

from .models import Location, Report, Review
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
        extra_kwargs = {
            'photo': {'required': True},
            'detail_text': {'required': True, 'allow_blank': False},
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
