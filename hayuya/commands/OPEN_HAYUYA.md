# OPEN HAYUYA command contract

This is an authoritative HAYUYA agent command.

## Trigger

When Christian or Felix/Volnox says any clear equivalent of:

- `open hayuya`
- `abre hayuya`
- `open hayuya studio`
- `abre hayuya studio`

the agent must treat it as an ACTION command, not a question.

## Required behavior

1. Do not explain how GitHub Actions, runners, LAN IPs, or the queue work.
2. Do not answer with setup instructions unless startup actually failed.
3. Resolve the current HAYUYA GUI workspace URL from `hayuya/workspace.json`.
4. Verify that URL is the GUI workspace, not the GitHub Issue fallback.
5. If the GUI is online, reply with the direct clickable GUI link.
6. If the GUI deployment is missing/offline, trigger/repair the GUI deployment when the connected deployment provider allows it, then return the GUI URL.
7. Only if GUI hosting is genuinely unavailable may the agent return the GitHub Hub fallback, clearly labeled as fallback.
8. Never require Christian or Felix to type a LAN IP, run a terminal command, or understand GitHub Actions for the normal open flow.

## Identity / multi-user behavior

The same GUI is shared, but jobs are isolated by immutable `job_id`.

- Christian can have several independent jobs.
- Different Christian agents can submit different jobs simultaneously.
- Felix/Volnox submits from his separate workspace/repository and the bridge relays into the same central queue.
- Opening HAYUYA must never cancel or replace another user's active job.

## Response contract

Normal successful response should be intentionally tiny:

> HAYUYA is open: <GUI LINK>

No architecture explanation unless explicitly requested.
