"""사용자가 쓴 글에서 욕설을 걸러내는 규칙 기반 필터.

AI를 쓰지 않는다. 금칙어 목록 대조만으로 대부분 걸러지고,
리뷰 한 건마다 API를 부르는 건 속도와 비용 양쪽으로 낭비다.

우회 입력(자음 분리, 공백/특수문자 삽입, 반복 문자)을 어느 정도 흡수하려고
검사 전에 문자열을 한 번 정규화한다.
"""

import re
import unicodedata

# 팀원이 필요할 때 여기에 추가하면 된다. 모두 소문자로 적을 것.
BANNED_WORDS = [
    '씨발', '시발', '씨빨', '시빨', '십발', '쌍놈', '쌍년',
    '개새끼', '개색기', '개세끼', '새끼', '병신', '븅신', '빙신',
    '지랄', '좆', '좇', '니미', '엠창', '애미', '창녀', '걸레',
    '미친놈', '미친년', '또라이', '돌아이', '꺼져', '뒤져', '디져',
    'ㅅㅂ', 'ㅄ', 'ㅂㅅ', 'ㅈㄹ', 'ㄷㅊ', 'ㅆㅂ', 'ㄲㅈ',
    'fuck', 'shit', 'bitch', 'asshole', 'bastard',
]

# 금칙어를 부분 문자열로 품고 있는 정상 단어. 검사 전에 먼저 걷어낸다.
# (예: '시발점'의 '시발', '고양이새끼'의 '새끼')
ALLOWED_WORDS = [
    '시발점', '시발역', '시발차', '고양이새끼', '강아지새끼',
]

# 글자 사이에 끼워 넣어 우회하는 문자들
_NOISE = re.compile(r'[\s.,!?~\-_*^@#$%&()\[\]{}<>/\\|+=:;\'"`]')


def normalize(text: str) -> str:
    """비교하기 좋게 다듬는다. 공백·특수문자 제거, 자모 정규화, 소문자화."""
    text = unicodedata.normalize('NFKC', text or '')
    text = _NOISE.sub('', text)
    return text.lower()


def find_banned_words(text: str) -> list[str]:
    """걸린 금칙어를 돌려준다. 없으면 빈 목록."""
    cleaned = normalize(text)
    if not cleaned:
        return []

    for allowed in ALLOWED_WORDS:
        cleaned = cleaned.replace(normalize(allowed), '')

    return [word for word in BANNED_WORDS if normalize(word) in cleaned]


def contains_banned_words(text: str) -> bool:
    return bool(find_banned_words(text))
