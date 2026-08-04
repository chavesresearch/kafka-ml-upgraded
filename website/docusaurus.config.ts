import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'Kafka-ML',
  tagline: 'Connecting the data stream with ML/AI frameworks',
  favicon: 'img/favicon.svg',

  future: {
    v4: true,
  },

  url: 'https://chavesresearch.github.io',
  baseUrl: '/kafka-ml-upgraded/',

  organizationName: 'chavesresearch',
  projectName: 'kafka-ml-upgraded',

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          path: 'docs',
          routeBasePath: 'docs',
          sidebarPath: './sidebars.ts',
          editUrl:
            'https://github.com/chavesresearch/kafka-ml-upgraded/tree/master/website/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  plugins: [
    [
      '@docusaurus/plugin-content-docs',
      {
        id: 'sdk',
        path: 'sdk',
        routeBasePath: 'sdk',
        sidebarPath: './sidebarsSdk.ts',
        editUrl:
          'https://github.com/chavesresearch/kafka-ml-upgraded/tree/master/website/',
      },
    ],
  ],

  themeConfig: {
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Kafka-ML',
      logo: {
        alt: 'Kafka-ML logo',
        src: 'img/logo.svg',
      },
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'docsSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          type: 'docSidebar',
          docsPluginId: 'sdk',
          sidebarId: 'sdkSidebar',
          position: 'left',
          label: 'SDK',
        },
        {to: '/showcase', label: 'Showcase', position: 'left'},
        {
          href: 'https://github.com/chavesresearch/kafka-ml-upgraded',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            {label: 'Introduction', to: '/docs/intro'},
            {label: 'Getting Started', to: '/docs/getting-started'},
            {label: 'Federated Learning', to: '/docs/usage/federated-learning'},
            {label: 'Security', to: '/docs/security'},
          ],
        },
        {
          title: 'SDK',
          items: [
            {label: 'Introduction', to: '/sdk/intro'},
            {label: 'API Reference', to: '/sdk/api-reference'},
          ],
        },
        {
          title: 'More',
          items: [
            {label: 'Interactive Showcase', to: '/showcase'},
            {label: 'Publications', to: '/docs/publications'},
            {
              label: 'GitHub',
              href: 'https://github.com/chavesresearch/kafka-ml-upgraded',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Kafka-ML. Released under the MIT License.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['python', 'bash', 'json'],
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
