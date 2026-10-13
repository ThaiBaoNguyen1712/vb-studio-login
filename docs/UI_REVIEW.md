# UI Review and Remediation Brief

This document is a preserve-first UI audit for the VB-Studio Login WebView UI. The goal is to modernize accessibility, responsiveness, rendering safety, and visual consistency without changing the operational workflows or information architecture.

## 1. Design Read

Reading this as an internal Vietnamese operations dashboard for content-team operators, with a trust-first, dense product-UI language. This is not a marketing page. Preserve the dashboard/table/drawer workflows and improve semantics, robustness, and visual discipline rather than restyling from scratch.

## 2. Current and Target Design Dials

| Dial | Current | Target | Reason |
|---|---:|---:|---|
| DESIGN_VARIANCE | 3/10 | 4/10 | Keep the predictable operator structure; add clearer hierarchy and improve overlay/drawer composition. |
| MOTION_INTENSITY | 4/10 | 3/10 | Keep only purposeful feedback: overlay transitions, toasts, progress, state changes. |
| VISUAL_DENSITY | 8/10 | 7/10 | Preserve density, but raise minimum text and target sizes and reduce filter clutter. |

## 3. Implementation Order

1. Replace unsafe dynamic rendering and centralize overlay behavior.
2. Add focus-visible styles and correct dialog, popover, tab, and sorting semantics.
3. Make the shell, header, drawer, and modals responsive.
4. Introduce semantic design tokens and migrate the theme engine.
5. Unify global and view-local filters and correct dynamic header titles.
6. Increase type and interactive target sizes.
7. Add inline validation and semantic progress/live states.
8. Normalize copy and terminology.
9. Add reduced-motion and forced-colors support.
10. Complete visual, keyboard, screen-reader, and contrast regression testing.

## 4. P0 Findings

### P0.1 Dialogs and drawer lack semantics and focus management

Affected:

- Confirm/prompt overlay: `src/web/index.html:266-280`
- CRUD modals: `src/web/index.html:874-1081`
- Update modal: `src/web/index.html:1114-1159`
- Channel drawer: `src/web/index.html:857-868`
- Confirm behavior: `src/web/js/ui.js:86-124`
- Drawer behavior: `src/web/js/channel_drawer.js:11-31`

Problems:

- Plain `div` overlays are presented as dialogs.
- Focus does not move into overlays when opened.
- Focus is not trapped while open.
- Escape behavior and focus return are incomplete.
- Background content remains interactive.

Required fix:

- Build one shared overlay controller for modal dialogs and the drawer.
- Use `role="dialog"` and `aria-modal="true"` for blocking dialogs.
- Give every overlay an accessible name from its visible title.
- Move focus to the first sensible focusable element on open.
- Trap focus while open.
- Close dismissible overlays with Escape.
- Return focus to the opener after close.
- Keep long content scrollable inside a maximum-height panel.

### P0.2 Unsafe runtime interpolation through innerHTML

Affected examples:

- Channel cards and attributes: `src/web/js/dashboard.js:53-94`
- Filter chips including search text: `src/web/js/dashboard.js:103-126`
- Account columns and metadata: `src/web/js/dashboard.js:317-375`
- Table rows and attributes: `src/web/js/table.js:116-191`
- Social registry rows: `src/web/js/socials.js:63-81`
- Drawer fields: `src/web/js/channel_drawer.js:50-74`
- Notification panel: `src/web/js/presence.js:181-202`
- Vault rows: `src/web/js/vault.js:20-31`
- Trash rows: `src/web/js/trash.js:12-33`

Problems:

- Runtime names, IDs, URLs, errors, and user input are interpolated into markup and attributes.
- Some paths escape only `<`, leaving quotes and other characters unsafe.
- Interpolated inline handlers can expose malformed or unsafe markup paths.

Required fix:

- Prefer DOM construction with `createElement` and `textContent` for dynamic text.
- Validate or normalize URLs and attribute values before assignment.
- Remove inline handlers built with runtime IDs.
- Add test fixtures containing `<`, `>`, `"`, `'`, backticks, and Vietnamese diacritics.

### P0.3 Focus visibility is insufficient

Affected examples:

- Header search: `src/web/index.html:300-301`
- Confirm input: `src/web/index.html:272-273`
- Table search: `src/web/index.html:433-434`
- Modal fields: `src/web/index.html:881-889`, `979-1008`, `1052-1073`

Problem:

- Inputs rely on `outline-none` plus subtle border changes.
- Most buttons do not define a visible focus indicator.

Required fix:

- Add a global focus-visible treatment using the active accent token.
- Use an offset ring with contrast in every theme and mode.
- Never rely on border color alone.

## 5. P1 Findings

### P1.1 Shell is desktop-only

Affected:

- Body shell classes: `src/web/index.html:41`
- Fixed sidebar: `src/web/index.html:121`
- Hover-only expansion: `src/web/css/base.css:46-54`
- Header row and fixed-width controls: `src/web/index.html:283-333`

Required behavior:

- Desktop: persistent sidebar with explicit collapsed and expanded states.
- Tablet: icon rail with clear labels on expansion.
- Narrow widths: off-canvas navigation with a visible menu trigger.
- Header search and secondary actions remain reachable.
- Main content remains the only primary scroll container.

### P1.2 Modals can clip on short viewports

Affected:

- Add account: `src/web/index.html:875-921`
- Edit account: `src/web/index.html:924-966`
- Platform dialog: `src/web/index.html:969-1016`
- Edit channel: `src/web/index.html:1042-1081`

Required fix:

- Constrain panel height to the viewport.
- Scroll long body content internally.
- Keep primary actions reachable without scrolling the page behind the modal.

### P1.3 Sorting is mouse-only

Affected:

- Channel table headers: `src/web/index.html:455-458`
- Social table headers: `src/web/index.html:496-499`
- Sort indicators: `src/web/js/table.js:34-45`, `src/web/js/socials.js:25-30`

Required fix:

- Render actual buttons inside sortable headers.
- Support keyboard activation.
- Expose current sort with `aria-sort`.
- Keep the visual indicator meaningful without color alone.

### P1.4 Navigation, tabs, and segmented controls lack selected semantics

Affected:

- Main navigation: `src/web/js/app.js:153-176`
- Settings tabs: `src/web/index.html:607-614`, `src/web/js/settings.js:3-15`
- Drawer tabs: `src/web/js/channel_drawer.js:137-143`
- Dashboard sort/status/display controls: `src/web/js/dashboard.js:399-445`

Required fix:

- Main navigation: `aria-current="page"` on the active item.
- Tabs: tablist, tab, and tabpanel semantics with arrow-key support.
- Toggle groups: `aria-pressed` for single-choice segmented states.

### P1.5 Status feedback is not announced

Affected:

- Toast container: `src/web/index.html:248-249`, `src/web/js/ui.js:133-159`
- Blocking loader: `src/web/index.html:237-246`
- Bulk progress: `src/web/index.html:261-263`
- Health progress: `src/web/index.html:525-532`
- Update progress: `src/web/index.html:1137-1144`

Required fix:

- Toast container: polite live region, assertive only for blocking failures.
- Blocking surfaces: `aria-busy="true"` plus a textual state.
- Progress: `role="progressbar"` with `aria-valuemin`, `aria-valuemax`, and `aria-valuenow`.
- Prevent duplicate pending feedback for one operation.

### P1.6 Selectable operational text is blocked

Affected:

- Body-level `select-none`: `src/web/index.html:41`

Required fix:

- Remove the body-level rule.
- Apply narrow restrictions only to buttons, labels, and decorative UI.
- Keep IDs, emails, URLs, reports, release notes, and error text selectable.

### P1.7 Typography and hit targets are too small

Affected examples:

- 9px verified label: `src/web/index.html:144`
- 10px labels: `src/web/index.html:157`, `177`, `323`
- 27px sidebar control: `src/web/index.html:130`
- 28px scroll controls: `src/web/index.html:398-399`
- 28px generated request controls: `src/web/js/presence.js:185-188`

Required minimums:

- No meaningful text below 12px.
- Interactive targets at least 36 by 36 px on desktop.
- Touch-equivalent targets at least 44 by 44 px.

### P1.8 Motion ignores reduced-motion preference

Affected:

- Sidebar and drawer transitions: `src/web/css/base.css:42-49`
- Smooth scrolling: `src/web/js/dashboard.js:448-470`, `src/web/js/health.js:126-127`
- Pulse, ping, and spin states across login, presence, and loading.

Required fix:

- Add a global `prefers-reduced-motion: reduce` policy.
- Disable decorative pulse, ping, smooth scroll, and looping movement.
- Keep textual and static state indicators when motion is removed.

## 6. P2 Findings

### P2.1 Filters are split across layers without visibility

Current:

- Sidebar platform filter: `src/web/index.html:204-208`
- Header search and account filter: `src/web/index.html:296-307`
- Dashboard sort/status/display: `src/web/index.html:363-401`
- Table-local filters: `src/web/index.html:430-448`
- Table inherits global filters: `src/web/js/table.js:47-79`

Fix:

- Choose one model: a shared query object, or explicit per-view filters.
- Show all inherited active filters as removable chips in the affected view.
- Ensure "clear all" removes every condition affecting the rendered result.
- Empty states must distinguish no data from no matches.

### P2.2 Header title does not follow view changes

Affected:

- Static title: `src/web/index.html:285`
- Class-only view switch: `src/web/js/app.js:153-176`

Fix:

- Maintain a view-to-title map.
- Include useful counts where appropriate.
- Update the document title only when it adds meaningful context.

### P2.3 Theme engine overrides utilities with important

Affected:

- Theme utility overrides: `src/web/js/themes.js:60-129`
- Theme registry: `src/web/js/themes.js:3-46`

Fix:

- Replace utility-selector overrides with semantic CSS variables.
- Define tokens for accent, surface, surface-elevated, border, input, text, and status colors.
- Keep status colors semantically separate from the brand accent.
- Preserve all six themes and their light/dark modes.

### P2.4 Status relies on dots, color, and tooltips

Affected:

- Channel status dot: `src/web/js/dashboard.js:51-58`
- Presence dot: `src/web/js/dashboard.js:67-71`

Fix:

- Show compact visible status text for channel state and presence.
- Provide screen-reader status without depending on `title`.
- Verify meaning in grayscale.

### P2.5 Validation is toast-only

Affected:

- Account validation: `src/web/js/accounts.js:132-175`
- Form labels: `src/web/index.html:879-889`, `978-1008`, `1051-1073`

Fix:

- Associate every label with its input.
- Add required and format expectations in visible helper text.
- Render inline errors beneath the relevant field.
- Set `aria-invalid` and `aria-describedby`.
- Focus the first invalid field on submit.
- Preserve user input after failed submission.

### P2.6 Switches and checkbox targets are weak

Affected:

- Appearance switch: `src/web/index.html:220-226`
- Settings checkboxes: `src/web/index.html:682`, `767`, `816`, `828`

Fix:

- Use switch semantics with `aria-checked` where the control represents on/off.
- Make the full row activatable where appropriate.
- Enforce target size and visible focus.

### P2.7 Notification popover lacks disclosure semantics

Affected:

- Trigger and panel: `src/web/index.html:319-332`
- Toggle and outside click: `src/web/js/presence.js:318-330`

Fix:

- Add `aria-expanded` and `aria-controls`.
- Support Escape to close.
- Return focus to the trigger.
- Keep the panel scrollable and responsive.

### P2.8 Loading feedback is inconsistent

Examples:

- Duplicate indicator and toast for update checks: `src/web/js/settings.js:76-79`
- Duplicate toast and loader for launches: `src/web/js/table.js:306-315`

Fix:

- Define one feedback policy per operation class.
- Inline pending state for button-owned work.
- Non-blocking indicator for background work.
- Blocking loader only for work that prevents interaction.
- Completion or failure feedback exactly once.

### P2.9 Copy needs normalization

Examples:

- "Tất cả Google Acc" and "Thêm Acc": `src/web/index.html:306`, `310-312`
- "card" count: `src/web/js/dashboard.js:330`
- Absolute safety claim: `src/web/index.html:518`
- "không nguy cơ khóa acc": `src/web/js/health.js:229-233`
- "Bạn không giam phiên nào": `src/web/js/presence.js:275-280`

Glossary:

- Acc: tài khoản
- Card: thẻ kênh
- Run: đợt kiểm tra
- Report: báo cáo
- Setup: thiết lập
- Copy: sao chép
- Platform: nền tảng

Also replace absolute safety promises with factual descriptions of what the app does and does not do.

### P2.10 Login screen uses generic glow treatment

Affected:

- Blue/purple glow and gradient text: `src/web/index.html:48-60`

Fix:

- Preserve the centered auth flow and functional states.
- Retire the generic glow language.
- Align the auth gate with active theme tokens and the product's operator-first character.

## 7. Preserve

- Card dashboard plus dense table as complementary views.
- Horizontal account-column power layout.
- Four-state channel status model.
- Presence, heartbeat, and access-request workflow.
- Secondary actions in the channel drawer.
- Existing loading, empty, error, and progress coverage.
- Six-tab settings organization.
- Six themes and light/dark mode support.
- Trash recovery workflow.
- Vendored offline dependencies.

## 8. Retire or Replace

- Body-level `select-none`.
- Hover-only sidebar expansion.
- `<th onclick>` sorting.
- Unsafe `innerHTML` interpolation.
- `!important` utility-selector theming.
- Desktop-only fixed shell at compact widths.
- Unlabelled overlay `div` patterns.
- Toast-only validation.
- Tooltip and color-only status.
- Generic login glow.
- 9 to 10px meaningful text.
- Sub-36px interactive targets.
- Absolute safety claims.

## 9. Accessibility Acceptance Checks

- Every modal and drawer has `role="dialog"` and, when blocking, `aria-modal="true"`.
- Every overlay has a programmatic label.
- Focus moves into overlays when opened.
- Focus remains trapped while an overlay is open.
- Escape closes dismissible overlays.
- Focus returns to the opener.
- Background content is inert while a modal is open.
- All interactive elements have a clearly visible focus ring in every theme.
- Sortable headers are buttons and expose `aria-sort`.
- Navigation exposes `aria-current`.
- Tabs expose tablist, tab, and tabpanel semantics.
- Toasts use appropriate live regions.
- Progress bars expose current, minimum, and maximum values.
- Forms have associated labels, inline errors, `aria-invalid`, and first-invalid focus.
- Status is understandable without color or tooltips.

## 10. Layout and Responsive Checks

- No clipping at 360 by 640, 768 by 768, 1024 by 600, 1280 by 720, and 1440 by 900.
- Sidebar is usable without hover.
- Compact viewports use off-canvas navigation.
- Header actions remain reachable at every supported width.
- Long modal content scrolls internally.
- Interface remains usable at 200 percent zoom and 125 percent OS scaling.

## 11. Token, Motion, and Rendering Checks

- All colors use semantic variables.
- Accent and status tokens are separate.
- All six themes render correctly in supported modes.
- No meaningful text is below 12px.
- Interactive targets are at least 36 by 36 px on desktop and 44 by 44 px for touch.
- Radius and elevation follow one documented hierarchy.
- Runtime values render through `textContent` or safe escaping.
- HTML-special characters display literally.
- Inline handlers built with runtime IDs are removed.
- `prefers-reduced-motion: reduce` disables decorative and persistent motion.
- Forced-colors mode remains usable.

## 12. Product Behavior Checks

- Header title updates for every view.
- All active filters affecting a view are visible in that view.
- "Clear all" clears every condition affecting the rendered result.
- Empty states distinguish no data from no filter matches.
- Copy follows the terminology glossary.
- Copy avoids absolute safety claims.
- Keyboard-only walkthroughs cover login, navigation, filtering, CRUD, drawer, health, settings, and notifications.
- Screen-reader walkthroughs cover dialogs, forms, tables, toasts, and status changes.
- Contrast is measured in every theme and mode.
