from django.db import models


class Location(models.Model):
    """텀블러 세척기가 설치된 장소 한 곳."""

    class Source(models.TextChoices):
        STARBUCKS = 'starbucks', '스타벅스'
        USER = 'user', '사용자 등록'

    class Status(models.TextChoices):
        CONFIRMED = 'confirmed', '확인됨'
        UNCONFIRMED = 'unconfirmed', '미확인'
        REVIEWING = 'reviewing', '검토중'
        REMOVED = 'removed', '삭제됨'

    lat = models.FloatField('위도')
    lng = models.FloatField('경도')
    building_name = models.CharField('건물/장소명', max_length=100)
    address = models.CharField('주소', max_length=200, blank=True)
    photo = models.ImageField('사진', upload_to='locations/%Y/%m', blank=True, null=True)
    detail_text = models.TextField('상세 위치 설명', blank=True)
    source = models.CharField('출처', max_length=20, choices=Source.choices, default=Source.USER)
    status = models.CharField('상태', max_length=20, choices=Status.choices, default=Status.UNCONFIRMED)
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
