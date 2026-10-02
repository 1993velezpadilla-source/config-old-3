# HAYUYA Job Queue

This folder is the simple multi-agent entry point for HAYUYA.

## Human rule

Christian/Felix should not need to understand GitHub Actions.

They can tell an authorized ChatGPT agent:

> Use Hayuya to create this model.

The agent stores/identifies the reference images, then creates exactly one request JSON under:

`hayuya/jobs/requests/<job_id>.json`

with a commit message in this form:

`HAYUYA_JOB <owner> :: <job_id> :: <short title>`

GitHub Actions picks up the request automatically.

## Request schema

```json
{
  "schema": 1,
  "job_id": "christian-zombie-001",
  "owner": "Christian",
  "title": "Police zombie",
  "geometry_input": "assets/characters/zombies/police/front.png",
  "reference_dir": "assets/characters/zombies/police/references",
  "detail_dir": "assets/characters/zombies/police/details",
  "profile": "monster",
  "mode": "character",
  "portable_target": "auto",
  "gpu_vram": 24,
  "backends": "triposg,trellis2,trellis,instantmesh,triposr"
}
```

Optional directories may be empty strings.

## Isolation

Every request writes only to:

`out/hayuya-jobs/<job_id>/`

and uploads a separate GitHub Actions artifact.

Different job IDs are independent. One physical GPU runner processes one heavy job at a time. Multiple matching GPU runners let independent jobs execute in parallel.

## Agent safety rules

- never reuse somebody else's active `job_id`;
- never overwrite another request JSON;
- use names that identify owner + asset;
- references remain authoritative; generated views are support only;
- do not edit another person's result tree;
- a queue request is immutable after submission; submit a new job ID for a revision.
