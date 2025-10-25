import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  PostgrestError,
  PostgrestFilterBuilder,
  SupabaseClient,
} from "@supabase/supabase-js";

type CursorValue = string | number | null;

type FilterFactory<T> = (
  query: PostgrestFilterBuilder<any, T[], unknown>
) => PostgrestFilterBuilder<any, T[], unknown>;

export interface UseInfiniteSupabaseQueryOptions<T> {
  client: SupabaseClient<any, "public", any>;
  table: string;
  select?: string;
  pageSize?: number;
  cursorColumn?: string;
  initialCursor?: CursorValue;
  order?: {
    column: string;
    ascending?: boolean;
    nullsFirst?: boolean;
  };
  filters?: FilterFactory<T>;
}

export interface UseInfiniteSupabaseQueryResult<T> {
  items: T[];
  cursor: CursorValue;
  hasMore: boolean;
  isInitialLoading: boolean;
  isFetchingMore: boolean;
  error: PostgrestError | null;
  fetchNext: () => Promise<void>;
  refresh: (cursor?: CursorValue) => Promise<void>;
  replaceItems: (updater: (current: T[]) => T[]) => void;
}

interface LoadOptions {
  append: boolean;
  cursor?: CursorValue;
}

export function useInfiniteSupabaseQuery<T = Record<string, unknown>>(
  options: UseInfiniteSupabaseQueryOptions<T>
): UseInfiniteSupabaseQueryResult<T> {
  const {
    client,
    table,
    select = "*",
    pageSize = 25,
    cursorColumn = "id",
    initialCursor = null,
    order,
    filters,
  } = options;

  const [items, setItems] = useState<T[]>([]);
  const [error, setError] = useState<PostgrestError | null>(null);
  const [isInitialLoading, setIsInitialLoading] = useState<boolean>(false);
  const [isFetchingMore, setIsFetchingMore] = useState<boolean>(false);
  const [hasMore, setHasMore] = useState<boolean>(true);
  const [cursor, setCursor] = useState<CursorValue>(initialCursor);

  const requestIdRef = useRef(0);
  const cursorRef = useRef<CursorValue>(initialCursor);

  const loadPage = useCallback(
    async ({ append, cursor: explicitCursor }: LoadOptions) => {
      const currentRequest = ++requestIdRef.current;
      const isInitial = !append;

      setError(null);
      if (isInitial) {
        setIsInitialLoading(true);
      } else {
        setIsFetchingMore(true);
      }

      try {
        let query = client
          .from<T>(table)
          .select(select, { head: false });

        if (filters) {
          query = filters(query) as PostgrestFilterBuilder<any, T[], unknown>;
        }

        if (order) {
          query = query.order(order.column, {
            ascending: order.ascending ?? true,
            nullsFirst: order.nullsFirst ?? false,
          });
        }

        const activeCursor =
          explicitCursor !== undefined
            ? explicitCursor
            : append
            ? cursorRef.current
            : initialCursor;

        if (activeCursor !== null && activeCursor !== undefined) {
          const ascending = order?.ascending ?? true;
          if (ascending) {
            query = query.gt(cursorColumn, activeCursor as never);
          } else {
            query = query.lt(cursorColumn, activeCursor as never);
          }
        }

        const { data, error: fetchError } = await query.range(0, pageSize - 1);

        if (currentRequest !== requestIdRef.current) {
          return;
        }

        if (fetchError) {
          setError(fetchError);
          if (!append) {
            setItems([]);
            setHasMore(false);
          }
          return;
        }

        const rows = Array.isArray(data) ? data : [];

        setItems((prev) => (append ? [...prev, ...rows] : rows));
        const received = rows.length;
        const newHasMore = received === pageSize;
        setHasMore(newHasMore);

        if (received > 0) {
          const last = rows[rows.length - 1] as Record<string, any>;
          const nextCursor = (last?.[cursorColumn] ?? null) as CursorValue;
          cursorRef.current = nextCursor;
          setCursor(nextCursor);
        } else if (!append) {
          cursorRef.current = activeCursor ?? null;
          setCursor(activeCursor ?? null);
        }
      } finally {
        if (currentRequest === requestIdRef.current) {
          setIsInitialLoading(false);
          setIsFetchingMore(false);
        }
      }
    },
    [client, table, select, filters, order, cursorColumn, pageSize, initialCursor]
  );

  const fetchNext = useCallback(async () => {
    if (isFetchingMore || !hasMore) {
      return;
    }
    await loadPage({ append: true });
  }, [hasMore, isFetchingMore, loadPage]);

  const refresh = useCallback(
    async (resetCursor?: CursorValue) => {
      cursorRef.current = resetCursor ?? initialCursor ?? null;
      setCursor(resetCursor ?? initialCursor ?? null);
      setHasMore(true);
      await loadPage({ append: false, cursor: resetCursor });
    },
    [initialCursor, loadPage]
  );

  useEffect(() => {
    void refresh();
    // The refresh function captures option dependencies; re-run when it changes.
  }, [refresh]);

  const replaceItems = useCallback((updater: (current: T[]) => T[]) => {
    setItems((prev) => updater(prev));
  }, []);

  return useMemo(
    () => ({
      items,
      cursor,
      hasMore,
      isInitialLoading,
      isFetchingMore,
      error,
      fetchNext,
      refresh,
      replaceItems,
    }),
    [
      cursor,
      error,
      fetchNext,
      hasMore,
      isFetchingMore,
      isInitialLoading,
      items,
      refresh,
      replaceItems,
    ]
  );
}

export default useInfiniteSupabaseQuery;
