# Blog posts — scheduled publishing

Drop markdown files here; the filename is the URL slug (`car-key-cost-hot-springs.md` → `/car-key-cost-hot-springs`). Posts publish **automatically on their `pubDate`** via the daily rebuild (GitHub Actions, 11:00 UTC = 6 AM Central) — commit and push, then walk away.

Until its pubDate a post is invisible everywhere: no page, no `/blog` card, no sitemap entry — and links pointing at it from other pages/posts are rendered as plain text, then restored automatically on publish day. The `/blog` hub and the Blog nav link only appear once at least one post is live.

## Frontmatter

```markdown
---
title: "On-Page H1 (can be long)"
seoTitle: "Short SERP Title"          # optional — only if title > ~60 chars
description: "Meta description, ~140-160 chars."
pubDate: 2026-08-01
heroImage: /assets/img/hero-keys.jpg
heroAlt: "Descriptive alt text"
author: "Arkey Locksmith"             # optional, defaults to the business
draft: true                           # optional — hide regardless of date
---

Body in markdown: `##`/`###` headings, paragraphs, `-` and `1.` lists,
`> quotes`, **bold**, *italic*, [links](/automotive-locksmith).
```

Rules enforced by `build.py` (build fails loudly if violated):
- `title`, `description`, `pubDate`, `heroImage`, `heroAlt` are required
- `heroImage` must exist under `assets/`
- the slug must not collide with an existing page

Legacy blog slugs (see `REDIRECTS` in build.py) currently 301 to the homepage; if a post reuses one of those slugs, the redirect is dropped automatically and the URL's history is reclaimed.

**Always push to main after adding posts or deploying** — the nightly cron builds GitHub main and will overwrite any unpushed local deploy.
