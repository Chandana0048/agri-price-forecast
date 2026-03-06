import { Outlet, NavLink } from "react-router-dom";
import { useEffect, useState } from "react";
import { api } from "../api";

function Pill({ children, tone = "neutral" }) {
  const cls =
    tone === "good"
      ? "bg-emerald-500/15 border-emerald-500/25 text-emerald-800"
      : tone === "bad"
      ? "bg-rose-500/15 border-rose-500/25 text-rose-900"
      : "bg-slate-500/10 border-slate-400/25 text-slate-700";
  return <span className={`text-xs border px-3 py-1 rounded-full ${cls}`}>{children}</span>;
}

export default function SiteLayout() {
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "soft");
  const soft = theme === "soft";

  const [apiLive, setApiLive] = useState(false);

  useEffect(() => {
    localStorage.setItem("theme", theme);
  }, [theme]);

  useEffect(() => {
    (async () => {
      try {
        await api.get("/health");
        setApiLive(true);
      } catch {
        setApiLive(false);
      }
    })();
  }, []);

  const linkCls = ({ isActive }) =>
    [
      "px-3 py-2 rounded-xl text-sm transition",
      isActive
        ? soft
          ? "bg-emerald-600 text-white"
          : "bg-sky-500 text-slate-950"
        : soft
        ? "text-slate-700 hover:bg-white"
        : "text-slate-200 hover:bg-slate-900/40",
    ].join(" ");

  return (
    <div className={soft ? "min-h-screen bg-gradient-to-b from-emerald-50 via-white to-amber-50 text-slate-900" : "min-h-screen bg-slate-950 text-white"}>
      {/* NAV */}
      <header className={soft ? "sticky top-0 z-40 bg-white/70 backdrop-blur border-b border-slate-200" : "sticky top-0 z-40 bg-slate-950/70 backdrop-blur border-b border-slate-800"}>
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={soft ? "h-10 w-10 rounded-2xl bg-emerald-500/10 border border-emerald-200 grid place-items-center" : "h-10 w-10 rounded-2xl bg-sky-500/20 border border-sky-400/30 grid place-items-center"}>
              <span className={soft ? "font-bold text-emerald-700" : "font-bold text-sky-200"}>₹</span>
            </div>
            <div>
              <div className="font-semibold leading-tight">Agri Price Forecast</div>
              <div className={soft ? "text-xs text-slate-600" : "text-xs text-slate-400"}>
                AI-driven market intelligence
              </div>
            </div>
          </div>

          <nav className="hidden md:flex items-center gap-2">
            <NavLink to="/" className={linkCls}>Home</NavLink>
            <NavLink to="/predict" className={linkCls}>Predict</NavLink>
            <NavLink to="/about" className={linkCls}>About</NavLink>
          </nav>

          <div className="flex items-center gap-2">
            <Pill tone="neutral">Quantile ML</Pill>
            <Pill tone={apiLive ? "good" : "bad"}>{apiLive ? "API Live" : "API Down"}</Pill>

            <button
              onClick={() => setTheme(soft ? "dark" : "soft")}
              className={soft ? "text-xs px-3 py-1 rounded-full border border-slate-200 hover:bg-white" : "text-xs px-3 py-1 rounded-full border border-slate-700 hover:bg-slate-900/40"}
            >
              {soft ? "Soft Mode" : "Dark Mode"}
            </button>
          </div>
        </div>
      </header>

      {/* MOBILE NAV */}
      <div className="md:hidden max-w-6xl mx-auto px-4 pt-3 flex gap-2">
        <NavLink to="/" className={linkCls}>Home</NavLink>
        <NavLink to="/predict" className={linkCls}>Predict</NavLink>
        <NavLink to="/about" className={linkCls}>About</NavLink>
      </div>

      <Outlet context={{ theme, setTheme }} />

      <footer className="max-w-6xl mx-auto px-4 py-10 text-center text-xs text-slate-500">
        Built with FastAPI + Quantile ML + React (Vite)
      </footer>
    </div>
  );
}