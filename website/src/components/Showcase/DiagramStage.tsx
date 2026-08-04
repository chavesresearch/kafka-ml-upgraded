import type {ReactNode} from 'react';
import type {ComponentType} from 'react';
import SingleClassicDiagram from './diagrams/SingleClassicDiagram';
import SingleIncrementalDiagram from './diagrams/SingleIncrementalDiagram';
import DistributedDiagram from './diagrams/DistributedDiagram';
import DistributedIncrementalDiagram from './diagrams/DistributedIncrementalDiagram';
import FederatedDiagram from './diagrams/FederatedDiagram';
import FederatedIncrementalDiagram from './diagrams/FederatedIncrementalDiagram';
import FederatedDistributedDiagram from './diagrams/FederatedDistributedDiagram';
import FederatedDistributedIncrementalDiagram from './diagrams/FederatedDistributedIncrementalDiagram';
import FederatedBlockchainDiagram from './diagrams/FederatedBlockchainDiagram';
import styles from './styles.module.css';

interface DiagramProps {
  active: boolean;
}

const DIAGRAMS: Record<number, ComponentType<DiagramProps>> = {
  1: SingleClassicDiagram,
  2: SingleIncrementalDiagram,
  3: DistributedDiagram,
  4: DistributedIncrementalDiagram,
  5: FederatedDiagram,
  6: FederatedIncrementalDiagram,
  7: FederatedDistributedDiagram,
  8: FederatedDistributedIncrementalDiagram,
  9: FederatedBlockchainDiagram,
};

export default function DiagramStage({caseId}: {caseId: number}): ReactNode {
  const Diagram = DIAGRAMS[caseId];
  return (
    <div className={styles.diagramStage}>
      {/* key={caseId} forces a remount on every case switch, so each
          diagram's own animation state (and useReplayAnimation's effect)
          restarts cleanly from step 0 instead of resuming mid-cycle. */}
      <Diagram key={caseId} active={true} />
    </div>
  );
}
