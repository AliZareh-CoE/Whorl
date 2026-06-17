import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { api, csrfToken } from "./api";
import { toSpaUrl } from "./links";
import CommandBar from "./CommandBar";
import { PetSvg } from "./PetSvg";
import { UpdaterButton } from "./UpdaterButton";

const navCls = ({ isActive }: { isActive: boolean }) =>
  `relative block rounded-md px-3 py-1.5 transition-colors ${
    isActive
      ? "bg-indigo-50 font-medium text-indigo-700 before:absolute before:inset-y-1 before:left-0 before:w-0.5 before:rounded-full before:bg-indigo-600 dark:bg-indigo-500/10 dark:text-indigo-300"
      : "text-stone-500 hover:bg-stone-50 hover:text-stone-900 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-100"
  }`;

/** SPA chrome mirroring the classic sidebar; unmigrated sections link to server pages. */
export default function Layout() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  // Intercept plain <a> clicks to classic URLs that have an SPA page — no full reloads
  // inside the app (owner feedback, cycle 69). True classic-only URLs still navigate.
  // #87: warm the ⌘K assistant index so even the first open is instant
  useEffect(() => {
    queryClient.prefetchQuery({
      queryKey: ["assistant-context", null],
      queryFn: () =>
        fetch("/assistant/context/?path=/", { credentials: "same-origin" }).then((r) => r.json()),
      staleTime: 60_000,
    });
  }, [queryClient]);

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const anchor = (e.target as HTMLElement).closest("a");
      if (!anchor || anchor.target || anchor.hasAttribute("download")) return;
      const href = anchor.getAttribute("href");
      if (!href || !href.startsWith("/")) return;
      const { to, spa } = toSpaUrl(href);
      if (spa) {
        e.preventDefault();
        navigate(to);
      }
    }
    document.addEventListener("click", onClick);
    return () => document.removeEventListener("click", onClick);
  }, [navigate]);
  const { data: pet } = useQuery({
    queryKey: ["pet"],
    queryFn: () =>
      api<{
        name: string;
        emoji: string;
        stage: string;
        mood: string;
        speech: string;
        speech_lines?: string[];
        reactions?: Record<string, string>;
      }>("/pet/"),
    staleTime: 300_000,
  });

  // Buddy-style life (Owner idea #23): rotate observation bubbles, hop on real events.
  const [lineIdx, setLineIdx] = useState(0);
  const [reaction, setReaction] = useState<string | null>(null);
  useEffect(() => {
    const t = setInterval(() => setLineIdx((i) => i + 1), 20_000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => {
    function onPet(e: Event) {
      const kind = (e as CustomEvent).detail?.kind as string;
      const line = pet?.reactions?.[kind];
      if (!line) return;
      setReaction(line);
      setTimeout(() => setReaction(null), 4000);
    }
    window.addEventListener("atlas-pet", onPet);
    return () => window.removeEventListener("atlas-pet", onPet);
  }, [pet]);
  const lines = pet?.speech_lines?.length ? pet.speech_lines : pet ? [pet.speech] : [];
  const bubble = reaction ?? (lines.length ? lines[lineIdx % lines.length] : "");
  const [speaking, setSpeaking] = useState(false);
  async function speakBubble(e: React.MouseEvent) {
    // Owner idea #29: opt-in voice via the local Piper /tts/ — never auto-plays.
    e.preventDefault();
    e.stopPropagation();
    if (speaking || !bubble) return;
    setSpeaking(true);
    try {
      const res = await fetch("/tts/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken() },
        body: new URLSearchParams({ text: bubble }),
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error();
      const audio = new Audio(URL.createObjectURL(await res.blob()));
      audio.addEventListener("ended", () => setSpeaking(false));
      audio.addEventListener("error", () => setSpeaking(false));
      await audio.play();
    } catch {
      setSpeaking(false);
    }
  }

  return (
    <div className="flex h-full">
      <CommandBar />
      <aside className="fixed inset-y-0 left-0 flex w-56 flex-col border-r border-stone-200 bg-white px-3 py-6 dark:border-stone-800 dark:bg-stone-900">
        <div className="px-2">
          <a href="/" className="block text-lg font-semibold tracking-tight text-stone-900 dark:text-stone-100">Atlas</a>
          <p className="mt-0.5 text-[10px] uppercase tracking-wide text-stone-400 dark:text-stone-500">⌘K for anything</p>
        </div>
        <nav className="mt-6 space-y-0.5 text-sm">
          <NavLink to="/" end className={navCls}>Dashboard</NavLink>
          <NavLink to="/review" className={navCls}>Review</NavLink>
          <NavLink to="/projects" className={navCls}>Projects</NavLink>
          {/* not yet migrated — classic pages */}
          <NavLink to="/library" className={navCls}>Library</NavLink>
          <NavLink to="/writing" className={navCls}>Writing</NavLink>
          <NavLink to="/prompts" className={navCls}>Prompts</NavLink>
          <NavLink to="/inbox" className={navCls}>Inbox</NavLink>
          <NavLink to="/search" className={navCls}>Search</NavLink>
        </nav>
        <div className="mt-auto border-t border-stone-100 px-2 pt-4 text-xs text-stone-400">
          {pet && (
            <a href="/pet/" title={`${pet.name} is ${pet.mood}`} className="group mb-3 block">
              <span
                key={bubble}
                className={`pet-bubble relative mb-1.5 block rounded-lg border px-2.5 py-1.5 text-[10px] leading-snug ${
                  reaction
                    ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                    : "border-stone-200 bg-white text-stone-500"
                }`}
              >
                {bubble}
                <button
                  type="button"
                  onClick={speakBubble}
                  title="Hear it (local TTS)"
                  className="ml-1 align-middle opacity-50 hover:opacity-100 disabled:opacity-30"
                  disabled={speaking}
                >
                  {speaking ? "…" : "🔊"}
                </button>
              </span>
              <span className="flex items-center gap-2 rounded border border-stone-100 bg-stone-50 px-2 py-1.5 group-hover:border-stone-200">
                <span className={reaction ? "pet-hop inline-block" : "inline-block"}>
                  <PetSvg stage={pet.stage} mood={pet.mood} size={28} />
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-medium text-stone-600">{pet.name}</span>
                  <span className="block truncate text-[10px] text-stone-400">
                    {pet.mood === "sleeping" ? "💤 " : ""}{pet.mood}
                  </span>
                </span>
              </span>
            </a>
          )}
          <NavLink to="/automations" className="mb-2 block rounded px-1 py-0.5 transition-colors hover:text-stone-700 dark:hover:text-stone-200">Automations</NavLink>
          <UpdaterButton />
          <button
            type="button"
            onClick={() => (window as unknown as { __toggleTheme?: () => void }).__toggleTheme?.()}
            className="mb-2 block w-full rounded px-1 py-0.5 text-left transition-colors hover:text-stone-700 dark:hover:text-stone-200"
          >
            <span className="dark:hidden">Dark mode 🌙</span>
            <span className="hidden dark:inline">Light mode ☀</span>
          </button>
          <a href="/classic/" className="block rounded px-1 py-0.5 transition-colors hover:text-stone-700 dark:hover:text-stone-200">← Classic Atlas</a>
        </div>
      </aside>
      <main className="ml-56 min-w-0 flex-1">
        <div className="mx-auto max-w-screen-2xl px-6 py-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
