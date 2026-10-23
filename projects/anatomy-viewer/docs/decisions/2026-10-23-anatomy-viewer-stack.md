# Decision Record 2026-10-23: anatomy-viewer Stack

## Status timeline

2026-10-23: Proposed by Claude (scheduled spec run), for JC's review in the pull request

## Objective Context

### Simple, lovable, complete must haves

#### Functional

A stack for [the spec](../../specs/SPEC-2026-10-03-anatomy-viewer.md): front, back, and side views of the body in SVG, with toggleable layers, hover and pick details, search, zoom and pan, and a skeleton drawn as a tree of segments ready for movement.

#### Non-functional

Installable in the pinned environment from the root `make`, with `make check` passing in CI.
A static page with no server, no account, and nothing fetched at run time; every source and license listed in the repo and in the page.

### Nice to haves

#### Functional

- Movement (rotating segments about their joints) without redrawing.
- More layers (ligaments, vessels, nerves, lymphatics) without changing the ones before.

#### Non-functional

- Data that can be checked against, and later filled from, open anatomy sources.

### Avoid out of scope runaway rabbit hole risks

#### Functional

- 3D, free rotation, sex or age variants, pathology, or medical advice.
- Hand-tracing anatomical art, or pulling in an illustration library whose license would bind the repo.

#### Non-functional

- A UI framework or a build pipeline beyond `Bun.build`.

## Decision

Started from the bun project template (see [Project template](../../../../docs/decisions/2026-10-04-project-template.md)).
There is no old repo to restart.
- **Stack**: TypeScript on Bun, with no runtime dependencies.
  `bun run build` bundles `src/app.ts` and copies `public/` into `dist/`; `bun run serve` builds and serves it at `http://localhost:8080/` (`PORT` changes the port).
  The page's content security policy allows only its own files.
- **Data file**: [`data/anatomy.json`](../../data/anatomy.json), plain JSON, separate from the drawings.
  It holds the sources, the layers (deep to superficial, with `planned` ones not drawn yet), the skeleton's segments (parent, joint, pivot in the front and side views, and ranges of motion), and the structures.
  Each structure has an id, its FMA name, Latin name, synonyms, system, count, an id per side when paired, a one-paragraph description written for this project, and its relations by id: a bone's joints, a muscle's origin, insertion, action, and nerve, and an organ's neighbors.
  Structures that are too small or too deep to draw yet carry a `notDrawn` reason instead.
- **Id vocabulary**: [Foundational Model of Anatomy](https://bioportal.bioontology.org/ontologies/FMA) (FMA 5.1) ids, written `FMA:<n>`.
  FMA has an id for each side of a paired structure (right femur `FMA:24474`, left femur `FMA:24475`) and for sets of small bones (the carpal bones of the right hand), which is exactly the unit a person picks on screen.
  Terminologia Anatomica is used only for Latin names FMA lacks, marked `latinSource: "TA"`.
  Ranges of motion are the AAOS values as tabulated by Hendriks et al. (2020); segments whose range is split across several joints (the spine) or estimated are marked `approximate`.
- **Drawings**: made in code for this project in [`src/drawings.ts`](../../src/drawings.ts) from a few geometry helpers (smooth closed curves, bands along a centreline, long bones from joint to joint), so they carry the repo's own license.
  Shapes are authored once for the body's right side and mirrored for the left; the back view is the front coordinates mirrored, with posterior muscles and organs drawn over the same skeleton.
  Drawings name structures by their data name, so a typo fails at build time rather than drawing an unknown id.
- **Movement-ready skeleton**: the skeleton layer is nested `<g class="segment" data-segment data-pivot>` groups following the segment tree (pelvis, spine, thorax, neck, head, and each limb's girdle, upper part, lower part, and hand or foot).
  Turning a segment is one `rotate(angle pivot)` on its group; [`src/pose.ts`](../../src/pose.ts) computes the same transforms without a browser, so tests can check that turning the elbow carries the hand.
- **Sources and licenses**, listed in the data file and shown in the page:
  - FMA 5.1 via the EBI Ontology Lookup Service, CC BY 3.0: ids, names, synonyms, and Latin names.
  - Terminologia Anatomica (FIPAT): Latin terms only.
  - Wikipedia muscle infoboxes, CC BY-SA 4.0: used as a cross-check of nerves and attachments; no text is copied.
  - AAOS ranges of motion via Hendriks et al., PRS Global Open 2020: facts, not copyrightable text.
  - Drawings: made for this project, under the repository's license.

### High-level C4(context/container/component/code) diagram

```text
data/anatomy.json ──► src/data.ts (types, lookups, search)
                         │
src/geometry.ts ──► src/drawings.ts (shapes per view, by structure name)
                         │
                    src/svg.ts (markup per layer; skeleton nested by segment) ──► src/pose.ts (posed pivots)
                         │
                    src/app.ts (page: layers, details, search, zoom/pan) ──► dist/ via build.ts

scripts/verify.ts ──► EBI OLS (FMA) and Wikipedia, on demand, not in CI
```

### Choices and Tradeoffs/Risks

- **Drawn in code, not traced from an atlas**: no license risk and every shape is reviewable as data, but the shapes are schematic rather than illustrative.
  Swapping in openly licensed art later only replaces `src/drawings.ts`, since everything else is keyed by id.
- **One SVG per view, layers built on first show**: the first view draws only the skeleton and muscles; organs and skin are built when turned on.
  The whole page is about 85 kB of script (24 kB compressed), data included, so a mid-range phone loads it at once.
- **A faded layer lets the pointer through**: it is see-through so you can reach the layer under it; to pick from it, show it.
- **Hover shows details, and so does a pick**: hover is a preview, the pick stays until another is made or Escape is pressed.
- **Data checked offline and online**: `make check` tests the data against the drawings (every drawn id has data, every data id is drawn or marked not drawn, every relation resolves, 206 bones, segment tree and ranges), while `bun run verify` checks names, Latin, synonyms, joints, and nerves against FMA and Wikipedia over the network.
  On 2026-10-23 it checked 268 FMA ids for 124 structures, 20 joints against FMA definitions, and 35 muscle nerves against Wikipedia, with no failures or warnings.

### Dependencies

None at run time.
Development: Bun, TypeScript, and Biome from the template.

### Interfaces

- `bun run build` writes `dist/`; `bun run serve` builds and serves it.
- `bun run verify` checks the data file against its open sources.
- `data/anatomy.json` is the interface for later layers and specs: a new layer adds structures with a new `system`, their drawings, and flips `planned` off.

## Key Results and retrospective feedback
