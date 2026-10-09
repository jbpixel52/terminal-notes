import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { getNotes } from '../lib/site';
import { url } from '../lib/url';
import { SITE } from '../consts';

/**
 * The feed, at /rss.xml (with the deployment base in front of it).
 *
 * The item links go through url() so they keep the base path: @astrojs/rss
 * joins them onto `site`, which is an origin, not a subdirectory.
 */
export async function GET(context: APIContext) {
  const notes = await getNotes();
  return rss({
    title: SITE.title,
    description: SITE.description,
    site: context.site ?? SITE.url,
    items: notes.map((note) => ({
      title: note.data.title,
      description: note.data.description,
      pubDate: note.data.pubDate,
      link: url(`/notes/${note.id}/`),
      categories: note.data.tags,
    })),
    customData: `<language>${SITE.lang}</language>`,
  });
}
