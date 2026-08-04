import {useEffect, useState} from 'react';

/**
 * A simple step-cycling animation driver shared by every diagram.
 * While `active`, cycles 0..numSteps-1 on a fixed interval, looping.
 * Resets to step 0 whenever `active` flips (so re-selecting a case
 * replays its animation from the start, rather than resuming wherever
 * it last was).
 */
export function useReplayAnimation(
  active: boolean,
  numSteps: number,
  stepMs = 1400,
): number {
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (!active || numSteps <= 0) {
      setStep(0);
      return;
    }
    setStep(0);
    const id = setInterval(() => {
      setStep((s) => (s + 1) % numSteps);
    }, stepMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, numSteps, stepMs]);

  return step;
}
