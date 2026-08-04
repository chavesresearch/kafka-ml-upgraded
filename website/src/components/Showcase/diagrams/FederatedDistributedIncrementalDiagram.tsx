import type {ReactNode} from 'react';
import FederatedBaseDiagram from './FederatedBaseDiagram';

export default function FederatedDistributedIncrementalDiagram({active}: {active: boolean}): ReactNode {
  return <FederatedBaseDiagram active={active} incremental={true} distributed={true} />;
}
