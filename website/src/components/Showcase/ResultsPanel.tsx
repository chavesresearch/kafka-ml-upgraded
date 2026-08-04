import type {ReactNode} from 'react';
import {useEffect, useMemo, useState} from 'react';
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {mulberry32} from './mulberry32';
import {chartColors} from '@site/src/theme/chartColors';
import type {MetricsProfile} from './caseDefinitions';
import styles from './styles.module.css';

interface Point {
  x: number;
  [metric: string]: number;
}

// Generates a plausible-looking (fake, seeded) training curve: accuracy
// rises and saturates, loss falls and saturates, with a little jitter -
// not real training output, just something that looks like one.
function buildSeries(metrics: MetricsProfile): Point[] {
  const rand = mulberry32(metrics.seed);
  const points: Point[] = [];
  for (let i = 0; i < metrics.numPoints; i++) {
    const t = metrics.numPoints <= 1 ? 1 : i / (metrics.numPoints - 1);
    const point: Point = {x: i + 1};
    for (const name of metrics.metricNames) {
      const jitter = (rand() - 0.5) * 0.06;
      if (name === 'loss') {
        point[name] = Math.max(0.02, 0.9 * Math.exp(-2.2 * t) + 0.05 + jitter);
      } else {
        point[name] = Math.min(0.99, 0.5 + 0.45 * (1 - Math.exp(-2.5 * t)) + jitter);
      }
    }
    points.push(point);
  }
  return points;
}

export default function ResultsPanel({
  metrics,
  active,
  xLabel,
}: {
  metrics: MetricsProfile;
  active: boolean;
  xLabel: string;
}): ReactNode {
  const fullSeries = useMemo(() => buildSeries(metrics), [metrics]);
  const [revealed, setRevealed] = useState(0);

  useEffect(() => {
    if (!active) {
      setRevealed(0);
      return;
    }
    setRevealed(0);
    const id = setInterval(() => {
      setRevealed((r) => {
        if (r >= fullSeries.length) return 1;
        return r + 1;
      });
    }, 500);
    return () => clearInterval(id);
  }, [active, fullSeries.length]);

  const data = fullSeries.slice(0, Math.max(revealed, 1));

  return (
    <div className={styles.resultsPanel}>
      <p className={styles.simulatedNote}>
        Simulated metrics - illustrative, not from a real training run.
      </p>
      <ResponsiveContainer width="100%" height={280}>
        <LineChart data={data} margin={{top: 8, right: 16, left: 0, bottom: 0}}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="x" label={{value: xLabel, position: 'insideBottom', offset: -4}} />
          <YAxis domain={[0, 1]} />
          <Tooltip />
          <Legend />
          {metrics.metricNames.map((name, i) => (
            <Line
              key={name}
              type="monotone"
              dataKey={name}
              stroke={chartColors[i % chartColors.length]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
