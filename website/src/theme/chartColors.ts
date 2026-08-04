// Kafka-ML chart palette, copied by value from frontend/src/index.css's
// --chart-1..5 tokens - kept as plain oklch strings here (not read from the
// CSS custom properties in custom.css) because recharts renders its own
// inline SVG `stroke`/`fill` attributes, which don't reliably resolve
// `var(--kml-chart-N)` across browsers the way a CSS property would.
export const chartColors = [
  'oklch(0.585 0.233 277.117)',
  'oklch(0.696 0.17 162.48)',
  'oklch(0.769 0.188 70.08)',
  'oklch(0.645 0.246 16.44)',
  'oklch(0.6 0.118 184.7)',
] as const;
