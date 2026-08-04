import type {ReactNode} from 'react';
import {useState} from 'react';
import CodeBlock from '@theme/CodeBlock';
import type {CaseDefinition} from './caseDefinitions';
import styles from './styles.module.css';

export default function CodePanel({caseDef}: {caseDef: CaseDefinition}): ReactNode {
  const [tab, setTab] = useState<'model' | 'sdk'>('model');

  return (
    <div>
      <div className={styles.codeTabs}>
        <button
          type="button"
          className={tab === 'model' ? styles.codeTabActive : styles.codeTab}
          onClick={() => setTab('model')}>
          Model code
        </button>
        <button
          type="button"
          className={tab === 'sdk' ? styles.codeTabActive : styles.codeTab}
          onClick={() => setTab('sdk')}>
          SDK deployment
        </button>
      </div>
      {tab === 'model' ? (
        <CodeBlock language="python">{caseDef.modelCode}</CodeBlock>
      ) : (
        <CodeBlock language="python">{caseDef.sdkSnippet}</CodeBlock>
      )}
    </div>
  );
}
