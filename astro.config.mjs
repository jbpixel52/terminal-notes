// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

// The site URL is a placeholder: change it in one place before deploying.
export const SITE = 'https://notes.example.com';

export default defineConfig({
  site: SITE,
  output: 'static',
  trailingSlash: 'ignore',
  integrations: [sitemap()],
  markdown: {
    shikiConfig: {
      theme: 'github-dark-default',
      wrap: true,
    },
  },
  vite: {
    build: {
      // The ascii pieces are small modules; keep them out of the critical path.
      assetsInlineLimit: 2048,
    },
  },
});
