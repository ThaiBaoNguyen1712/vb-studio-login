# VB-Studio Login WebView Frontend UI Architecture & Design Guidelines

This authoritative technical documentation outlines the architectural standards, visual ergonomics, security protocols, accessibility mechanics, and responsive design systems governing the VB-Studio Login desktop WebView client (`src/web/`).

---

## 1. Overview & Architecture

### 1.1 Context & Mission
VB-Studio Login is an operator-facing desktop application running within a Python PyWebView shell. It coordinates multi-channel social media profiles, native browser automation lifecycles, and security vaults for enterprise content teams in Vietnam. The frontend interface communicates bidirectionally with the Python runtime through `window.pywebview.api`.

Because operators spend 8–10 consecutive hours navigating high-density channel grids, multi-profile account tables, and diagnostic drawers, the UI architecture prioritizes:
1. **Absolute Rendering Security**: Zero execution of unescaped runtime data or untrusted server inputs.
2. **Predictable Operator Ergonomics**: Fast keyboard navigation, robust focus traps, and low-latency rendering.
3. **Information Integrity**: Crisp contrast ratios across both Dark and Light themes with unambiguous status indicators.
4. **Resilient Responsive Shell**: Continuous functionality across extreme viewport ranges from ultra-compact displays (360×640, 1024×600) to standard workstations (1440×900).

### 1.2 Technology Stack & Module Boundaries
The frontend stack relies strictly on native browser standards and pre-bundled assets, requiring zero external runtime CDNs:
- **Core Markup**: Semantic HTML5 (`src/web/index.html`) structured with WAI-ARIA landmark and widget roles.
- **Styling Architecture**: Tailwind CSS offline utility classes supplemented with CSS Custom Property semantic design tokens (`src/web/css/base.css`).
- **Application Logic**: Modular vanilla JavaScript (`src/web/js/`) organized by operational domains:
  - `ui.js`: DOM sanitization utilities, `escapeHtml`, safe builder `createElement`, toast notifications, and centralized `OverlayController`.
  - `themes.js`: Theme token registry, dynamic stylesheet generator, and Dark/Light mode engine.
  - `app.js`: Global application lifecycle, responsive shell coordinator, dynamic view transitions, and filter synchronization.
  - `dashboard.js`: Channel card grid view, grouping, and multi-profile column layouts.
  - `table.js`: High-density tabular channel view with multi-column keyboard sorting and row actions.
  - `channel_drawer.js`: Slide-over drawer presenting detailed channel telemetry, cookie status, and configuration.
  - `accounts.js`: Modal dialogs for adding/editing platform accounts with inline validation.
  - `presence.js`, `vault.js`, `trash.js`, `health.js`, `socials.js`, `settings.js`: Domain-specific view controllers.

### 1.3 Desktop WebView Environment Constraints
Running inside PyWebView introduces specific runtime realities:
- **IPC Latency**: Calls to `window.pywebview.api` are asynchronous JSON-RPC promises. UI state must provide immediate optimistic local feedback while preventing duplicate invocations.
- **Single Process Scroll**: The outer document body is non-scrollable (`overflow: hidden`). Viewports and modal dialogs manage their own internal scrolling (`overflow-y: auto`) to prevent window-level jitter.
- **Offline Self-Containment**: No remote font files, script tags, or stylesheet links are permitted. All SVGs are inline or generated through local icon helpers.
- **Strict Text Selection Rules**: Operational telemetry (IDs, channel URLs, email addresses, error logs, release notes) must remain freely selectable by the operator, while interactive chrome (buttons, switches, tabs) prevents accidental highlighting.

---

## 2. Design Dials & Principles

### 2.1 The Three Product Design Dials
To maintain cohesive visual discipline across all modules, every interface element must align with three calibrated design dials:

| Dial | Metric | Target | Rationale & Architectural Rule |
|---|:---:|:---:|---|
| **Design Variance** | 4/10 | Low-Moderate | Keep layout hierarchy strictly predictable. Operators rely on spatial muscle memory; modal structures, drawer placements, and table columns must not vary unexpectedly across views. |
| **Motion Intensity** | 3/10 | Minimal-Functional | Limit animations strictly to state transitions (modals sliding in, toast dismissals, progress bars, drawer toggles). Zero decorative infinite pulsing, looping spinners, or jarring parallax. |
| **Visual Density** | 7/10 | High-Utility | Preserve compact information density for bulk channel management, while enforcing strict minimum tap targets (>=36×36px) and legible typography (>=12px) to eliminate operator fatigue. |

### 2.2 Core Operational Design Principles
1. **Preserve-First Workflow Integrity**: Never disrupt existing operator workflows. Enhance accessibility, semantics, and safety behind established visual patterns.
2. **Dual-Channel Status Communication**: Never communicate state solely via color hue. Always combine color tokens with distinct iconography, shape geometry, or visible text labels (e.g., status badges displaying "Hoạt động", "Lỗi", "Tạm dừng").
3. **Single Channel Feedback Policy**: One operation initiates exactly one feedback signal. Never trigger both a full-screen blocking overlay and an ephemeral toast notification for the same action.
4. **Optimized Information Scent**: Provide immediate visual hierarchy: Header Title > Filter Chips > Primary Action > Data Visualization > Metadata.

---

## 3. Safe DOM Construction & Escaping

### 3.1 Security Mandate: Zero Unsafe `innerHTML`
The primary vulnerability in desktop WebView dashboards is Cross-Site Scripting (XSS) and DOM markup corruption caused by interpolating runtime database values, user inputs, or profile identifiers directly into `.innerHTML`.

**Strict Rule**: Direct string interpolation of runtime variables into `.innerHTML` is strictly prohibited across the entire codebase.

### 3.2 HTML Entity Escaping Rules & Contract (`escapeHtml`)
When generating dynamic text strings or attribute values, developers must use the authoritative sanitization function `escapeHtml(str)`. The function enforces a strict contract:
- Replaces `&` with `&amp;` (must be processed first).
- Replaces `<` with `&lt;`.
- Replaces `>` with `&gt;`.
- Replaces `"` with `&quot;`.
- Replaces `'` with `&#39;`.
- Replaces `` ` `` with `&#96;`.
- Safely converts `null` and `undefined` to empty strings `""`.
- Preserves all UTF-8 characters and Vietnamese diacritics (`á, à, ả, ã, ạ, ă, ắ, ằ, ẳ, ẵ, ặ, â, ấ, ầ, ẩ, ẫ, ậ, đ, é, è, ẻ, ẽ, ẹ, ê, ế, ề, ể, ễ, ệ, í, ì, ỉ, ĩ, ị, ó, ò, ỏ, õ, ọ, ô, ố, ồ, ổ, ỗ, ộ, ơ, ớ, ờ, ở, ỡ, ợ, ú, ù, ủ, ũ, ụ, ư, ứ, ừ, ử, ữ, ự, ý, ỳ, ỷ, ỹ, ỵ`).

```javascript
// Reference Implementation: src/web/js/ui.js
function escapeHtml(s) {
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/`/g, '&#96;');
}
```

### 3.3 Declarative Safe DOM Builder (`createElement`)
For complex dynamic components (table rows, channel cards, notification feeds), use the safe DOM builder helper `createElement`:

```javascript
// Safe DOM Creation Pattern
function createChannelCard(channel) {
  const card = createElement('div', {
    class: 'p-4 rounded-xl border border-[var(--border-subtle)] bg-[var(--bg-surface)] shadow-sm',
    'data-channel-id': channel.id
  });

  const title = createElement('h3', { class: 'text-sm font-semibold text-[var(--text-primary)]' });
  title.textContent = channel.title; // Safe text assignment

  const statusBadge = createElement('span', {
    class: 'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/10 text-emerald-500'
  });
  statusBadge.textContent = 'Hoạt động';

  card.appendChild(title);
  card.appendChild(statusBadge);
  return card;
}
```

### 3.4 Event Delegation & Data Attribute Binding
Inline event handlers containing interpolated variables (e.g., `<button onclick="deleteChannel('${channel.id}')">`) are strictly banned because they create syntax breakage when handling names with quotes, backticks, or diacritics.

**Required Pattern**: Use dataset event delegation on container elements:
```javascript
// Container binding in table.js
tableContainer.addEventListener('click', (event) => {
  const trigger = event.target.closest('[data-action]');
  if (!trigger) return;

  const action = trigger.dataset.action;
  const channelId = trigger.dataset.channelId;

  if (action === 'launch-browser') {
    handleLaunchBrowser(channelId);
  } else if (action === 'delete-channel') {
    handleDeleteChannel(channelId);
  }
});
```

### 3.5 Anti-Pattern Catalog: DOM & Rendering Vulnerabilities

| Anti-Pattern | Severity | Why It Fails | Remediated Standard |
|---|:---:|---|---|
| Direct `.innerHTML = ` template literals | **Critical (P0)** | Allows XSS injection, attribute escape, and breaks on Vietnamese quotes. | Use `createElement()`, `textContent`, or strictly escaped templates via `escapeHtml()`. |
| Inline `onclick="func('${id}')"` | **Critical (P0)** | Fails when `id` or title contains single quotes (e.g., `'Hải Phòng'`), corrupting HTML. | Use dataset attributes (`data-action`, `data-id`) and event delegation. |
| Relying on `textContent` for input attributes | **High (P1)** | `textContent` does not sanitize attributes like `title` or `data-*`. | Pass attributes through `setAttribute()` or escape with `escapeHtml()`. |
| Raw unescaped search chips in DOM | **High (P1)** | Searching `<script>` renders actual DOM elements or triggers script parsing. | Always wrap chip labels in `escapeHtml()` or use `document.createTextNode()`. |

---

## 4. Centralized Overlay & Focus Management

### 4.1 Architecture of the `OverlayController`
All floating surfaces—including confirmation dialogs, modal forms, drawer panels, and popover menus—must be managed centrally by the singleton `OverlayController` (`src/web/js/ui.js`). Decentralized modal toggling (`el.classList.remove('hidden')`) leads to leaked focus, scrolling bugs, and orphaned backdrop listeners.

### 4.2 WAI-ARIA Modal Dialog Semantics
Every modal and drawer element must expose programmatic semantics conforming to WAI-ARIA Authoring Practices:
1. `role="dialog"` declared on the outer container.
2. `aria-modal="true"` for all blocking overlays.
3. `aria-labelledby="<heading-id>"` linking directly to the visible dialog title.
4. `aria-describedby="<description-id>"` optional link to explanatory text.

```html
<!-- Accessible Modal Structure -->
<div id="modal-add-account" role="dialog" aria-modal="true" aria-labelledby="title-add-account" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm hidden">
  <div class="w-full max-w-lg bg-[var(--bg-surface)] border border-[var(--border-subtle)] rounded-2xl shadow-2xl flex flex-col max-h-[calc(100vh-2rem)] overflow-hidden">
    <!-- Fixed Header -->
    <header class="px-6 py-4 border-b border-[var(--border-subtle)] flex items-center justify-between flex-shrink-0">
      <h2 id="title-add-account" class="text-base font-bold text-[var(--text-primary)]">Thêm tài khoản mới</h2>
      <button data-action="close-modal" aria-label="Đóng hộp thoại" class="w-8 h-8 rounded-lg flex items-center justify-center text-[var(--text-muted)] hover:text-[var(--text-primary)]">
        &times;
      </button>
    </header>
    <!-- Scrollable Body -->
    <div class="px-6 py-5 overflow-y-auto space-y-4 flex-1">
      <!-- Form Fields -->
    </div>
    <!-- Fixed Footer -->
    <footer class="px-6 py-4 border-t border-[var(--border-subtle)] flex items-center justify-end gap-3 flex-shrink-0 bg-[var(--bg-elevated)]">
      <button data-action="close-modal" class="px-4 py-2 rounded-xl text-sm font-medium border border-[var(--border-subtle)]">Hủy</button>
      <button type="submit" class="px-4 py-2 rounded-xl text-sm font-medium bg-[var(--accent-primary)] text-white">Lưu tài khoản</button>
    </footer>
  </div>
</div>
```

### 4.3 Focus Lifecycle: Trap, Initial Focus, and Restoration
The `OverlayController` strictly governs the user focus journey:
1. **Focus Capture on Open**: Before displaying the overlay, store the active element (`previousActiveElement = document.activeElement`).
2. **Initial Focus**: Automatically shift focus to the first interactive field inside the modal (e.g., the primary input or the close button).
3. **Tab Key Trap**: Intercept `Tab` and `Shift + Tab` keydown events. If the user tabs past the last focusable element, wrap focus back to the first. If shift-tabbing past the first, wrap focus to the last.
4. **Focus Restoration on Close**: When the overlay closes, immediately restore focus back to `previousActiveElement` to preserve operator keyboard flow.

### 4.4 Dismissal Protocols: Escape, Backdrop, and Background Inert
- **Global Escape Key**: Pressing `Escape` at any point immediately closes the uppermost active overlay.
- **Backdrop Click**: Clicking on the translucent scrim outside the modal panel closes dismissible dialogs.
- **Background `inert`**: While a blocking modal is active, the main application shell receives the `inert` attribute (or `aria-hidden="true"` with pointer-events disabled) and body scrolling is locked to prevent background interaction.

### 4.5 Responsive 3-Part Layout & Viewport Clipping Prevention
On compact screens (e.g., 360×640 mobile viewports or 1024×600 compact desktop monitors), modals frequently clip their headers or action buttons off-screen if unconstrained.

**Mandatory 3-Part Structure**:
1. **Fixed Header (`flex-shrink-0`)**: Houses title and close trigger; never scrolls.
2. **Scrollable Body (`flex-1 overflow-y-auto max-h-[calc(100vh-8rem)]`)**: Houses inputs, descriptions, and dynamic content; scrolls smoothly inside the modal.
3. **Fixed Footer (`flex-shrink-0`)**: Houses Cancel/Submit action buttons; permanently visible and immediately reachable without requiring form scrolling.

---

## 5. Accessibility & Component Semantics

### 5.1 WCAG 2.1 AA Compliance & Contrast Standards
Every view must satisfy the Web Content Accessibility Guidelines (WCAG) 2.1 AA level:
- **Normal Text (<18pt / <24px regular)**: Minimum contrast ratio of **4.5:1** against the underlying background.
- **Large Text (>=18pt or >=14pt bold)**: Minimum contrast ratio of **3:1**.
- **Interactive Components & Graphical Boundaries**: Minimum contrast ratio of **3:1** for borders, icons, and focus rings.

### 5.2 Theme-Aware Focus Ring System (`:focus-visible`)
To provide clear feedback for keyboard navigators while remaining subtle for mouse clicks, the global focus ring utilizes `:focus-visible`:
- Ring width: `2px solid var(--accent-primary)`.
- Ring offset: `2px` (`offset-color: var(--bg-surface)`).
- Never use `outline: none` without providing an explicit `:focus-visible` replacement.
- High contrast (>3:1) must be verified across all 6 themes in both Dark and Light modes.

```css
/* src/web/css/base.css Focus Standard */
:focus-visible {
  outline: 2px solid var(--accent-primary) !important;
  outline-offset: 2px !important;
}

button:focus-visible,
input:focus-visible,
select:focus-visible,
textarea:focus-visible,
[role="tab"]:focus-visible,
[role="button"]:focus-visible {
  outline: 2px solid var(--accent-primary);
  outline-offset: 2px;
}
```

### 5.3 Accessible Table Sorting with `<button>` and `aria-sort`
Table headers must never use clickable `<th>` elements without interactive semantics.
- Wrap header contents in a native `<button>` element with full keyboard focusability (`Tab`, `Enter`, `Space`).
- Expose sorting direction via the `aria-sort` attribute on the parent `<th>`:
  - `aria-sort="ascending"`: Sorted lowest-to-highest or A-to-Z.
  - `aria-sort="descending"`: Sorted highest-to-lowest or Z-to-A.
  - `aria-sort="none"`: Column is sortable but currently unsorted.
- Display dual-channel sort indicators (visual chevron icons + accessible screen-reader announcement).

### 5.4 Navigation, Tabs, and Segmented Controls
- **Main Shell Navigation**: Active navigation links must explicitly expose `aria-current="page"`.
- **Tabbed Interfaces (Settings / Channel Details)**:
  - Tab bar: `role="tablist"` with `aria-label`.
  - Tab triggers: `role="tab"`, `aria-selected="true"|"false"`, `aria-controls="panel-id"`, and `tabindex="0"` (for active) or `tabindex="-1"` (for inactive).
  - Tab panels: `role="tabpanel"`, `id="panel-id"`, `aria-labelledby="tab-id"`.
  - Keyboard Navigation: Support Arrow Left/Right to cycle tabs, `Home` to jump to the first tab, and `End` to jump to the last tab.
- **Segmented Controls & Toggle Buttons**: Must expose `aria-pressed="true"|"false"` or `aria-checked="true"|"false"` for boolean switch modes.

### 5.5 Live Regions, Toasts, and Progress Bars
- **Toast Notifications Container**: Must declare `aria-live="polite"` and `aria-atomic="true"`. Urgent blocking system failures may use `aria-live="assertive"`.
- **Progress Indicators (Bulk Sync, Update, Health Check)**: Must expose semantic `role="progressbar"`, with `aria-valuenow`, `aria-valuemin="0"`, `aria-valuemax="100"`, and a companion percentage label.

### 5.6 Inline Form Validation & Error Associations
Toast-only error messages fail accessibility standards because they disappear quickly and fail to indicate which input is invalid.
- Associate every input directly with its `<label for="<input-id>">`.
- Render error messages inline directly beneath the invalid field.
- Set `aria-invalid="true"` on invalid inputs.
- Link the error message to the field via `aria-describedby="<error-message-id>"`.
- Upon form submission failure, automatically shift focus to the first invalid field.

### 5.7 Target Sizing & Operational Text Selectability
- **Minimum Hit Targets**: All interactive elements (buttons, checkboxes, select toggles, icons) must measure at least **36×36px** on desktop workstations (and >=44×44px on touch viewports).
- **Minimum Typography**: No operational text may be rendered below **12px** (`text-xs`).
- **Text Selectability**: Never place `select-none` on the document `<body>`. Operational text (account emails, channel IDs, URLs, proxy strings, error logs) must remain freely selectable and copyable by the operator.

### 5.8 Keyboard Interaction Matrix

| Key / Combination | Target Component | Required Behavior |
|---|---|---|
| `Tab` | Global / Modals | Advances focus to next interactive element. Trapped inside modals. |
| `Shift + Tab` | Global / Modals | Reverses focus to previous interactive element. Trapped inside modals. |
| `Escape` | Overlays, Drawers, Popovers | Immediately closes top-most active surface and restores focus to opener. |
| `Enter` | Buttons, Links, Table Headers | Activates button action, navigation link, or toggles table sorting. |
| `Space` | Buttons, Checkboxes, Switches | Toggles button state, checkbox checked state, or segmented switch. |
| `ArrowLeft` / `ArrowRight` | `role="tablist"` | Cycles focus between adjacent horizontal tabs. |
| `ArrowUp` / `ArrowDown` | Dropdowns, Menus | Navigates vertical list items without closing panel. |
| `Home` / `End` | `role="tablist"`, Tables | Shifts focus immediately to first or last tab/row. |

---

## 6. Responsive Shell & Breakpoints

### 6.1 Breakpoint System & Grid Foundation
The VB-Studio desktop shell adapts dynamically across three primary viewport tiers:

| Breakpoint Tier | Media Query Range | Navigation Shell Behavior | Main Viewport Layout |
|---|:---:|---|---|
| **Mobile / Compact** | `< 768px` | Off-canvas sliding drawer (`#mobile-drawer`), hidden by default, toggled via `#btn-mobile-menu`. | Single-column stacked cards, full-width search, scrollable table. |
| **Tablet / Narrow** | `768px` – `1023px` | Collapsed icon rail (w-16) with tooltips. Expandable on click. | Two-column cards, condensed table padding, sticky search header. |
| **Desktop / Standard** | `>= 1024px` | Persistent sidebar (w-64) with full labels, collapsible via explicit toggle button. | Multi-column grid (3–4 columns), expanded table, sticky header. |

### 6.2 Responsive Shell Layout Rules
1. **No Hover-Only Navigation**: The sidebar expansion and menu toggles must rely strictly on explicit click/keyboard actions, never on `:hover` styles which fail on touchscreens and virtual tablets.
2. **Persistent Header Reachability**: The search input, account filter dropdown, and top secondary action buttons must remain visible and accessible across all screen widths without horizontal overflow.
3. **Single Main Scroll Container**: Only the `#main-content` area scrolls vertically. The header and sidebar remain sticky to anchor spatial orientation.

---

## 7. Design Token System & Theming

### 7.1 Semantic Token Architecture vs. Utility Overrides
Legacy implementations often relied on `!important` utility overrides in JavaScript to forcibly recolor DOM nodes. This creates severe maintenance bottlenecks and breaks theme switching.

**Standard**: The theme engine (`src/web/js/themes.js`) defines pure CSS Custom Properties bound to the root element (`html[data-theme="<id>"]`). All UI components consume these semantic variables directly. Zero `!important` declarations are allowed in the theme engine.

### 7.2 The 14 Core CSS Custom Properties Reference

| CSS Custom Property | Semantic Role & Purpose | Theme Value Example (Dark) | Theme Value Example (Light) |
|---|---|---|---|
| `--bg-app` | Application-level background behind panels | `#0b0f19` | `#f0f4f9` |
| `--bg-surface` | Primary surface for cards, modals, and tables | `#111827` | `#ffffff` |
| `--bg-elevated` | Secondary elevated surface for headers, footers | `#161f30` | `#e9f1fe` |
| `--text-primary` | High-contrast body text and prominent titles | `#f8fafc` | `#0f172a` |
| `--text-secondary` | Medium-contrast descriptions and table cells | `#94a3b8` | `#475569` |
| `--text-muted` | Low-contrast placeholders, timestamps, icons | `#64748b` | `#64748b` |
| `--border-subtle` | Fine divider lines and card borders | `#1f293d` | `#e2e8f0` |
| `--border-default` | Standard input borders and table dividers | `#334155` | `#cbd5e1` |
| `--accent-primary` | Brand primary color for active states, CTA buttons | `#3b82f6` (Ocean) | `#3b82f6` (Ocean) |
| `--accent-hover` | Interactive hover state for primary buttons | `#2563eb` | `#2563eb` |
| `--status-success` | Operational success badges, active channels | `#10b981` | `#10b981` |
| `--status-warning` | Pending approvals, warnings, expiring sessions | `#f59e0b` | `#f59e0b` |
| `--status-error` | Channel disconnects, auth failures, errors | `#ef4444` | `#ef4444` |
| `--status-info` | Telemetry notifications, informative banners | `#3b82f6` | `#3b82f6` |

Companion gradient variables (`--grad-start`, `--grad-mid`, `--grad-end`) provide subtle brand accents for progress bars and active indicator tabs.

### 7.3 Separation of Brand Accents and Operational Status Colors
Brand accent tokens (`--accent-*`) must remain strictly isolated from operational status tokens (`--status-*`).
- If an operator selects the "Emerald Green" theme, the primary action button becomes green (`#10b981`).
- However, status badges must never conflate the theme brand with operational state: an "Error" status remains red (`--status-error`), and an "Info" badge remains blue (`--status-info`), regardless of the active theme palette.

### 7.4 The 6 Multi-Mode Themes
The application provides 6 distinct colorways, each supporting both **Dark** and **Light** modes:
1. **Ocean Blue (`ocean`)**: Classic technical indigo/blue balance.
2. **Emerald Green (`emerald`)**: High-contrast organic mint/emerald.
3. **Violet Purple (`violet`)**: Deep violet/purple creative operations.
4. **Sunset Orange (`sunset`)**: Warm amber/orange energy.
5. **Rose Pink (`rose`)**: Distinctive rose/crimson high-legibility palette.
6. **Midnight Mono (`mono`)**: Ultra-clean neutral grayscale for maximum contrast.

### 7.5 Operator Login Gate Visual Alignment
The login authentication gate must align visually with the operator dashboard:
- **Retired**: Generic decorative glow effects (e.g., `blur-[120px]` background ambient glow balls, harsh saturated gradient text).
- **Adopted**: Clean, crisp card geometry utilizing `--bg-surface`, `--border-subtle`, and standard typography. Supports both Dark and Light themes seamlessly.

### 7.6 Đảm bảo đồng bộ Theme trên cả Dark Mode và Light Mode (Quy tắc kiến trúc cốt lõi)
**Vấn đề từng gặp (Bài học kinh nghiệm)**:
Khi chuyển sang hệ thống CSS Custom Properties, nếu chỉ bridge các class `dark:*` (như `.dark .dark:bg-dark-bg`) sang biến CSS, thì khi chuyển sang **Light Mode**, các theme khác nhau (Ocean, Emerald, Violet, Sunset, Rose, Mono) sẽ **không có tác dụng** vì các phần tử Light Mode vẫn dính chặt vào các class Tailwind tĩnh (`bg-slate-50`, `bg-white`, `border-slate-200`, `text-slate-800`, `bg-blue-600`).

**Quy tắc bắt buộc khi thiết kế Theme lưỡng thể (Dual-mode)**:
1. **Bridge lưỡng chiều trong `base.css`**:
   - Phải cấu hình tường minh selector `html:not(.dark) body` nhận `var(--bg-app)` và `var(--text-primary)`.
   - Các class nền/viền/chữ cơ bản ở Light Mode (`bg-slate-50`, `bg-slate-100`, `border-slate-200`, `text-slate-800/900`) phải được map sang semantic tokens (`--bg-app`, `--bg-elevated`, `--border-subtle`, `--text-primary`).
   - Các shell panel (`.thm-nav`, `.thm-header`, `.thm-panel`) phải nhận biến tương ứng ở Light Mode (`--bg-nav`, `--bg-surface`, `--bg-panel`).
2. **Bridge màu Accent & Gradient đa chế độ**:
   - Nút hành động chính (`.bg-blue-600`, `.hover:bg-blue-500`), văn bản liên kết (`.text-blue-600`, `.text-blue-500`), huy hiệu (`.bg-blue-50`, `.bg-blue-500/10`) và dải gradient (`.from-blue-500`, `.to-purple-500`) phải được nối trực tiếp vào `var(--accent-primary)`, `var(--accent-hover)`, `var(--grad-*)` thay vì giữ màu xanh dương cố định.
3. **Thẻ xem trước Theme (Preview Cards) phản hồi thời gian thực**:
   - Hàm `renderThemeCards()` phải kiểm tra cờ `isDark` để hiển thị màu xem trước tương ứng (dùng `t.light.*` khi ở Light Mode và `t.dark.*` khi ở Dark Mode).
   - Khi hàm `setColorMode(isDark)` được kích hoạt, phải gọi lại `renderThemeCards()` ngay lập tức để cập nhật trực quan cho người dùng.

---

## 8. Motion Policy & Reduced Motion

### 8.1 Motion Philosophy & Vestibular Safety
Motion in VB-Studio Login is strictly utilitarian. It communicates state transitions, spatial continuity, and progress telemetry. It must never distract operators or trigger vestibular motion sensitivity.

### 8.2 Implementing `@media (prefers-reduced-motion: reduce)`
The stylesheet enforces a comprehensive reduced-motion override:

```css
/* src/web/css/base.css Reduced Motion Standard */
@media (prefers-reduced-motion: reduce) {
  *,
  *::before,
  *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

### 8.3 Preservation of Functional State During Reduced Motion
When reduced motion is enabled by the operating system:
1. Decorative pulse (`animate-pulse`), spinning icons (`animate-spin`), and radar pings (`animate-ping`) are suppressed immediately.
2. Modals and drawers appear instantaneously without sliding or fading transitions.
3. Smooth scrolling (`scroll-behavior: smooth`) is disabled in favor of immediate jump scrolling.
4. **Crucial Rule**: Functional state indicators must never vanish. If an animated spinner is disabled, it must remain visible as a static loading glyph accompanied by the text label "Đang xử lý...".

---

## 9. Terminology & Vietnamese Glossary

### 9.1 Professional Operations Copy Standards
All user-facing copy must use clear, standardized Vietnamese operations terminology. Informal developer shorthand, mixed-language phrases, and hyperbolic marketing jargon are strictly forbidden.

### 9.2 The Normalized 46-Term Vietnamese Glossary

| # | Legacy / Unnormalized Shorthand | Normalized Vietnamese Term | Operational Context & Application |
|:---:|---|---|---|
| 1 | `Acc` / `Google Acc` | **Tài khoản** / **Tài khoản Google** | Profile account selector, filter dropdowns, headings |
| 2 | `Thêm Acc` | **Thêm tài khoản** | Primary modal action button |
| 3 | `Xóa Acc` | **Xóa tài khoản** | Account deletion dialog |
| 4 | `Khóa acc` | **Khóa tài khoản** | Status alert for restricted accounts |
| 5 | `Card` / `card count` | **Thẻ kênh** / **Số lượng thẻ kênh** | Channel grid item and counter badge |
| 6 | `Cards grid` | **Lưới thẻ kênh** | View toggle label |
| 7 | `Run` | **Đợt kiểm tra** | Batch automation or diagnostics execution |
| 8 | `Report` | **Báo cáo** | Operational export and health logs |
| 9 | `Setup` | **Thiết lập** | Configuration views and preferences tabs |
| 10 | `Copy` | **Sao chép** | Clipboard copy action for IDs, URLs, and cookies |
| 11 | `Platform` | **Nền tảng** | Social platform filter (YouTube, TikTok, Facebook) |
| 12 | `Session` | **Phiên làm việc** | Active browser profile login session |
| 13 | `Giam phiên` | **Giữ phiên** / **Chiếm dụng phiên** | Multi-operator session lock indication |
| 14 | `Profile` | **Hồ sơ trình duyệt** | Native browser user data directory profile |
| 15 | `Proxy` | **Máy chủ ủy quyền** (hoặc **Proxy**) | Network routing configuration |
| 16 | `Cookie` | **Dữ liệu cookie** | Authentication token management |
| 17 | `Vault` | **Két bảo mật** | Encrypted credential store |
| 18 | `Trash` | **Thùng rác** | Deleted channel recovery bin |
| 19 | `Presence` | **Trạng thái trực tuyến** | Operator presence heartbeat |
| 20 | `Health` | **Tình trạng hoạt động** | System and network health check |
| 21 | `Heartbeat` | **Nhịp kiểm tra định kỳ** | Background keepalive telemetry |
| 22 | `Sync` | **Đồng bộ hóa** | Data synchronization action |
| 23 | `Export` | **Xuất dữ liệu** | Data export action |
| 24 | `Import` | **Nhập dữ liệu** | Data import action |
| 25 | `Filter` | **Bộ lọc** | Search and attribute filter controls |
| 26 | `Clear all` | **Xóa tất cả** | Reset all active filter chips |
| 27 | `Apply` | **Áp dụng** | Submit filter or settings changes |
| 28 | `Reset` | **Đặt lại** | Restore default configuration |
| 29 | `Drawer` | **Ngăn chi tiết** | Slide-over channel detail panel |
| 30 | `Modal` | **Hộp thoại** | Center-screen blocking dialog |
| 31 | `Toast` | **Thông báo nhanh** | Ephemeral notification banner |
| 32 | `Progress` | **Tiến trình thực hiện** | Progress bar percentage label |
| 33 | `Loading` | **Đang tải...** | Asynchronous operation pending state |
| 34 | `Launch` | **Khởi chạy trình duyệt** | Spawning native Chrome/Edge process |
| 35 | `Close` | **Đóng cửa sổ** | Terminating browser process or closing dialog |
| 36 | `Status` | **Trạng thái** | Channel or process operational state |
| 37 | `Active` | **Đang hoạt động** | Green operational state |
| 38 | `Idle` | **Chờ xử lý** | Gray standby state |
| 39 | `Error` | **Gặp sự cố** | Red failure state |
| 40 | `Success` | **Thành công** | Green confirmation feedback |
| 41 | `Warning` | **Cảnh báo** | Amber cautionary notice |
| 42 | `Info` | **Thông tin** | Blue diagnostic notice |
| 43 | `Dark mode` | **Giao diện Tối** | Appearance switch label |
| 44 | `Light mode` | **Giao diện Sáng** | Appearance switch label |
| 45 | `Overview` | **Tổng quan** | Dashboard main view title |
| 46 | `Settings` | **Cài đặt hệ thống** | Main navigation settings label |

### 9.3 Eradication of Absolute Safety Claims
Technical copy must be honest, precise, and professional. **Never promise absolute immunity or safety against third-party platform actions.**

- **Strictly Forbidden Claims**:
  - ❌ "100% an toàn"
  - ❌ "tuyệt đối an toàn"
  - ❌ "chống khóa vĩnh viễn"
  - ❌ "không nguy cơ khóa acc"
- **Mandatory Factual Replacements**:
  - ✅ "Sử dụng tiến trình trình duyệt native độc lập, không gắn CDP hook hay cờ automation, giảm thiểu rủi ro kích hoạt cơ chế phát hiện tự động."
  - ✅ "Dữ liệu cookie được đọc trực tiếp từ profile SQLite ở chế độ sao chép an toàn, bảo toàn tính toàn vẹn phiên đăng nhập."

---

## 10. QA & Regression Testing Checklist

### 10.1 Pre-Commit Developer Checklist
Every developer and automated pull request must verify this checklist prior to merging changes into `src/web/`:

- [ ] **DOM Safety**: Zero unescaped `.innerHTML` assignments. All dynamic strings sanitized via `escapeHtml()`.
- [ ] **Event Binding**: Zero inline `onclick`, `onchange`, or `onerror` handlers interpolating runtime IDs. All events bound via `addEventListener` or dataset delegation.
- [ ] **Overlay Semantics**: All modal dialogs possess `role="dialog"`, `aria-modal="true"`, and `aria-labelledby`.
- [ ] **Focus Management**: Opening a modal traps focus; closing with `Escape` or backdrop click restores focus to opener.
- [ ] **Viewport Resilience**: Modals use 3-part layout (`max-h-[calc(100vh-2rem)]`, `overflow-y-auto` body); zero clipping on 360×640 or 1024×600 viewports.
- [ ] **Focus Rings**: All interactive elements display a clear `:focus-visible` offset ring across all 6 themes.
- [ ] **Table Sorting**: Sort headers are `<button>` elements exposing `aria-sort="ascending|descending|none"`.
- [ ] **Navigation Semantics**: Active navigation items expose `aria-current="page"`. Tabs implement `tablist`/`tab`/`tabpanel` ARIA roles.
- [ ] **Live Regions**: Toast notifications container declares `aria-live="polite"`. Progress bars declare `role="progressbar"`.
- [ ] **Form Validation**: Form errors appear inline with `aria-invalid="true"` and `aria-describedby`. Auto-focuses first invalid field.
- [ ] **Target Sizes & Typography**: Interactive hit targets are >=36×36px; text is >=12px; operational telemetry is selectable (no body `select-none`).
- [ ] **Responsive Shell**: Mobile menu drawer `<768px` is toggleable via `#btn-mobile-menu`. Header search is permanently reachable.
- [ ] **Theme Architecture**: Zero `!important` overrides in the theme engine. 14 semantic tokens utilized. Status colors separated from accents.
- [ ] **Motion Policy**: `@media (prefers-reduced-motion: reduce)` disables pulse/spin/ping/smooth scroll without dropping functional state.
- [ ] **Terminology Compliance**: All 46 operational terms adhere to the Vietnamese glossary; zero absolute safety claims.

### 10.2 Automated Test Matrix & Verification Commands
The test suite in `tests/test_ui_refactor.py` provides opaque-box verification across 82 automated test cases:

```bash
# Execute Full E2E Test Suite with Structured Reporting
python tests/test_ui_refactor.py

# Execute via Standard Python Unittest Runner
python -m unittest tests.test_ui_refactor

# Execute Milestone 5 Specific Tests (R7 UI Guidelines Verification)
python -m unittest tests.test_ui_refactor.TestTier1FeatureCoverage.test_tier1_r7_01_ui_guidelines_file_exists \
                   tests.test_ui_refactor.TestTier1FeatureCoverage.test_tier1_r7_02_ui_guidelines_10_chapters_present \
                   tests.test_ui_refactor.TestTier1FeatureCoverage.test_tier1_r7_03_ui_guidelines_design_dials_documented \
                   tests.test_ui_refactor.TestTier1FeatureCoverage.test_tier1_r7_04_ui_guidelines_component_and_a11y_rules \
                   tests.test_ui_refactor.TestTier1FeatureCoverage.test_tier1_r7_05_ui_guidelines_qa_checklist \
                   tests.test_ui_refactor.TestTier2BoundaryAndCornerCases.test_tier2_r7_b01_ui_guidelines_markdown_syntax_and_table_integrity \
                   tests.test_ui_refactor.TestTier2BoundaryAndCornerCases.test_tier2_r7_b02_ui_guidelines_wcag_contrast_references \
                   tests.test_ui_refactor.TestTier2BoundaryAndCornerCases.test_tier2_r7_b03_ui_guidelines_anti_pattern_catalog \
                   tests.test_ui_refactor.TestTier2BoundaryAndCornerCases.test_tier2_r7_b04_ui_guidelines_keyboard_interaction_matrix \
                   tests.test_ui_refactor.TestTier2BoundaryAndCornerCases.test_tier2_r7_b05_ui_guidelines_component_token_cross_reference
```

### 10.3 Manual Keyboard & Assistive Technology Walkthrough Script
1. **Keyboard-Only Traversal**:
   - Tab through sidebar navigation; verify high-contrast outline ring and `aria-current="page"`.
   - Open Add Account modal with `Enter`; verify initial focus lands on Account Name input.
   - Press `Tab` through all fields; verify focus wraps from Cancel/Save back to Header Close button.
   - Press `Escape`; verify modal dismisses and focus returns to the "Thêm tài khoản" button.
2. **Adversarial Input Validation**:
   - Enter malicious string `<script>alert('XSS')</script> "test" 'channel'` into the search box.
   - Verify filter chip renders literal text without executing script or breaking DOM layout.
3. **Screen Reader Announcement Simulation**:
   - Inspect `#toast-container` in DevTools; verify `aria-live="polite"` receives dynamic status updates.
   - Inspect sortable table headers; verify screen reader receives column name and sort state (`aria-sort`).
4. **Theme Switch Verification**:
   - Switch through all 6 themes (Ocean, Emerald, Violet, Sunset, Rose, Mono) in both Dark and Light modes.
   - Verify focus ring maintains >=3:1 contrast against surface colors in all modes.
   - Verify status badges (Success, Warning, Error) maintain distinct operational colors independent of brand accent.
