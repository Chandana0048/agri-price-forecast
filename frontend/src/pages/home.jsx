import { Link } from "react-router-dom";

export default function Home() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-50 via-white to-amber-50 text-slate-900">
      <header className="sticky top-0 z-40 bg-white/70 backdrop-blur border-b border-slate-200">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-2xl bg-emerald-500/10 border border-emerald-200 grid place-items-center">
              <span className="font-bold text-emerald-700">₹</span>
            </div>
            <div>
              <div className="font-semibold leading-tight">Agri Price Forecast</div>
              <div className="text-xs text-slate-600">AI/ML based price intelligence</div>
            </div>
          </div>

          <nav className="flex items-center gap-2 text-sm">
            <Link className="px-3 py-1 rounded-full hover:bg-slate-100" to="/">Home</Link>
            <Link className="px-3 py-1 rounded-full hover:bg-slate-100" to="/predict">Predict</Link>
            <Link className="px-3 py-1 rounded-full hover:bg-slate-100" to="/about">About</Link>
          </nav>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 pt-14 pb-16">
        <div className="rounded-[28px] border border-slate-200 bg-white/75 backdrop-blur shadow-sm overflow-hidden">
          <div className="px-6 py-12 md:px-10 bg-gradient-to-r from-emerald-100/60 via-white to-amber-100/50">
            <h1 className="text-3xl md:text-5xl font-extrabold tracking-tight">
              Predict commodity prices with risk awareness.
            </h1>
            <p className="mt-4 text-base md:text-lg text-slate-700 max-w-2xl">
              A modern agri-fintech style experience: clean inputs, meaningful outputs, and confidence-driven insights.
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                to="/predict"
                className="px-5 py-2.5 rounded-2xl font-semibold bg-emerald-600 hover:bg-emerald-700 text-white shadow-sm"
              >
                Start Predicting
              </Link>
              <Link
                to="/about"
                className="px-5 py-2.5 rounded-2xl font-semibold border border-slate-200 hover:bg-white text-slate-800"
              >
                Learn More
              </Link>
            </div>

            <div className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card title="Quantile Forecasting" text="Gives a price band (min–fair–max), not a single blind number." />
              <Card title="Confidence Meter" text="Tells you how reliable the prediction is based on data match quality." />
              <Card title="Market Insights" text="Shows top markets for quick comparison (based on historical averages)." />
            </div>
          </div>
        </div>

        <footer className="mt-10 text-center text-xs text-slate-500">
          Built with FastAPI + Quantile ML + React (Vite)
        </footer>
      </main>
    </div>
  );
}

function Card({ title, text }) {
  return (
    <div className="rounded-2xl bg-white/70 border border-slate-200 p-5 hover:shadow-sm transition">
      <div className="font-semibold">{title}</div>
      <div className="text-sm text-slate-600 mt-2">{text}</div>
    </div>
  );
}