import type {ReactNode} from 'react';
import FederatedBaseDiagram from './FederatedBaseDiagram';

export default function FederatedDiagram({active}: {active: boolean}): ReactNode {
  return <FederatedBaseDiagram active={active} incremental={false} distributed={false} />;
}
