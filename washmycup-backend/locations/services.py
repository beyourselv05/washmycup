"""Gemini를 호출하는 서비스 모듈.

- 신뢰도 리포트는 백그라운드 워커가 계산해 ``Location.reliability_*``에 저장한다.
  조회 API는 저장된 값만 읽으므로 Gemini 호출이 요청 경로에 들어가지 않는다.
- 사진 검증과 사용 리포트 문구는 요청 시 호출한다. 실패하면 각각 통과 또는 규칙 기반
  폴백으로 처리한다.
"""

import json
import logging
import re

from django.conf import settings
from django.core.cache import cache

from .models import Review

logger = logging.getLogger(__name__)

# SDK가 매 호출마다 남기는 안내 로그를 줄여 워커 콘솔을 깨끗하게 유지한다.
logging.getLogger('google_genai.models').setLevel(logging.ERROR)

# 사용 리포트는 입력이 바뀌면 캐시 키가 바뀌므로 오래 보관해도 안전하다.
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7

# 호출 실패로 만든 폴백은 짧게만 담아둔다. 곧 다시 시도하게 만들기 위해서다.
FALLBACK_CACHE_TTL_SECONDS = 60

# 다만 한도·요청량 초과는 곧바로 다시 불러도 똑같이 실패한다.
# 60초 캐시로는 화면을 열 때마다 실패할 호출이 반복되므로 이 경우만 길게 잡는다.
# 하루 한도가 풀릴 때까지 붙잡아두진 않는다. 그 사이 한도가 회복될 수도 있어서다.
QUOTA_FALLBACK_CACHE_TTL_SECONDS = 60 * 10

# 항목 점수는 리뷰에서 언급된 것만 받는다. 언급이 없는 항목까지 채우게 하면
# 모델이 근거 없는 별점을 지어낸다.
ASPECT_KEYS = ('세척력', '접근성', '대기시간', '세척 속도', '냄새 제거')
PROMPT_TEMPLATE = """너는 텀블러 세척기 정보를 정리해주는 도우미야.

아래는 '{building_name}'에 설치된 무료 텀블러 세척기에 대한 사용자 리뷰야.
최신 리뷰가 위에 온다.

{reviews}

다음 세 가지를 뽑아줘.

1. score: 지금 이 세척기를 이용 가능할 확률이 높음(high)/보통(medium)/낮음(low) 중 무엇인지.
2. summary: 그렇게 판단한 이유를 2-3문장으로.
3. aspects: 아래 항목 중 리뷰에서 실제로 언급된 것만 1~5점으로.
   {aspect_keys}
   언급이 없는 항목은 아예 넣지 마. 억지로 채우지 마.
4. notes: 사용자가 알아두면 좋은 점을 0~2개, 각 한 문장으로.
   예) "냄새 제거 관련 부정 리뷰가 반복적으로 나타났어요."
       "커피를 마신 뒤라면 다른 곳도 함께 보세요."

최신 리뷰에 더 무게를 두고, 리뷰에 없는 사실은 지어내지 마.

반드시 아래 형태의 JSON만 출력해:
{{"score": "high" | "medium" | "low",
  "summary": "한국어 2-3문장 요약",
  "aspects": {{"항목명": 1~5 정수}},
  "notes": ["한 문장", "한 문장"]}}"""


def _format_reviews(reviews):
    lines = []
    for review in reviews:
        mark = '👍 긍정' if review.type == Review.Type.UP else '👎 부정'
        parts = [f'- [{review.created_at:%Y-%m-%d}] {mark}']
        if review.tags:
            parts.append(f'태그: {", ".join(review.tags)}')
        if review.free_text:
            parts.append(f'의견: {review.free_text}')
        lines.append(' / '.join(parts))
    return '\n'.join(lines)


def _fallback_report(reviews):
    """Gemini를 못 쓸 때 쓰는 규칙 기반 요약."""
    total = len(reviews)
    if total == 0:
        return {
            'score': 'medium',
            'summary': '아직 등록된 리뷰가 없어 이용 가능 여부를 판단하기 어렵습니다. '
                       '방문하신 뒤 첫 리뷰를 남겨주시면 다음 사용자에게 큰 도움이 됩니다.',
            'aspects': {},
            'notes': [],
        }

    up = sum(1 for review in reviews if review.type == Review.Type.UP)
    ratio = up / total

    if ratio >= 0.7:
        score = 'high'
        tone = '최근 리뷰 대부분이 긍정적이라 지금 이용할 수 있을 가능성이 높습니다.'
    elif ratio >= 0.4:
        score = 'medium'
        tone = '긍정과 부정 리뷰가 섞여 있어 상황에 따라 이용이 어려울 수 있습니다.'
    else:
        score = 'low'
        tone = '부정적인 리뷰가 많아 지금은 이용이 어려울 가능성이 큽니다.'

    return {
        'score': score,
        'summary': f'리뷰 {total}건 중 {up}건이 긍정 평가입니다. {tone} (AI 요약을 사용할 수 없어 리뷰 집계로 대신했습니다.)',
        'aspects': {},
        'notes': [],
    }


def _is_quota_error(error):
    """한도/요청량 초과로 인한 실패인지. SDK 예외 타입이 버전마다 달라 문자열로 본다."""
    text = f'{type(error).__name__} {error}'.lower()
    return any(
        keyword in text
        for keyword in ('429', 'resource_exhausted', 'quota', 'rate limit', 'too many requests')
    )


def _parse_gemini_json(text):
    text = (text or '').strip()
    if not text:
        raise ValueError('빈 응답')

    # 모델이 ```json ... ``` 로 감싸는 경우 대비
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    data = json.loads(text)
    score = str(data.get('score', '')).lower().strip()
    summary = str(data.get('summary', '')).strip()

    if score not in ('high', 'medium', 'low') or not summary:
        raise ValueError(f'예상치 못한 응답 형태: {data!r}')

    return {
        'score': score,
        'summary': summary,
        'aspects': _clean_aspects(data.get('aspects')),
        'notes': _clean_notes(data.get('notes')),
    }


def _clean_aspects(raw):
    """모델이 정한 항목 중 우리가 정의한 것만, 1~5 범위로 걸러 받는다."""
    if not isinstance(raw, dict):
        return {}

    cleaned = {}
    for key in ASPECT_KEYS:
        value = raw.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue
        score = int(round(value))
        if 1 <= score <= 5:
            cleaned[key] = score
    return cleaned


def _clean_notes(raw):
    if not isinstance(raw, list):
        return []
    notes = [str(n).strip() for n in raw if str(n).strip()]
    return notes[:2]


def compute_reliability_report(location):
    """{'score': 'high'|'medium'|'low', 'summary': str} 를 새로 계산한다.

    캐시를 쓰지 않고 항상 Gemini(또는 폴백)를 호출한다 — 백그라운드 워커가
    "리뷰가 바뀐 위치만" 골라 이 함수를 부르는 걸 전제로 하기 때문에,
    여기서 또 캐싱할 필요가 없다.
    """
    reviews = list(location.reviews.all()[:30])

    if not reviews or not settings.GEMINI_API_KEY:
        return _fallback_report(reviews)

    try:
        return _call_gemini(location, reviews)
    except Exception:
        logger.exception('Gemini 신뢰도 요약 실패 (location=%s)', location.id)
        return _fallback_report(reviews)


def save_reliability_report(location, report):
    """계산된 리포트를 Location 필드에 저장한다 (워커/초기화 공용)."""
    from django.utils import timezone

    location.reliability_score = report['score']
    location.reliability_summary = report['summary']
    location.reliability_aspects = report.get('aspects', {})
    location.reliability_notes = report.get('notes', [])
    location.reliability_updated_at = timezone.now()
    location.save(update_fields=[
        'reliability_score', 'reliability_summary', 'reliability_aspects',
        'reliability_notes', 'reliability_updated_at',
    ])


def initialize_reliability(location):
    """위치 등록 직후, 워커가 아직 안 돌았을 때를 대비해 즉시 규칙 기반으로 채워둔다.

    이 시점엔 리뷰가 없는 게 보통이라 Gemini를 부르지 않고 즉시 끝난다.
    """
    save_reliability_report(location, _fallback_report([]))


def _call_gemini(location, reviews):
    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    prompt = PROMPT_TEMPLATE.format(
        building_name=location.building_name,
        reviews=_format_reviews(reviews),
        aspect_keys=' / '.join(ASPECT_KEYS),
    )
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config={'response_mime_type': 'application/json', 'temperature': 0.2},
    )
    return _parse_gemini_json(response.text)


# ---------------------------------------------------------------------------
# 등록 사진 검증
# ---------------------------------------------------------------------------

PHOTO_PROMPT = """이 사진이 텀블러 세척기 등록용으로 적절한지 판단해줘.

적절한 사진: 텀블러 세척기, 컵 세척기, 세면대, 급수대, 싱크대처럼
물로 무언가를 씻을 수 있는 설비가 찍힌 사진. 설비가 있는 주변 공간이
넓게 찍힌 것도 괜찮다.

부적절한 사진: 사람 얼굴이나 셀카, 음식, 반려동물, 스크린샷,
풍경만 찍힌 사진처럼 세척 설비와 전혀 관련이 없는 것.

애매하면 적절한 쪽으로 판단해. 잘못 막는 것보다 통과시키는 편이 낫다.

반드시 아래 형태의 JSON만 출력해:
{"ok": true 또는 false, "reason": "부적절할 때만 한 문장으로 이유"}"""

# 사진 검증은 등록을 막을 수 있으므로 판단이 확실할 때만 거절한다.
PHOTO_CHECK_ENABLED = True


def verify_location_photo(image_bytes, mime_type):
    """{'ok': bool, 'reason': str} 를 돌려준다.

    호출에 실패하면 항상 통과시킨다. 한도 초과나 일시적 장애 때문에
    사용자가 등록을 못 하는 상황을 만들지 않기 위해서다.
    """
    if not (PHOTO_CHECK_ENABLED and settings.GEMINI_API_KEY and image_bytes):
        return {'ok': True, 'reason': ''}

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type or 'image/jpeg'),
                PHOTO_PROMPT,
            ],
            config={'response_mime_type': 'application/json', 'temperature': 0},
        )
        data = json.loads((response.text or '').strip())
        ok = bool(data.get('ok', True))
        reason = str(data.get('reason', '')).strip()
        return {'ok': ok, 'reason': reason if not ok else ''}
    except Exception:
        logger.exception('사진 검증 실패 — 통과 처리합니다')
        return {'ok': True, 'reason': ''}


# ---------------------------------------------------------------------------
# 개인 사용 리포트
#
# 통계는 stats.build_usage_stats가 실제 기록으로 계산한다. 여기서는 그 결과를
# 사람이 읽을 문장으로 바꾸는 일만 한다. 모델에게 숫자 계산을 맡기지 않는 이유는
# 리포트에 틀린 수치가 나오면 기능 자체를 믿을 수 없게 되기 때문이다.
# ---------------------------------------------------------------------------

USAGE_CACHE_VERSION = 1

USAGE_PROMPT_TEMPLATE = """너는 텀블러 쓰는 습관을 응원해주는 코치야.

아래는 사용자가 남긴 '텀블러 세척기 사용 기록' 통계야.
숫자는 이미 계산이 끝난 사실이니 그대로 쓰고, 없는 숫자를 새로 지어내지 마.

{facts}

다음 세 가지를 만들어줘.

1. headline: 이 사람의 습관을 한 문장으로 표현한 별명 같은 제목. 20자 이내.
   예) "점심시간의 텀블러 지킴이"
2. message: 기록에서 드러나는 패턴을 2~3문장으로. 관찰과 칭찬 위주로 써.
   '사용자가 직접 적은 상황'이 있으면 그 표현을 살려서 언급해줘.
   그 사람이 실제로 쓴 말이라 통계보다 더 그 사람답다.
3. tip: 다음 주에 가볍게 해볼 만한 제안 한 문장.

혼내거나 죄책감을 주는 말투는 절대 쓰지 마. 못 한 것 말고 해낸 것을 말해줘.
'~해야 합니다' 대신 '~해보는 건 어때요?' 같은 부드러운 말투를 써.

반드시 아래 형태의 JSON만 출력해:
{{"headline": "...", "message": "...", "tip": "..."}}"""


def _format_usage_facts(stats):
    """통계 딕셔너리를 프롬프트에 넣을 사실 목록으로 편다."""
    lines = [
        f'- 총 사용 횟수: {stats["total_count"]}회',
        f'- 다녀온 장소 수: {stats["location_count"]}곳',
        f'- 최근 4주 사용: {stats["recent_count"]}회',
        f'- 연속 사용 주: {stats["streak_weeks"]}주',
        f'- 아낀 일회용 컵: 약 {stats["saved_cups"]}개',
        f'- 가장 자주 쓴 요일: {stats["busiest_weekday"]}요일',
        f'- 가장 자주 쓴 시간대: {stats["busiest_time"]}',
    ]

    weekdays = ', '.join(
        f'{item["label"]} {item["count"]}회' for item in stats['weekday_counts']
    )
    lines.append(f'- 요일별 분포: {weekdays}')

    buckets = ', '.join(
        f'{item["label"]} {item["count"]}회' for item in stats['time_buckets'] if item['count']
    )
    if buckets:
        lines.append(f'- 시간대별 분포: {buckets}')

    trend = ', '.join(
        f'{item["label"]} 주 {item["count"]}회' for item in stats['weekly_trend']
    )
    lines.append(f'- 최근 4주 추이: {trend}')

    if stats.get('place_categories'):
        categories = ', '.join(
            f'{item["label"]} {item["count"]}회' for item in stats['place_categories']
        )
        lines.append(f'- 장소 성격별 분포(이름으로 추정): {categories}')

    if stats.get('top_contexts'):
        contexts = ', '.join(
            f'{item["label"]} {item["count"]}회' for item in stats['top_contexts']
        )
        lines.append(f'- 사용자가 직접 적은 상황: {contexts}')

    if stats['top_locations']:
        places = ', '.join(
            f'{item["name"]} {item["count"]}회' for item in stats['top_locations']
        )
        lines.append(f'- 자주 가는 곳: {places}')

    return '\n'.join(lines)


def _fallback_usage_narrative(stats):
    """Gemini를 못 쓸 때의 규칙 기반 문구. 어조는 AI 쪽과 맞춘다."""
    total = stats['total_count']

    if total == 0:
        return {
            'headline': '기록은 지금부터',
            'message': '아직 남긴 사용 기록이 없어요. 세척기를 쓴 뒤 상세 화면에서 '
                       '"여기서 씻었어요"를 눌러두면 여기에 나의 패턴이 쌓입니다.',
            'tip': '오늘 들른 곳부터 한 번 기록해보는 건 어때요?',
        }

    place = stats['top_locations'][0]['name'] if stats['top_locations'] else '자주 가는 곳'
    return {
        'headline': f'{stats["busiest_weekday"]}요일의 텀블러 습관',
        'message': f'지금까지 {total}번, {stats["location_count"]}곳에서 텀블러를 씻으셨어요. '
                   f'{stats["busiest_weekday"]}요일 {stats["busiest_time"]} 시간대에 가장 자주 들르셨고, '
                   f'{place}을(를) 가장 많이 찾으셨습니다.',
        'tip': '다음 주에도 같은 흐름을 이어가 보세요.',
    }


def _parse_usage_narrative(text):
    text = (text or '').strip()
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    data = json.loads(text)
    headline = str(data.get('headline', '')).strip()
    message = str(data.get('message', '')).strip()
    tip = str(data.get('tip', '')).strip()

    if not headline or not message:
        raise ValueError(f'예상치 못한 응답 형태: {data!r}')

    return {'headline': headline, 'message': message, 'tip': tip}


def build_usage_report(stats, latest_usage_id=0, use_cache=True):
    """계산된 통계에 AI 코멘트를 붙여 돌려준다.

    {'stats': {...}, 'narrative': {'headline':, 'message':, 'tip':}}
    """
    # 기록이 늘면 키가 바뀌어 다시 생성된다. 기록이 그대로면 같은 문구를 재사용한다.
    cache_key = f'usage_report:{USAGE_CACHE_VERSION}:{stats["total_count"]}:{latest_usage_id}'

    if use_cache:
        cached = cache.get(cache_key)
        if cached:
            return {'stats': stats, 'narrative': cached}

    if stats['total_count'] == 0 or not settings.GEMINI_API_KEY:
        narrative = _fallback_usage_narrative(stats)
        cache.set(cache_key, narrative, CACHE_TTL_SECONDS)
        return {'stats': stats, 'narrative': narrative}

    try:
        narrative = _call_gemini_usage(stats)
    except Exception as error:
        logger.exception('Gemini 사용 리포트 생성 실패')
        narrative = _fallback_usage_narrative(stats)
        ttl = (QUOTA_FALLBACK_CACHE_TTL_SECONDS if _is_quota_error(error)
               else FALLBACK_CACHE_TTL_SECONDS)
        cache.set(cache_key, narrative, ttl)
        return {'stats': stats, 'narrative': narrative}

    cache.set(cache_key, narrative, CACHE_TTL_SECONDS)
    return {'stats': stats, 'narrative': narrative}


def _call_gemini_usage(stats):
    from google import genai

    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=USAGE_PROMPT_TEMPLATE.format(facts=_format_usage_facts(stats)),
        # 응원 문구라 신뢰도 요약보다 조금 더 자유롭게 둔다.
        config={'response_mime_type': 'application/json', 'temperature': 0.6},
    )
    return _parse_usage_narrative(response.text)
