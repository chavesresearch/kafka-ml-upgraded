import type {ReactNode} from 'react';
import clsx from 'clsx';
import {useReplayAnimation} from '../useReplayAnimation';
import {useTicker} from '../useTicker';
import styles from '../styles.module.css';

const EDGE_COUNT = 4;

// Shared by FederatedDiagram, FederatedIncrementalDiagram,
// FederatedDistributedDiagram, and FederatedDistributedIncrementalDiagram
// (CASE 5/6/7/8) - same cloud + edge-device layout as
// FederatedBlockchainDiagram (CASE 9), minus the smart-contract node.
// `incremental` swaps the one-shot training icon for a loop+ticker
// (same treatment as SingleIncrementalDiagram/DistributedBaseDiagram);
// `distributed` marks each device as training a linked submodel chain
// rather than one model (same "father/child pair" concept as
// DistributedBaseDiagram, condensed into a chain icon here to keep the
// multi-device layout readable).
export default function FederatedBaseDiagram({
  active,
  incremental,
  distributed,
}: {
  active: boolean;
  incremental: boolean;
  distributed: boolean;
}): ReactNode {
  const step = useReplayAnimation(active, 4, 1500);
  const batch = useTicker(active && incremental, 700);

  const cloudActive = step === 0 || step === 3;
  const edgesActive = step === 1 || step === 2;

  const downPulse = step === 0 ? styles.pulseDotActive : '';
  const upPulse = step === 2 ? styles.pulseDotActiveReverse : '';

  const modelWord = distributed ? 'submodel chain' : 'model';
  const captions = [
    `Cloud sends the global ${modelWord} to devices...`,
    incremental
      ? 'Devices train locally on their own streaming data...'
      : 'Devices train locally on their own data...',
    'Devices send their updates back to the cloud...',
    'Cloud aggregates every update (FedAvg)...',
  ];

  return (
    <div className={styles.diagramRoot}>
      <div className={clsx(styles.node, cloudActive && styles.nodeActive)}>
        <span className={styles.nodeIcon}>☁️</span>
        <span className={styles.nodeLabel}>Cloud / Backend</span>
      </div>

      <div className={clsx(styles.connectorVertical, (step === 0 || step === 2) && styles.connectorActive)}>
        <span className={clsx(styles.pulseDot, downPulse, upPulse)} />
      </div>

      <div className={styles.edgeRow}>
        {Array.from({length: EDGE_COUNT}).map((_, i) => (
          <div key={i} className={clsx(styles.node, styles.smallNode, edgesActive && styles.nodeActive)}>
            <span className={styles.nodeIcon}>
              {step === 1 ? (incremental ? '🔁' : '⚙️') : distributed ? '🔗' : '📱'}
            </span>
            <span className={styles.nodeLabel}>Device {i + 1}</span>
            {incremental && step === 1 && (
              <span style={{fontSize: '0.65rem', opacity: 0.7}}>batch {batch}</span>
            )}
          </div>
        ))}
      </div>

      <p className={styles.diagramCaption}>{captions[step]}</p>
    </div>
  );
}
