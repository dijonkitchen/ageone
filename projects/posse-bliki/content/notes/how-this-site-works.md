---
title: How this site works
tags: [meta, indieweb]
summary: The vault, the build, and the IndieWeb pieces.
---
The vault is the `content/` folder: `posts/`, `notes/`, and `pages/`.
A small Python build turns it into static HTML with `[[wiki links]]`, tags, and backlinks resolved.

Each post is an h-entry, the blog is an h-feed, and the author is an h-card, all [microformats2](https://microformats.org/wiki/microformats2).
Feeds come as RSS 2.0 and JSON Feed 1.1.
New posts send [Webmentions](https://www.w3.org/TR/webmention/) to the sites they link to.

Back to the [[hello-world|first post]].
