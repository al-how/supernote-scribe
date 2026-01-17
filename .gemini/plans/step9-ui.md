# Step 9: Streamlit Pages Implementation Plan

## Goal
Implement the user interface for the Supernote Converter application using Streamlit. This involves creating the Scan, Review, and History pages, and updating the Dashboard to show real data.

## Tasks

### 1. Update `app/Home.py` (Dashboard)
-   [ ] Connect to database to fetch real counts for:
    -   Pending Notes (`status='pending'`)
    -   In Review (`status='review'`)
    -   Processed (`status='approved'` or `status='completed'`)
-   [ ] Fetch and display recent activity log (last 5 entries from `history` table or similar).

### 2. Implement `app/pages/1_Scan.py`
-   [ ] **Configuration Section**:
    -   Date Picker for `cutoff_date` (default: today or saved preference).
    -   Folder Checkboxes (WORK, Daily Journal, Other) - filter based on path.
-   [ ] **Scan Action**:
    -   Button "Scan & Process".
    -   Call `scanner.scan_folder()` to find new files.
    -   Display list of found files.
-   [ ] **Process Action**:
    -   Call `processor.process_all()` (or iterate through found notes).
    -   Use `st.status` or `st.progress` to show progress (Exporting -> OCR -> Saving).
    -   Handle errors gracefully.

### 3. Implement `app/pages/2_Review.py`
-   [ ] **Queue Management**:
    -   Fetch notes with `status='review'` from database.
    -   If queue is empty, show "All caught up!" message.
-   [ ] **Review Interface**:
    -   Sidebar or Selectbox to choose a note from the queue.
    -   **Left Column**: Display the generated PNG image.
        -   Need to handle multi-page notes (pagination or scroll).
    -   **Right Column**: Text Area with the extracted text.
        -   Allow user to edit the text.
    -   **Actions**:
        -   "Approve & Save": Updates DB, generates Markdown, moves to `approved`.
        -   "Reject/Ignore": Marks as `rejected` or `ignored`.
        -   "Re-process": (Optional) Re-run OCR with different settings? (Maybe later).

### 4. Implement `app/pages/3_History.py`
-   [ ] **List View**:
    -   Dataframe or Table of all processed notes.
    -   Columns: Date, Filename, Status, Category (Work/Journal), Output Path.
    -   Search bar to filter by filename or content.
-   [ ] **Detail View**:
    -   Clicking a row (or selecting from list) shows details.
    -   Show Final Markdown content (or link to file).
    -   Option to "Re-process" or "Edit" (if we want to allow editing after approval).

## Implementation Details

### Dependencies
-   `app.database`: For querying `notes` table.
-   `app.services.scanner`: For finding files.
-   `app.services.processor`: For running the pipeline.
-   `app.services.exporter`: (Used by processor).
-   `app.config`: For paths and settings.

### Styling
-   Use standard Streamlit widgets.
-   Use `st.columns` for layout.
-   Use `st.toast` for notifications.

## Execution Order
1.  Update `Home.py` to ensure DB connection works and we see "0" stats clearly.
2.  Implement `1_Scan.py` to populate the DB.
3.  Implement `2_Review.py` to process the populated notes.
4.  Implement `3_History.py` to view results.
