import { useQuery } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";
import { api } from "./api";
import CommandBar from "./CommandBar";

const navCls = ({ isActive }: { isActive: boolean }) =>
  `block rounded px-2 py-1.5 ${isActive ? "bg-stone-100 font-medium" : "text-stone-600 hover:bg-stone-50"}`;

/** SPA chrome mirroring the classic sidebar; unmigrated sections link to server pages. */
export default function Layout() {
  const { data: pet } = useQuery({
    queryKey: ["pet"],
    queryFn: () => api<{ name: string; emoji: string; mood: string; speech: string }>("/pet/"),
    staleTime: 300_000,
  });
  return (
    <div className="flex h-full">
      <CommandBar />
      <aside className="fixed inset-y-0 left-0 flex w-56 flex-col border-r border-stone-200 bg-white px-4 py-6">
        <a href="/" className="mb-1 text-lg font-semibold tracking-tight">Atlas</a>
        <p className="mb-4 text-[10px] uppercase tracking-wide text-stone-400">⌘K for anything</p>
        <nav className="space-y-1 text-sm">
          <NavLink to="/" end className={navCls}>Dashboard</NavLink>
          <NavLink to="/projects" className={navCls}>Projects</NavLink>
          {/* not yet migrated — classic pages */}
          <NavLink to="/library" className={navCls}>Library</NavLink>
          <NavLink to="/writing" className={navCls}>Writing</NavLink>
          <NavLink to="/prompts" className={navCls}>Prompts</NavLink>
          <NavLink to="/inbox" className={navCls}>Inbox</NavLink>
          <NavLink to="/search" className={navCls}>Search</NavLink>
        </nav>
        <div className="mt-auto pt-6 text-xs text-stone-400">
          {pet && (
            <a href="/pet/" title={`${pet.name} is ${pet.mood} — ${pet.speech}`}
               className="mb-3 flex items-center gap-2 rounded border border-stone-100 bg-stone-50 px-2 py-1.5 hover:border-stone-200">
              <span className="pet-idle inline-block text-xl">{pet.emoji}</span>
              <span className="min-w-0">
                <span className="block truncate font-medium text-stone-600">{pet.name}</span>
                <span className="block truncate text-[10px] italic text-stone-400">“{pet.speech}”</span>
              </span>
            </a>
          )}
          <NavLink to="/automations" className="mb-2 block hover:text-stone-600">Automations</NavLink>
          <a href="/classic/" className="hover:text-stone-600">← Classic Atlas</a>
        </div>
      </aside>
      <main className="ml-56 min-w-0 flex-1">
        <div className="mx-auto max-w-5xl px-8 py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
