import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

/**
 * Every note carries one ascii piece. `piece` is validated against the
 * ascii.rest catalogue at build time (see src/components/Ascii.astro).
 */
const notes = defineCollection({
  loader: glob({ base: './src/content/notes', pattern: '**/*.{md,mdx}' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    updatedDate: z.coerce.date().optional(),
    tags: z.array(z.string()).default([]),
    /** The ascii art shown at the top of the note: one generated piece or one
     *  catalogue piece, never both. */
    ascii: z.object({
      /** slug of a generated piece in src/art/pieces/ */
      art: z.string().optional(),
      /** name of a catalogue piece from ascii.rest */
      piece: z.string().optional(),
      caption: z.string().optional(),
      mono: z.boolean().optional(),
      fps: z.number().optional(),
      options: z.record(z.string(), z.unknown()).optional(),
    }),
    /** Estimated minutes; shown in the list. */
    minutes: z.number().optional(),
    draft: z.boolean().default(false),
  })
  .refine((n) => Boolean(n.ascii.art) !== Boolean(n.ascii.piece), {
    message: 'set exactly one of ascii.art / ascii.piece',
    path: ['ascii'],
  }),
});

export const collections = { notes };
