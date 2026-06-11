import { NavLink, Outlet } from "react-router-dom";

const navCls = ({ isActive }: { isActive: boolean }) =>
  `block rounded px-2 py-1.5 ${isActive ? "bg-stone-100 font-medium" : "text-stone-600 hover:bg-stone-50"}`;

/** SPA chrome mirroring the classic sidebar; unmigrated sections link to server pages. */
export default function Layout() {
  return (
    <div className="flex h-full">
      <aside className="fixed inset-y-0 left-0 flex w-56 flex-col border-r border-stone-200 bg-white px-4 py-6">
        <a href="/app/" className="mb-1 text-lg font-semibold tracking-tight">Atlas</a>
        <p className="mb-4 text-[10px] uppercase tracking-wide text-indigo-500">React preview</p>
        <nav className="space-y-1 text-sm">
          <NavLink to="/" end className={navCls}>Dashboard</NavLink>
          <NavLink to="/projects" className={navCls}>Projects</NavLink>
          {/* not yet migrated — classic pages */}
          <NavLink to="/library" className={navCls}>Library</NavLink>
          <a href="/writing/" className="block rounded px-2 py-1.5 text-stone-600 hover:bg-stone-50">Writing ↗</a>
          <a href="/prompts/" className="block rounded px-2 py-1.5 text-stone-600 hover:bg-stone-50">Prompts ↗</a>
          <a href="/inbox/" className="block rounded px-2 py-1.5 text-stone-600 hover:bg-stone-50">Inbox ↗</a>
        </nav>
        <div className="mt-auto pt-6 text-xs text-stone-400">
          <a href="/" className="hover:text-stone-600">← Classic Atlas</a>
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
