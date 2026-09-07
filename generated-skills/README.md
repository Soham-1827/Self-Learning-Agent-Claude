# Generated skills

Skills authored by the pipeline land here **before** they are live.

They are ordinary tracked files, so `git diff` shows you exactly what was written
before any of it takes effect, and `git revert` undoes a skill built on advice that
turned out to be wrong.

Nothing in this directory is active until you run:

```bash
sla apply
```

which copies the approved skill into `~/.claude/skills/`. See PLAN.md §8 Rule 6.
