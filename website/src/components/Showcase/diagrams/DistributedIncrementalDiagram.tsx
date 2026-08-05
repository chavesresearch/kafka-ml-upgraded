import type {ReactNode} from 'react';
import clsx from 'clsx';
import {useTicker} from '../useTicker';
import styles from '../styles.module.css';

// Same continuous-stream treatment as SingleIncrementalDiagram, applied
// to the distributed father/child chain - the edge and cloud submodels
// both update continuously as data streams in, handing off intermediate
// features on every batch rather than once per bounded epoch. Two
// explicit rows, same reasoning as DistributedDiagram's own comment.
export default function DistributedIncrementalDiagram({active}: {active: boolean}): ReactNode {
  const batch = useTicker(active, 650);
  const justCheckpointed = batch > 0 && batch % 3 === 0;

  return (
    <div className={styles.diagramRoot}>
      <span className={styles.asyncNote}>♾️ Continuous - the whole chain updates as data streams in</span>

      <div className={styles.diagramRow}>
        <div className={clsx(styles.node, active && styles.nodeActive)}>
          <span className={styles.nodeIcon}>🌊</span>
          <span className={styles.nodeLabel}>Data Source</span>
          <span className={styles.nodeSublabel}>streaming</span>
        </div>

        <div className={clsx(styles.connector, active && styles.connectorFlowing)} />

        <div className={styles.chainGroup}>
          <span className={styles.chainGroupLabel}>Distributed model chain</span>

          <div className={clsx(styles.node, active && styles.nodeActive)}>
            <span className={styles.nodeIcon}>🔁</span>
            <span className={styles.nodeLabel}>Edge Submodel</span>
            <span className={styles.nodeSublabel}>batch {batch}</span>
          </div>

          <div className={clsx(styles.connector, active && styles.connectorFlowing)}>
            <span className={clsx(styles.dataBadge, active && styles.dataBadgeActive)}>4-dim features</span>
          </div>

          <div className={clsx(styles.node, active && styles.nodeActive)}>
            <span className={styles.nodeIcon}>🔁</span>
            <span className={styles.nodeLabel}>Cloud Submodel</span>
            <span className={styles.nodeSublabel}>batch {batch}</span>
          </div>
        </div>
      </div>

      <div className={clsx(styles.connectorVertical, justCheckpointed && styles.connectorActive)}>
        <span className={clsx(styles.pulseDot, justCheckpointed && styles.pulseDotActive)} />
      </div>

      <div className={styles.diagramRow}>
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
        Both submodels update continuously as data streams in - no fixed dataset size, no
        waiting for an epoch to finish.
      </p>
    </div>
  );
}
