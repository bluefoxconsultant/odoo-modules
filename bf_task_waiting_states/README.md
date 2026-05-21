# Task Waiting States (`bf_task_waiting_states`)

Adds two project task states — **Attente - Client** and **Attente - Externe**
— so a task can be marked as blocked while waiting on a client or a third
party, distinct from the standard in-progress / done states.

## What it does

- Extends the task kanban state selection (client-side patch) with the two
  "waiting" states.
- Lets reporting and filters distinguish work that is stalled on an external
  party from work that is actively in progress.

## Dependencies

`project`.

## Licence

Distributed under **LGPL-3**. See the `LICENSE` file.
