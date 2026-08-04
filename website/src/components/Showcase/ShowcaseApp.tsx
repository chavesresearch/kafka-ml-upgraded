import type {ReactNode} from 'react';
import {useMemo, useState} from 'react';
import {useLocation} from '@docusaurus/router';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import CaseSidebar from './CaseSidebar';
import DiagramStage from './DiagramStage';
import CodePanel from './CodePanel';
import ResultsPanel from './ResultsPanel';
import {caseDefinitions, getCaseById} from './caseDefinitions';
import styles from './styles.module.css';

type StepTab = 'architecture' | 'code' | 'results';

function initialCaseId(search: string): number {
  const params = new URLSearchParams(search);
  const raw = params.get('case');
  const id = raw ? parseInt(raw, 10) : NaN;
  return caseDefinitions.some((c) => c.id === id) ? id : 1;
}

export default function ShowcaseApp(): ReactNode {
  const location = useLocation();
  const [selectedId, setSelectedId] = useState<number>(() => initialCaseId(location.search));
  const [tab, setTab] = useState<StepTab>('architecture');

  const caseDef = useMemo(() => getCaseById(selectedId), [selectedId]);

  function selectCase(id: number) {
    setSelectedId(id);
    setTab('architecture');
  }

  return (
    <div className={styles.showcaseLayout}>
      <CaseSidebar selectedId={selectedId} onSelect={selectCase} />

      <div className={styles.showcaseMain}>
        <div className={styles.caseHeader}>
          <span className={styles.caseHeaderBadge}>CASE {caseDef.id}</span>
          <h1>{caseDef.title}</h1>
          <p>{caseDef.summary}</p>
          <Link to={caseDef.docsLink}>Read the docs for this mode &rarr;</Link>
        </div>

        <div className={styles.stepTabs} role="tablist">
          {(
            [
              ['architecture', 'Architecture'],
              ['code', 'Code'],
              ['results', 'Results'],
            ] as [StepTab, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              className={clsx(styles.stepTab, tab === key && styles.stepTabActive)}
              onClick={() => setTab(key)}>
              {label}
            </button>
          ))}
        </div>

        <div className={styles.stepContent}>
          {tab === 'architecture' && <DiagramStage caseId={caseDef.id} />}
          {tab === 'code' && <CodePanel caseDef={caseDef} />}
          {tab === 'results' && (
            <ResultsPanel
              key={caseDef.id}
              metrics={caseDef.metrics}
              xLabel={caseDef.metrics.xLabel}
              active={tab === 'results'}
            />
          )}
        </div>
      </div>
    </div>
  );
}
