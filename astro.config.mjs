// @ts-check
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

/*
 * Environment-driven, so the same commit can be deployed at a project path
 * (https://user.github.io/repo/) or at a domain root:
 *
 *   BASE_PATH='' SITE_URL='https://notes.example.com' npm run build
 *
 * The defaults match the GitHub Pages deployment.
 */
const base = process.env.BASE_PATH ?? '/terminal-notes';
const site = process.env.SITE_URL ?? 'https://jbpixel52.github.io';

export default defineConfig({
  site,
  base,
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
