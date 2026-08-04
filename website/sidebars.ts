import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'intro',
    'architecture',
    'getting-started',
    {
      type: 'category',
      label: 'Usage',
      link: {type: 'doc', id: 'usage/single-models'},
      items: [
        'usage/single-models',
        'usage/distributed-models',
        'usage/semi-supervised-learning',
        'usage/incremental-training',
        'usage/federated-learning',
      ],
    },
    {
      type: 'category',
      label: 'Installation & Development',
      link: {type: 'doc', id: 'installation/build'},
      items: [
        'installation/build',
        'installation/single-node',
        'installation/distributed-cluster',
        'installation/gpu-configuration',
      ],
    },
    'security',
    'publications',
    'changelog',
  ],
};

export default sidebars;
