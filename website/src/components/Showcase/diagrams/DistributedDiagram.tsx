import type {ReactNode} from 'react';
import DistributedBaseDiagram from './DistributedBaseDiagram';

export default function DistributedDiagram({active}: {active: boolean}): ReactNode {
  return <DistributedBaseDiagram active={active} incremental={false} />;
}
