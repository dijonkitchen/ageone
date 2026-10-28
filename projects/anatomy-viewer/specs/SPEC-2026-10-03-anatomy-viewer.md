# SPEC-2026-10-03-anatomy-viewer: Anatomy Viewer

## Functional requirements

An interactive browser view of the human body, drawn in SVG, where you turn body systems on and off, pick a structure to learn what it is, and search for structures by name.
Movement comes later, in its own spec; this one only keeps the drawings ready for it.
- **Views**: front (anterior) and back (posterior) views of a whole adult body, standing in the anatomical position, plus a side (lateral) view.
  Switching views keeps the selected structure selected when it shows in the new view.
- **Layers**: each body system is its own layer, drawn from deep to superficial: skeleton, ligaments, muscles (deep and superficial), organs, blood vessels, nerves, lymphatics, and skin with surface landmarks.
  Each layer can be shown, hidden, or faded, so you can peel the body from skin to bone.
- **Structures**: every drawn structure (a bone, a muscle, an organ) is its own SVG shape with a stable id, so it can be hovered, picked, highlighted, and searched.
  A first release covers the skeleton (all named bones of the 206, with small bones of the hands, feet, and ears grouped where too small to pick), the major superficial muscles, and the major organs; the other layers can come later, each without changing the ones before.
- **Details**: picking a structure highlights it and shows its name (common and Latin), its system, a one-paragraph description, and what it connects to: a muscle's origin, insertion, action, and nerve; a bone's joints; an organ's neighbors.
  Picking a related structure from the details jumps to it.
- **Search**: type a name or synonym to find a structure, then jump to it in a view where it shows.
- **Navigation**: zoom and pan with mouse, touch, and keyboard, and zoom to the picked structure.
- **Data**: the structure list, names, descriptions, and relations live in one plain-text data file, separate from the drawings, keyed by the same ids.
  Ids follow an open anatomy vocabulary (such as [Terminologia Anatomica](https://ifaa.net/committees/anatomical-terminology-fipat/terminologia/) or [FMA](https://bioportal.bioontology.org/ontologies/FMA) ids) so the data can be checked against, or filled from, open sources.
- **Ready for movement**: the skeleton is drawn as a tree of SVG groups, one per segment (such as upper arm, forearm, hand), each with its joint's pivot point and its range of motion in the data file, and each muscle names the bones it attaches to.
  A later spec can then rotate segments around joints to show movements such as flexion and extension, with attached muscles following, without redrawing.

## Non-functional requirements

- Simple: a static web page with no server, database, or account.
  No 3D, free rotation, sex or age variants, pathology, or medical advice for now.
- SVG first: 2D SVG fits layered, labeled, clickable diagrams, styles with CSS, and stays sharp at any zoom.
  It can't rotate the body freely; if that's ever needed, a 3D view (WebGL with open models such as [Z-Anatomy](https://github.com/LluisV/Z-Anatomy) or [BodyParts3D](https://lifesciencedb.jp/bp3d/)) is a separate spec.
- Open and attributed: drawings are made for this project or taken from openly licensed sources, and every source and its license is listed in the repo and shown in the page.
- Accurate: names, relations, and descriptions are checked against an open reference, and tests check that every drawn id has data, every data id is drawn or marked not yet drawn, and every relation points to a real id.
- Accessible: every structure has a text name for screen readers, layers and picks work by keyboard, and colors keep enough contrast in light and dark themes.
- Fast: the first view loads and responds smoothly on a mid-range phone, loading layers only when shown.
- Runs in the pinned environment from [SPEC-2026-09-26-make-setup](../../../specs/SPEC-2026-09-26-make-setup.md), with no global installs.

## Definition of done

1. The page shows front, back, and side views with the skeleton, major superficial muscles, and major organs as separate, toggleable layers.
2. Hovering or picking any drawn structure shows its details, and its relations jump to the related structures.
3. Search finds a structure by common or Latin name and jumps to it.
4. Tests check the data file against the drawings as described above, and run in CI.
5. The skeleton is grouped into segments with pivot points and ranges of motion in the data file, so one segment can be rotated in a test without breaking the drawing.
6. One command builds the static page, and one command starts it locally.
7. A decision record states the stack, the data file format, the id vocabulary, and the drawing sources and their licenses.
