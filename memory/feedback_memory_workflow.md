# Memory Workflow Rule

## Type

feedback

## Rule

Whenever the user corrects Codex or says to remember something about this project, save that information as its own Markdown file inside the root `memory/` folder.

## File naming

Each memory file must start with one of these prefixes:

- `user_` for how the user personally works.
- `project_` for this specific project.
- `feedback_` for corrections to Codex behavior.
- `reference_` for links, facts, or external context.

## Required index

Keep `memory/MEMORY.md` updated with a one-line summary of every memory rule so the right memory can load next session.

## Required companion files

- `memory/lessons.md` stores narrative strategic learnings.
- `tasks/todo.md` stores active sprint work. Plan there before building and mark items complete as work ships.

## Session startup rule

At the start of every new session, read:

- `memory/MEMORY.md`
- `memory/lessons.md`
- `tasks/todo.md`

Then confirm setup and continue working normally.
