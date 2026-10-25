# Grounding and links: your sources and your sessions in the graph

Date: 25 October 2026. Asked for by the user: "a way to add my access to vedicreader or its sources for grounding, and my leela
and ramabana sessions and vaults. That would let it connect my knowledge graph along with the sessions I use it for."

## What it does

1. Grounding. The tutor writes questions, grades answers and teaches lessons from passages in your own sources. It cites them.
2. Links. Each concept keeps a list of the places where it shows up in your work: a vault document, a verse in the
   vedicreader library, a ramabana session, a leela notebook. The concept page and the graph show these links.
3. Growth from sessions. The tutor can read your recent sessions and add the concepts you worked on, each linked to its session.

## Sources

A source has one method: `search(q, k) -> [Passage]`. A passage has `src`, `ref`, `title`, `text` and `url`.

| source | reads | how |
|---|---|---|
| vault shelves | every shelf of the vault except `learning` | `Vault.elsewhere`, read only |
| vedicreader library | `data/db/shlokas/*.db` in the vedicreader repo | the `sections_fts` table (porter), read only |
| ramabana sessions | the `ramabana` shelf, after you index it | a vault shelf, so Sanketa finds it too |
| leela notebooks | the `notebooks` shelf, after you index it | a vault shelf |

Sessions go into the vault because the user wants one search across every tool. The indexers only add new shelves. They do not
change any shelf that exists. You start them yourself:

```sh
uv run abhyasa-index ramabana     # ~/.config/ramabana/agent-history.jsonl -> shelf `ramabana`, one document per session
uv run abhyasa-index notebooks    # leela notebooks under ~/code -> shelf `notebooks`
```

An index runs again in seconds: a session whose text did not change is skipped.

## Links

`Learning.connect(slug)` searches every source for the concept's name and statement and keeps the best five hits in the
concept's `seen_in` meta, with the time. The concept page calls it when the list is older than a day. The graph can show
each source as a small node joined to its concepts.

## Grounding in the tutor

`Tutor(sources=...)` gives the question, grade and lesson prompts up to three passages, with their citations. The learner
sees the citations only after the question closes, so a passage cannot give the answer away.

## vedicreader.com

The first build reads the vedicreader repo files on this machine. Access to the website (an account token and an API) is a
later step. It needs a new route in vedicreader, so it is the user's decision.

## Not in this step

No change to ramabana, leela or vishalakshi. No writes to the user's vault until the user runs an index command.
