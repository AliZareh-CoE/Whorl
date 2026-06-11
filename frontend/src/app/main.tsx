import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./Layout";
import Dashboard from "./pages/Dashboard";
import Documents from "./pages/Documents";
import Inbox from "./pages/Inbox";
import Prompts from "./pages/Prompts";
import Automations from "./pages/Automations";
import Decisions from "./pages/Decisions";
import Graph from "./pages/Graph";
import Research from "./pages/Research";
import Search from "./pages/Search";
import Library from "./pages/Library";
import { NoteEditor, NotesList } from "./pages/Notes";
import Literature from "./pages/Literature";
import Plan from "./pages/Plan";
import ProjectOverview from "./pages/ProjectOverview";
import Projects from "./pages/Projects";
import { ManuscriptDetail, WritingBoard } from "./pages/Writing";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter basename="/">
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="projects" element={<Projects />} />
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
          <Route path="writing" element={<WritingBoard />} />
          <Route path="manuscripts/:id" element={<ManuscriptDetail />} />
          <Route path="inbox" element={<Inbox />} />
          <Route path="prompts" element={<Prompts />} />
          <Route path="search" element={<Search />} />
          <Route path="*" element={<p className="text-sm text-stone-400">Not migrated yet — try the classic pages.</p>} />
        </Route>
      </Routes>
    </BrowserRouter>
  </QueryClientProvider>,
);
