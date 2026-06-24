# Workflow Orchestration

**Owner:** Ayaan Khan &lt;ayaan.khan2812@gmail.com&gt;

The stateful execution engine that turns agents into multi-step, controllable
workflows — the most complex subsystem in the project.

## Scope

- **Execution engine** — executor, graph builder, node runner, and run state
  (`backend/app/core/workflow/`).
- **Execution control** — pause, resume, and terminate a running workflow
  mid-flight (`backend/app/services/execution_control.py`).
- **Scheduled triggers** — time-based workflow runs via the worker/task layer
  (`backend/app/worker/`, migration `005_workflow_schedules`).
- **Human-in-the-loop** — approval gating over Slack and the UI before a run
  proceeds.
- **Observability** — logging, monitoring, and trace views for executions
  (`frontend/components/monitoring/`, `frontend/components/workflows/ExecutionMonitor.tsx`).

## Highlights

- Built pause/resume/terminate semantics over persisted execution state.
- Added scheduled triggers and a human approval step into the run lifecycle.
- Shipped logging, monitoring, and trace visualization for live executions.
