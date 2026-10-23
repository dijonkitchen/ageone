# posse-bliki

A blog and wiki written in Obsidian as plain Markdown, built into a static site for GitHub Pages that follows [POSSE](https://indieweb.org/POSSE) and the IndieWeb.
Live at <https://dijonkitchen.github.io/ageone/bliki/> once the site workflow runs on `main`.

## The vault

Open `content/` in Obsidian (wikilinks may be on; the build resolves `[[slug]]`, `[[Title]]`, `[[slug|text]]` and `[[slug#heading]]`).
No plugins are needed.

| Folder | Kind | URL |
|---|---|---|
| `content/posts/` | dated posts, in the h-feed | `/posts/<slug>/` |
| `content/notes/` | wiki notes, with backlinks | `/notes/<slug>/` |
| `content/pages/` | pages such as About | `/<slug>/` |
| `content/assets/` | images and files, copied as is | `/assets/...` |

Files are `<slug>.md` with a kebab-case slug and YAML front matter:

| Field | Applies to | Meaning |
|---|---|---|
| `title` | all, required | page title |
| `date` | posts (required), notes | `YYYY-MM-DD` or a timestamp |
| `tags` | posts, notes | kebab-case list; each gets `/tags/<tag>/` |
| `aliases` | all | old paths such as `/old/path/`; each redirects to the page |
| `summary` | all | feed description |
| `syndication` | posts | URLs of POSSE copies, shown as `u-syndication` |
| `draft` | all | `true` keeps it out of the build |

Site settings (title, URL, author, Webmention endpoint) are in `site.toml`.

## Output

Built by `bliki build`: HTML with microformats2 (`h-entry`, `h-card`, `h-feed`), `feed.xml` (RSS 2.0), `feed.json` (JSON Feed 1.1), `sitemap.xml`, `robots.txt`, `404.html`, tag pages, the notes index, and alias redirects.
The build fails on a schema problem, an unresolved wiki link, a URL claimed twice, or a published URL in `urls.lock` that no longer exists.

## Publishing and Webmention

Pushing to `main` builds the site into the shared GitHub Pages deploy under `/bliki/` ([site workflow](../../.github/workflows/site.yml)).
After the deploy, `bliki webmention` sends a Webmention from each post of the last seven days to the external sites it links to (receivers deduplicate repeats).
To receive them, set `webmention_endpoint` in `site.toml` (for example a [webmention.io](https://webmention.io) endpoint).

To copy a post elsewhere, post the copy with a link to its original URL, then add the copy's URL to `syndication`.
