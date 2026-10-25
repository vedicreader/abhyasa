# Release notes

<!-- do not remove -->

## 0.0.1

- First release. abhyasa asks you questions, grades your reasoning and never gives the answer before you try.
- A learner model keeps a depth from 0 to 5 for each concept, a floor and a ceiling, and an FSRS-style review date.
- Code, not the model, picks the next question: due reviews first, then the frontier of concepts whose prereqs you know.
- A wrong answer gets the first error and a nudge. Hints come in six steps. After three tries, the tutor teaches the smallest step and asks its check next.
- All data is on the `learning` shelf of the vishalakshi vault, so other tools can search it.
- Concepts come from pasted text, a vault document, or the vedicreader repo (Sanskrit lessons and terms, jyotiṣa grahas, rāśis and nakṣatras).
- A web app built from blocks: today, session, graph, concepts, search, add and voice. Speech to text runs on this machine with Gemma 4 E2B.
- `/learn` for ramabana, and question cards and checked code exercises for notebooks.
