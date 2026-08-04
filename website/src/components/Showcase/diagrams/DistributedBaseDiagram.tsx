import type {ReactNode} from 'react';
import clsx from 'clsx';
import {useReplayAnimation} from '../useReplayAnimation';
import {useTicker} from '../useTicker';
import styles from '../styles.module.css';

// Shared by DistributedDiagram and DistributedIncrementalDiagram (CASE 3
// and 4) - same 5-node chain, only the training-node presentation
// differs (one-shot progress vs. loop+ticker), matching the "split the
// training-job node into a linked father/child pair" pattern from
// SingleClassicDiagram/SingleIncrementalDiagram.
export default function DistributedBaseDiagram({
  active,
  incremental,
}: {
  active: boolean;
  incremental: boolean;
}): ReactNode {
  const step = useReplayAnimation(active, 5, 1400);
  const batch = useTicker(active && incremental, 700);

  const captions = incremental
    ? [
        'A new batch streams in from Kafka...',
        'Edge submodel trains on the raw input...',
        'Cloud submodel trains on the edge\'s intermediate output...',
        'Saving both updated submodels...',
        'Serving predictions with the latest chain...',
      ]
    : [
        'Streaming training data from Kafka...',
        'Edge submodel trains on the raw input...',
        'Cloud submodel trains on the edge\'s intermediate output...',
        'Saving both trained submodels...',
        'Serving real-time predictions...',
      ];

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
          <span className={styles.nodeIcon}>{incremental ? '🔁' : '📱'}</span>
          <span className={styles.nodeLabel}>Edge Submodel</span>
          {incremental && (
            <span className={styles.diagramCaption} style={{fontSize: '0.7rem'}}>
              batch {batch}
            </span>
          )}
        </div>

        <div className={clsx(styles.connector, step === 2 && styles.connectorActive)}>
          <span className={clsx(styles.pulseDot, step === 2 && styles.pulseDotActive)} />
        </div>

        <div className={clsx(styles.node, step === 2 && styles.nodeActive)}>
          <span className={styles.nodeIcon}>{incremental ? '🔁' : '☁️'}</span>
          <span className={styles.nodeLabel}>Cloud Submodel</span>
        </div>

        <div className={clsx(styles.connector, step === 3 && styles.connectorActive)}>
          <span className={clsx(styles.pulseDot, step === 3 && styles.pulseDotActive)} />
        </div>

        <div className={clsx(styles.node, step === 3 && styles.nodeActive)}>
          <span className={styles.nodeIcon}>💾</span>
          <span className={styles.nodeLabel}>Model Storage</span>
        </div>

        <div className={clsx(styles.connector, step === 4 && styles.connectorActive)}>
          <span className={clsx(styles.pulseDot, step === 4 && styles.pulseDotActive)} />
        </div>

        <div className={clsx(styles.node, step === 4 && styles.nodeActive)}>
          <span className={styles.nodeIcon}>🔮</span>
          <span className={styles.nodeLabel}>Inference</span>
        </div>
      </div>
      <p className={styles.diagramCaption}>{captions[step]}</p>
    </div>
  );
}
