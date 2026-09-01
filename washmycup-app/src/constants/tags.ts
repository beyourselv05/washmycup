import type { ReviewType } from '@/types';

/** 리뷰 작성 화면의 태그 선택지. 태그와 별개로 자유 의견은 언제든 적을 수 있다. */

export const REVIEW_TAGS: Record<ReviewType, string[]> = {
  up: ['깨끗해요', '위치가 좋아요', '대기 없음'],
  down: ['더러워요', '고장났어요', '대기가 길어요', '실제로 존재하지 않아요'],
};

export const FREE_TEXT_MAX_LENGTH = 100;
