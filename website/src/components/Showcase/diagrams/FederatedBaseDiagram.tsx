import type {CSSProperties, ReactNode} from 'react';
import clsx from 'clsx';
import {useAsyncFederation} from '../useAsyncFederation';
import styles from '../styles.module.css';

const EDGE_COUNT = 4;

// Shared by FederatedDiagram, FederatedIncrementalDiagram,
// FederatedDistributedDiagram, and FederatedDistributedIncrementalDiagram
// (CASE 5/6/7/8). Models Kafka-ML's *real* aggregation behavior
// (edgeBasedTraining.py: send the global model, block until the FIRST
// device response arrives, merge just that one in, start the next round
// immediately) rather than a synchronized "wait for everyone" round -
// each device below runs on its own independent clock (useAsyncFederation),
// so they visibly finish at different times, and the cloud's model
// version bumps irregularly, only when *some* device happens to land.
export default function FederatedBaseDiagram({
  active,
  incremental,
  distributed,
}: {
  active: boolean;
  incremental: boolean;
  distributed: boolean;
}): ReactNode {
  const {devices, cloudVersion, cloudPulse} = useAsyncFederation(active, EDGE_COUNT);

  const anyTraining = devices.some((d) => d.phase === 'training');
  const modelWord = distributed ? 'submodel chain' : 'model';

  let caption: string;
  if (cloudVersion === 0 && anyTraining) {
    caption = `Cloud broadcasts the initial global ${modelWord} - devices start training whenever they're ready...`;
  } else {
    caption = `Devices train independently and report back on their own schedule - the cloud merges each update the moment it arrives, without waiting for the others.`;
  }

  return (
    <div className={styles.diagramRoot}>
      <span className={styles.asyncNote}>⏱️ Asynchronous - no device waits for another</span>

      <div className={clsx(styles.node, cloudPulse && styles.nodeActive)}>
        <span className={styles.nodeIcon}>☁️</span>
        <span className={styles.nodeLabel}>Cloud / Backend</span>
        <span className={clsx(styles.versionBadge, cloudPulse && styles.versionBadgePulse)}>
          model v{cloudVersion}
        </span>
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
                <div className={styles.ringWrap} style={{'--ring-deg': deg} as CSSProperties}>
                  <div className={styles.ringInner}>
                    <span className={styles.nodeIcon}>
                      {d.phase === 'sending' ? '📤' : distributed ? '🔗' : incremental ? '🔁' : '⚙️'}
                    </span>
                  </div>
                </div>
                <span className={styles.nodeLabel}>Device {i + 1}</span>
                <span className={styles.nodeSublabel}>
                  {d.phase === 'training' ? `training ${Math.round(d.progress * 100)}%` : 'sending update'}
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
