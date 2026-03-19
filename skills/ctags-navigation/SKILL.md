---
name: ctags-navigation
description: Use when needing to find definitions of functions, classes, or components across both backend (Python) and frontend (TypeScript/React).
---

# Ctags Navigation

## Overview
Efficiently navigate and search large codebases using `ctags`. This skill allows you to jump directly to definitions instead of sifting through grep results.

## When to Use
- **Deep search required:** When `grep_search` returns too many matches (imports, usages).
- **Cross-language exploration:** When you need to trace symbols across Python (backend) and TypeScript (frontend).
- **Understanding structure:** When you want a quick overview of symbols in a file or project.

## Core Pattern
### 1. Generate Tags
Always regenerate the `tags` file to ensure it's up to date. Exclude build artifacts and environments.

```bash
ctags -R --exclude=node_modules --exclude=.venv --exclude=.git --exclude=dist --exclude=build --langmap=TypeScript:+.tsx .
```

### 2. Search for a Symbol
Search for the EXACT symbol definition using `grep -w`.

```bash
grep -w "SymbolName" tags
```

## Quick Reference
| Operation | Command |
|-----------|---------|
| Generate tags | `ctags -R --exclude=node_modules --exclude=.venv ...` |
| Search for symbol | `grep -w "SymbolName" tags` |
| List methods in class | `grep "class:ClassName" tags` |
| Search by file | `grep "path/to/file.py" tags` |

## Common Mistakes
- **Outdated tags:** Forgetting to regenerate the `tags` file after significant code changes.
- **Missing TSX:** Not including `--langmap=TypeScript:+.tsx` for React projects.
- **Too many matches:** Not using `-w` in `grep`, which might return symbols that are substrings of others.

## Real-World Impact
- **Cross-boundary tracing:** Instantly jump from a React component using an API to its Python implementation.
- **Instant Discovery:** Zero-turn discovery of where a class is defined, even in a project with hundreds of files.
