/** Calm loading skeletons (#271): pulsing placeholders shaped like the content that's
 * coming, so the layout doesn't jump when data arrives and a blank "Loading…" line is
 * replaced by something with weight. Dark-mode aware. */

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-stone-200/70 dark:bg-stone-800 ${className}`}
      aria-hidden="true"
    />
  );
}

export function SkeletonLines({ lines = 3, className = "" }: { lines?: number; className?: string }) {
  return (
    <div className={`space-y-2 ${className}`} aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <Skeleton key={i} className={`h-4 ${i === lines - 1 ? "w-2/3" : "w-full"}`} />
      ))}
    </div>
  );
}

export function SkeletonCard({ className = "" }: { className?: string }) {
  return (
    <div className={`card ${className}`} aria-hidden="true">
      <Skeleton className="mb-3 h-3 w-24" />
      <SkeletonLines lines={3} />
    </div>
  );
}

/** A page-level loading shell: a title bar plus a few card skeletons. */
export function SkeletonPage({ cards = 3 }: { cards?: number }) {
  return (
    <div role="status" aria-label="Loading" className="space-y-4">
      <Skeleton className="h-7 w-48" />
      {Array.from({ length: cards }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  );
}
