"""리뷰를 모아 '지금 이용 가능할 확률'을 요약하는 AI 신뢰도 리포트.

Gemini는 요청(request) 경로에서 절대 호출하지 않는다. 대신 백그라운드 워커
(management command `update_reliability`)가 주기적으로 리뷰가 바뀐 위치만
골라 재계산해서 Location.reliability_* 필드에 저장해두고, API는 그 필드를
읽기만 한다 — 동시접속자가 많아도 Gemini 호출 수는 위치 개수 × (운영시간/주기)로
고정되고, 응답 속도도 항상 DB 조회 수준으로 유지된다.
API 키가 없거나 호출이 실패하면 규칙 기반 폴백으로 항상 결과를 만들어낸다.
"""

import json
import logging
import re

from django.conf import settings

from .models import Review

logger = logging.getLogger(__name__)

# SDK가 매 호출마다 남기는 안내 로그를 줄여 워커 콘솔을 깨끗하게 유지한다.
logging.getLogger('google_genai.models').setLevel(logging.ERROR)

PROMPT_TEMPLATE = """너는 텀블러 세척기 정보를 정리해주는 도우미야.

아래는 '{building_name}'에 설치된 무료 텀블러 세척기에 대한 사용자 리뷰야.
최신 리뷰가 위에 온다.

{reviews}

이 리뷰들을 종합해서 지금 이 세척기를 이용 가능할 확률이 높음/보통/낮음인지
판단하고, 그 이유를 2-3문장으로 요약해줘.
최신 리뷰에 더 무게를 두고, 리뷰에 없는 사실은 지어내지 마.

반드시 아래 형태의 JSON만 출력해:
{{"score": "high" | "medium" | "low", "summary": "한국어 2-3문장 요약"}}"""


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

    return {'score': score, 'summary': summary}


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
    location.reliability_updated_at = timezone.now()
    location.save(update_fields=[
        'reliability_score', 'reliability_summary', 'reliability_updated_at',
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
    )
    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config={'response_mime_type': 'application/json', 'temperature': 0.2},
    )
    return _parse_gemini_json(response.text)
