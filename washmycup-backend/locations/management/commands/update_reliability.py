"""위치별 AI 신뢰도 리포트를 재계산하는 백그라운드 워커.

체크(폴링)와 실제 Gemini 호출을 분리한다 — DB 확인은 자주(기본 60초) 하되,
아래 둘 중 하나를 만족할 때만 실제로 재계산(Gemini 호출)한다:

  1. 마지막 계산 이후 새 리뷰가 --review-threshold(기본 3)개 이상 쌓임
     → 대회 당일처럼 특정 위치에 리뷰가 몰릴 때 빠르게 반응한다.
  2. 마지막 계산 이후 --min-interval(기본 300초/5분)이 지났고, 그 사이 리뷰가
     하나라도 생김 → 리뷰가 뜸한 위치도 결국은 반영되도록 보장한다.

이렇게 하면 "몰릴 때는 거의 즉시, 아니어도 최대 5분 안엔 반영"되면서, 안 바뀐
위치는 호출하지 않아 Gemini 무료 티어(하루 250건)를 아낀다.

    python manage.py update_reliability
    python manage.py update_reliability --poll-interval 30 --review-threshold 5
    python manage.py update_reliability --once   # 한 번만 확인하고 종료

`python manage.py runserver`와는 별개의 터미널(또는 `just worker`)로 띄워둔다.
API(`/reliability/`)는 이 워커가 채워둔 Location.reliability_* 필드를 읽기만
하고, Gemini는 절대 호출하지 않는다.
"""

import time

from django.core.management.base import BaseCommand
from django.db.models import Count, F, Max, Q
from django.utils import timezone

from locations.models import Location
from locations.services import compute_reliability_report, save_reliability_report


class Command(BaseCommand):
    help = '리뷰가 몰린 위치는 즉시, 아니면 주기적으로 AI 신뢰도 리포트를 재계산한다.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--poll-interval', type=int, default=60,
            help='DB에서 갱신 대상을 확인하는 주기(초). 기본 60초. (Gemini 호출 주기가 아니다)',
        )
        parser.add_argument(
            '--review-threshold', type=int, default=3,
            help='마지막 계산 이후 새 리뷰가 이 개수 이상 쌓이면 즉시 재계산한다. 기본 3.',
        )
        parser.add_argument(
            '--min-interval', type=int, default=300,
            help='새 리뷰가 있는데 threshold를 못 채웠어도, 이 시간(초)이 지나면 재계산한다. 기본 300초(5분).',
        )
        parser.add_argument(
            '--once', action='store_true',
            help='한 번만 확인하고 종료한다 (테스트/데모 직전 강제 갱신용).',
        )

    def handle(self, *args, **options):
        poll_interval = options['poll_interval']
        review_threshold = options['review_threshold']
        min_interval = options['min_interval']
        run_once = options['once']

        while True:
            updated = self._update_stale_locations(review_threshold, min_interval)
            if updated:
                self.stdout.write(
                    f'[{timezone.now():%H:%M:%S}] 신뢰도 재계산: {updated}개 위치 갱신'
                )
            if run_once:
                break
            time.sleep(poll_interval)

    def _update_stale_locations(self, review_threshold, min_interval):
        locations = (
            Location.objects
            .exclude(status=Location.Status.REMOVED)
            .annotate(
                latest_review_at=Max('reviews__created_at'),
                # 마지막 계산 이후 새로 달린 리뷰 개수. reliability_updated_at이
                # NULL이면(아직 한 번도 계산 안 됨) 이 조건은 항상 거짓이 되는데,
                # 그 경우는 _needs_update에서 별도로 True 처리하므로 문제없다.
                new_review_count=Count(
                    'reviews',
                    filter=Q(reviews__created_at__gt=F('reliability_updated_at')),
                ),
            )
        )

        updated = 0
        for location in locations:
            if not self._needs_update(location, review_threshold, min_interval):
                continue
            report = compute_reliability_report(location)
            save_reliability_report(location, report)
            updated += 1
        return updated

    @staticmethod
    def _needs_update(location, review_threshold, min_interval):
        if location.reliability_updated_at is None:
            return True
        if not location.latest_review_at or location.latest_review_at <= location.reliability_updated_at:
            return False  # 새 리뷰 없음

        if location.new_review_count >= review_threshold:
            return True  # 리뷰가 몰림 → 즉시 재계산

        elapsed = (timezone.now() - location.reliability_updated_at).total_seconds()
        return elapsed >= min_interval  # 뜸해도 최소 주기는 보장
