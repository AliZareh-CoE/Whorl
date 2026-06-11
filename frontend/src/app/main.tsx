import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./Layout";
import Dashboard from "./pages/Dashboard";
import Documents from "./pages/Documents";
import Plan from "./pages/Plan";
import ProjectOverview from "./pages/ProjectOverview";
import Projects from "./pages/Projects";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={queryClient}>
    <BrowserRouter basename="/app">
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="projects" element={<Projects />} />
          <Route path="projects/:slug" element={<ProjectOverview />} />
          <Route path="projects/:slug/plan" element={<Plan />} />
          <Route path="projects/:slug/documents" element={<Documents />} />
          <Route path="*" element={<p className="text-sm text-stone-400">Not migrated yet — try the classic pages.</p>} />
        </Route>
      </Routes>
    </BrowserRouter>
  </QueryClientProvider>,
);
