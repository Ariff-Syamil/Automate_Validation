# TC-GUI-110 — GestureOverlay Becomes Visible After Play

**Component:** Base Panel / Gesture Overlay &nbsp;·&nbsp; **Priority:** P1 &nbsp;·&nbsp; **Severity:** Major &nbsp;·&nbsp; **Jira:** https://latticesemi.atlassian.net/browse/DSSOL-220
**Also depends on (covered in Phase 1, already automated):** `TC-GUI-020`

## Manual Procedure

**Precondition:** System is RUNNING (Play clicked); CAM1 is live (mock or real); gesture pipeline is available (GestureController module present).


1. Click Play
2. Verify base_gesture_enabled is True on bridge
3. Verify GestureOverlay QML item is visible

**Record as PASS if:** base_gesture_enabled is True; GestureOverlay.visible == True in QML.

**Record as FAIL if:** Overlay not visible even when gesture is enabled; overlay flickers.
**If it fails:** Confirm GestureController is present at backend/gesture_controller.py; check base_gesture_enabled binding in GestureOverlay.qml.


### Recording the result

Once done, add an entry to `automate_5/runs.yaml` consistent with existing entries for this case, e.g.:

```yaml
- test_case_id: TC-GUI-110
  date: 'YYYY-MM-DD'
  work_week: WWxx
  result: PASS   # or FAIL / BLOCKED
  notes: 'Manual run per Manual/runbooks/gui/TC-GUI-110.md.'
  jira_link: https://latticesemi.atlassian.net/browse/DSSOL-220
```
