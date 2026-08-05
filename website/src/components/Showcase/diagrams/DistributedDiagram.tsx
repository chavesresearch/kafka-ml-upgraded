import type {ReactNode} from 'react';
import clsx from 'clsx';
import {useReplayAnimation} from '../useReplayAnimation';
import styles from '../styles.module.css';

const CAPTIONS = [
  'Streaming training data from Kafka...',
  'Edge submodel trains on the raw input...',
  "Edge hands its intermediate features to the cloud submodel...",
  'Cloud submodel trains on those features...',
  'Saving both trained submodels...',
  'Serving real-time predictions through the whole chain...',
];

// Two explicit rows (not one wide row left to wrap on its own) - the
// chain-group's dashed border + padding makes a single-row layout too
// wide for the panel at normal viewport sizes, and an accidental flex-wrap
// here previously orphaned the Inference node on its own line.
export default function DistributedDiagram({active}: {active: boolean}): ReactNode {
  const step = useReplayAnimation(active, 6, 1300);
  const handoff = step === 2;

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

        <div className={styles.chainGroup}>
          <span className={styles.chainGroupLabel}>Distributed model chain</span>

          <div className={clsx(styles.node, step === 1 && styles.nodeActive)}>
            <span className={styles.nodeIcon}>📱</span>
            <span className={styles.nodeLabel}>Edge Submodel</span>
            <span className={styles.nodeSublabel}>raw input</span>
          </div>

          <div className={clsx(styles.connector, handoff && styles.connectorActive)}>
            <span className={clsx(styles.dataBadge, handoff && styles.dataBadgeActive)}>4-dim features</span>
            <span className={clsx(styles.pulseDot, handoff && styles.pulseDotActive)} />
          </div>

          <div className={clsx(styles.node, step === 3 && styles.nodeActive)}>
            <span className={styles.nodeIcon}>☁️</span>
            <span className={styles.nodeLabel}>Cloud Submodel</span>
            <span className={styles.nodeSublabel}>intermediate features</span>
          </div>
        </div>
      </div>

      <div className={clsx(styles.connectorVertical, step === 4 && styles.connectorActive)}>
        <span className={clsx(styles.pulseDot, step === 4 && styles.pulseDotActive)} />
      </div>

      <div className={styles.diagramRow}>
        <div className={clsx(styles.node, step === 4 && styles.nodeActive)}>
          <span className={styles.nodeIcon}>💾</span>
          <span className={styles.nodeLabel}>Model Storage</span>
        </div>

        <div className={clsx(styles.connector, step === 5 && styles.connectorActive)}>
          <span className={clsx(styles.pulseDot, step === 5 && styles.pulseDotActive)} />
        </div>

        <div className={clsx(styles.node, step === 5 && styles.nodeActive)}>
          <span className={styles.nodeIcon}>🔮</span>
          <span className={styles.nodeLabel}>Inference</span>
        </div>
      </div>

      <p className={styles.diagramCaption}>{CAPTIONS[step]}</p>
    </div>
  );
}
