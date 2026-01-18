# Review Pipeline Improvements Plan

## User Stories

### US1: Reject Notes Without Losing Records
**As a** user reviewing notes
**I want to** reject a note and remove it from the review queue
**So that** I can skip notes I don't want to process while keeping a record of what was rejected

**Acceptance Criteria:**
- Clicking "Reject" shows a confirmation dialog
- Confirming rejection sets status to "rejected" (not deleted)
- Note disappears from Review Queue
- Note appears in History with "rejected" status
- **Rejected notes can be moved back to Review queue** (recovery from accidental rejection)

---

### US2: Edit Previously Approved Notes
**As a** user browsing my note history
**I want to** edit the extracted text of any approved note
**So that** I can fix errors I discover later without reprocessing the entire note

**Acceptance Criteria:**
- History page shows an "Edit" button for approved/auto_approved notes
- Clicking Edit shows PNG on one side, editable text on the other
- Saving updates the markdown file (overwrites existing) and preserves the original OCR text
- I can see both rejected and approved notes in History
- **Editing an auto_approved note changes its status to "approved"** (distinguishes AI-only from human-verified)

---

### US3: Track Changes for Future Improvements
**As a** developer improving OCR quality
**I want to** compare original OCR output vs user-edited text
**So that** I can identify common OCR errors and improve the system

**Acceptance Criteria:**
- Original OCR text (`raw_text`) is never overwritten
- User edits are stored separately (`edited_text`)
- Both values are preserved even after re-editing
- Status distinguishes: `auto_approved` (AI-only) vs `approved` (human-verified)

---

## Summary

Implement three improvements to the review pipeline:
1. Fix the broken Delete button in Review page (use "rejected" status instead of delete)
2. Add Edit capability to History page for re-reviewing approved notes
3. Preserve before/after change tracking (already exists, just verify it works)

---

## Changes

### 1. Database: Add Status Helper Functions

**File:** [database.py](app/database.py)

Add new functions after `mark_note_error()` (~line 566):

```python
def mark_note_rejected(note_id: int) -> None:
    """Set status to 'rejected' - removes from queue but keeps record."""
    update_note_status(note_id, "rejected")


def move_note_to_review(note_id: int) -> None:
    """Move a rejected or approved note back to review queue."""
    update_note_status(note_id, "review")
```

---

### 2. Review Page: Fix Delete Button

**File:** [2_Review.py](app/pages/2_Review.py)

**Problem:** Lines 146-150 use nested buttons which don't work in Streamlit (the inner button only appears after clicking outer, but then a rerun clears it).

**Solution:** Use session state for confirmation dialog.

**Changes:**

1. Add session state initialization at top of file (after imports):
```python
# Initialize session state for delete confirmation
if "confirm_delete" not in st.session_state:
    st.session_state.confirm_delete = None
```

2. Replace lines 145-150 (the c3 column with Delete button) with:
```python
with c3:
    if st.session_state.confirm_delete == note_id:
        # Show confirmation buttons
        st.warning("Are you sure?")
        conf_col1, conf_col2 = st.columns(2)
        with conf_col1:
            if st.button("Yes, Reject", type="primary", use_container_width=True):
                mark_note_rejected(note_id)
                st.session_state.confirm_delete = None
                st.toast("Note rejected")
                st.rerun()
        with conf_col2:
            if st.button("Cancel", use_container_width=True):
                st.session_state.confirm_delete = None
                st.rerun()
    else:
        if st.button("🗑️ Reject", type="secondary", use_container_width=True):
            st.session_state.confirm_delete = note_id
            st.rerun()
```

3. Update imports to include `mark_note_rejected` (can remove `delete_note` if no longer used elsewhere).

---

### 3. History Page: Add Edit and Recovery Capabilities

**File:** [3_History.py](app/pages/3_History.py)

**Approach:** Add action buttons in the detail view for editing and status recovery.

**Changes:**

1. Add imports at top:
```python
from app.database import get_extractions_for_note, update_extraction_text, move_note_to_review
from app.services.markdown import approve_and_save_note
```

2. Add session state for edit mode:
```python
if "editing_note_id" not in st.session_state:
    st.session_state.editing_note_id = None
```

3. In the detail view section (after line 95), add action buttons:

**For rejected notes:** Show "↩️ Move to Review" button
- Calls `move_note_to_review(note_id)`
- Shows success message, reruns page

**For approved/auto_approved notes:** Show "✏️ Edit" button
- Sets `st.session_state.editing_note_id = selected_note['id']`
- Shows PNG + editable text side-by-side (reuse pattern from 2_Review.py)
- "Save Changes" button:
  - Updates extractions via `update_extraction_text()`
  - Calls `approve_and_save_note()` (overwrites markdown file)
  - Status changes to "approved" (human-verified)
- "Cancel" button clears edit mode

4. Update status filter defaults to include "rejected":
```python
default=["approved", "auto_approved", "rejected"]
```

---

### 4. Markdown Service: Ensure Status Update on Re-save

**File:** [markdown.py](app/services/markdown.py)

**Verified:** `save_markdown()` uses `write_text()` which correctly overwrites existing files. Output path is calculated from stored `output_folder` and `file_name`, so no duplicate files are created.

**Verified:** `approve_and_save_note()` calls `mark_note_approved()` which sets status to "approved", so editing an `auto_approved` note will correctly change it to `approved`.

No changes needed - existing behavior is correct.

---

### 5. Change Tracking Verification

**Already implemented:** The `extractions` table stores:
- `raw_text` - Original OCR output (immutable)
- `edited_text` - User edits (nullable)

**Verify:** When re-editing an already-approved note:
- `raw_text` should remain unchanged (original OCR)
- `edited_text` should be updated with new edits
- `get_aggregated_text(use_edited=True)` prefers edited_text

This is already working correctly. No changes needed.

---

## Files to Modify

| File | Change |
|------|--------|
| [database.py](app/database.py) | Add `mark_note_rejected()` and `move_note_to_review()` functions |
| [2_Review.py](app/pages/2_Review.py) | Fix reject button with session state confirmation |
| [3_History.py](app/pages/3_History.py) | Add edit mode for approved notes, recovery for rejected notes |

---

## Verification

1. **Test Reject in Review page (US1):**
   - Process a note to review queue
   - Click Reject → confirm → verify note appears in History with "rejected" status
   - Verify note is NOT deleted from database

2. **Test Recovery from Rejection (US1):**
   - In History, filter by "rejected"
   - Click "Move to Review" on a rejected note
   - Verify note appears back in Review Queue

3. **Test Edit in History page (US2):**
   - Select an `auto_approved` note
   - Click Edit → modify text → Save
   - Verify markdown file is updated (not duplicated)
   - Verify status changed from `auto_approved` to `approved`
   - Verify `raw_text` unchanged, `edited_text` updated

4. **Test Change Tracking (US3):**
   - Query database to confirm `raw_text` preserved after edits
   - Compare `raw_text` vs `edited_text` to see what user changed
