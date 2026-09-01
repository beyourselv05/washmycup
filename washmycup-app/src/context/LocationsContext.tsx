import { createContext, use, useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { fetchLocations } from '@/api/locations';
import type { WashLocation } from '@/types';

interface LocationsContextValue {
  locations: WashLocation[];
  isLoading: boolean;
  /** 백엔드에 붙지 못해 목업 데이터를 보여주는 중이면 true. */
  isMock: boolean;
  refresh: () => Promise<void>;
}

const LocationsContext = createContext<LocationsContextValue | null>(null);

export function LocationsProvider({ children }: { children: ReactNode }) {
  const [locations, setLocations] = useState<WashLocation[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isMock, setIsMock] = useState(false);

  const refresh = useCallback(async () => {
    setIsLoading(true);
    const result = await fetchLocations();
    setLocations(result.locations);
    setIsMock(result.isMock);
    setIsLoading(false);
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const value = useMemo(
    () => ({ locations, isLoading, isMock, refresh }),
    [locations, isLoading, isMock, refresh],
  );

  return <LocationsContext value={value}>{children}</LocationsContext>;
}

export function useLocations(): LocationsContextValue {
  const context = use(LocationsContext);
  if (!context) {
    throw new Error('useLocations는 LocationsProvider 안에서만 쓸 수 있습니다.');
  }
  return context;
}
