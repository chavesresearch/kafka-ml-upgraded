import type {ReactNode} from 'react';
import clsx from 'clsx';
import {useReplayAnimation} from '../useReplayAnimation';
import styles from '../styles.module.css';

const CAPTIONS = [
  'Streaming training data from Kafka...',
  'Training the model...',
  'Saving the trained model...',
  'Serving real-time predictions...',
];

export default function SingleClassicDiagram({active}: {active: boolean}): ReactNode {
  const step = useReplayAnimation(active, 4, 1400);

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
          <span className={styles.nodeIcon}>🧠</span>
          <span className={styles.nodeLabel}>Training Job</span>
          <div className={styles.progressBar}>
            <div className={clsx(styles.progressFill, step === 1 && styles.progressFillActive)} />
          </div>
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
