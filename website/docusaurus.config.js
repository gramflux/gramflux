const {themes} = require('prism-react-renderer');
const surface = require('../docs/api-surface.json');

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'GramFlux',
  tagline: 'An independent async Python client for Telegram.',
  customFields: {gramfluxVersion: surface.version, rawMethodCount: surface.async_api_method_count, updateConstructorCount: surface.raw_update_constructors.length},
  favicon: 'img/gramflux.svg',
  url: process.env.DOCS_URL || 'https://gramflux.github.io',
  baseUrl: process.env.DOCS_BASE_URL || '/gramflux/',
  organizationName: 'gramflux',
  projectName: 'gramflux',
  trailingSlash: true,
  onBrokenLinks: 'throw',
  onBrokenAnchors: 'throw',
  onDuplicateRoutes: 'throw',
  i18n: {defaultLocale: 'en', locales: ['en']},
  markdown: {
    format: 'detect',
    hooks: {onBrokenMarkdownLinks: 'throw', onBrokenMarkdownImages: 'throw'},
  },
  presets: [['classic', {
    docs: {
      path: '../docs',
      sidebarPath: require.resolve('./sidebars.js'),
      editUrl: ({docPath}) => `https://github.com/gramflux/gramflux/edit/v0.x-dev/docs/${docPath}`,
      showLastUpdateAuthor: false,
      showLastUpdateTime: false,
    },
    blog: false,
    theme: {customCss: require.resolve('./src/css/custom.css')},
    sitemap: {changefreq: 'weekly', priority: 0.5},
  }]],
  plugins: [['@cmfcmf/docusaurus-search-local', {
    indexDocs: true, indexBlog: false, indexPages: false,
    language: 'en', maxSearchResults: 8,
  }]],
  themeConfig: {
    image: 'img/social-card.svg',
    colorMode: {defaultMode: 'light', respectPrefersColorScheme: true},
    navbar: {
      title: 'GramFlux',
      logo: {alt: '', src: 'img/gramflux.svg', width: 30, height: 30},
      items: [
        {type: 'docSidebar', sidebarId: 'documentation', position: 'left', label: 'Documentation'},
        {to: '/docs/reference/client', label: 'API reference', position: 'left'},
        {to: '/docs/releases/0.5.0a2', label: '0.5.0a2', position: 'right'},
        {href: 'https://github.com/gramflux/gramflux', label: 'GitHub', position: 'right'},
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {title: 'Start building', items: [
          {label: 'Quick start', to: '/docs/getting-started/quickstart'},
          {label: 'Authentication', to: '/docs/guides/authentication'},
          {label: 'Sessions', to: '/docs/guides/sessions'},
        ]},
        {title: 'Go deeper', items: [
          {label: 'Client reference', to: '/docs/reference/client'},
          {label: 'Raw API', to: '/docs/reference/raw'},
          {label: 'Architecture', to: '/docs/design/architecture'},
        ]},
        {title: 'Project', items: [
          {label: 'Contributing', to: '/docs/contributing'},
          {label: 'Security', href: 'https://github.com/gramflux/gramflux/blob/v0.x-dev/SECURITY.md'},
          {label: 'License', href: 'https://github.com/gramflux/gramflux/blob/v0.x-dev/LICENSE'},
        ]},
      ],
      copyright: 'GramFlux contributors · MIT licensed · Engineering alpha',
    },
    prism: {
      theme: themes.github, darkTheme: themes.dracula,
      additionalLanguages: ['python', 'bash', 'toml', 'json'],
    },
    tableOfContents: {minHeadingLevel: 2, maxHeadingLevel: 3},
  },
};
module.exports = config;
