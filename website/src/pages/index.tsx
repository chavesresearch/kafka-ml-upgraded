import type {ReactNode} from 'react';
import clsx from 'clsx';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import HomepageFeatures from '@site/src/components/HomepageFeatures';
import Heading from '@theme/Heading';

import styles from './index.module.css';

function HomepageHeader() {
  const {siteConfig} = useDocusaurusContext();
  return (
    <header className={clsx('hero hero--primary', styles.heroBanner)}>
      <div className="container">
        <img src="img/logo.svg" alt="" className={styles.heroLogo} />
        <Heading as="h1" className="hero__title">
          {siteConfig.title}
        </Heading>
        <p className="hero__subtitle">{siteConfig.tagline}</p>
        <p className={styles.heroAbstract}>
          A framework to manage the pipeline of TensorFlow/Keras and
          PyTorch (Ignite) machine learning models on Kubernetes - trained
          and served on data streamed through Apache Kafka.
        </p>
        <div className={styles.buttons}>
          <Link className="button button--secondary button--lg" to="/docs/intro">
            Read the Docs
          </Link>
          <Link className="button button--secondary button--lg" to="/sdk/intro">
            Explore the SDK
          </Link>
          <Link className="button button--secondary button--lg" to="/showcase">
            Interactive Showcase
          </Link>
        </div>
      </div>
    </header>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Kafka-ML"
      description="Connecting the data stream with ML/AI frameworks - a Kubernetes-native pipeline for training and serving TensorFlow and PyTorch models over Apache Kafka.">
      <HomepageHeader />
      <main>
        <HomepageFeatures />
      </main>
    </Layout>
  );
}
