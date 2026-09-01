/** 백엔드(Django/DRF) 응답과 필드명을 그대로 맞춘 타입 (snake_case). */

export type LocationSource = 'starbucks' | 'admin' | 'user';

export type LocationStatus = 'confirmed' | 'unconfirmed' | 'reviewing' | 'removed';

export type ReviewType = 'up' | 'down';

export type ReliabilityScore = 'high' | 'medium' | 'low';

export interface Review {
  id: number;
  location: number;
  type: ReviewType;
  tags: string[];
  free_text: string;
  created_at: string;
}

export interface WashLocation {
  id: number;
  lat: number;
  lng: number;
  building_name: string;
  address: string;
  photo: string | null;
  detail_text: string;
  source: LocationSource;
  status: LocationStatus;
  up_count: number;
  down_count: number;
  created_at: string;
}

/** GET /api/locations/{id}/ 는 리뷰 목록을 함께 내려준다. */
export interface WashLocationDetail extends WashLocation {
  reviews: Review[];
}

export interface ReliabilityReport {
  score: ReliabilityScore;
  summary: string;
  /**
   * 리뷰에서 실제로 언급된 항목만 담긴다. 언급이 없으면 아예 빠진다.
   * 옛 버전 백엔드나 캐시된 응답에는 이 필드가 없을 수 있어 optional로 둔다.
   */
  aspects?: Record<string, number>;
  /** 사용자가 알아두면 좋은 점. 없거나 빈 배열일 수 있다. */
  notes?: string[];
}

/** 위치 등록 폼에서 서버로 보내는 값. */
export interface NewLocationInput {
  lat: number;
  lng: number;
  building_name: string;
  address: string;
  detail_text: string;
  photoUri: string;
}

/** 리뷰 작성 폼에서 서버로 보내는 값. */
export interface NewReviewInput {
  type: ReviewType;
  tags: string[];
  free_text: string;
}

/** 사용 기록 한 건. */
export interface Usage {
  id: number;
  location: number;
  location_name: string;
  used_at: string;
  /** 사용자가 직접 적은 상황. 비어 있을 수 있다. */
  note: string;
}

/** 기록 직후 응답. id가 있어 바로 '실행 취소'를 걸 수 있다. */
export interface UsageCreated extends Usage {
  total_count: number;
}

/** 요일별·시간대별·주간 추이 그래프의 막대 하나. */
export interface UsageBucket {
  label: string;
  count: number;
}

export interface UsageTopLocation {
  id: number;
  name: string;
  count: number;
}

/**
 * 사용 기록에서 계산한 통계. 숫자는 전부 서버가 실제 기록으로 센 값이라
 * 앱에서 다시 계산하지 않는다.
 */
export interface UsageStats {
  total_count: number;
  location_count: number;
  first_used_at: string | null;
  last_used_at: string | null;
  saved_cups: number;
  saved_co2_grams: number;
  /** 최근 4주 사용 횟수. 달이 바뀌어도 0으로 떨어지지 않게 이 기준을 쓴다. */
  recent_count: number;
  streak_weeks: number;
  busiest_weekday: string | null;
  busiest_time: string | null;
  weekday_counts: UsageBucket[];
  time_buckets: UsageBucket[];
  weekly_trend: UsageBucket[];
  top_locations: UsageTopLocation[];
  /** 장소 이름으로 추정한 성격별 분포. 많은 순. */
  place_categories: UsageBucket[];
  /** 사용자가 직접 적은 상황 중 자주 나온 것. */
  top_contexts: UsageBucket[];
  /** 최근 상황 원문 (AI 문구 생성용이라 화면에는 안 쓴다). */
  recent_contexts: string[];
}

/** 통계를 읽고 AI가 붙인 응원 문구. */
export interface UsageNarrative {
  headline: string;
  message: string;
  /** 제안이 없을 수도 있어 빈 문자열이 올 수 있다. */
  tip: string;
}

/** GET /api/me/report/ */
export interface UsageReport {
  stats: UsageStats;
  narrative: UsageNarrative;
}
