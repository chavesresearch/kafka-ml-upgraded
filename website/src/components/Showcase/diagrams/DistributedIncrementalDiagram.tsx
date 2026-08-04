import type {ReactNode} from 'react';
import DistributedBaseDiagram from './DistributedBaseDiagram';

export default function DistributedIncrementalDiagram({active}: {active: boolean}): ReactNode {
  return <DistributedBaseDiagram active={active} incremental={true} />;
}
