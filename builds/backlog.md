# Development Backlog

This file lists pending tasks, UI issues, and testing items identified during development that should be addressed in future builds.

## UI Issues & Refinements

*   [ ] **Table Row Height:** Investigate and fix the excessive vertical height of table rows on the "View Generated Lists" page (`#lists-table-body td`) and the "List Details" page (`#word-items-table-container .table td`). Ensure rows are compact while content remains readable.
*   [ ] **Button Alignment (List View):** Fix the vertical stacking of action buttons in the "Actions" column on the "View Generated Lists" page. They should align horizontally or responsively based on screen size.
*   [ ] **Detail Page Formatting:** Further investigate and fix any remaining formatting issues on the "List Details" page beyond row height (e.g., ensure long text fields like prompts/schemas scroll correctly within their containers).

## Testing

*   [ ] **"Regenerate" Flow:** Explicitly test the end-to-end flow for the "Regenerate" button on the "View Generated Lists" page to ensure it correctly pre-populates the generation form.
*   [ ] **Comprehensive Testing:** After major refactoring (like Build 8 CSS and Build 9 Python), perform thorough testing covering:
    *   All API endpoints.
    *   All UI screens and interactions.
    *   End-to-end user flows (create, view, detail, edit, regenerate, delete).
    *   Dark mode rendering.
    *   Responsiveness.

## Environment & Configuration

*   [ ] **Verify `lsof`:** After reloading the IDX environment with the updated `.idx/dev.nix`, confirm that the `lsof` command is available in the terminal to ensure the `devserver.sh` script's port clearing works as intended.
*   [ ] **Logging Review:** Review application logs (`mylogs/`) during testing to ensure adequate information is captured for debugging and monitoring. Enhance logging if necessary.
*   [ ] **Error Handling Review:** Review user-facing error messages and backend error handling for clarity and robustness.
