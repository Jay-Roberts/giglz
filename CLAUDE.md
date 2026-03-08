# CLAUDE.md

Instructions for Claude Code when working in this repository.

## Status

**v2 in progress.** v1 code archived in `v1/`.

Design docs in `notes/v2/scratch.md`. Coding standards in `notes/coding-standards.md`.

## Working with Jay

Use the notes directory for planning and research.

```
notes/
  v2/
    scratch.md           # main design doc
    YYYY-MM-DD_status.md # daily status
  learnings/             # project-wide learnings
  coding-standards.md    # style, patterns, principles
```

- Daily status docs capture context that survives compactification
- Flag things for discussion with `#!` in docs or code
- Iterative: sketch, poke, refine

## What's Here

```
v1/           # archived v1 code (reference only)
notes/        # design docs, learnings, status (symlink)
CLAUDE.md     # this file
LICENSE
```

## v2 Build

Not started yet. See `notes/v2/scratch.md` for:
- Data model
- Components
- Interactions
- Build sequence (walking skeleton → vertical slices)

When we start coding:
- `pyproject.toml` for deps and linting config
- `Makefile` for common commands
- `.pre-commit-config.yaml` for quality gates
