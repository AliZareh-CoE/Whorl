import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./Layout";
import { DialogHost } from "../components/Dialog";
import { UndoHost } from "../components/UndoToast";
import { ErrorBoundary, reportClientError } from "../components/ErrorBoundary";
import { installDesktopContextMenuGuard, installDevtoolsShortcut } from "./external";

// Route-level code splitting (Backlog #76): each page is its own chunk, fetched on
// first visit — spa.js carries only the shell, router, and query client.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Projects = lazy(() => import("./pages/Projects"));
const NewProject = lazy(() => import("./pages/NewProject"));
const ImportProjects = lazy(() => import("./pages/ImportProjects"));
const ProjectOverview = lazy(() => import("./pages/ProjectOverview"));
const Plan = lazy(() => import("./pages/Plan"));
const Timeline = lazy(() => import("./pages/Timeline"));
const Documents = lazy(() => import("./pages/Documents"));
const Files = lazy(() => import("./pages/Files"));
const Literature = lazy(() => import("./pages/Literature"));
const ReadingFlow = lazy(() => import("./pages/ReadingFlow"));
const Library = lazy(() => import("./pages/Library"));
const Reference = lazy(() => import("./pages/Reference"));
const Notes = lazy(() => import("./pages/Notes"));
const Research = lazy(() => import("./pages/Research"));
const Review = lazy(() => import("./pages/Review"));
const Matrix = lazy(() => import("./pages/Matrix"));
const Decisions = lazy(() => import("./pages/Decisions"));
const Graph = lazy(() => import("./pages/Graph"));
const WritingBoard = lazy(() => import("./pages/Writing").then((m) => ({ default: m.WritingBoard })));
const ManuscriptDetail = lazy(() => import("./pages/Writing").then((m) => ({ default: m.ManuscriptDetail })));
const Studio = lazy(() => import("./pages/Studio"));
const PetPage = lazy(() => import("./pages/Pet"));
const Achievements = lazy(() => import("./pages/Achievements"));
const Connect = lazy(() => import("./pages/Connect"));
const Diagnostics = lazy(() => import("./pages/Diagnostics"));
const Report = lazy(() => import("./pages/Report"));
const Inbox = lazy(() => import("./pages/Inbox"));
const Today = lazy(() => import("./pages/Today"));
const Prompts = lazy(() => import("./pages/Prompts"));
const Search = lazy(() => import("./pages/Search"));
const Automations = lazy(() => import("./pages/Automations"));
const Figures = lazy(() => import("./pages/Figures"));
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

installDesktopContextMenuGuard();
installDevtoolsShortcut();

// Anything thrown outside React's render (#382) — an event handler, a promise — is reported
// too; the boot watchdog in spa.html covers the time before this script ran.
window.addEventListener("error", (e) => reportClientError("window", [`${e.message} @ ${String(e.filename).replace(location.origin, "")}:${e.lineno}`]));
window.addEventListener("unhandledrejection", (e) => { const r = e.reason as { stack?: string } | undefined; const text = r?.stack ? String(r.stack).split("\n").slice(0, 3).join(" · ") : String(r); if (text !== "Error: auth") reportClientError("promise", [text]); });
// #451: "mounted" means *painted* — the flag flips only once the app has put readable text on
// screen, so a render that inserts nodes and then stalls (a hanging chunk, a swallowed error)
// still trips the boot watchdog in spa.html instead of leaving a silent dark window.
(function markPainted() {
  const started = performance.now();
  const tick = () => {
    const root = document.getElementById("root");
    if (root && (root.textContent ?? "").trim().length > 20) {
      (window as unknown as { __atlasMounted?: boolean }).__atlasMounted = true;
      return;
    }
    if (performance.now() - started < 60_000) window.setTimeout(tick, 250);
  };
  window.setTimeout(tick, 0);
})();

createRoot(document.getElementById("root")!).render(
  <ErrorBoundary scope="app">
  <QueryClientProvider client={queryClient}>
    <BrowserRouter basename="/">
      <Suspense fallback={<p className="p-8 text-sm text-stone-400">Loading…</p>}>
      <Routes>
        {/* the LaTeX studio owns the whole window — no sidebar, its own chrome */}
        <Route path="manuscripts/:id/editor" element={<Studio />} />
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="projects" element={<Projects />} />
          <Route path="projects/new" element={<NewProject />} />
          <Route path="projects/import" element={<ImportProjects />} />
          <Route path="projects/:slug" element={<ProjectOverview />} />
          <Route path="projects/:slug/plan" element={<Plan />} />
          <Route path="projects/:slug/timeline" element={<Timeline />} />
          <Route path="projects/:slug/documents" element={<Documents />} />
          <Route path="projects/:slug/figures" element={<Figures />} />
          <Route path="projects/:slug/files" element={<Files />} />
          <Route path="projects/:slug/literature" element={<Literature />} />
          <Route path="projects/:slug/queue" element={<Literature queue />} />
          <Route path="projects/:slug/read" element={<ReadingFlow />} />
          <Route path="library/read" element={<ReadingFlow />} />
          <Route path="projects/:slug/notes" element={<Notes />} />
          <Route path="projects/:slug/notes/new" element={<Notes />} />
          <Route path="projects/:slug/notes/:id" element={<Notes />} />
          <Route path="projects/:slug/research" element={<Research />} />
          <Route path="projects/:slug/review" element={<Review />} />
          <Route path="projects/:slug/report" element={<Report />} />
          <Route path="projects/:slug/matrix" element={<Matrix />} />
          <Route path="review" element={<Review />} />
          <Route path="projects/:slug/decisions" element={<Decisions />} />
          <Route path="projects/:slug/graph" element={<Graph />} />
          <Route path="automations" element={<Automations />} />
          <Route path="pet" element={<PetPage />} />
          <Route path="achievements" element={<Achievements />} />
          <Route path="connect" element={<Connect />} />
          <Route path="diagnostics" element={<Diagnostics />} />
          <Route path="library" element={<Library />} />
          <Route path="references/:id" element={<Reference />} />
          <Route path="writing" element={<WritingBoard />} />
          <Route path="manuscripts/:id" element={<ManuscriptDetail />} />
          <Route path="inbox" element={<Inbox />} />
          <Route path="today" element={<Today />} />
          <Route path="prompts" element={<Prompts />} />
          <Route path="search" element={<Search />} />
          <Route path="*" element={
            <div className="pt-24 text-center">
              <p className="mb-2 text-4xl">🧭</p>
              <h1 className="mb-2 text-2xl font-semibold tracking-tight">Page not found</h1>
              <p className="text-sm text-stone-500">No Atlas page lives here. Try the <a href="/" className="text-indigo-600 hover:underline">dashboard</a> or the <a href="/classic/" className="text-indigo-600 hover:underline">classic UI</a>.</p>
            </div>
          } />
        </Route>
      </Routes>
      </Suspense>
      <DialogHost />
      <UndoHost />
    </BrowserRouter>
  </QueryClientProvider>
  </ErrorBoundary>,
);
