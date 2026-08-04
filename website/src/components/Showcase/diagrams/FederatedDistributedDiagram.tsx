import type {ReactNode} from 'react';
import FederatedBaseDiagram from './FederatedBaseDiagram';

export default function FederatedDistributedDiagram({active}: {active: boolean}): ReactNode {
  return <FederatedBaseDiagram active={active} incremental={false} distributed={true} />;
}
