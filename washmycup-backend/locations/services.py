"""리뷰를 모아 '지금 이용 가능할 확률'을 요약하는 AI 신뢰도 리포트.

Gemini는 /reliability 를 호출할 때만(온디맨드) 부른다. 상시로 도는 프로세스는 없다.
API 키가 없거나 호출이 실패하면 규칙 기반 폴백으로 항상 응답을 만들어낸다.
(무료 티어 하루 250회라 같은 결과는 캐시해서 재사용한다.)
"""

import json
import logging
import re

from django.conf import settings
from django.core.cache import cache

from .models import Review

logger = logging.getLogger(__name__)

# SDK가 매 호출마다 남기는 안내 로그를 줄여 개발 서버 콘솔을 깨끗하게 유지한다.
logging.getLogger('google_genai.models').setLevel(logging.ERROR)

# 리뷰가 바뀌면 캐시 키 자체가 바뀌므로 오래 두어도 낡은 요약이 나오지 않는다.
# 무료 한도(하루 단위)를 아끼려면 길수록 좋다.
CACHE_TTL_SECONDS = 60 * 60 * 24 * 7

# 응답 형태가 바뀌면 올릴 것. 옛 형식 캐시를 무시하게 된다.
CACHE_VERSION = 2

# 호출 실패로 만든 폴백은 짧게만 담아둔다. 곧 다시 시도하게 만들기 위해서다.
FALLBACK_CACHE_TTL_SECONDS = 60

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


def build_reliability_report(location, use_cache=True):
    """{'score': 'high'|'medium'|'low', 'summary': str} 를 반환한다."""

    reviews = list(location.reviews.all()[:30])

    # 리뷰가 바뀌면 캐시 키도 바뀌도록 최신 리뷰 id와 개수를 섞는다.
    # 응답에 필드를 추가/변경할 때는 CACHE_VERSION을 올린다. 그래야 옛 형식으로
    # 저장된 캐시를 앱이 받아서 깨지는 일이 없다.
    latest_review_id = reviews[0].id if reviews else 0
    cache_key = f'reliability:{CACHE_VERSION}:{location.id}:{len(reviews)}:{latest_review_id}'

    if use_cache:
        cached = cache.get(cache_key)
        if cached:
            return cached

    if not reviews or not settings.GEMINI_API_KEY:
        # 리뷰가 없거나 키가 없는 건 상태가 바뀌기 전까지 결과가 같으므로 그대로 캐시한다.
        report = _fallback_report(reviews)
        cache.set(cache_key, report, CACHE_TTL_SECONDS)
        return report

    try:
        report = _call_gemini(location, reviews)
    except Exception:
        # 한도 초과·일시적 장애로 실패한 경우다. 이 결과를 오래 캐시해두면
        # 한도가 풀린 뒤에도 계속 폴백만 나오므로 짧게만 담아둔다.
        logger.exception('Gemini 신뢰도 요약 실패 (location=%s)', location.id)
        report = _fallback_report(reviews)
        cache.set(cache_key, report, FALLBACK_CACHE_TTL_SECONDS)
        return report

    cache.set(cache_key, report, CACHE_TTL_SECONDS)
    return report


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
