import {useEffect, useState} from 'react';

/**
 * A small incrementing counter, for incremental-training diagrams (CASE
 * 2/6/8) to show a "live" streaming batch/message count next to a loop
 * icon, instead of the one-shot progress bar the classic (bounded)
 * modes use.
 */
export function useTicker(active: boolean, intervalMs = 900): number {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!active) {
      setCount(0);
      return;
    }
    const id = setInterval(() => setCount((c) => c + 1), intervalMs);
    return () => clearInterval(id);
  }, [active, intervalMs]);

  return count;
}
