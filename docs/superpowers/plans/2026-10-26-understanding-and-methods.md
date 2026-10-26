# Plan: an understanding map, named gaps, and ways to learn

Date: 26 October 2026. From the user's request:

> maintain a graph about my understanding of these concepts ... so I can also see what my strengths and weaknesses are. also, it should
> learn from how I respond to specific methods of learning, for ex, if I learn better with code ... use that to drill concepts I'm not
> quite getting. but also expand me to learn in different ways sometimes, as in with equations if my understanding of math equations
> has gotten better.

## Decisions (the main session's calls; the user can change them)

1. A named gap comes first, but it does not block its parent.
2. Credit is the raw outcome: solid 1, shaky 0.5, a miss 0.
3. The default for "try a new way" is "sometimes" (15%).
4. Code is a way for every subject. The counts show if it helps.

## Data

| what | where |
|---|---|
| `method` (`code`, `maths`, `analogy`, `example`, `diagram`, `words`) | the question, the session log row, the attempt |
| `gaps` (terms the learner says they do not know) | attempt meta, from a `gaps` field in the grader JSON |
| `taught`, `teach_method` | the final attempt, set by `Session.teach` |
| a named gap | a concept with `provenance` `{src: 'gap', of, said, at}`, linked as a prereq of the parent |
| per-method counts | a `kind='stats'` doc (`learning://stats/me`): `methods[subject or '*'][m] = [a, b]`, `recent[m]`, `calib`. A cache: `method_stats` builds it again from the attempts |
| `explore` (`never`, `sometimes`, `often`) | the profile |

## Rules

- Credit on close: add `s` to `a` and `1 - s` to `b`, for the subject and for `*`. "I don't know" before a try gives none. A lesson's check
  credits the lesson's method. A demo prediction credits `diagram`. A teach request changes no counts.
- Prior: Beta(1, 1), plus 2 on `a` for each way in `profile.examples`.
- `choose`: drill a weak concept with the best mean. For a concept that is not weak: first a method that got better (its last 5 at least
  0.2 above its mean, with 4 or more credits), else with chance epsilon a Thompson sample over the other methods, else the best. The
  choice and its reason go in the question's "why" line.
- `understanding(c)`: floor, ceiling, recall and reasons (named gap, misconception, misses, shaky, fading, not located). Strong: floor 3
  or more, recall 0.8 or more, no misses, no reasons.

## Build order

1. Record teach requests. 2. Grader `gaps`, `name_gaps`. 3. `evidence` reads the thread. 4. Calibration into prompts.
5. The `method` module and the stats doc. 6. Tag the prompts and credit outcomes. 7. `choose` and `explore`.
8. `understanding` and graph fields. 9. The strengths page. 10. Drill sessions. 11. "Another way" and `asks_for`.
12. Graph colour by understanding.
