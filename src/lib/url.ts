/**
 * Prefix a root-absolute path with the deployment base, so the same build
 * works at `https://user.github.io/repo/` and at a domain root.
 *
 * With `base: '/terminal-notes'` in astro.config.mjs, `import.meta.env.BASE_URL`
 * is `/terminal-notes/`; at the root it is `/`. External URLs, `mailto:` and
 * in-page `#anchors` are returned untouched — they are not ours to prefix.
 */
export function url(path: string): string {
  if (/^(?:[a-z][a-z0-9+.-]*:)?\/\//i.test(path) || path.startsWith('#')) return path;
  const base = import.meta.env.BASE_URL || '/';
  const trimmed = base.endsWith('/') ? base.slice(0, -1) : base;
  return trimmed + (path.startsWith('/') ? path : `/${path}`);
}
