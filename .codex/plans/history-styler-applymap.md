# History Styler applymap fix

## Issue

The live History page fails with:

`AttributeError: 'Styler' object has no attribute 'applymap'`

The failing line is in `app/pages/3_History.py`, where pandas Styler uses `applymap` for the status column.

## Root cause

The deployed pandas version no longer exposes `Styler.applymap`. Newer pandas uses `Styler.map` for element-wise styling. The app should prefer `map` while keeping an `applymap` fallback for older pandas versions.

## Plan

1. Add a focused test that simulates a pandas Styler without `applymap`.
2. Add a small status styling helper in `app/styles.py`.
3. Update `app/pages/3_History.py` to use the helper.
4. Run the focused test and relevant test suite.

