/** Figure gallery (#256): a calm grid of every image in the project, grouped by folder,
 * with a tag filter and click-to-lightbox. Reads the #8 /figures/ feed; thumbnails and the
 * lightbox both point an <img> at each figure's nosniff'd raw_url. */
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

type Figure = {
  id: number;
  title: string;
  folder: string | null;
  folder_id: number | null;
  tags: string[];
  size: number;
  content_type: string;
  created_at: string;
  raw_url: string;
};

export default function Figures() {
  const { slug } = useParams();
  const [tag, setTag] = useState<string | null>(null);
  const [active, setActive] = useState<Figure | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["figures", slug],
    queryFn: () => api<Figure[]>(`/projects/${slug}/figures/`),
  });

  const allTags = useMemo(() => {
    const set = new Set<string>();
    (data ?? []).forEach((f) => f.tags.forEach((t) => set.add(t)));
    return [...set].sort();
  }, [data]);

  const figures = (data ?? []).filter((f) => !tag || f.tags.includes(tag));

  // group by folder, keeping the feed's newest-first order within each group
  const groups = useMemo(() => {
    const byFolder = new Map<string, Figure[]>();
    for (const f of figures) {
      const key = f.folder ?? "Project root";
      (byFolder.get(key) ?? byFolder.set(key, []).get(key)!).push(f);
    }
    return [...byFolder.entries()];
  }, [figures]);

  if (isLoading) return <p className="text-sm text-stone-400">Loading figures…</p>;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Figures
      </nav>
      <div className="mb-6 flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Figures</h1>
        {(data?.length ?? 0) > 0 && (
          <span className="text-sm text-stone-400">{data!.length} images</span>
        )}
      </div>

      {(data?.length ?? 0) === 0 ? (
        <div className="rounded border border-dashed border-stone-300 bg-white p-10 text-center">
          <p className="text-sm text-stone-500">
            No figures yet. Upload images (PNG, JPEG, GIF, WebP, BMP) to this project's documents
            and they'll appear here as a gallery.
          </p>
          <Link
            to={`/projects/${slug}/documents`}
            className="mt-3 inline-block text-sm font-medium text-indigo-600 hover:underline"
          >
            Go to Documents →
          </Link>
        </div>
      ) : (
        <>
          {allTags.length > 0 && (
            <div className="mb-5 flex flex-wrap items-center gap-2">
              <button
                onClick={() => setTag(null)}
                className={`rounded-full px-3 py-1 text-xs font-medium ${
                  tag === null ? "bg-indigo-600 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                }`}
              >
                All
              </button>
              {allTags.map((t) => (
                <button
                  key={t}
                  onClick={() => setTag(t)}
                  className={`rounded-full px-3 py-1 text-xs font-medium ${
                    tag === t ? "bg-indigo-600 text-white" : "bg-stone-100 text-stone-600 hover:bg-stone-200"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          )}

          {groups.map(([folder, items]) => (
            <section key={folder} className="mb-8">
              <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-stone-400">
                {folder} <span className="text-stone-300">{items.length}</span>
              </h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {items.map((f) => (
                  <button
                    key={f.id}
                    onClick={() => setActive(f)}
                    className="group overflow-hidden rounded border border-stone-200 bg-white text-left hover:border-indigo-300"
                  >
                    <img
                      src={f.raw_url}
                      alt={f.title}
                      loading="lazy"
                      className="h-36 w-full bg-stone-50 object-contain"
                    />
                    <p className="truncate px-2 py-1.5 text-xs text-stone-600 group-hover:text-indigo-700">
                      {f.title}
                    </p>
                  </button>
                ))}
              </div>
            </section>
          ))}
        </>
      )}

      {active && (
        <div
          onClick={() => setActive(null)}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-black/70 p-6"
        >
          <img
            src={active.raw_url}
            alt={active.title}
            onClick={(e) => e.stopPropagation()}
            className="max-h-[82vh] max-w-full rounded border border-stone-700 bg-white"
          />
          <div className="mt-3 flex items-center gap-3 text-sm text-stone-200">
            <span>{active.title}</span>
            <a href={active.raw_url} download className="text-indigo-300 hover:underline">
              Download
            </a>
            <button onClick={() => setActive(null)} className="text-stone-400 hover:text-white">
              Close ✕
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
