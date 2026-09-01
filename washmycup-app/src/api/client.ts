import axios from 'axios';

import { API_BASE_URL } from '@/constants/config';

export const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
});

/** DRF가 내려주는 필드별 검증 에러를 사용자에게 보여줄 한 줄로 바꾼다. */
export function toErrorMessage(error: unknown, fallback = '요청을 처리하지 못했습니다.'): string {
  if (!axios.isAxiosError(error)) {
    return fallback;
  }

  if (error.code === 'ECONNABORTED') {
    return '응답이 너무 오래 걸려 중단했습니다. 다시 시도해주세요.';
  }

  if (!error.response) {
    return '서버에 연결하지 못했습니다. 백엔드가 실행 중인지 확인해주세요.';
  }

  const data = error.response.data;
  if (typeof data === 'string') {
    return data;
  }

  if (data && typeof data === 'object') {
    const messages = Object.values(data as Record<string, unknown>)
      .flatMap((value) => (Array.isArray(value) ? value : [value]))
      .filter((value): value is string => typeof value === 'string');

    if (messages.length > 0) {
      return messages.join('\n');
    }
  }

  return fallback;
}
