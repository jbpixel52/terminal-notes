import { getCollection, type CollectionEntry } from 'astro:content';

export type Note = CollectionEntry<'notes'>;

/** Published notes, newest first. */
export async function getNotes(): Promise<Note[]> {
  const notes = await getCollection('notes', ({ data }) => !data.draft);
  return notes.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
}

/** Reading time in minutes, from the raw markdown when not given. */
export function minutes(note: Note): number {
  if (note.data.minutes) return note.data.minutes;
  const words = (note.body ?? '').split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 210));
}

/** A tag index: tag -> notes that carry it. */
export function tagIndex(notes: Note[]): Map<string, Note[]> {
  const map = new Map<string, Note[]>();
  for (const note of notes) {
    for (const tag of note.data.tags) {
      const list = map.get(tag) ?? [];
      list.push(note);
      map.set(tag, list);
    }
  }
  return new Map([...map].sort((a, b) => b[1].length - a[1].length || a[0].localeCompare(b[0])));
}

/** Dates are pinned to UTC so the same build renders the same string everywhere. */
export function formatDate(date: Date): string {
  return date.toLocaleDateString('en-GB', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  });
}

export function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}
