# Layers

The pages of abhyasa were on one flat plane. The demo, the reading text and the reference lists had the same weight.
This plan adds three surface levels. The page must stay calm and bookish. It must not look like a dashboard.

## The three surfaces

Each surface is a CSS custom property in `core/base.css`. Each property comes from the colours of the theme, so all five
themes get the surfaces. `light-dark()` gives one value for light and one value for dark.

| Level | Token | Light | Dark | Use |
|---|---|---|---|---|
| Page | `--page` | the theme `--bg` | the theme `--bg` | the reading text |
| Raised | `--raised` | `--bg` mixed with 50% white | `--bg` mixed with 7% `--fg` | the things that you do |
| Sunken | `--sunken` | `--bg` mixed with 4% `--fg` | `--bg` mixed with 16% black | the things that you look up |

- A raised surface has a soft shadow (`--lift`): low opacity, large blur, and a hairline ring of 5% or less. In dark mode the
  surface is lighter than the page, because a shadow does not show well on a dark page.
- A sunken surface has no shadow. Only its tint makes it different.
- The radius is 10 px for a surface (`--r`) and 8 px for a small part (`--r-s`), for example code.
- No surface has a heavy border.
- Each surface sets `--bg` to its own colour. Thus the parts that use `--bg` (the text on a primary button, the journey dots, the
  rupaka demo) agree with the surface below them.
- Code blocks (`.md pre`) are a small sunken well on each surface: a little darker than the surface in light mode, and darker in
  dark mode. KaTeX takes the text colour, so it shows correctly on each surface.

The utility classes are `.raised` and `.sunken`. The class `.refs` is the quiet group of reference sections.

## Which part is on which level

| Page | Raised | Page level | Sunken |
|---|---|---|---|
| Concept | the demo card | the title, the meta line, the statement, the actions | `.refs`: how well you know it, your journeys, misconceptions, needs first and related (side by side), your attempts, seen in your work, the source |
| Session | the composer, the lesson | the question and the thread | the "From your sources" list under the feedback; code |
| Today | the "Continue where you stopped" card | everything else | none |
| Journeys | the goal box (also on Today when you have no journey) | the list of journeys | none |
| Journey | none | the path and its steps | `.refs`: next to this path, your other journeys |
| Walk step | the check card | the outline, the title, the passage and the note | the code editor |
| Side pane | the check card in the pane | the pane has the surface of the page; a hairline divides it from the paper | the code editor |
| Your learning | none | this week, what you learned | the list of past sessions |
| Settings | the theme and the mode that you chose | the forms | the model tables |

Today has only one raised card. Then the main action is clear, and the page stays quiet.

## Spacing and groups

- Sections on the page level have 44 px above each label, as before.
- The `.refs` group starts 52 px under the content above it. In the group, the labels have 28 px above them. The first label
  has none.
- In a sunken group the lists keep their hairlines between items, but not above the first item or below the last item.
- A surface has 20 to 24 px of padding at the sides. Text in a surface aligns with its label.

## The accent

The accent colour (the blue of Ink, the umber of Paper) is for primary actions only: the `go` buttons, the focus ring, and the
marks that show where you are (the current nav item, the progress bars). The question and the hint in a session, and the
continue card, no longer have an accent line at the left. A neutral line or a surface marks them.

## Motion

- Buttons and links fade their colour, background and shadow in 140 ms.
- A secondary button lifts its shadow a little on hover and on focus. Nothing moves more than 1 px.
- With `prefers-reduced-motion: reduce`, nothing moves and nothing fades (the rule in `base.css` stops all transitions).

## Contrast

Each text colour (`--fg`, `--ink2`, `--mute`, and the outcome colours) must have a contrast of 4.5:1 or more on each surface,
in light and in dark, for each theme. A raised surface in light mode is lighter than the page, so the contrast increases. A sunken
surface in light mode is only 4% darker, so `--mute` stays above 4.5:1. A browser check measures the contrast of each text
element on each surface for all five themes in both modes. The lowest result is 5.47:1 (Clear, light).
