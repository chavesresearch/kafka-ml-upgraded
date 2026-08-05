import type {ReactNode} from 'react';
import clsx from 'clsx';
import {useTicker} from '../useTicker';
import styles from '../styles.module.css';

// Incremental training never "finishes" a bounded cycle the way classic
// training does - the stream just keeps flowing (kafka_dataset.py's
// get_streaming_kafka_batches polls indefinitely until stream_timeout of
// silence). Represented here as a genuinely continuous flow (marquee
// connector, always-on) rather than a discrete step loop - the model
// checkpoints and redeploys itself periodically as batches land, not on
// one fixed schedule.
export default function SingleIncrementalDiagram({active}: {active: boolean}): ReactNode {
  const batch = useTicker(active, 650);
  const justCheckpointed = batch > 0 && batch % 3 === 0;

  return (
    <div className={styles.diagramRoot}>
      <span className={styles.asyncNote}>♾️ Continuous - no fixed dataset size, never "completes"</span>

      <div className={styles.diagramRow}>
        <div className={clsx(styles.node, active && styles.nodeActive)}>
          <span className={styles.nodeIcon}>🌊</span>
          <span className={styles.nodeLabel}>Data Source</span>
          <span className={styles.nodeSublabel}>streaming</span>
        </div>

        <div className={clsx(styles.connector, active && styles.connectorFlowing)} />

        <div className={clsx(styles.node, active && styles.nodeActive)}>
          <span className={styles.nodeIcon}>🔁</span>
          <span className={styles.nodeLabel}>Training Job</span>
          <span className={styles.nodeSublabel}>batch {batch}</span>
        </div>

        <div className={clsx(styles.connector, justCheckpointed && styles.connectorActive)}>
          <span className={clsx(styles.pulseDot, justCheckpointed && styles.pulseDotActive)} />
        </div>

        <div className={clsx(styles.node, justCheckpointed && styles.nodeActive)}>
          <span className={styles.nodeIcon}>💾</span>
          <span className={styles.nodeLabel}>Model Storage</span>
          <span className={styles.nodeSublabel}>{justCheckpointed ? 'checkpointing' : 'idle'}</span>
        </div>

        <div className={clsx(styles.connector, justCheckpointed && styles.connectorActive)}>
          <span className={clsx(styles.pulseDot, justCheckpointed && styles.pulseDotActive)} />
        </div>

        <div className={clsx(styles.node, justCheckpointed && styles.nodeActive)}>
          <span className={styles.nodeIcon}>🔮</span>
          <span className={styles.nodeLabel}>Inference</span>
          <span className={styles.nodeSublabel}>{justCheckpointed ? 'redeployed' : 'serving'}</span>
        </div>
      </div>
      <p className={styles.diagramCaption}>
        A new batch streams in continuously - the model updates incrementally and
        checkpoints every few batches, without ever waiting for a fixed dataset to finish.
      </p>
    </div>
  );
}
