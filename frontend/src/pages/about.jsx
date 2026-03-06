export default function About() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-emerald-50 via-white to-amber-50 text-slate-900">
      <div className="max-w-6xl mx-auto px-4 pt-12 pb-16">
        <div className="rounded-[28px] border border-slate-200 bg-white/75 p-8 shadow-sm">
          <h1 className="text-3xl font-extrabold tracking-tight">About this Project</h1>

          <p className="mt-4 text-slate-700">
            This B.Tech major project predicts agri-horticultural commodity prices using AI/ML quantile models.
            Instead of a single number, we provide a range to communicate uncertainty and risk.
          </p>

          <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
            <Box title="Minimum Expected (q10)" text="Lower bound of expected price." />
            <Box title="Fair Market Price (q50)" text="Median / most likely price." />
            <Box title="Maximum Potential (q90)" text="Upper bound of expected price." />
          </div>

          <div className="mt-8">
            <div className="font-semibold">Tech Stack</div>
            <ul className="mt-2 text-sm text-slate-700 list-disc pl-5 space-y-1">
              <li>Backend: FastAPI</li>
              <li>ML: Quantile models (q10, q50, q90)</li>
              <li>Frontend: React + Tailwind + Recharts</li>
            </ul>
          </div>
        </div>

        <footer className="mt-10 text-center text-xs text-slate-500">
          Built with FastAPI + Quantile ML + React (Vite)
        </footer>
      </div>
    </div>
  );
}

function Box({ title, text }) {
  return (
    <div className="rounded-2xl bg-white border border-slate-200 p-5">
      <div className="font-semibold">{title}</div>
      <div className="text-sm text-slate-600 mt-2">{text}</div>
    </div>
  );
}