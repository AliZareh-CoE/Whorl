import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./Layout";

// Route-level code splitting (Backlog #76): each page is its own chunk, fetched on
// first visit — spa.js carries only the shell, router, and query client.
const Dashboard = lazy(() => import("./pages/Dashboard"));
const Projects = lazy(() => import("./pages/Projects"));
const NewProject = lazy(() => import("./pages/NewProject"));
const ProjectOverview = lazy(() => import("./pages/ProjectOverview"));
const Plan = lazy(() => import("./pages/Plan"));
const Documents = lazy(() => import("./pages/Documents"));
const Literature = lazy(() => import("./pages/Literature"));
const Library = lazy(() => import("./pages/Library"));
const Reference = lazy(() => import("./pages/Reference"));
const NotesList = lazy(() => import("./pages/Notes").then((m) => ({ default: m.NotesList })));
const NoteEditor = lazy(() => import("./pages/Notes").then((m) => ({ default: m.NoteEditor })));
const Research = lazy(() => import("./pages/Research"));
const Decisions = lazy(() => import("./pages/Decisions"));
const Graph = lazy(() => import("./pages/Graph"));
const WritingBoard = lazy(() => import("./pages/Writing").then((m) => ({ default: m.WritingBoard })));
const ManuscriptDetail = lazy(() => import("./pages/Writing").then((m) => ({ default: m.ManuscriptDetail })));
const Inbox = lazy(() => import("./pages/Inbox"));
const Prompts = lazy(() => import("./pages/Prompts"));
const Search = lazy(() => import("./pages/Search"));
const Automations = lazy(() => import("./pages/Automations"));
const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter basename="/">
      <Suspense fallback={<p className="p-8 text-sm text-stone-400">Loading…</p>}>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="projects" element={<Projects />} />
          <Route path="projects/new" element={<NewProject />} />
          <Route path="projects/:slug" element={<ProjectOverview />} />
          <Route path="projects/:slug/plan" element={<Plan />} />
          <Route path="projects/:slug/documents" element={<Documents />} />
          <Route path="projects/:slug/literature" element={<Literature />} />
          <Route path="projects/:slug/queue" element={<Literature queue />} />
          <Route path="projects/:slug/notes" element={<NotesList />} />
          <Route path="projects/:slug/notes/new" element={<NoteEditor />} />
          <Route path="projects/:slug/notes/:id" element={<NoteEditor />} />
          <Route path="projects/:slug/research" element={<Research />} />
          <Route path="projects/:slug/decisions" element={<Decisions />} />
          <Route path="projects/:slug/graph" element={<Graph />} />
          <Route path="automations" element={<Automations />} />
          <Route path="library" element={<Library />} />
          <Route path="references/:id" element={<Reference />} />
          <Route path="writing" element={<WritingBoard />} />
          <Route path="manuscripts/:id" element={<ManuscriptDetail />} />
          <Route path="inbox" element={<Inbox />} />
          <Route path="prompts" element={<Prompts />} />
          <Route path="search" element={<Search />} />
          <Route path="*" element={<p className="text-sm text-stone-400">Not migrated yet — try the classic pages.</p>} />
        </Route>
      </Routes>
      </Suspense>
    </BrowserRouter>
  </QueryClientProvider>,
);
