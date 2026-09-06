/** Figure gallery (#256): a calm grid of every image in the project, grouped by folder,
 * with a tag filter and click-to-lightbox. Reads the #8 /figures/ feed; thumbnails and the
 * lightbox both point an <img> at each figure's nosniff'd raw_url. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Download, Maximize2, Pencil, Trash2 } from "lucide-react";
import { api } from "../api";
import { ErrorState } from "../../components/ErrorState";
import { confirmDialog, errorDialog, promptDialog } from "../../components/Dialog";
import { Kebab, useMenu, type MenuItem } from "../../components/Menu";

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

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["figures", slug],
    queryFn: () => api<Figure[]>(`/projects/${slug}/figures/`),
  });
  // CRUD sweep 2026-09-06: figures are documents — rename and delete them right here
  const queryClient = useQueryClient();
  const menu = useMenu();
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["figures", slug] }); queryClient.invalidateQueries({ queryKey: ["tree", slug] }); queryClient.invalidateQueries({ queryKey: ["documents-table", slug] }); };
  const rename = useMutation({ mutationFn: (v: { id: number; title: string }) => api(`/documents/${v.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: v.title }) }), onSuccess: refresh, onError: (e) => void errorDialog("Couldn't rename the figure", e) });
  const remove = useMutation({ mutationFn: (id: number) => api(`/documents/${id}/`, { method: "DELETE" }), onSuccess: () => { setActive(null); refresh(); }, onError: (e) => void errorDialog("Couldn't delete the figure", e) });
  const askRename = async (f: Figure) => { const t = await promptDialog({ title: "Rename figure", label: "Title", initial: f.title, validate: (v) => (v.trim() ? null : "A figure needs a title.") }); if (t && t.trim() !== f.title) rename.mutate({ id: f.id, title: t.trim() }); };
  const askDelete = async (f: Figure) => { if (await confirmDialog({ title: `Delete “${f.title}”?`, body: "The image file is removed from the project.", danger: true, confirmLabel: "Delete figure" })) remove.mutate(f.id); };
  const itemsFor = (f: Figure): MenuItem[] => [
    { label: "Open", icon: <Maximize2 className="h-3.5 w-3.5" />, onSelect: () => setActive(f) },
    { label: "Download", icon: <Download className="h-3.5 w-3.5" />, onSelect: () => { const a = document.createElement("a"); a.href = f.raw_url; a.download = f.title; a.click(); } },
    "-",
    { label: "Rename…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: () => void askRename(f) },
    { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: () => void askDelete(f) },
  ];

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
  if (error || !data) return <ErrorState message="Couldn't load figures." onRetry={() => refetch()} />;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-300">
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
        <div className="rounded-lg border border-dashed border-stone-300 bg-white p-12 text-center dark:border-stone-700 dark:bg-stone-900">
          <p className="mb-2 text-3xl">🖼️</p>
          <p className="mx-auto max-w-md text-sm text-stone-500 dark:text-stone-300">
            No figures yet. Upload images (PNG, JPEG, GIF, WebP, BMP) to this project's documents
            and they'll appear here as a gallery.
          </p>
          <Link
            to={`/projects/${slug}/documents`}
            className="mt-4 inline-block text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400"
          >
            Go to Documents →
          </Link>
        </div>
      ) : (
        <>
          {allTags.length > 0 && (
            <div className="mb-6 flex flex-wrap items-center gap-2">
              <button
                onClick={() => setTag(null)}
                className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                  tag === null
                    ? "bg-indigo-600 text-white"
                    : "border border-stone-200 bg-white text-stone-500 hover:border-stone-300 hover:text-stone-700 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-400 dark:hover:text-stone-300"
                }`}
              >
                All
              </button>
              {allTags.map((t) => (
                <button
                  key={t}
                  onClick={() => setTag(t)}
                  className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    tag === t
                      ? "bg-indigo-600 text-white"
                      : "border border-stone-200 bg-white text-stone-500 hover:border-stone-300 hover:text-stone-700"
                  }`}
                >
                  {t}
                </button>
              ))}
            </div>
          )}

          {groups.map(([folder, items]) => (
            <section key={folder} className="mb-10">
              <h2 className="mb-4 flex items-baseline gap-2 text-sm font-medium uppercase tracking-wide text-stone-400">
                {folder} <span className="text-stone-300 dark:text-stone-400">{items.length}</span>
              </h2>
              <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
                {items.map((f) => (
                  <div key={f.id} className="group relative" onContextMenu={(e) => menu.open(e, itemsFor(f))} data-testid="figure-card">
                    <button
                      type="button"
                      onClick={() => setActive(f)}
                      className="w-full overflow-hidden rounded-lg border border-stone-200 bg-white text-left shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:border-stone-300 hover:shadow-md focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:border-stone-800 dark:bg-stone-900"
                    >
                      <div className="aspect-[4/3] overflow-hidden bg-stone-50 dark:bg-stone-800">
                        <img
                          src={f.raw_url}
                          alt={f.title}
                          loading="lazy"
                          className="h-full w-full object-contain transition-transform duration-200 group-hover:scale-[1.02]"
                        />
                      </div>
                      <p className="truncate border-t border-stone-100 px-2.5 py-2 pr-8 text-xs text-stone-600 group-hover:text-indigo-700 dark:border-stone-800 dark:text-stone-300 dark:group-hover:text-indigo-300">
                        {f.title}
                      </p>
                    </button>
                    <Kebab items={itemsFor(f)} label={`Actions for ${f.title}`} className="absolute bottom-1.5 right-1.5 bg-white/80 opacity-0 group-hover:opacity-100 focus:opacity-100 dark:bg-stone-900/80" />
                  </div>
                ))}
              </div>
            </section>
          ))}
        </>
      )}

      {active && (
        <div
          onClick={() => setActive(null)}
          className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-stone-950/80 p-6 backdrop-blur-sm"
        >
          <img
            src={active.raw_url}
            alt={active.title}
            onClick={(e) => e.stopPropagation()}
            className="max-h-[80vh] max-w-full rounded-lg bg-white shadow-2xl ring-1 ring-white/10"
          />
          <div
            onClick={(e) => e.stopPropagation()}
            className="mt-4 flex max-w-full items-center gap-4 rounded-full bg-stone-900/70 px-4 py-2 text-sm text-stone-200 ring-1 ring-white/10"
          >
            <span className="min-w-0 truncate text-stone-100">{active.title}</span>
            <a
              href={active.raw_url}
              download
              className="shrink-0 font-medium text-indigo-300 hover:text-indigo-200"
            >
              Download
            </a>
            <button onClick={() => void askRename(active)} className="shrink-0 text-stone-300 hover:text-white">Rename</button>
            <button onClick={() => void askDelete(active)} className="shrink-0 text-red-300 hover:text-red-200">Delete</button>
            <button
              onClick={() => setActive(null)}
              className="shrink-0 text-stone-400 hover:text-white"
            >
              Close ✕
            </button>
          </div>
        </div>
      )}
      {menu.element}
    </div>
  );
}
