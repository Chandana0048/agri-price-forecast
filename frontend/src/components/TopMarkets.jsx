import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { inr } from "../lib/format";
import {
  ResponsiveContainer,
  BarChart, Bar, XAxis, YAxis, Tooltip,
} from "recharts";

export default function TopMarkets({ state, commodity }) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!state || !commodity) return;
    (async () => {
      setLoading(true);
      try {
        const res = await api.get("/meta/top-markets", {
          params: { state, commodity, k: 10 },
        });
        setItems(res.data.items || []);
      } finally {
        setLoading(false);
      }
    })();
  }, [state, commodity]);

  return (
    <div className="rounded-2xl bg-slate-900/40 border border-slate-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-lg font-semibold">Top Markets</h3>
        <span className="text-xs text-slate-400">
          {loading ? "Loading…" : "Based on train data"}
        </span>
      </div>

      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={items}>
            <XAxis dataKey="market" tick={{ fontSize: 10 }} interval={0} angle={-25} textAnchor="end" height={60} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v, name) => name === "avg_price" ? inr(v) : v} />
            <Bar dataKey="avg_price" />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div className="mt-3 grid gap-2">
        {items.slice(0, 5).map((x) => (
          <div key={x.market} className="flex items-center justify-between text-sm bg-slate-950/40 rounded-xl px-3 py-2 border border-slate-800">
            <div className="font-medium">{x.market}</div>
            <div className="text-slate-300">{inr(x.avg_price)}</div>
          </div>
        ))}
      </div>
    </div>
  );
}