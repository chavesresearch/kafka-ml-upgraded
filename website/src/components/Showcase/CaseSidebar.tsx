import type {ReactNode} from 'react';
import clsx from 'clsx';
import {caseDefinitions, type CaseGroup} from './caseDefinitions';
import styles from './styles.module.css';

const GROUPS: CaseGroup[] = ['Single', 'Distributed', 'Federated'];

export default function CaseSidebar({
  selectedId,
  onSelect,
}: {
  selectedId: number;
  onSelect: (id: number) => void;
}): ReactNode {
  return (
    <nav className={styles.caseSidebar} aria-label="Training mode">
      {GROUPS.map((group) => (
        <div key={group} className={styles.caseGroup}>
          <div className={styles.caseGroupLabel}>{group}</div>
          {caseDefinitions
            .filter((c) => c.group === group)
            .map((c) => (
              <button
                key={c.id}
                type="button"
                className={clsx(styles.caseItem, c.id === selectedId && styles.caseItemActive)}
                onClick={() => onSelect(c.id)}>
                <span className={styles.caseItemNumber}>{c.id}</span>
                <span>{c.title}</span>
              </button>
            ))}
        </div>
      ))}
    </nav>
  );
}
