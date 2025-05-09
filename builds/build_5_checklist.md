# Build 5 Checklist: AdminLTE Integration

## I. Setup and Integration

- [ ] Download AdminLTE `dist/` assets (CSS, JS, fonts) and place them in `static/adminlte/`
- [ ] Include AdminLTE CSS and JS in the base HTML template or each screen
- [ ] Ensure Tailwind and AdminLTE do not conflict (load AdminLTE after Tailwind or scope styles)

## II. Template Refactoring

- [x] Create `templates/base_adminlte.html` with AdminLTE layout (navbar, sidebar, content wrapper)
- [x] Refactor `index.html`, `manage_categories.html`, `manage_language_pairs.html`, and `language_pair_config_detail.html` to extend `base_adminlte.html`
- [x] Move screen-specific content into `{% block content %}` sections

## III. UI Enhancements

- [ ] Replace current buttons with AdminLTE button classes (e.g., `btn btn-primary`, `btn btn-secondary`)
- [ ] Apply AdminLTE form styles to all forms
- [ ] Use AdminLTE cards or boxes for grouping content
- [ ] Add AdminLTE breadcrumbs and headers for each screen

## IV. Footer and Versioning

- [ ] Update footer to match AdminLTE style
- [ ] Ensure screen ID and version are still visible (e.g., in footer or header)

## V. Testing and Validation

- [ ] Start Flask server and verify all screens render correctly
- [ ] Confirm responsiveness and layout integrity
- [ ] Validate that all buttons and forms still function as expected
