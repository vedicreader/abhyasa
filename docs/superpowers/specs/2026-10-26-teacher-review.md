# abhyasa: a review from the view of learning science

Date: 26 October 2026. Status: a review, with four small changes built on the branch `teacher-review`.
The reference is [learnharness](https://github.com/amosblomqvist/learnharness) (read only; its code did not run).

## What learnharness does well

learnharness keeps its teaching method in its prompts (`src/agent/prompts/`). The important parts:

1. **Measure, then plan, then teach, then practice.** A probe finds the edge of each "strand" by binary search. It starts near
   the top: an adult who asks for hard material knows the basics. A plan map shows the path. Teaching moves one reasoning step at
   a time. Practice is a separate kind of session.
2. **Predict, teach, check.** Each step opens with a prediction about the next idea. The learner guesses first. The teaching then
   resolves the guess. A check follows, and it asks the learner to use the idea, not to repeat words.
3. **Unconditional truths first, then "how could I have discovered this?"** Each new fact must feel motivated, not arbitrary.
4. **Confidence is read against the answer.** Right and sure: move on. Right and unsure: one more touch. Wrong and sure: the
   strongest signal, a misconception. "I don't know" is a gap, never a wrong answer.
5. **The think-aloud is the primary data.** One answer is one bit; the thinking shows the model. Transcribed speech is read
   with tolerance: "a garbled word is a slipped recognition, not a slipped concept".
6. **A practice doctrine.** Retrieval must start from an inactive idea. Interleave targets. Never re-ask in the same surface.
   Aim at about 85% success for each retrieval event. A hint ladder from R0 (look again) to R5 (a worked step), one rung for each
   request. Classify each miss: cue miss, wrong candidate, slip, careless, or a structural misconception.
   **Close with retests:** each miss, each hint-heavy item, comes back before the end, in a fresh surface.
7. **Three practice modes:** recall, discrimination (the right idea against its near twin), and composition (a chain run whole).
   Templates: reverse (give the result, ask for the grounds) and "probe the premises" (weaken a premise; what breaks?).
8. **A graph of propositions and reasoning chains**, not ratings. It links back to the sessions that made each node.

## Where abhyasa falls short

abhyasa already has more of a learner model than learnharness: depth 0-5, floor and ceiling, FSRS-like recall, four outcomes,
the hint ladder (the same six rungs), grounding in the vault, journeys and a profile. The gaps:

| gap | what the learner sees today | the learning science |
|---|---|---|
| A new concept starts at "explain" (depth 3) | a hard question on a thing never taught | retrieval needs something to retrieve; a pretest helps only with feedback that teaches |
| Difficulty does not follow how the session goes | miss after miss at the same level; or many easy passes | the design goal is about 85% success; flow needs a band |
| A miss gets an immediate check, and no delayed retest | the check comes while the lesson is still in mind | the immediate check measures comprehension; a delayed retest makes memory |
| Confidence is collected but never shown back | the 0-100% buttons seem to do little | calibration (knowing what you know) is a skill to train, and a guard against the "illusion of knowing" |
| The learner is not asked to predict before a lesson | lessons are told, not discovered | prediction (the generation effect) makes the lesson land on an attempt |
| Transfer questions do not use the other subjects of the learner | "connect it to another idea" with no idea named | the user wants connected learning across Sanskrit, jyotiṣa, maths, ML and code |
| Practice is not separate from teaching | one loop does both | different jobs: a click (teach) and quiet availability (practice) |
| Misses are not classified | one outcome, "gap" or "misconception" | a cue miss and a structural misconception need different help |

The main session fixes four other gaps now: "I don't know what X means" must teach, a garbled transcript must not fail,
"Right, but shaky" must come with a lesson, and a "Teach me this" button.

## Ideas, ranked

Size: S is one notebook cell and its tests; M is a few cells or one block; L is a new flow.

| # | idea | why | what the learner sees | size | state |
|---|---|---|---|---|---|
| 1 | **Flow pace.** The session reads its last outcomes. Two misses in a row: the next question is one pace easier. Three solid passes in a row: one pace harder. | design goal 4 (about 85% success); learnharness V.3 | the "why" line says "easier: you missed the last two" or "harder: 3 clean passes in a row" | S | built |
| 2 | **Retest before the end.** Each concept missed in the session comes back once, with at least two other questions between, before the session ends. | successive relearning; learnharness IX "close with retests" | near the end: "A retest: you missed this earlier in this session." | S-M | built |
| 3 | **Calibration on About you.** "When you felt sure, you were right in 7 of 10. When you felt unsure, in 3 of 8." With one plain read of what it means. | metacognition is the skill the user wants to keep; it uses data that abhyasa already has | a new section on the About you page | S | built |
| 4 | **Bridges for transfer.** A transfer question gets up to three concepts that the learner knows well, from other subjects first, and the tutor connects to one if a real link exists. | connected learning; schema induction across varied cases | a transfer question on attention can use a Sanskrit or jyotiṣa idea that you know | S | built |
| 5 | **Predict before the first question on a new concept.** For an unseen concept, the first turn is a prediction ("guess first; you are not expected to know"), not graded. A short lesson then resolves it, then the usual check. | generation effect; learnharness predict-teach-check | a new topic opens with a guess and a short lesson, not a hard "explain" | M | proposed (touches the close and the lesson; wait for the main session) |
| 6 | **Read confidence for the outcome, also on misses.** Wrong and sure gives a different nudge ("you were sure: what made you sure?") than wrong and unsure. | learnharness confidence matrix | a nudge that matches how sure you were | S | proposed (the nudge text is with the main session) |
| 7 | **Classify each miss** (cue miss, wrong candidate, slip, misconception) in the grader, and keep it on the attempt. Use it to choose the next question: a wrong candidate gets a discrimination question. | learnharness VII | the summary says what kind of miss it was | M | proposed (needs the grade prompt) |
| 8 | **Practice sessions.** A session kind that interleaves known concepts and uses recall, discrimination and composition demands, with "reverse" and "probe the premises". | practice is a different job from teaching | "Practice" on Today, next to "Continue" | L | proposed |
| 9 | **Self-explanation prompt.** After a pass at depth 1-2, ask "why?" in one line before the close, and grade it lightly. | the self-explanation effect | one short "why?" after an easy pass | S | proposed |
| 10 | **Clear a misconception when it is fixed.** After a solid pass on a question that targeted it, mark it fixed; stop targeting it in each question. | the list of misconceptions now only grows; old ones steer new questions | "fixed" next to a misconception on the concept page | S | proposed |
| 11 | **Confidence in the model.** Feed the calibration line into the profile text, so the tutor asks "how could this be wrong?" when you are often sure and wrong. | uses idea 3 in the loop | prompts that fit how you judge yourself | S | proposed |
| 12 | **Propositions and chains in the graph.** Keep the claims that a lesson taught, with the premises, as nodes under the concept. | learnharness graph; "how could I have discovered this?" | the concept page lists what you were taught, and why it follows | L | proposed |

## What was built

Each one is its own commit, with tests (`nbdev-prepare` and `pytest` pass).

1. Flow pace: `flow` in `nbs/03_tutor.ipynb`; `Tutor.next` takes a `pace`; `Session.next` uses it and says why.
2. Retest before the end: `retests` and `Session._retest` in `nbs/03_tutor.ipynb`.
3. Calibration: `calibration` and `calibration_text` in `nbs/12_profile.ipynb`; a section on the About you page.
4. Bridges for transfer: `bridges` and the `bridge` lines of `question_prompt` in `nbs/03_tutor.ipynb`.

None of these changes `_close`, `grade_prompt`, `teach_prompt`, the nudge text, or the `Close` of the session block.
