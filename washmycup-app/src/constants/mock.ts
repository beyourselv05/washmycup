import type { WashLocation } from '@/types';

/**
 * 백엔드가 안 떠 있을 때 지도가 비어 보이지 않도록 쓰는 목업 데이터.
 * 서버가 응답하면 이 값은 쓰이지 않는다.
 */
export const MOCK_LOCATIONS: WashLocation[] = [
  {
    id: -1,
    lat: 37.517236,
    lng: 127.047325,
    building_name: '강남구청 (샘플)',
    address: '서울특별시 강남구 학동로 426 (삼성동)',
    photo: null,
    detail_text: '민원실 1층 로비 정수기 옆\n무료 이용',
    source: 'user',
    status: 'confirmed',
    up_count: 3,
    down_count: 0,
    created_at: new Date().toISOString(),
  },
  {
    id: -2,
    lat: 37.545837,
    lng: 126.964458,
    building_name: '숙명여대 정문 (샘플)',
    address: '서울특별시 용산구 청파로47길 100 (청파동2가)',
    photo: null,
    detail_text: '정문 경비실 옆 야외 급수대',
    source: 'user',
    status: 'confirmed',
    up_count: 1,
    down_count: 2,
    created_at: new Date().toISOString(),
  },
  {
    id: -3,
    lat: 37.5665,
    lng: 126.978,
    building_name: '서울시청 (샘플)',
    address: '서울특별시 중구 세종대로 110 (태평로1가)',
    photo: null,
    detail_text: '지하 1층 시민청 입구 옆',
    source: 'user',
    status: 'unconfirmed',
    up_count: 0,
    down_count: 0,
    created_at: new Date().toISOString(),
  },
];
