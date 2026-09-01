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
