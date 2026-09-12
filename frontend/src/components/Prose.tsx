/** Rendered markdown from the API (#407): decisions, experiment entries, protocols and
 * captures come with `*_html` companions where [[note]] and @cite-key mentions are already
 * links. The HTML is nh3-sanitized server-side; internal links are picked up by the global
 * SPA link interceptor in Layout, so a mention navigates without a reload. */
export function Prose({ html, className = "", clamp, testId }: { html: string; className?: string; clamp?: boolean; testId?: string }) {
  if (!html) return null;
  return (
    <div
      className={`prose prose-sm prose-stone max-w-none prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-a:text-indigo-600 prose-a:no-underline hover:prose-a:underline dark:prose-invert dark:prose-a:text-indigo-300 ${clamp ? "line-clamp-4" : ""} ${className}`}
      data-testid={testId}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
