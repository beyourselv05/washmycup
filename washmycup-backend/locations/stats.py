"""사용 기록에서 개인 행동 패턴을 계산한다. (AI 없음)

리포트에 나오는 숫자는 전부 여기서 실제 기록으로 만든다.
AI는 이 결과를 읽고 문장으로 풀어 쓰는 역할만 한다(services.build_usage_report).
그래야 모델이 없는 숫자를 지어낼 여지가 없다.
"""

from collections import Counter
from datetime import timedelta

from django.utils import timezone

WEEKDAY_NAMES = ('월', '화', '수', '목', '금', '토', '일')

# 시간대 구간. (이름, 시작시각, 끝시각) — 끝시각은 포함하지 않는다.
# 마지막 '심야'는 자정을 넘어가므로 시작 > 끝인 경우로 따로 처리한다.
TIME_BUCKETS = (
    ('아침', 6, 11),
    ('점심', 11, 14),
    ('오후', 14, 18),
    ('저녁', 18, 23),
    ('심야', 23, 6),
)

# 일회용 컵 한 개를 만들고 버리는 데 드는 온실가스 추정치(g CO2e).
# 컵 재질과 계산 기준에 따라 편차가 크기 때문에 널리 인용되는 보수적인 값을 쓰고,
# 화면에서도 '약'을 붙여 어림값임을 밝힌다.
CO2_GRAMS_PER_CUP = 11

# 추세 그래프에 보여줄 주 수.
TREND_WEEKS = 4

# 장소 이름으로 성격을 추정하는 규칙. 위에서부터 먼저 걸리는 것을 쓴다.
#
# 집·회사 주소를 저장하지 않고도 '어떤 성격의 장소에서 주로 씻는가'를 보여주려는 것이다.
# 사용자의 근무지 좌표 같은 걸 받아두면 더 정확하겠지만, 그만한 개인정보를 저장할 만큼
# 이 정보가 중요하지는 않다고 봤다.
#
# 순서가 중요하다. '복지센터'는 '센터'보다, '법원'은 '원'보다 먼저 걸려야 한다.
PLACE_CATEGORY_RULES = (
    ('카페', ('스타벅스', '카페', '커피', '투썸', '이디야', '빽다방', '커피빈', '파스쿠찌')),
    ('학교', ('대학교', '여대', '대학', '학교', '캠퍼스', '학관', '정보관', '도서관')),
    ('공공시설', ('구청', '시청', '주민센터', '복지센터', '법원', '보건소', '우체국',
                 '체육관', '문화센터', '지원센터')),
    ('직장·사무실', ('빌딩', '타워', '사옥', '오피스', '방송', '본사', '지사')),
)

# 규칙에 안 걸리는 장소. 억지로 분류하느니 '기타'로 두는 편이 정직하다.
PLACE_CATEGORY_DEFAULT = '기타'


def categorize_place(building_name):
    """장소 이름에서 성격을 추정한다. 어디까지나 이름 기반 추정이다."""
    for category, keywords in PLACE_CATEGORY_RULES:
        if any(keyword in building_name for keyword in keywords):
            return category
    return PLACE_CATEGORY_DEFAULT


def _bucket_for_hour(hour):
    for name, start, end in TIME_BUCKETS:
        if start < end:
            if start <= hour < end:
                return name
        # 자정을 넘는 구간 (예: 23시 ~ 6시)
        elif hour >= start or hour < end:
            return name
    return TIME_BUCKETS[0][0]


def _week_start(date):
    """그 날짜가 속한 주의 월요일."""
    return date - timedelta(days=date.weekday())


def _streak_weeks(week_starts, this_week):
    """최근까지 한 주도 거르지 않고 이어온 주 수.

    이번 주에 아직 기록이 없어도 지난주까지 이어졌다면 끊긴 것으로 보지 않는다.
    주가 막 바뀌었다는 이유로 기록이 0으로 보이면 응원이 되지 않기 때문이다.
    """
    if not week_starts:
        return 0

    cursor = this_week if this_week in week_starts else this_week - timedelta(weeks=1)
    streak = 0
    while cursor in week_starts:
        streak += 1
        cursor -= timedelta(weeks=1)
    return streak


def build_usage_stats(usages):
    """사용 기록 목록에서 리포트용 통계를 만든다.

    usages는 Usage 인스턴스의 리스트다. 정렬 순서에 의존하지 않는다.
    """
    total = len(usages)
    now = timezone.localtime()
    this_week = _week_start(now.date())

    empty_weekdays = [{'label': name, 'count': 0} for name in WEEKDAY_NAMES]
    empty_buckets = [{'label': name, 'count': 0} for name, _, _ in TIME_BUCKETS]

    if total == 0:
        return {
            'total_count': 0,
            'location_count': 0,
            'first_used_at': None,
            'last_used_at': None,
            'saved_cups': 0,
            'saved_co2_grams': 0,
            'recent_count': 0,
            'streak_weeks': 0,
            'busiest_weekday': None,
            'busiest_time': None,
            'weekday_counts': empty_weekdays,
            'time_buckets': empty_buckets,
            'weekly_trend': _empty_trend(this_week),
            'top_locations': [],
            'place_categories': [],
            'top_contexts': [],
            'recent_contexts': [],
        }

    # DB에는 UTC로 들어있다. 요일·시간대는 사용자가 체감한 한국 시각 기준이어야 한다.
    local_times = [timezone.localtime(usage.used_at) for usage in usages]

    weekday_counter = Counter(dt.weekday() for dt in local_times)
    bucket_counter = Counter(_bucket_for_hour(dt.hour) for dt in local_times)
    week_counter = Counter(_week_start(dt.date()) for dt in local_times)
    location_counter = Counter(usage.location_id for usage in usages)
    location_names = {usage.location_id: usage.location.building_name for usage in usages}

    weekday_counts = [
        {'label': name, 'count': weekday_counter.get(index, 0)}
        for index, name in enumerate(WEEKDAY_NAMES)
    ]
    time_buckets = [
        {'label': name, 'count': bucket_counter.get(name, 0)}
        for name, _, _ in TIME_BUCKETS
    ]

    weekly_trend = []
    for offset in range(TREND_WEEKS - 1, -1, -1):
        start = this_week - timedelta(weeks=offset)
        weekly_trend.append({
            'label': f'{start.month}/{start.day}',
            'count': week_counter.get(start, 0),
        })

    top_locations = [
        {'id': location_id, 'name': location_names[location_id], 'count': count}
        for location_id, count in location_counter.most_common(3)
    ]

    # 사용자가 직접 적은 '상황'. 고정 분류가 아니라서 집계는 같은 문구끼리만 묶는다.
    context_counter = Counter(
        usage.note.strip() for usage in usages if usage.note.strip()
    )
    top_contexts = [
        {'label': label, 'count': count}
        for label, count in context_counter.most_common(5)
    ]
    # AI에게 넘길 원문. 집계로는 안 보이는 결이 여기 남아 있다.
    recent_contexts = [
        usage.note.strip()
        for usage in sorted(usages, key=lambda u: u.used_at, reverse=True)
        if usage.note.strip()
    ][:10]

    category_counter = Counter(
        categorize_place(usage.location.building_name) for usage in usages
    )
    place_categories = [
        {'label': label, 'count': count}
        for label, count in category_counter.most_common()
    ]

    first_used = min(local_times)
    last_used = max(local_times)

    return {
        'total_count': total,
        'location_count': len(location_counter),
        'first_used_at': first_used.isoformat(),
        'last_used_at': last_used.isoformat(),
        # 세척기를 한 번 쓸 때마다 일회용 컵 한 개를 대신했다고 본다.
        'saved_cups': total,
        'saved_co2_grams': total * CO2_GRAMS_PER_CUP,
        # 달이 바뀌면 0으로 떨어지는 '이번 달' 대신 최근 4주로 센다.
        # 습관을 보여주는 화면에서 매달 1일마다 숫자가 리셋되면 응원이 되지 않는다.
        'recent_count': sum(item['count'] for item in weekly_trend),
        'streak_weeks': _streak_weeks(set(week_counter), this_week),
        'busiest_weekday': WEEKDAY_NAMES[weekday_counter.most_common(1)[0][0]],
        'busiest_time': bucket_counter.most_common(1)[0][0],
        'weekday_counts': weekday_counts,
        'time_buckets': time_buckets,
        'weekly_trend': weekly_trend,
        'top_locations': top_locations,
        'place_categories': place_categories,
        'top_contexts': top_contexts,
        'recent_contexts': recent_contexts,
    }


def _empty_trend(this_week):
    trend = []
    for offset in range(TREND_WEEKS - 1, -1, -1):
        start = this_week - timedelta(weeks=offset)
        trend.append({'label': f'{start.month}/{start.day}', 'count': 0})
    return trend
