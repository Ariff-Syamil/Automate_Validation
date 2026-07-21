# TC-GUI-111 — GestureOverlay Hides After Stop

**Component:** Base Panel / Gesture Overlay &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-220
**Run immediately after:** `TC-GUI-110` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** System is RUNNING; GestureOverlay is visible.

1. Click Stop
2. Verify base_gesture_enabled is False on bridge
3. Verify GestureOverlay.visible == False

**Record as PASS if:** Overlay is no longer visible; gesture pipeline stopped.
**Record as FAIL if:** Overlay remains visible after Stop; gesture continues processing frames.
**If it fails:** Check _handle_stop in base_presenter.py; verify gesture.stop() is called.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-GUI-111
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/gui/TC-GUI-111.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-220
```
