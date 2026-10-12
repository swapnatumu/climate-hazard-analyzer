import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import type { AnalysisParams } from "../types";

const WAKING_AFTER_MS = 5000;

/** Runs an analysis when `params` is set. Reports `waking` when a request is slow,
 *  since the free backend host sleeps after 15 minutes idle. */
export function useHazard(params: AnalysisParams | null) {
  const query = useQuery({
    queryKey: ["hazard", params],
    queryFn: ({ signal }) => api.analyze(params!, signal),
    enabled: params !== null,
    staleTime: 60 * 60 * 1000,
    // Retry once only on network failure (server asleep); never on 4xx.
    retry: (count, err) => count < 1 && (err as { status?: number }).status === 0,
  });

  const [waking, setWaking] = useState(false);
  useEffect(() => {
    if (!query.isFetching) {
      setWaking(false);
      return;
    }
    const t = setTimeout(() => setWaking(true), WAKING_AFTER_MS);
    return () => clearTimeout(t);
  }, [query.isFetching]);

  return { ...query, waking };
}
