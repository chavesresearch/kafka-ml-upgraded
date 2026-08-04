import type {ReactNode} from 'react';
import Layout from '@theme/Layout';
import BrowserOnly from '@docusaurus/BrowserOnly';

export default function ShowcasePage(): ReactNode {
  return (
    <Layout
      title="Interactive Showcase"
      description="See all 9 Kafka-ML training modes - single, distributed, federated, incremental, and blockchain-traced - with animated architecture diagrams, real example code, and simulated results. No cluster required.">
      <div className="container">
        {/* Reads the URL's ?case= query param and drives per-case
            animation timers - client-only, no need to render (or keep
            in sync) during static-site generation. */}
        <BrowserOnly>
          {() => {
            const ShowcaseApp = require('@site/src/components/Showcase/ShowcaseApp').default;
            return <ShowcaseApp />;
          }}
        </BrowserOnly>
      </div>
    </Layout>
  );
}
