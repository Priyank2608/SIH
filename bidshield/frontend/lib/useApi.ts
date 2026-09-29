import { useState, useEffect, useCallback } from 'react';
import { api } from './api';

const globalCache = new Map<string, any>();
const listeners = new Map<string, Set<(data: any) => void>>();

export function mutateGlobal(key: string, data?: any) {
  if (data !== undefined) {
    globalCache.set(key, data);
  } else {
    globalCache.delete(key);
  }
  const fns = listeners.get(key);
  if (fns) {
    fns.forEach(fn => fn(globalCache.get(key)));
  }
}

export function useApi<T>(key: string | null, autoFetch = true) {
  const [data, setData] = useState<T | undefined>(key ? (globalCache.get(key) || undefined) : undefined);
  const [loading, setLoading] = useState<boolean>(autoFetch && data === undefined);
  const [error, setError] = useState<any>(null);

  const fetcher = useCallback(async (force = false) => {
    if (!key) return;
    if (!force && globalCache.has(key)) {
      setData(globalCache.get(key));
      setLoading(false);
      // still revalidate in background
    }
    
    setLoading(!globalCache.has(key));
    try {
      const res = await api(key);
      globalCache.set(key, res);
      mutateGlobal(key, res);
      setError(null);
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, [key]);

  useEffect(() => {
    if (!key) return;
    
    if (!listeners.has(key)) {
      listeners.set(key, new Set());
    }
    const handler = (newData: any) => setData(newData);
    listeners.get(key)!.add(handler);
    
    if (autoFetch) {
      fetcher();
    }

    return () => {
      listeners.get(key)?.delete(handler);
    };
  }, [key, fetcher, autoFetch]);

  return { data, loading, error, mutate: fetcher };
}
