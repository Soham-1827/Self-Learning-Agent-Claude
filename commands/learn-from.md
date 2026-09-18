---
description: Turn a YouTube video or channel into a vault note plus setup proposals awaiting your approval
argument-hint: <youtube-url | @handle>
---

Use the `learn-from-source` skill to process: $ARGUMENTS

Follow it exactly. Build the brief, classify the source, reconcile entity names
against the description links, check against what is already installed, write
the validated synthesis, and render the note.

If the argument is a channel (`@handle` or a channel URL), follow the skill's
**Channels** section: triage with `sla queue`, let me pick, process the picks one
video at a time, then write a digest with `sla digest`.

Stop after the note (or digest) is written. Report its path and a one-line summary
of each proposal with its risk tier. Do not install anything.
