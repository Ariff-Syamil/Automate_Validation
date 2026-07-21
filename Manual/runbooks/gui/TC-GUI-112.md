# TC-GUI-112 — Detected Gesture Updates Bridge Motor Id

**Component:** Base Panel / Gesture Overlay &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-220
**Run immediately after:** `TC-GUI-110` — do not run any other test case between that one finishing and this one starting.

## Manual Procedure

**Precondition:** System RUNNING; GestureOverlay visible; gesture detection active.

1. Trigger a gesture event (simulate via signal or physical gesture in front of camera)
2. Verify base_gesture_motor_id is set to the expected motor index
3. Verify base_gesture_speed is set to a non-null value
4. Verify base_gesture_stopped reflects the gesture's stop flag

**Record as PASS if:** Bridge gesture properties (motor_id, speed, stopped) are updated matching the detected gesture payload.

**Record as FAIL if:** Properties remain at defaults; gesture detection fires but bridge not updated.
**If it fails:** Verify _handle_gesture_detected bridge update path in base_presenter.py.

### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-GUI-112
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/gui/TC-GUI-112.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-220
```
