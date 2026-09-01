"""데모용 세척기 위치를 넣는다.

    python manage.py seed_locations
    python manage.py seed_locations --with-reviews   # AI 신뢰도 시연용 리뷰까지
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

from django.conf import settings
from django.core.management.base import BaseCommand

from locations.models import Location, Review

LOCAL_SEED_FILE = settings.BASE_DIR / 'seed_data_local.json'

# 직접 확인한 위치
SEED_LOCATIONS = [
    {
        'building_name': '강남구청',
        'address': '서울특별시 강남구 학동로 426 (삼성동)',
        'lat': 37.517236, 'lng': 127.047325,
        'detail_text': '민원실 1층 로비 정수기 옆\n무료 이용',
    },
    {
        'building_name': '숙명여대 정문',
        'address': '서울특별시 용산구 청파로47길 100 (청파동2가)',
        'lat': 37.545837, 'lng': 126.964458,
        'detail_text': '정문 경비실 옆 야외 급수대',
    },
]

# AI 신뢰도 리포트 시연용 리뷰 (지어낸 예시).
# 긍정만 모인 곳과 부정이 많은 곳을 나눠, 같은 화면에서 판단이 갈리는 걸 보여준다.
SEED_REVIEWS = {
    '강남구청': [
        {'type': Review.Type.UP, 'tags': ['잘 작동함', '대기 없음'], 'free_text': '평일 낮에 한산해요.'},
        {'type': Review.Type.UP, 'tags': ['잘 작동함', '깨끗함'], 'free_text': '물 잘 나오고 깨끗했어요.'},
        {'type': Review.Type.UP, 'tags': ['찾기 쉬움'], 'free_text': ''},
    ],
    '숙명여대 정문': [
        {'type': Review.Type.DOWN, 'tags': ['고장남'], 'free_text': '물이 안 나와요. 수리 중인 듯.'},
        {'type': Review.Type.DOWN, 'tags': ['위치를 못 찾음'], 'free_text': '한참 찾았어요.'},
        {'type': Review.Type.UP, 'tags': ['잘 작동함'], 'free_text': '지난주엔 잘 됐는데.'},
    ],
}


class Command(BaseCommand):
    help = '데모용 세척기 위치(및 리뷰) 시드 데이터를 생성합니다.'

    def add_arguments(self, parser):
        parser.add_argument('--with-reviews', action='store_true', help='AI 신뢰도 시연용 리뷰도 함께 생성')
        parser.add_argument('--reset', action='store_true', help='같은 이름의 기존 시드 위치를 삭제하고 다시 생성')

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
                    'status': Location.Status.CONFIRMED,
                },
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

            if options['with_reviews'] and not location.reviews.exists():
                for review in reviews.get(entry['building_name'], []):
                    Review.objects.create(location=location, **review)

        self.stdout.write(self.style.SUCCESS(
            f'시드 완료: 신규 {created_count}개 / 중복 건너뜀 {skipped_count}개 / '
            f'전체 {Location.objects.count()}개'
        ))

    def build_seed_data(self):
        """이 파일의 시드에 로컬 전용 데이터가 있으면 합쳐서 돌려준다."""
        entries = [{**item, 'source': Location.Source.USER} for item in SEED_LOCATIONS]
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
