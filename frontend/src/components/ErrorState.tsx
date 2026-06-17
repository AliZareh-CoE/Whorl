/** Calm, consistent data-load failure state (#280): replaces the bare red "Couldn't load…"
 * lines scattered across pages with one dark-aware block that offers a retry — so a transient
 * API hiccup recovers in place, without a full reload. */

export function ErrorState({
  message = "Something went wrong.",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-300"
    >
      <p>{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-2 rounded border border-red-300 px-2.5 py-1 text-xs font-medium text-red-700 transition-colors hover:bg-red-100 active:opacity-80 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/40"
        >
          Try again
        </button>
      )}
    </div>
  );
}
