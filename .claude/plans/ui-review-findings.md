# UI Review Findings - Commit db199a0

## Summary

Code review of commit db199a0 (review pipeline improvements) and live UI testing revealed bugs and UX improvements.

---

## Bugs

### Bug 1: Undefined `delete_note` in Review Page

**File:** `app/pages/2_Review.py:68`

**Problem:** The import was changed from `delete_note` to `mark_note_rejected`, but line 68 still calls `delete_note()`:

```python
if not extractions:
    st.error("⚠️ Note has no extracted pages. It might have failed processing.")
    if st.button("Delete Note"):
        delete_note(note_id)  # ← NameError: delete_note is not defined
        st.rerun()
```

**Impact:** If a note has no extractions and user clicks "Delete Note", the app crashes.

**Fix:**
```python
if st.button("Delete Note"):
    mark_note_rejected(note_id)  # Use the new function
    st.rerun()
```

---

### Bug 2: Suspicious Indentation in History Page

**File:** `app/pages/3_History.py:205-232`

**Problem:** The `with col1:` and `with col2:` blocks appear to be outside the `else:` block:

```python
    else:
        # Normal Detail View (not editing)
        col1, col2 = st.columns([1, 1])

    with col1:  # ← This is at same indent as 'else', so it's OUTSIDE
        st.markdown("**Metadata**")
```

**Expected behavior:** When in edit mode, `col1` is undefined, so `with col1:` should raise NameError.

**Observed behavior:** UI works correctly in testing. Streamlit may be handling this gracefully, or the code flow prevents the issue.

**Status:** Monitor - may not be causing issues in practice, but should be fixed for correctness.

**Fix:** Indent lines 209-232 to be inside the `else:` block:
```python
    else:
        # Normal Detail View (not editing)
        col1, col2 = st.columns([1, 1])

        with col1:
            st.markdown("**Metadata**")
            # ... rest of col1 content

        with col2:
            st.markdown("**Content Preview**")
            # ... rest of col2 content
```

---

## UX Issues

### Issue 1: Status Filter Labels Truncated

**Location:** History page, Status multiselect

**Problem:** Filter chips show "ap...", "au...", "re..." which are hard to read.

**Fix options:**
1. Use shorter status names in the filter
2. Add custom CSS to increase chip width
3. Use abbreviations: "Appr", "Auto", "Rej"

---

### Issue 2: Duplicate Cancel Buttons in Edit Mode

**Location:** History page, Edit mode

**Problem:** Two cancel buttons exist:
- "Cancel Edit" at top (action bar)
- "Cancel" at bottom (save bar)

**Fix:** Remove the bottom Cancel button, or rename to "Discard Changes" with different semantics.

---

### Issue 3: Content Preview Uses Editable-Looking Textarea

**Location:** History page, detail view (non-edit mode)

**Problem:** `st.text_area()` is used for read-only display, which looks editable.

**Fix:** Use `st.code()` or `st.markdown()` for read-only content display:
```python
st.code(content, language="markdown")
# or
st.markdown(f"```markdown\n{content}\n```")
```

---

### Issue 4: No "Move to Review" for Auto-Approved Notes

**Location:** History page

**Problem:** Users can only edit auto_approved notes, not send them to review queue for later.

**Fix:** Add "Move to Review" button for `auto_approved` status (same as for `rejected`):
```python
if selected_note['status'] in ['rejected', 'auto_approved']:
    if st.button("↩️ Move to Review", ...):
        move_note_to_review(note_id)
```

---

### Issue 5: No Pagination on History Table

**Location:** History page

**Problem:** Limit defaults to 50 with no visible pagination.

**Fix:** Add pagination controls or use Streamlit's built-in pagination when available.

---

## Minor Issues

| Issue | Location | Notes |
|-------|----------|-------|
| Unused `action_col3` | 3_History.py:110 | Defined but never used |
| OCR quality | Florida.note | Shows "boner boner boner" - model tuning needed |

---

## Verification Checklist

After fixes:

- [ ] Review page: Click "Delete Note" on a note with no extractions - should not crash
- [ ] History page: Enter edit mode, verify no duplicate content appears
- [ ] History page: Status filter chips are readable
- [ ] History page: Cancel buttons are not redundant
- [ ] History page: Content preview doesn't look editable in normal view

---

## Files to Modify

| File | Changes |
|------|---------|
| `app/pages/2_Review.py` | Line 68: Replace `delete_note` with `mark_note_rejected` |
| `app/pages/3_History.py` | Lines 209-232: Fix indentation to be inside `else:` block |
| `app/pages/3_History.py` | Optional: Remove duplicate Cancel button |
| `app/pages/3_History.py` | Optional: Change text_area to code block for preview |
