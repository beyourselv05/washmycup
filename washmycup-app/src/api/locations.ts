import { client } from '@/api/client';
import { MOCK_LOCATIONS } from '@/constants/mock';
import type {
  NewLocationInput,
  NewReviewInput,
  ReliabilityReport,
  Review,
  WashLocation,
  WashLocationDetail,
} from '@/types';

export interface LocationsResult {
  locations: WashLocation[];
  /** 서버 대신 목업 데이터를 쓴 경우 true. 지도에 안내 배너를 띄우는 데 쓴다. */
  isMock: boolean;
}

/** GET /api/locations/ — 실패하면 목업으로 대체해 지도가 비지 않게 한다. */
export async function fetchLocations(): Promise<LocationsResult> {
  try {
    const { data } = await client.get<WashLocation[]>('/locations/');
    return { locations: data, isMock: false };
  } catch {
    return { locations: MOCK_LOCATIONS, isMock: true };
  }
}

/** GET /api/locations/{id}/ — 위치 상세 + 리뷰 목록 */
export async function fetchLocationDetail(id: number): Promise<WashLocationDetail> {
  const { data } = await client.get<WashLocationDetail>(`/locations/${id}/`);
  return data;
}

/**
 * GET /api/locations/{id}/reliability/ — AI 신뢰도 리포트
 *
 * Gemini 호출이 들어가는 요청이라 다른 API보다 오래 걸린다(보통 5~10초).
 * 기본 제한시간(15초)으로는 빠듯해서 이 요청만 넉넉하게 잡는다.
 */
export async function fetchReliability(id: number): Promise<ReliabilityReport> {
  const { data } = await client.get<ReliabilityReport>(`/locations/${id}/reliability/`, {
    timeout: 60000,
  });
  return data;
}

/** POST /api/locations/ — 사진을 포함해 multipart/form-data로 보낸다. */
export async function createLocation(input: NewLocationInput): Promise<WashLocation> {
  const form = new FormData();
  form.append('lat', String(input.lat));
  form.append('lng', String(input.lng));
  form.append('building_name', input.building_name);
  form.append('address', input.address);
  form.append('detail_text', input.detail_text);
  form.append('photo', {
    uri: input.photoUri,
    name: guessFileName(input.photoUri),
    type: guessMimeType(input.photoUri),
  } as unknown as Blob);

  const { data } = await client.post<WashLocation>('/locations/', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

/** POST /api/locations/{id}/reviews/ */
export async function createReview(locationId: number, input: NewReviewInput): Promise<Review> {
  const { data } = await client.post<Review>(`/locations/${locationId}/reviews/`, input);
  return data;
}

/** POST /api/locations/{id}/report/ */
export async function createReport(locationId: number, reason: string): Promise<void> {
  await client.post(`/locations/${locationId}/report/`, { reason });
}

function guessFileName(uri: string): string {
  const name = uri.split('/').pop();
  return name && name.includes('.') ? name : 'photo.jpg';
}

function guessMimeType(uri: string): string {
  const extension = uri.split('.').pop()?.toLowerCase();
  if (extension === 'png') return 'image/png';
  if (extension === 'heic') return 'image/heic';
  if (extension === 'webp') return 'image/webp';
  return 'image/jpeg';
}
