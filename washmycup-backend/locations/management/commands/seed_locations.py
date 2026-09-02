"""데모용 세척기 위치를 넣는다.

    python manage.py seed_locations
    python manage.py seed_locations --with-reviews   # AI 신뢰도 시연용 리뷰까지
    python manage.py seed_locations --with-usages    # 개인 리포트 시연용 사용 기록까지
    python manage.py seed_locations --reset          # 기존 시드 데이터를 지우고 다시 넣기

같은 이름이 이미 있으면 건너뛰므로 여러 번 실행해도 중복 등록되지 않는다.

아래 SEED_REVIEWS의 리뷰는 AI 신뢰도 리포트를 시연하려고 지어낸 예시다.
실제 이용 후기가 아니다.

외부에서 받아온 매장 목록처럼 출처 확인이 필요한 데이터는 이 파일에 넣지 말고
`washmycup-backend/seed_data_local.json`에 두면 된다. 그 파일은 gitignore 대상이라
저장소에 올라가지 않고, 있으면 자동으로 함께 시드된다. 형식은 아래와 같다.

    {
      "locations": [
        {"building_name": "...", "address": "...", "lat": 0.0, "lng": 0.0, "detail_text": "..."}
      ],
      "reviews": {
        "위치 이름": [{"type": "up", "tags": ["..."], "free_text": "..."}]
      }
    }
"""

import json
import random
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from locations.models import Location, Review, Usage

LOCAL_SEED_FILE = settings.BASE_DIR / 'seed_data_local.json'

# 시연용으로 직접 적어둔 위치.
# 주소는 공개된 정보를 직접 확인해 적었고, 좌표는 그 주소를 지오코딩한 값이다.
# 세척기가 매장 안 어디에 있는지까지는 확인하지 못해 안내 문구로 대신한다.
#
# building_name은 장소 식별만 하고, 층·상세 위치는 detail_text에 적는다.
# '임직원 전용'처럼 이용 제한이 있으면 detail_text 첫 줄에 둘 것.
# 지도 말풍선이 앞에서부터 잘리기 때문에 뒤에 적으면 가려진다.
SEED_LOCATIONS = [
    {
        'building_name': '스타벅스 강남대로점',
        'address': '서울특별시 강남구 강남대로 456, 한석타워 2층 1-2호 (역삼동)',
        'lat': 37.503221, 'lng': 127.025535,
        'detail_text': '1층 픽업대 옆\n매장 이용객 아니어도 사용 가능',
        'source': Location.Source.STARBUCKS,
    },
    {
        'building_name': '스타벅스 홍대입구역사거리R점',
        'address': '서울특별시 마포구 양화로 125 (서교동)',
        'lat': 37.554734, 'lng': 126.920306,
        'detail_text': '매장 내 위치는 직원에게 문의',
        'source': Location.Source.STARBUCKS,
    },
    {
        'building_name': '고려대학교 우정정보관',
        'address': '서울특별시 성북구 안암로 145 (안암동5가)',
        'lat': 37.585138, 'lng': 127.028592,
        'detail_text': '복도',
        'source': Location.Source.ADMIN,
    },
    {
        'building_name': '고려대학교 아산이학관',
        'address': '서울특별시 성북구 안암로 145 (안암동5가)',
        'lat': 37.585173, 'lng': 127.025327,
        'detail_text': '1층',
        'source': Location.Source.ADMIN,
    },
    {
        'building_name': '고려대학교 현대자동차 경영관',
        'address': '서울특별시 성북구 안암로 145 (안암동5가)',
        'lat': 37.590711, 'lng': 127.035351,
        'detail_text': '라운지',
        'source': Location.Source.ADMIN,
    },
    {
        'building_name': '서울서부지방법원',
        'address': '서울특별시 마포구 마포대로 174 (공덕동)',
        'lat': 37.549173, 'lng': 126.955350,
        'detail_text': '2층 카페 서율',
        'source': Location.Source.USER,
    },
    {
        # 한 건물에 두 대가 있어 상세 안내에 나란히 적었다.
        'building_name': 'LG서울역빌딩',
        'address': '서울특별시 중구 후암로 98 (남대문로5가)',
        'lat': 37.553965, 'lng': 126.974854,
        'detail_text': '임직원 전용\n4층 대로변 1대 · 건물 뒷편 1대',
        'source': Location.Source.ADMIN,
    },
    {
        'building_name': '서울노인복지센터',
        'address': '서울특별시 종로구 삼일대로 467 (경운동)',
        'lat': 37.576009, 'lng': 126.985940,
        'detail_text': '3층',
        'source': Location.Source.USER,
    },
    {
        # 서울노인복지센터와 같은 건물의 다른 층이다.
        'building_name': '은빛행복가게 은빛매점 2층',
        'address': '서울특별시 종로구 삼일대로 467 (경운동)',
        'lat': 37.576000, 'lng': 126.985000,
        'detail_text': '2층',
        'source': Location.Source.USER,
        'status': Location.Status.UNCONFIRMED,
    },
    {
        'building_name': 'BBS 불교방송',
        'address': '서울특별시 마포구 마포대로 20 (도화동)',
        'lat': 37.538826, 'lng': 126.945327,
        'detail_text': '임직원 전용',
        'source': Location.Source.ADMIN,
    },
    {
        'building_name': '강남구청',
        'address': '서울특별시 강남구 학동로 426 (삼성동)',
        'lat': 37.517236, 'lng': 127.047325,
        'detail_text': '민원실 1층 로비 정수기 옆\n무료 이용',
        'source': Location.Source.USER,
    },
    {
        'building_name': '숙명여대 정문',
        'address': '서울특별시 용산구 청파로47길 100 (청파동2가)',
        'lat': 37.545837, 'lng': 126.964458,
        'detail_text': '정문 경비실 옆 야외 급수대',
        'source': Location.Source.USER,
    },
]

# AI 신뢰도 리포트 시연용 리뷰 (지어낸 예시).
# 태그는 앱의 REVIEW_TAGS와 같은 값만 쓴다. 사용자가 만들 수 없는 태그가 섞이면
# 시연 데이터가 실제 앱 동작과 어긋나 보인다.
#   👍 깨끗해요 / 위치가 좋아요 / 대기 없음
#   👎 더러워요 / 고장났어요 / 대기가 길어요 / 실제로 존재하지 않아요
#
# 목록 앞쪽이 오래된 리뷰, 뒤쪽이 최신이다. AI가 최신 리뷰에 무게를 두므로
# "예전엔 괜찮았는데 지금은 고장" 같은 흐름은 순서로 표현한다.
UP = Review.Type.UP
DOWN = Review.Type.DOWN

SEED_REVIEWS = {
    '스타벅스 강남대로점': [
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': '픽업대 바로 옆이라 금방 찾았어요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': '줄 안 서고 바로 썼습니다.'},
        {'type': DOWN, 'tags': ['대기가 길어요'], 'free_text': '출근 시간엔 사람이 많아요.'},
        {'type': UP, 'tags': [], 'free_text': '음료 안 시켜도 쓸 수 있다고 안내해 주셨어요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['위치가 좋아요', '대기 없음'], 'free_text': ''},
        {'type': DOWN, 'tags': ['더러워요'], 'free_text': '받침 트레이가 좀 지저분했어요.'},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': '저녁 늦게 가면 한산합니다.'},
        {'type': UP, 'tags': ['깨끗해요', '위치가 좋아요'], 'free_text': ''},
        {'type': UP, 'tags': [], 'free_text': '강남 나올 때마다 여기서 씻어요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['대기가 길어요'], 'free_text': '점심시간은 피하는 게 좋아요.'},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': '오늘도 문제없이 사용했습니다.'},
    ],
    '스타벅스 홍대입구역사거리R점': [
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': '역에서 가까워 들르기 좋아요.'},
        {'type': UP, 'tags': ['대기 없음', '깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': [], 'free_text': '직원분께 물어보니 바로 알려주셨어요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '상태 좋습니다.'},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': ''},
    ],
    'BBS 불교방송': [
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '사내에 있어서 사람이 몰리지 않아요.'},
        {'type': DOWN, 'tags': [], 'free_text': '외부인은 못 들어가니 참고하세요.'},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': '점심 이후에 여유롭게 썼습니다.'},
    ],
    '고려대학교 현대자동차 경영관': [
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['위치가 좋아요', '대기 없음'], 'free_text': '라운지 들어가자마자 바로 보여요.'},
        {'type': DOWN, 'tags': ['대기가 길어요'], 'free_text': '점심시간엔 줄이 좀 있어요.'},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': [], 'free_text': '텀블러 두 개 연속으로 씻었는데 물 세기가 좋았습니다.'},
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['더러워요'], 'free_text': '배수구 쪽에 물때가 좀 꼈어요.'},
        {'type': UP, 'tags': ['깨끗해요', '위치가 좋아요'], 'free_text': '수업 사이에 잠깐 들러 쓰기 좋아요.'},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': '오후 3시쯤 갔는데 아무도 없었어요.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '이날은 전원이 안 들어와 있었어요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '관리가 잘 되는 편입니다.'},
        {'type': UP, 'tags': [], 'free_text': '학교에 이런 게 있는 줄 몰랐는데 유용하네요.'},
        {'type': UP, 'tags': ['위치가 좋아요', '깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '건조까지는 안 되지만 세척은 만족스러워요.'},
    ],
    '고려대학교 우정정보관': [
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': '복도라 지나가면서 쓰기 편해요.'},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': ''},
        {'type': DOWN, 'tags': ['더러워요'], 'free_text': '받침대에 물이 고여 있었어요.'},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': ''},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '물이 찔끔 나오다 말아요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '아침에는 깨끗한 편입니다.'},
        {'type': DOWN, 'tags': ['더러워요', '대기가 길어요'], 'free_text': '시험기간엔 사람도 많고 지저분해요.'},
        {'type': UP, 'tags': [], 'free_text': '없는 것보다 훨씬 낫습니다.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '수압이 거의 없어서 헹구기 어려웠어요.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '고장 안내문이 붙어 있었습니다.'},
    ],
    '고려대학교 아산이학관': [
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['대기가 길어요'], 'free_text': '쉬는 시간엔 기다려야 해요.'},
        {'type': UP, 'tags': ['위치가 좋아요', '대기 없음'], 'free_text': '1층이라 찾기 쉬웠어요.'},
        {'type': DOWN, 'tags': ['더러워요'], 'free_text': '주변 정리가 잘 안 되어 있었어요.'},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': '지금은 잘 나옵니다.'},
    ],
    '서울서부지방법원': [
        {'type': DOWN, 'tags': ['대기가 길어요'], 'free_text': '재판 끝나는 시간엔 좀 붐볐어요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': '2층 카페 안쪽에 있어요.'},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': [], 'free_text': '카페 이용 안 해도 쓸 수 있었습니다.'},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '관리 상태가 아주 좋습니다.'},
        {'type': UP, 'tags': ['위치가 좋아요', '깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': '평일 오전에 바로 썼어요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': [], 'free_text': '물 온도도 적당하고 수압도 좋아요.'},
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': ''},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': '늘 깨끗하게 유지되네요.'},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '직원분들도 안내를 잘 해주십니다.'},
        {'type': UP, 'tags': ['위치가 좋아요', '대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': [], 'free_text': '근처에서 제일 쓸 만한 세척기입니다.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': '점심 지나고 가면 한산해요.'},
        {'type': UP, 'tags': ['깨끗해요', '위치가 좋아요'], 'free_text': ''},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '오늘도 문제없이 잘 썼습니다.'},
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': ''},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': '이 근처 오면 항상 여기서 씻어요.'},
    ],
    '서울노인복지센터': [
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': '3층 올라가면 바로 있어요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '처음 갔을 땐 잘 나왔습니다.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '물이 아예 안 나와요.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '수리 중이라는 안내문이 붙어 있어요.'},
        {'type': DOWN, 'tags': ['더러워요'], 'free_text': '오래 안 쓴 티가 납니다.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '버튼을 눌러도 반응이 없어요.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['더러워요', '고장났어요'], 'free_text': '먼지가 많이 쌓여 있었어요.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '헛걸음했습니다.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '두 번 갔는데 두 번 다 안 됐어요.'},
        {'type': DOWN, 'tags': ['더러워요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '전원이 꺼져 있습니다.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '아직도 그대로예요.'},
        {'type': DOWN, 'tags': ['더러워요', '고장났어요'], 'free_text': '관리가 안 되는 것 같아요.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '고쳐지면 좋겠네요.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '몇 달째 방치된 듯합니다.'},
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '오늘도 안 됐어요.'},
    ],
    '은빛행복가게 은빛매점 2층': [
        {'type': DOWN, 'tags': ['실제로 존재하지 않아요'], 'free_text': '2층 다 둘러봤는데 없어요.'},
        {'type': DOWN, 'tags': ['실제로 존재하지 않아요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['실제로 존재하지 않아요'], 'free_text': '직원분께 여쭤봤는데 없다고 하십니다.'},
        {'type': DOWN, 'tags': ['실제로 존재하지 않아요'], 'free_text': '헛걸음했습니다. 정보 수정이 필요해 보여요.'},
    ],
    'LG서울역빌딩': [
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['대기 없음', '위치가 좋아요'], 'free_text': '4층에 두 대라 기다릴 일이 없어요.'},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': [], 'free_text': '뒷편 기계가 사람이 적어서 더 편합니다.'},
    ],
    '강남구청': [
        {'type': UP, 'tags': ['대기 없음'], 'free_text': '평일 낮에 한산해요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': '물 잘 나오고 깨끗했어요.'},
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': ''},
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': '민원 보러 왔다가 발견했어요.'},
        {'type': UP, 'tags': ['깨끗해요', '대기 없음'], 'free_text': ''},
        {'type': UP, 'tags': [], 'free_text': '직원분이 친절하게 위치 알려주셨습니다.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': UP, 'tags': ['대기 없음'], 'free_text': '주말엔 사람이 거의 없어요.'},
    ],
    '숙명여대 정문': [
        {'type': DOWN, 'tags': ['고장났어요'], 'free_text': '물이 안 나와요. 수리 중인 듯.'},
        {'type': DOWN, 'tags': [], 'free_text': '위치를 한참 찾았어요.'},
        {'type': UP, 'tags': [], 'free_text': '지난주엔 잘 됐는데.'},
        {'type': UP, 'tags': ['위치가 좋아요'], 'free_text': '정문 지나가다 바로 쓸 수 있어 편해요.'},
        {'type': UP, 'tags': ['깨끗해요'], 'free_text': ''},
        {'type': DOWN, 'tags': ['더러워요'], 'free_text': '주변에 낙엽이랑 쓰레기가 좀 있었어요.'},
        {'type': UP, 'tags': ['대기 없음', '깨끗해요'], 'free_text': '아침에는 한산합니다.'},
        {'type': UP, 'tags': [], 'free_text': '수업 가기 전에 텀블러 씻고 갑니다.'},
        {'type': UP, 'tags': ['위치가 좋아요', '대기 없음'], 'free_text': ''},
    ],
}


# ---------------------------------------------------------------------------
# 개인 리포트(#4) 시연용 사용 기록
#
# 리포트의 통계는 실제 Usage 행에서 계산되므로, 보여줄 패턴이 있으려면 기록도
# 있어야 한다. 아래 가중치로 최근 8주치를 만들어 넣는다.
# 평일 점심에 학교 건물을 자주 쓰는 사람을 상정했다.
# ---------------------------------------------------------------------------

# 장소별 상대 빈도. 자주 가는 곳이 뚜렷해야 리포트가 할 말이 생긴다.
SEED_USAGE_WEIGHTS = {
    '고려대학교 우정정보관': 14,
    '고려대학교 현대자동차 경영관': 9,
    '스타벅스 강남대로점': 6,
    '고려대학교 아산이학관': 5,
    '강남구청': 3,
    '숙명여대 정문': 2,
    '스타벅스 홍대입구역사거리R점': 2,
    'LG서울역빌딩': 1,
}

# 요일 가중치 (월~일). 주말에는 확 줄어드는 평일 생활 패턴.
SEED_USAGE_WEEKDAY_WEIGHTS = (5, 5, 7, 6, 4, 1, 1)

# 시간대 가중치. (시작시각, 끝시각, 가중치) — 점심시간에 몰린다.
SEED_USAGE_HOUR_WEIGHTS = (
    (8, 11, 3),
    (11, 14, 8),
    (14, 18, 4),
    (18, 21, 2),
)

# 사용자가 직접 적는 '상황' 예시. 고정 선택지가 아니라 자유 입력이라,
# 한 사람이 자기 말투를 반복해서 쓰는 모습을 흉내낸다.
# 빈 문자열이 섞여 있는 건 매번 적지는 않기 때문이다. 그게 실제 사용에 가깝다.
SEED_USAGE_NOTES = (
    ('', 5),
    ('점심 먹고', 4),
    ('수업 끝나고', 3),
    ('카페에서 공부하다가', 3),
    ('출근길에', 2),
    ('운동 가기 전', 1),
    ('친구와 약속 전에', 1),
)

SEED_USAGE_WEEKS = 8
SEED_USAGE_PER_WEEK = (4, 7)

# 실행할 때마다 기록이 달라지면 팀원끼리 화면이 서로 달라진다. 고정 시드를 쓴다.
SEED_USAGE_RANDOM_SEED = 20260902


class Command(BaseCommand):
    help = '데모용 세척기 위치(및 리뷰) 시드 데이터를 생성합니다.'

    def add_arguments(self, parser):
        parser.add_argument('--with-reviews', action='store_true', help='AI 신뢰도 시연용 리뷰도 함께 생성')
        parser.add_argument('--with-usages', action='store_true', help='개인 리포트 시연용 사용 기록도 함께 생성')
        parser.add_argument('--reset-usages', action='store_true', help='사용 기록만 지우고 다시 생성')
        # --reset은 위치를 지웠다 다시 만든다. 위치에 딸린 리뷰·신고·사용 기록까지
        # 함께 사라지므로, 사용 기록만 다시 만들려면 --reset-usages를 쓸 것.
        parser.add_argument('--reset', action='store_true',
                            help='같은 이름의 기존 시드 위치를 삭제하고 다시 생성 (딸린 리뷰·신고·사용 기록도 함께 삭제)')

    def handle(self, *args, **options):
        entries, reviews = self.build_seed_data()
        names = [entry['building_name'] for entry in entries]

        if options['reset']:
            deleted, _ = Location.objects.filter(building_name__in=names).delete()
            self.stdout.write(self.style.WARNING(f'기존 시드 데이터 {deleted}건 삭제'))

        created_count = 0
        skipped_count = 0

        for entry in entries:
            location, created = Location.objects.get_or_create(
                building_name=entry['building_name'],
                defaults={
                    'address': entry.get('address', ''),
                    'lat': entry['lat'],
                    'lng': entry['lng'],
                    'detail_text': entry.get('detail_text', ''),
                    'source': entry['source'],
                    'status': entry.get('status', Location.Status.CONFIRMED),
                },
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

            if options['with_reviews'] and not location.reviews.exists():
                for review in reviews.get(entry['building_name'], []):
                    Review.objects.create(location=location, **review)

        if options['with_usages']:
            self.seed_usages(reset=options['reset'] or options['reset_usages'])

        self.stdout.write(self.style.SUCCESS(
            f'시드 완료: 신규 {created_count}개 / 중복 건너뜀 {skipped_count}개 / '
            f'전체 {Location.objects.count()}개'
        ))

    def seed_usages(self, reset=False):
        """최근 8주치 '여기서 씻었어요' 기록을 만든다.

        이미 기록이 있으면 건너뛴다. 여러 번 실행해도 기록이 부풀지 않게 하기 위해서다.
        """
        if reset:
            deleted, _ = Usage.objects.all().delete()
            if deleted:
                self.stdout.write(self.style.WARNING(f'기존 사용 기록 {deleted}건 삭제'))
        elif Usage.objects.exists():
            self.stdout.write('사용 기록이 이미 있어 건너뜁니다 (--reset으로 다시 생성)')
            return

        locations = {
            location.building_name: location
            for location in Location.objects.filter(building_name__in=SEED_USAGE_WEIGHTS)
        }
        if not locations:
            self.stdout.write(self.style.WARNING('사용 기록을 붙일 위치가 없어 건너뜁니다'))
            return

        names = list(locations)
        weights = [SEED_USAGE_WEIGHTS[name] for name in names]

        rng = random.Random(SEED_USAGE_RANDOM_SEED)
        now = timezone.localtime()
        this_monday = now.date() - timedelta(days=now.date().weekday())

        records = []
        for week_offset in range(SEED_USAGE_WEEKS):
            monday = this_monday - timedelta(weeks=week_offset)
            count = rng.randint(*SEED_USAGE_PER_WEEK)

            # 이번 주는 아직 다 지나지 않았다. 지나간 요일까지만 쓰고 횟수도 그만큼 줄인다.
            # 이렇게 해야 '이번 달 n회'가 0으로 비지 않으면서, 지난 주들보다
            # 부자연스럽게 빽빽해지지도 않는다.
            last_weekday = now.weekday() if week_offset == 0 else 6
            if week_offset == 0:
                count = max(1, round(count * (last_weekday + 1) / 7))

            weekday_pool = list(range(last_weekday + 1))
            weekday_weights = SEED_USAGE_WEEKDAY_WEIGHTS[:last_weekday + 1]

            for _ in range(count):
                weekday = rng.choices(weekday_pool, weights=weekday_weights)[0]
                start, end, _weight = rng.choices(
                    SEED_USAGE_HOUR_WEIGHTS,
                    weights=[item[2] for item in SEED_USAGE_HOUR_WEIGHTS],
                )[0]

                used_at = timezone.make_aware(datetime.combine(
                    monday + timedelta(days=weekday),
                    time(hour=rng.randrange(start, end), minute=rng.randrange(0, 60)),
                ))

                # 오늘치는 아직 오지 않은 시각일 수 있다. 미래 기록은 만들지 않는다.
                if used_at > now:
                    continue

                name = rng.choices(names, weights=weights)[0]
                note = rng.choices(
                    [text for text, _ in SEED_USAGE_NOTES],
                    weights=[weight for _, weight in SEED_USAGE_NOTES],
                )[0]
                records.append(Usage(location=locations[name], used_at=used_at, note=note))

        Usage.objects.bulk_create(records)
        self.stdout.write(f'사용 기록 {len(records)}건 생성 ({len(locations)}곳)')

    def build_seed_data(self):
        """이 파일의 시드에 로컬 전용 데이터가 있으면 합쳐서 돌려준다."""
        entries = list(SEED_LOCATIONS)
        reviews = dict(SEED_REVIEWS)

        if not LOCAL_SEED_FILE.exists():
            self.stdout.write(f'(로컬 전용 데이터 없음: {LOCAL_SEED_FILE.name})')
            return entries, reviews

        with open(LOCAL_SEED_FILE, encoding='utf-8') as f:
            local = json.load(f)

        local_entries = local.get('locations', [])
        for item in local_entries:
            entries.append({**item, 'source': Location.Source.STARBUCKS})
        reviews.update(local.get('reviews', {}))

        self.stdout.write(f'로컬 전용 데이터 {len(local_entries)}건 포함 ({LOCAL_SEED_FILE.name})')
        return entries, reviews
