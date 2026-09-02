from django.db import models
from django.utils import timezone


class Location(models.Model):
    """텀블러 세척기가 설치된 장소 한 곳."""

    class Source(models.TextChoices):
        STARBUCKS = 'starbucks', '스타벅스'
        ADMIN = 'admin', '운영진 등록'
        USER = 'user', '사용자 등록'

    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', '위치 확인됨'
        UNCONFIRMED = 'unconfirmed', '운영진 확인 전'
        REVIEWING = 'reviewing', '신고 검토중'
        # 소프트 삭제. 행은 남고 목록 API에서만 빠진다. (진짜 지우려면 Admin의 삭제 버튼)
        REMOVED = 'removed', '숨김 처리 (앱 비노출)'

    lat = models.FloatField('위도')
    lng = models.FloatField('경도')
    building_name = models.CharField('건물/장소명', max_length=100)
    address = models.CharField('주소', max_length=200, blank=True)
    photo = models.ImageField('사진', upload_to='locations/%Y/%m', blank=True, null=True)
    detail_text = models.TextField('상세 위치 설명', blank=True)
    source = models.CharField('출처', max_length=20, choices=Source.choices, default=Source.USER)
    status = models.CharField(
        '상태', max_length=20, choices=Status.choices, default=Status.UNCONFIRMED,
        help_text='"숨김 처리"는 앱에서만 감추고 데이터는 남깁니다. '
                  '아래 삭제 버튼은 리뷰·신고까지 영구 삭제하니 주의하세요.',
    )
    created_at = models.DateTimeField('등록일시', auto_now_add=True)

    class ReliabilityScore(models.TextChoices):
        HIGH = 'high', '높음'
        MEDIUM = 'medium', '보통'
        LOW = 'low', '낮음'

    # 백그라운드 워커(update_reliability 명령어)가 주기적으로 채워두는 AI 신뢰도 리포트.
    # 요청 시점엔 이 필드만 읽고, Gemini는 절대 호출하지 않는다.
    reliability_score = models.CharField(
        'AI 신뢰도', max_length=10, choices=ReliabilityScore.choices, blank=True,
    )
    reliability_summary = models.TextField('AI 신뢰도 요약', blank=True)
    reliability_aspects = models.JSONField('AI 신뢰도 항목 점수', default=dict, blank=True)
    reliability_notes = models.JSONField('AI 신뢰도 안내', default=list, blank=True)
    reliability_updated_at = models.DateTimeField('AI 신뢰도 갱신일시', null=True, blank=True)

    class Meta:
        verbose_name = '세척기 위치'
        verbose_name_plural = '세척기 위치'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.building_name} ({self.get_status_display()})'


class Review(models.Model):
    """특정 위치에 대한 사용자 리뷰 (👍/👎 + 태그 + 자유 텍스트)."""

    class Type(models.TextChoices):
        UP = 'up', '👍 좋아요'
        DOWN = 'down', '👎 별로예요'

    location = models.ForeignKey(Location, related_name='reviews', on_delete=models.CASCADE)
    type = models.CharField('평가', max_length=10, choices=Type.choices)
    tags = models.JSONField('태그', default=list, blank=True)
    free_text = models.CharField('의견', max_length=100, blank=True)
    created_at = models.DateTimeField('작성일시', auto_now_add=True)

    class Meta:
        verbose_name = '리뷰'
        verbose_name_plural = '리뷰'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_type_display()}] {self.location.building_name}'


class Report(models.Model):
    """허위/부적절 등록 신고. 처리는 Django Admin에서 한다."""

    class Status(models.TextChoices):
        PENDING = 'pending', '미처리'
        RESOLVED = 'resolved', '처리완료'

    location = models.ForeignKey(Location, related_name='reports', on_delete=models.CASCADE)
    reason = models.TextField('신고 사유')
    status = models.CharField('처리 상태', max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField('신고일시', auto_now_add=True)

    class Meta:
        verbose_name = '신고'
        verbose_name_plural = '신고'
        ordering = ['-created_at']

    def __str__(self):
        return f'[{self.get_status_display()}] {self.location.building_name}'


class Usage(models.Model):
    """'여기서 씻었어요' 기록 한 건.

    로그인이 없는 프로토타입이라 사용자 구분 없이 쌓는다. 이 앱을 쓰는 사람이
    한 명이라는 전제이고, 계정이 붙으면 여기에 user 필드가 추가될 자리다.

    개인 리포트(GET /api/me/report/)의 원재료가 된다.
    """

    location = models.ForeignKey(Location, related_name='usages', on_delete=models.CASCADE)
    # 시드로 과거 기록을 넣어야 해서 실제 사용 시각과 기록이 남은 시각을 따로 둔다.
    used_at = models.DateTimeField('사용일시', default=timezone.now)
    # 어떤 상황에서 썼는지. 고정 선택지 대신 자유 입력으로 둔다.
    # 맥락은 사람마다 너무 달라서 목록을 정해두면 대부분 '기타'로 몰리고,
    # 목록에 없는 상황은 아예 기록을 포기하게 된다.
    note = models.CharField('상황', max_length=40, blank=True)
    created_at = models.DateTimeField('기록일시', auto_now_add=True)

    class Meta:
        verbose_name = '사용 기록'
        verbose_name_plural = '사용 기록'
        ordering = ['-used_at']

    def __str__(self):
        return f'{self.location.building_name} @ {timezone.localtime(self.used_at):%Y-%m-%d %H:%M}'
