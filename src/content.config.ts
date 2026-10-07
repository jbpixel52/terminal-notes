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
    /** The ascii art shown at the top of the note. */
    ascii: z.object({
      piece: z.string(),
      caption: z.string().optional(),
      mono: z.boolean().optional(),
      fps: z.number().optional(),
      options: z.record(z.string(), z.unknown()).optional(),
    }),
    /** Estimated minutes; shown in the list. */
    minutes: z.number().optional(),
    draft: z.boolean().default(false),
  }),
});

export const collections = { notes };
