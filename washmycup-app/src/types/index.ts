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
