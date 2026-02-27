export const inr = (n) => {
  const x = Number(n);
  if (!Number.isFinite(x)) return "—";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(x);
};