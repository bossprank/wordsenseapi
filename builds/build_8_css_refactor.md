# Build 8: CSS Refactoring Plan

**Goal:** Refactor the large `static/style.css` into smaller, logically grouped files to improve maintainability and reduce context window usage during UI changes.

**Proposed Structure:**

Create a new directory `static/css/` and split existing styles from `static/style.css` into:

*   `static/css/base.css`: General styles for body, typography, links.
*   `static/css/tables.css`: Styles for `table`, `th`, `td`, and specific table containers/bodies (e.g., `#category-table-container`, `#word-items-table-container`, `#lists-table-body`).
*   `static/css/forms.css`: Styles for `.form-section`, inputs, labels, fieldsets, buttons within forms.
*   `static/css/components.css`: Styles for reusable components like buttons (outside forms), breadcrumbs, error messages, filter/action sections.
*   `static/css/dark_mode.css`: The entire `@media (prefers-color-scheme: dark)` block.
*   `static/css/responsive.css`: The `@media (max-width: ...)` blocks.

**Steps:**

1.  [ ] Analyze current `static/style.css` to confirm logical groupings.
2.  [ ] Analyze `templates/base_adminlte.html` to identify where `static/style.css` is currently linked.
3.  [ ] Create the `static/css/` directory.
4.  [ ] Create the new CSS files (`base.css`, `tables.css`, etc.) within `static/css/`.
5.  [ ] Carefully move the corresponding CSS rules from the original `static/style.css` to the appropriate new files.
6.  [ ] Empty or delete the original `static/style.css`.
7.  [ ] Update the `<link>` tag(s) in `templates/base_adminlte.html` to include the new CSS files in the correct order (e.g., base, tables, forms, components, dark_mode, responsive).
8.  [ ] Test UI rendering across different pages and in dark/light mode to ensure styles are applied correctly and nothing is broken.

**UI Lessons Learned (from previous session):**

*   **Context Cost:** Large monolithic CSS files significantly increase context window usage and associated costs when making iterative UI changes. Modular CSS is more efficient.
*   **Caching:** Browser/environment caching (like IDX preview services) can be very persistent and may ignore standard cache-busting techniques (query parameters, headers). Thorough testing (including hard refreshes) and potentially server restarts might be needed during development. Sometimes, environment-specific cache clearing mechanisms might exist.
*   **CSS Specificity & Globals:** Global CSS rules (e.g., general `td` padding/whitespace) can have unintended broad effects (like overly tall table rows). Use targeted selectors (classes, IDs) for specific components where possible to avoid conflicts and make styling more predictable.
*   **Inline Styles:** Styles applied directly in HTML (`style="..."`) or via JavaScript can be harder to override and manage than class-based styles defined in CSS files. Prefer CSS classes when feasible.
