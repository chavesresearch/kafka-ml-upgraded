import type {ReactNode} from 'react';
import clsx from 'clsx';
import {useReplayAnimation} from '../useReplayAnimation';
import {useTicker} from '../useTicker';
import styles from '../styles.module.css';

const CAPTIONS = [
  'A new batch streams in from Kafka...',
  'Incrementally updating the model - no fixed dataset size...',
  'Saving the updated model...',
  'Serving predictions with the latest update...',
];

export default function SingleIncrementalDiagram({active}: {active: boolean}): ReactNode {
  const step = useReplayAnimation(active, 4, 1400);
  const batch = useTicker(active, 700);

  return (
    <div className={styles.diagramRoot}>
      <div className={styles.diagramRow}>
        <div className={clsx(styles.node, step === 0 && styles.nodeActive)}>
          <span className={styles.nodeIcon}>🌊</span>
          <span className={styles.nodeLabel}>Data Source</span>
        </div>

        <div className={clsx(styles.connector, step === 0 && styles.connectorActive)}>
          <span className={clsx(styles.pulseDot, step === 0 && styles.pulseDotActive)} />
        </div>

        <div className={clsx(styles.node, step === 1 && styles.nodeActive)}>
          <span className={styles.nodeIcon}>🔁</span>
          <span className={styles.nodeLabel}>Training Job</span>
          <span className={styles.diagramCaption} style={{fontSize: '0.7rem'}}>
            batch {batch}
          </span>
        </div>

        <div className={clsx(styles.connector, step === 2 && styles.connectorActive)}>
          <span className={clsx(styles.pulseDot, step === 2 && styles.pulseDotActive)} />
        </div>

        <div className={clsx(styles.node, step === 2 && styles.nodeActive)}>
          <span className={styles.nodeIcon}>💾</span>
          <span className={styles.nodeLabel}>Model Storage</span>
        </div>

        <div className={clsx(styles.connector, step === 3 && styles.connectorActive)}>
          <span className={clsx(styles.pulseDot, step === 3 && styles.pulseDotActive)} />
        </div>

        <div className={clsx(styles.node, step === 3 && styles.nodeActive)}>
          <span className={styles.nodeIcon}>🔮</span>
          <span className={styles.nodeLabel}>Inference</span>
        </div>
      </div>
      <p className={styles.diagramCaption}>{CAPTIONS[step]}</p>
    </div>
  );
}
