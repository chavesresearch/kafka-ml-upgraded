import {useEffect, useMemo, useRef, useState, type ReactNode} from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
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

const DEVICE_NAMES = ['Device 1', 'Device 2', 'Device 3', 'Device 4'];

interface Point {
  x: number;
  value: number;
  device?: number;
}

// A plausible (fake, seeded) accuracy curve: rises and saturates with
// jitter. `federated` curves get extra noise and the occasional dip -
// real async FL can regress a round when a *stale* device's update
// (trained against an older global model version) gets merged in, so a
// perfectly smooth line would actually be less honest here than a
// slightly bumpy one.
function nextValue(rng: () => number, t: number, federated: boolean): number {
  const base = Math.min(0.97, 0.5 + 0.42 * (1 - Math.exp(-2.3 * t)));
  const jitter = (rng() - 0.5) * (federated ? 0.1 : 0.05);
  const staleDip = federated && rng() < 0.18 ? -(0.05 + rng() * 0.06) : 0;
  return Math.max(0.05, Math.min(0.99, base + jitter + staleDip));
}

function buildBoundedSeries(seed: number, n: number): Point[] {
  const rng = mulberry32(seed);
  return Array.from({length: n}, (_, i) => ({
    x: i + 1,
    value: nextValue(rng, n <= 1 ? 1 : i / (n - 1), false),
  }));
}

function buildFederatedSeries(seed: number, n: number): Point[] {
  const rng = mulberry32(seed);
  return Array.from({length: n}, (_, i) => ({
    x: i + 1,
    value: nextValue(rng, n <= 1 ? 1 : i / (n - 1), true),
    device: Math.floor(rng() * DEVICE_NAMES.length),
  }));
}

function buildRewardSeries(points: Point[]): {device: string; tokens: number}[] {
  const totals = new Array(DEVICE_NAMES.length).fill(0);
  for (const p of points) {
    if (p.device !== undefined) totals[p.device] += 15 + Math.round((p.value % 1) * 20);
  }
  return DEVICE_NAMES.map((name, i) => ({device: name, tokens: totals[i]}));
}

function MiniChart({data, color, label}: {data: Point[]; color: string; label: string}): ReactNode {
  return (
    <div>
      <p className={styles.diagramSubcaption}>{label}</p>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{top: 4, right: 8, left: -20, bottom: 0}}>
          <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
          <XAxis dataKey="x" tick={{fontSize: 11}} />
          <YAxis domain={[0, 1]} tick={{fontSize: 11}} />
          <Tooltip />
          <Line type="monotone" dataKey="value" stroke={color} strokeWidth={2} dot={false} isAnimationActive={false} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export default function ResultsPanel({
  metrics,
  active,
}: {
  metrics: MetricsProfile;
  active: boolean;
}): ReactNode {
  const {kind, seed, xLabel, distributed, rewards, numPoints} = metrics;

  const boundedFull = useMemo(() => buildBoundedSeries(seed, Math.max(numPoints, 1)), [seed, numPoints]);
  const boundedFullB = useMemo(() => buildBoundedSeries(seed + 1000, Math.max(numPoints, 1)), [seed, numPoints]);
  const federatedFull = useMemo(
    () => (kind === 'federated' ? buildFederatedSeries(seed, numPoints) : []),
    [kind, seed, numPoints],
  );
  const federatedFullB = useMemo(
    () => (kind === 'federated' && distributed ? buildFederatedSeries(seed + 1000, numPoints) : []),
    [kind, seed, numPoints, distributed],
  );

  const [revealed, setRevealed] = useState(0);
  const [streamData, setStreamData] = useState<Point[]>([]);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const batchRef = useRef(0);
  const lastValueRef = useRef(0.5);
  const streamRng = useRef(mulberry32(seed));

  useEffect(() => {
    if (!active) {
      setRevealed(0);
      setStreamData([]);
      return;
    }
    setRevealed(0);
    setStreamData([]);
    batchRef.current = 0;
    lastValueRef.current = 0.45 + streamRng.current() * 0.1;

    const rng = mulberry32(seed + 7);
    let cancelled = false;
    let i = 0;

    function scheduleStream() {
      timeoutRef.current = setTimeout(() => {
        if (cancelled) return;
        batchRef.current += 1;
        const target = 0.93;
        const next = Math.max(
          0.05,
          Math.min(0.99, lastValueRef.current + (target - lastValueRef.current) * 0.12 + (rng() - 0.5) * 0.05),
        );
        lastValueRef.current = next;
        setStreamData((prev) => [...prev.slice(-13), {x: batchRef.current, value: next}]);
        scheduleStream();
      }, 550);
    }

    function step() {
      if (cancelled) return;
      i += 1;
      setRevealed(i);
      if (i >= Math.max(numPoints, 1)) {
        timeoutRef.current = setTimeout(() => {
          if (cancelled) return;
          i = 0;
          setRevealed(0);
          step();
        }, 2600);
        return;
      }
      const delay = kind === 'federated' ? 500 + rng() * 1300 : 500;
      timeoutRef.current = setTimeout(step, delay);
    }

    if (kind === 'streaming') {
      scheduleStream();
    } else {
      timeoutRef.current = setTimeout(step, 400);
    }

    return () => {
      cancelled = true;
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, kind, seed, numPoints]);

  const boundedData = boundedFull.slice(0, Math.max(revealed, 1));
  const boundedDataB = boundedFullB.slice(0, Math.max(revealed, 1));
  const federatedData = federatedFull.slice(0, Math.max(revealed, 1));
  const federatedDataB = federatedFullB.slice(0, Math.max(revealed, 1));

  const lastFederatedPoint = federatedData[federatedData.length - 1];
  const rewardData = kind === 'federated' && rewards ? buildRewardSeries(federatedData) : [];

  return (
    <div className={styles.resultsPanel}>
      <div style={{display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.5rem'}}>
        {kind === 'streaming' && (
          <span className={styles.asyncNote}>🔴 Live - never stops, no fixed dataset size</span>
        )}
        {kind === 'federated' && (
          <span className={styles.asyncNote}>⏱️ Rounds land whenever a device finishes - not on a fixed clock</span>
        )}
        {kind === 'bounded' && <span className={styles.asyncNote}>🔒 One bounded training run</span>}
      </div>

      {kind === 'bounded' && !distributed && (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={boundedData} margin={{top: 8, right: 16, left: 0, bottom: 0}}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis dataKey="x" label={{value: xLabel, position: 'insideBottom', offset: -4}} />
            <YAxis domain={[0, 1]} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="value"
              name="accuracy"
              stroke={chartColors[0]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {kind === 'bounded' && distributed && (
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem'}}>
          <MiniChart data={boundedData} color={chartColors[0]} label="Edge submodel - accuracy" />
          <MiniChart data={boundedDataB} color={chartColors[1]} label="Cloud submodel - accuracy" />
        </div>
      )}

      {kind === 'streaming' && !distributed && (
        <ResponsiveContainer width="100%" height={280}>
          <LineChart data={streamData} margin={{top: 8, right: 16, left: 0, bottom: 0}}>
            <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
            <XAxis dataKey="x" label={{value: xLabel, position: 'insideBottom', offset: -4}} />
            <YAxis domain={[0, 1]} />
            <Tooltip />
            <Line
              type="monotone"
              dataKey="value"
              name="accuracy"
              stroke={chartColors[0]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      )}

      {kind === 'streaming' && distributed && (
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem'}}>
          <MiniChart data={streamData} color={chartColors[0]} label="Edge submodel - accuracy (live)" />
          <MiniChart
            data={streamData.map((p) => ({...p, value: Math.max(0, Math.min(1, p.value * 0.94))}))}
            color={chartColors[1]}
            label="Cloud submodel - accuracy (live)"
          />
        </div>
      )}

      {kind === 'federated' && (
        <>
          <ResponsiveContainer width="100%" height={distributed ? 200 : 240}>
            <LineChart data={federatedData} margin={{top: 8, right: 16, left: 0, bottom: 0}}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis dataKey="x" label={{value: xLabel, position: 'insideBottom', offset: -4}} />
              <YAxis domain={[0, 1]} />
              <Tooltip
                formatter={(value) => (typeof value === 'number' ? value.toFixed(3) : value)}
                labelFormatter={(x) => `Round ${x}`}
              />
              <Line
                type="monotone"
                dataKey="value"
                name={distributed ? 'edge accuracy (global)' : 'global accuracy'}
                stroke={chartColors[0]}
                strokeWidth={2}
                dot={{r: 3}}
                isAnimationActive={false}
              />
              {distributed && (
                <Line
                  type="monotone"
                  data={federatedDataB}
                  dataKey="value"
                  name="cloud accuracy (global)"
                  stroke={chartColors[1]}
                  strokeWidth={2}
                  dot={{r: 3}}
                  isAnimationActive={false}
                />
              )}
            </LineChart>
          </ResponsiveContainer>
          <p className={styles.diagramSubcaption}>
            {lastFederatedPoint
              ? `Round ${lastFederatedPoint.x}: merged from ${DEVICE_NAMES[lastFederatedPoint.device ?? 0]}`
              : 'Waiting for the first device to report...'}
          </p>

          {rewards && (
            <div style={{marginTop: '0.75rem'}}>
              <p className={styles.diagramSubcaption}>Cumulative ERC-20 (KML) rewards paid, by device</p>
              <ResponsiveContainer width="100%" height={140}>
                <BarChart data={rewardData} margin={{top: 4, right: 16, left: 0, bottom: 0}}>
                  <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                  <XAxis dataKey="device" tick={{fontSize: 11}} />
                  <YAxis tick={{fontSize: 11}} />
                  <Tooltip />
                  <Bar
                    dataKey="tokens"
                    fill={chartColors[2]}
                    isAnimationActive={false}
                    radius={[4, 4, 0, 0]}
                    maxBarSize={56}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}

      <p className={styles.simulatedNote}>Simulated metrics - illustrative, not from a real training run.</p>
    </div>
  );
}
