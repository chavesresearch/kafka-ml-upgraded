import {useEffect, useRef, useState} from 'react';

export type DevicePhase = 'training' | 'sending';

export interface DeviceState {
  phase: DevicePhase;
  progress: number; // 0..1 within the current phase
  completions: number; // how many updates this device has landed so far
}

export interface AsyncFederationState {
  devices: DeviceState[];
  /** Bumps by 1 every time *any* device's update lands - irregularly,
   * not on a fixed schedule, since devices finish independently. */
  cloudVersion: number;
  /** True for a brief moment right after a version bump, for a flash/glow. */
  cloudPulse: boolean;
  /** Index of the device that most recently landed an update, or null. */
  lastSender: number | null;
}

const TRAIN_FRACTION = 0.7;
const TICK_MS = 100;

/**
 * Drives Kafka-ML's real federated aggregation behavior: `backend`'s
 * EdgeBasedTraining loop (model_training/tensorflow/edgeBasedTraining.py)
 * sends the global model once per round, then blocks on
 * `consumer.poll()` until *the first* device response arrives, merges
 * just that one update in (pairwise FedAvg against the current global
 * model), and immediately starts the next round - it never waits for
 * every device. CASE=9's blockchain variant does the identical thing
 * against `elements_to_aggregate() < 1` instead of a Kafka poll. Devices
 * that finish later simply get folded in on a subsequent round, against
 * whatever the global model has become by then.
 *
 * Modeled here with each device on its own period (deliberately not
 * synchronized - different devices "finish" at different real-world
 * times, exactly like real heterogeneous edge hardware would), split
 * into a `training` phase and a brief `sending` phase. Whenever *any*
 * device crosses into `sending`, the shared cloud state bumps its
 * version once - independent of what every other device is doing.
 */
export function useAsyncFederation(active: boolean, count: number): AsyncFederationState {
  const periods = useRef<number[]>(
    Array.from({length: count}, (_, i) => 2600 + i * 900 + ((i * 37) % 5) * 130),
  );
  const prevPhase = useRef<DevicePhase[]>(Array(count).fill('training'));
  const completions = useRef<number[]>(Array(count).fill(0));
  const startedAt = useRef<number>(Date.now());
  const pulseTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [devices, setDevices] = useState<DeviceState[]>(() =>
    Array.from({length: count}, () => ({phase: 'training' as DevicePhase, progress: 0, completions: 0})),
  );
  const [cloudVersion, setCloudVersion] = useState(0);
  const [cloudPulse, setCloudPulse] = useState(false);
  const [lastSender, setLastSender] = useState<number | null>(null);

  useEffect(() => {
    if (!active) return;
    startedAt.current = Date.now();
    prevPhase.current = Array(count).fill('training');
    completions.current = Array(count).fill(0);
    setCloudVersion(0);
    setLastSender(null);

    const id = setInterval(() => {
      const elapsed = Date.now() - startedAt.current;
      let bumped = false;
      let sender: number | null = null;

      const next = periods.current.map((period, i) => {
        const trainMs = period * TRAIN_FRACTION;
        const t = elapsed % period;
        const phase: DevicePhase = t < trainMs ? 'training' : 'sending';
        const progress = phase === 'training' ? t / trainMs : (t - trainMs) / (period - trainMs);

        if (prevPhase.current[i] === 'training' && phase === 'sending') {
          bumped = true;
          sender = i;
          completions.current[i] += 1;
        }
        prevPhase.current[i] = phase;
        return {phase, progress, completions: completions.current[i]};
      });

      setDevices(next);
      if (bumped) {
        setCloudVersion((v) => v + 1);
        setLastSender(sender);
        setCloudPulse(true);
        if (pulseTimeout.current) clearTimeout(pulseTimeout.current);
        pulseTimeout.current = setTimeout(() => setCloudPulse(false), 450);
      }
    }, TICK_MS);

    return () => {
      clearInterval(id);
      if (pulseTimeout.current) clearTimeout(pulseTimeout.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, count]);

  return {devices, cloudVersion, cloudPulse, lastSender};
}
