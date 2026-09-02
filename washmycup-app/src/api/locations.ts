import { client } from '@/api/client';
import { MOCK_LOCATIONS } from '@/constants/mock';
import type {
  NewLocationInput,
  NewReviewInput,
  ReliabilityReport,
  Review,
  Usage,
  UsageCreated,
  UsageReport,
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

  // 사진은 선택이다. 없을 때 빈 값을 보내면 서버가 파일로 파싱하려다 실패하므로 아예 뺀다.
  if (input.photoUri) {
    form.append('photo', {
      uri: input.photoUri,
      name: guessFileName(input.photoUri),
      type: guessMimeType(input.photoUri),
    } as unknown as Blob);
  }

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

/**
 * POST /api/locations/{id}/usages/ — '여기서 씻었어요' 기록을 남긴다.
 *
 * usedAt을 주면 지나간 시각으로, 생략하면 서버가 지금 시각으로 잡는다.
 * note는 사용자가 직접 적은 상황이라 비어 있을 수 있다.
 */
export async function recordUsage(
  locationId: number,
  input: { usedAt?: Date; note?: string } = {},
): Promise<UsageCreated> {
  const { data } = await client.post<UsageCreated>(`/locations/${locationId}/usages/`, {
    ...(input.usedAt ? { used_at: input.usedAt.toISOString() } : {}),
    ...(input.note ? { note: input.note } : {}),
  });
  return data;
}

/** GET /api/usages/notes/ — 전에 직접 적었던 상황 문구 (다시 쓰기 쉽게) */
export async function fetchUsageNotes(): Promise<string[]> {
  const { data } = await client.get<string[]>('/usages/notes/');
  return data;
}

/** DELETE /api/usages/{id}/ — 잘못 남긴 기록을 되돌린다. */
export async function deleteUsage(usageId: number): Promise<void> {
  await client.delete(`/usages/${usageId}/`);
}

/** GET /api/usages/ — 최근 기록 목록 (되돌리기용) */
export async function fetchUsages(): Promise<Usage[]> {
  const { data } = await client.get<Usage[]>('/usages/');
  return data;
}

/**
 * GET /api/me/report/ — 내 사용 기록으로 만든 개인 리포트
 *
 * 신뢰도 요약과 마찬가지로 Gemini 호출이 들어가서 오래 걸릴 수 있다.
 */
export async function fetchUsageReport(): Promise<UsageReport> {
  const { data } = await client.get<UsageReport>('/me/report/', { timeout: 60000 });
  return data;
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
