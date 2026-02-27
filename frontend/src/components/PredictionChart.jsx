import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

export default function PredictionChart({ q10, q50, q90 }) {
  const data = [
    { name: "Low (q10)", price: q10 },
    { name: "Median (q50)", price: q50 },
    { name: "High (q90)", price: q90 },
  ];

  return (
    <div className="bg-gray-800 p-4 rounded-xl shadow-lg">
      <h3 className="text-lg font-semibold mb-4 text-white">
        Prediction Distribution
      </h3>
      <ResponsiveContainer width="100%" height={250}>
        <BarChart data={data}>
          <XAxis dataKey="name" stroke="#ccc" />
          <YAxis stroke="#ccc" />
          <Tooltip />
          <Bar dataKey="price" fill="#38bdf8" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}