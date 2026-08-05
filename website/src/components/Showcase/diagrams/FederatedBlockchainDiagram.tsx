import {useEffect, useState, type ReactNode, type CSSProperties} from 'react';
import clsx from 'clsx';
import {useAsyncFederation} from '../useAsyncFederation';
import styles from '../styles.module.css';

const EDGE_COUNT = 4;

// Same asynchronous model as FederatedBaseDiagram (see its comment for
// why - Kafka-ML's real edgeBlockchainBasedTraining.py loop is the exact
// same "wait for the first arrival, not everyone" pattern, just against
// `elements_to_aggregate() < 1` on the FederatedLearning contract
// instead of a Kafka poll), plus the two things unique to CASE=9: a
// smart-contract node mediating the queue, and a real ERC-20 reward paid
// to whichever device's update just landed.
export default function FederatedBlockchainDiagram({active}: {active: boolean}): ReactNode {
  const {devices, cloudVersion, cloudPulse, lastSender} = useAsyncFederation(active, EDGE_COUNT);
  const [rewardFlash, setRewardFlash] = useState<{device: number; key: number} | null>(null);

  useEffect(() => {
    if (lastSender === null) return;
    setRewardFlash({device: lastSender, key: Date.now()});
  }, [lastSender, cloudVersion]);

  const anyTraining = devices.some((d) => d.phase === 'training');
  const caption =
    cloudVersion === 0 && anyTraining
      ? 'Cloud registers the FederatedLearning contract and broadcasts the initial model...'
      : 'Whichever device finishes first gets its update queued on-chain, aggregated immediately, and paid a real ERC-20 reward - the rest keep training, unaware.';

  return (
    <div className={styles.diagramRoot}>
      <span className={styles.asyncNote}>⏱️ Asynchronous - contract queue, not a synchronized round</span>

      <div className={clsx(styles.node, cloudPulse && styles.nodeActive)}>
        <span className={styles.nodeIcon}>☁️</span>
        <span className={styles.nodeLabel}>Cloud / Backend</span>
        <span className={clsx(styles.versionBadge, cloudPulse && styles.versionBadgePulse)}>
          model v{cloudVersion}
        </span>
      </div>

      <div className={clsx(styles.connectorVertical, cloudPulse && styles.connectorActive)} />

      <div className={clsx(styles.node, cloudPulse && styles.nodeActive)}>
        <span className={styles.nodeIcon}>📜</span>
        <span className={styles.nodeLabel}>FederatedLearning contract</span>
        <span className={styles.nodeSublabel}>on-chain queue</span>
      </div>

      <div className={styles.bus} />

      <div className={styles.deviceStubRow}>
        {devices.map((d, i) => (
          <div key={i} className={clsx(styles.deviceStub, d.phase === 'sending' && styles.deviceStubActive)}>
            <span
              className={clsx(styles.livePulseVertical, d.phase === 'sending' && styles.livePulseVisible)}
              style={{bottom: d.phase === 'sending' ? `${d.progress * 100}%` : '0%'}}
            />
          </div>
        ))}
      </div>

      <div className={styles.edgeRow}>
        {devices.map((d, i) => {
          const deg = d.phase === 'training' ? Math.round(d.progress * 360) : 360;
          return (
            <div key={i} className={styles.deviceColumn}>
              <div className={clsx(styles.node, styles.smallNode, d.phase === 'sending' && styles.nodeActive)}>
                {rewardFlash && rewardFlash.device === i && (
                  <span key={rewardFlash.key} className={styles.rewardToast}>
                    +🪙 KML
                  </span>
                )}
                <div className={styles.ringWrap} style={{'--ring-deg': deg} as CSSProperties}>
                  <div className={styles.ringInner}>
                    <span className={styles.nodeIcon}>{d.phase === 'sending' ? '📤' : '⚙️'}</span>
                  </div>
                </div>
                <span className={styles.nodeLabel}>Device {i + 1}</span>
                <span className={styles.nodeSublabel}>
                  {d.phase === 'training'
                    ? `training ${Math.round(d.progress * 100)}%`
                    : `🪙 ${d.completions} reward${d.completions === 1 ? '' : 's'}`}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <p className={styles.diagramCaption}>{caption}</p>
    </div>
  );
}
