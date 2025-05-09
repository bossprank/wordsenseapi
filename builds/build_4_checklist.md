# Build 4 Checklist

**Goal:** Achieve fully functional and visually consistent buttons (including size and font size) using Tailwind CSS as the primary styling mechanism, fix the "Add New Configuration" button, and update the build number.

**I. Functionality Fixes:**

1.  **`static/language_pair_manager.js`:**
    *   [x] Add an event listener for the `add-config-button`.
        *   On click, it should redirect the user to `window.location.href = '/language-pair-config-detail/new';`.

**II. Styling Consistency (Tailwind Prioritization):**

1.  **`static/style.css`:**
    *   [x] **Carefully remove or comment out** all general `button` styling rules (this includes `font-size`, `padding`, `background-color`, `color`, `border`, `border-radius`).
    *   [x] **Carefully remove or comment out** specific button styling rules by ID (e.g., `#cancel-button`) and class (e.g., `.edit-button`) that conflict with Tailwind, especially those affecting `font-size`, `padding`, and other visual properties.

2.  **Verify Button Appearance Post-CSS Changes (Emphasizing Font Size):**
    *   [ ] Review all buttons on all screens (`index.html`, `manage_categories.html`, `manage_language_pairs.html`, `language_pair_config_detail.html`) to ensure they now correctly and consistently display the intended Tailwind styles:
        *   Primary actions (Save, Add, Filter): `bg-indigo-600 text-white px-4 py-2 rounded-md hover:bg-indigo-700`
        *   Secondary/Cancel: `bg-gray-700 text-white px-4 py-2 rounded-md hover:bg-gray-600`
        *   Edit (dynamic): `bg-yellow-500 text-white px-4 py-2 rounded-md hover:bg-yellow-600`
        *   Delete (dynamic): `bg-red-600 text-white px-4 py-2 rounded-md hover:bg-red-700`
    *   [ ] **Crucially, verify that the *font size* is consistent across all buttons (e.g., Save, Cancel, Edit, Delete) on all screens.**
    *   [ ] Confirm all buttons are now consistently sized due to uniform `px-4 py-2` padding *and* consistent font size from Tailwind taking effect.

**III. Build Number Update:**

1.  **All HTML Templates (`index.html`, `manage_categories.html`, `manage_language_pairs.html`, `language_pair_config_detail.html`):**
    *   [x] Update the footer text from "Build: 3" to "Build: 4".

**IV. JavaScript Error Investigation (Low Priority if Linting Only):**

1.  **`templates/language_pair_config_detail.html`:**
    *   [ ] Briefly investigate the linter error on line 89.

**V. Testing & Finalization:**

1.  [ ] Start the Flask server (`flask run`).
2.  [ ] Thoroughly test all buttons on all screens for:
    *   Correct visual appearance (consistent Tailwind styling, **including font size and overall button size**).
    *   Correct functionality.
3.  [ ] Verify "Build: 4" is displayed on all screen footers.
4.  [x] Create `builds/build_4_checklist.md` by copying this plan and marking items as they are completed.
