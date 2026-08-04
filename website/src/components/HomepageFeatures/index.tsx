import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  icon: string;
  description: ReactNode;
  to: string;
};

const FeatureList: FeatureItem[] = [
  {
    title: '9 Training Modes',
    icon: '🧩',
    to: '/showcase',
    description: (
      <>
        Single, distributed, federated, incremental - and every
        combination in between. Explore all nine in the interactive
        showcase.
      </>
    ),
  },
  {
    title: 'TensorFlow + PyTorch',
    icon: '🧠',
    to: '/docs/usage/single-models',
    description: (
      <>
        Define models in the Web UI with no need for external libraries -
        both frameworks are first-class citizens across the pipeline.
      </>
    ),
  },
  {
    title: 'Kubernetes-native',
    icon: '☸️',
    to: '/docs/getting-started',
    description: (
      <>
        Training and inference run as real Kubernetes Jobs and
        Deployments - deploy the whole pipeline with a single{' '}
        <code>kubectl apply -k</code>.
      </>
    ),
  },
  {
    title: 'Streamed via Apache Kafka',
    icon: '🌊',
    to: '/docs/architecture',
    description: (
      <>
        Training and inference data flows through Kafka topics, so models
        connect directly to real-time IoT and streaming data sources.
      </>
    ),
  },
  {
    title: 'Federated Learning',
    icon: '🕸️',
    to: '/docs/usage/federated-learning',
    description: (
      <>
        Edge devices train locally on their own data; the cloud
        aggregates updates with FedAvg - no raw data ever leaves the
        edge.
      </>
    ),
  },
  {
    title: 'Blockchain-Traced Rewards',
    icon: '⛓️',
    to: '/showcase?case=9',
    description: (
      <>
        A smart contract can coordinate federated rounds on-chain and pay
        out real ERC-20 rewards to participants by contribution.
      </>
    ),
  },
];

function Feature({title, icon, description, to}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <Link to={to} className={styles.featureCard}>
        <div className={styles.featureIcon}>{icon}</div>
        <div className="text--center padding-horiz--md">
          <Heading as="h3">{title}</Heading>
          <p>{description}</p>
        </div>
      </Link>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
