/** One gate for "is the page's data here yet?" (#409, backlog #282).
 *
 * Every page used to hand-wire the same ladder — `if (isLoading) return <Skeleton/>` and,
 * when someone remembered, `if (error) return <ErrorState/>` — and half of them forgot the
 * second rung, so a failed request left a skeleton pulsing forever or an empty page. Now a
 * page calls `queryGate(query, …)` once, right after its hooks, and returns what it gets:
 *
 *     const gate = queryGate(q, { skeleton: <MySkeleton/>, message: "Couldn't load the plan." });
 *     if (gate) return gate;
 *
 * `QueryBoundary` is the same thing as a render-prop component for the cases where the
 * whole body is a function of the data. core/tests/test_query_boundary.py fails the build
 * when a page queries without either. */
import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";
import { ErrorState } from "./ErrorState";
import { SkeletonPage } from "./Skeleton";

type Options = { skeleton?: ReactNode; message?: string };

/** The node to render *instead of* the page while loading or failed; null when data is in. */
export function queryGate<T>(query: UseQueryResult<T>, { skeleton, message }: Options = {}): ReactNode | null {
  if (query.isError && query.data === undefined) {
    const detail = query.error instanceof Error && query.error.message ? ` (${query.error.message})` : "";
    return <ErrorState message={`${message ?? "Couldn't load this page."}${detail}`} onRetry={() => void query.refetch()} />;
  }
  if (query.data === undefined) return skeleton ?? <SkeletonPage />;
  return null;
}

export function QueryBoundary<T>({ query, skeleton, message, children }: Options & { query: UseQueryResult<T>; children: (data: T) => ReactNode }) {
  const gate = queryGate(query, { skeleton, message });
  if (gate) return <>{gate}</>;
  return <>{children(query.data as T)}</>;
}
