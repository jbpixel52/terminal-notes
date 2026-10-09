/**
 * One place for the site's identity. Everything here is deliberately generic:
 * no real names, no client names, no hostnames.
 */
export const SITE = {
  title: 'Terminal Notes',
  tagline: 'what I learned about tech, servers and coding — written down before I forget it',
  description:
    'Field notes on Linux servers, Docker, networking, storage, web development, testing and automation. Every post is a lesson that cost something to learn.',
  author: 'an anonymous engineer',
  /** The deployed origin. Keep in step with `site` in astro.config.mjs. */
  url: process.env.SITE_URL ?? 'https://jbpixel52.github.io',
  /** The path the site is served from, when it is not the origin root. */
  base: process.env.BASE_PATH ?? '/terminal-notes',
  lang: 'en',
  /** Shown in the footer. No personal links. */
  builtWith: 'Astro',
} as const;

export const NAV = [
  { href: '/', label: 'index' },
  { href: '/notes/', label: 'notes' },
  { href: '/tags/', label: 'tags' },
  { href: '/about/', label: 'about' },
  { href: '/colophon/', label: 'colophon' },
] as const;
