"""A tutor that asks you questions: active recall, a learner model and a concept graph in your vault

Modules:

- `abhyasa.blocks.detour.app`: Rabbit holes: learn a missing idea beside the step, then come back to the same place (spec 6.10).
- `abhyasa.blocks.guide.app`: The screen guide: Hyper+E or Explain on any page, and the tutor answers with a board drawn over the page.
- `abhyasa.blocks.talk.app`: The talk: a walk made into slides for a group. "Present this walk" makes the talk on the pool, and the editor changes its slides. On a walk planned from a goal, "Present this walk" first makes a walk for the talk from its steps, in their order, and a second press opens the same talk. A change to the talk never changes the walk. When the walk changes after the talk was made, the editor says what changed and offers "Make it again" (`talk_again`): the same talk takes the new walk, and each slide keeps the parts that you changed. Each change runs `check_talk`, and a talk with a problem is not saved.
- `abhyasa.core.edit`: The shared parts of the two editors, the talk editor and the walk path editor: the Undo bar, the history list, the list of rows and a live field.
- `abhyasa.core.hooks`: Blocks add to each other's pages without importing each other (vedicreader's `vr/core/hooks.py`).
- `abhyasa.core.pane`: The side pane: a page of this app beside the page, after vedicreader's `vr/core/pane.py`.
- `abhyasa.core.stage`: The stage bundle: the presenter window and the audience window of a talk, in step over a checked `BroadcastChannel`."""

__version__ = "0.0.16"
