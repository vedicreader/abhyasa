# Known issues

These issues are known in the release that adds the builder. None of them gives the room wrong content or loses data. They are the next fixes.

## Talks
- A code piece with very long lines can run past the right edge of a slide. Newer code pieces have shorter lines, but a slide that was made earlier keeps its long lines. The room cannot scroll a slide.
- Maths in a passage or a point shows as plain text, for example `c_n·e^{i2πnt/T}`. It is not rendered with KaTeX.

## The builder
- Some sources that research finds have bad names in the source list, such as "untitled", "__What is a Fourier Series?" or "articlesCauses of World War One - BBC".
- A step that the builder refuses, for example because the walk has that topic already, still shows under "What changed", with a "See it" link.
- After an Undo, the builder's own words under "What the builder said" can contradict each other. The summary line is correct.
- The agent sometimes puts a rule about the shape of the talk into the aim. That rule no longer reaches the slides.
- When you keep research finds for a walk, the walk can be made one time before the kept pages are read, and then made again with them. The result is correct, but it takes longer.
