import type {ReactNode} from 'react';
import clsx from 'clsx';
import {useReplayAnimation} from '../useReplayAnimation';
import styles from '../styles.module.css';

const CAPTIONS = [
  'Cloud sends the global model...',
  'Smart contract relays the model to devices...',
  'Devices train locally on their own data...',
  'Devices submit updates on-chain (addUpdateToQueue)...',
  'Cloud dequeues updates and aggregates (FedAvg)...',
  'Paying real ERC-20 rewards by contribution...',
];

const EDGE_COUNT = 4;

export default function FederatedBlockchainDiagram({active}: {active: boolean}): ReactNode {
  const step = useReplayAnimation(active, 6, 1600);
  const round = 1; // illustrative - a real round counter would need cross-cycle state

  const cloudActive = step === 0 || step === 4;
  const contractActive = step === 1 || step === 3;
  const edgesActive = step === 2 || step === 5;

  const cloudContractPulse =
    step === 0 ? styles.pulseDotActive : step === 4 ? styles.pulseDotActiveReverse : '';
  const contractEdgesPulse =
    step === 1 ? styles.pulseDotActive : step === 3 ? styles.pulseDotActiveReverse : '';

  return (
    <div className={styles.diagramRoot}>
      <span className={styles.roundBadge}>Round {round} / 3</span>

      <div className={clsx(styles.node, cloudActive && styles.nodeActive)}>
        <span className={styles.nodeIcon}>☁️</span>
        <span className={styles.nodeLabel}>Cloud / Backend</span>
      </div>

      <div className={clsx(styles.connectorVertical, (step === 0 || step === 4) && styles.connectorActive)}>
        <span className={clsx(styles.pulseDot, cloudContractPulse)} />
      </div>

      <div className={clsx(styles.node, contractActive && styles.nodeActive)}>
        <span className={styles.nodeIcon}>📜</span>
        <span className={styles.nodeLabel}>FederatedLearning contract</span>
      </div>

      <div
        className={clsx(
          styles.connectorVertical,
          (step === 1 || step === 3 || step === 5) && styles.connectorActive,
        )}>
        <span className={clsx(styles.pulseDot, contractEdgesPulse)} />
        <span className={clsx(styles.coinIcon, step === 5 && styles.coinIconActive)}>🪙</span>
      </div>

      <div className={styles.edgeRow}>
        {Array.from({length: EDGE_COUNT}).map((_, i) => (
          <div
            key={i}
            className={clsx(styles.node, styles.smallNode, edgesActive && styles.nodeActive)}>
            <span className={styles.nodeIcon}>{step === 2 ? '⚙️' : '📱'}</span>
            <span className={styles.nodeLabel}>Device {i + 1}</span>
          </div>
        ))}
      </div>

      <p className={styles.diagramCaption}>{CAPTIONS[step]}</p>
    </div>
  );
}
