import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Bot, CheckSquare, Command, FolderKanban, Inbox, LayoutDashboard, Library, Moon, PenLine, Plug, Search, Sparkles, Sun, Wand2,
} from "lucide-react";
import { api, csrfToken } from "./api";
import { toSpaUrl } from "./links";
import CommandBar from "./CommandBar";
import { PetSvg } from "./PetSvg";
import { UpdaterButton } from "./UpdaterButton";

// Observatory rail: a glowing gradient bar marks the active page; the rest stays quiet.
const navCls = ({ isActive }: { isActive: boolean }) =>
  `group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm transition-colors ${
    isActive
      ? "bg-indigo-50 font-medium text-indigo-700 dark:bg-indigo-500/15 dark:text-stone-100 dark:shadow-[inset_0_0_0_1px_rgba(139,124,255,0.25)]"
      : "text-stone-600 hover:bg-stone-100 hover:text-stone-900 dark:text-stone-300 dark:hover:bg-stone-800 dark:hover:text-stone-100"
  }`;
const iconCls = "h-4 w-4 shrink-0 opacity-70 transition-opacity group-hover:opacity-100 group-[.active]:opacity-100";

function openCommandBar() {
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
}

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
      <aside className="fixed inset-y-0 left-0 z-20 flex w-60 flex-col border-r border-stone-200 bg-white px-3 py-5 dark:border-stone-800 dark:bg-stone-900">
        <div className="px-2">
          <a href="/" className="flex items-center gap-2.5">
            <span className="glow-accent inline-block h-2.5 w-2.5 rounded-full bg-gradient-to-br from-indigo-400 to-[#4ff2e0]" aria-hidden="true" />
            <span className="font-display text-xl font-bold tracking-tight text-stone-900 dark:text-stone-100">Atlas</span>
          </a>
          <button
            type="button"
            onClick={openCommandBar}
            className="mt-4 flex w-full items-center gap-2 rounded-lg border border-stone-200 bg-stone-50 px-2.5 py-1.5 text-left text-xs text-stone-500 transition-colors hover:border-indigo-300 hover:text-stone-700 dark:border-stone-700 dark:bg-stone-950/40 dark:text-stone-400 dark:hover:border-indigo-500/60 dark:hover:text-stone-200"
          >
            <Sparkles className="h-3.5 w-3.5 text-indigo-500" aria-hidden="true" />
            <span className="flex-1">Ask Atlas anything</span>
            <kbd className="inline-flex items-center gap-0.5 rounded border border-stone-200 bg-white px-1 font-sans text-[10px] text-stone-400 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-400"><Command className="h-2.5 w-2.5" aria-hidden="true" />K</kbd>
          </button>
        </div>
        <nav className="mt-5 space-y-0.5">
          <NavLink to="/" end className={navCls}><LayoutDashboard className={iconCls} aria-hidden="true" />Dashboard</NavLink>
          <NavLink to="/today" className={navCls}><CheckSquare className={iconCls} aria-hidden="true" />Today</NavLink>
          <NavLink to="/review" className={navCls}><Sparkles className={iconCls} aria-hidden="true" />Review</NavLink>
          <NavLink to="/projects" className={navCls}><FolderKanban className={iconCls} aria-hidden="true" />Projects</NavLink>
          <NavLink to="/library" className={navCls}><Library className={iconCls} aria-hidden="true" />Library</NavLink>
          <NavLink to="/writing" className={navCls}><PenLine className={iconCls} aria-hidden="true" />Writing</NavLink>
          <NavLink to="/prompts" className={navCls}><Wand2 className={iconCls} aria-hidden="true" />Prompts</NavLink>
          <NavLink to="/inbox" className={navCls}><Inbox className={iconCls} aria-hidden="true" />Inbox</NavLink>
          <NavLink to="/search" className={navCls}><Search className={iconCls} aria-hidden="true" />Search</NavLink>
        </nav>
        <div className="mt-auto border-t border-stone-100 px-1 pt-4 text-xs text-stone-400 dark:border-stone-800">
          {pet && (
            <a href="/pet/" title={`${pet.name} is ${pet.mood}`} className="group mb-3 block">
              <span
                key={bubble}
                className={`pet-bubble relative mb-1.5 block rounded-lg border px-2.5 py-1.5 text-[10px] leading-snug calm:hidden ${
                  reaction
                    ? "border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-200"
                    : "border-stone-200 bg-white text-stone-500 dark:border-stone-800 dark:bg-stone-950/40 dark:text-stone-300"
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
              <span className="flex items-center gap-2 rounded-lg border border-stone-100 bg-stone-50 px-2 py-1.5 group-hover:border-stone-200 dark:border-stone-800 dark:bg-stone-950/40 dark:group-hover:border-stone-700">
                <span className={reaction ? "pet-hop inline-block" : "inline-block"}>
                  <PetSvg stage={pet.stage} mood={pet.mood} size={28} />
                </span>
                <span className="min-w-0">
                  <span className="block truncate font-medium text-stone-600 dark:text-stone-200">{pet.name}</span>
                  <span className="block truncate text-[10px] text-stone-400">
                    {pet.mood === "sleeping" ? "💤 " : ""}{pet.mood}
                  </span>
                </span>
              </span>
            </a>
          )}
          <NavLink to="/automations" className="mb-1 flex items-center gap-2 rounded-md px-1.5 py-1 transition-colors hover:text-stone-700 dark:hover:text-stone-200"><Bot className="h-3.5 w-3.5" aria-hidden="true" />Automations</NavLink>
          <a href="/connect/claude/" className="mb-1 flex items-center gap-2 rounded-md px-1.5 py-1 transition-colors hover:text-stone-700 dark:hover:text-stone-200"><Plug className="h-3.5 w-3.5" aria-hidden="true" />Connect Claude Code</a>
          <UpdaterButton />
          <button
            type="button"
            onClick={() => (window as unknown as { __toggleTheme?: () => void }).__toggleTheme?.()}
            className="mb-1 flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left transition-colors hover:text-stone-700 dark:hover:text-stone-200"
          >
            <Moon className="h-3.5 w-3.5 dark:hidden" aria-hidden="true" /><span className="dark:hidden">Observatory (dark)</span>
            <Sun className="hidden h-3.5 w-3.5 dark:inline" aria-hidden="true" /><span className="hidden dark:inline">Paper (light)</span>
          </button>
          <a href="/classic/" className="block rounded-md px-1.5 py-1 transition-colors hover:text-stone-700 dark:hover:text-stone-200">← Classic Atlas</a>
        </div>
      </aside>
      <main className="ml-60 min-w-0 flex-1">
        <div className="mx-auto max-w-screen-2xl px-8 py-7">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
