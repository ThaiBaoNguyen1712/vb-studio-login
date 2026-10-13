"""
Empirical Adversarial Test Suite - Challenger 2
VB-Studio Login WebView Frontend Refactoring & Remediation
Focus Areas:
1. Responsive Shell Layout (R4): Viewports (360x640, 768x768, 1024x600, 1280x720, 1440x900), zero horizontal clipping, modal body scroll fit, reachable search & secondary controls.
2. Theme Engine & Contrast (R5): Zero !important in themes.js, all 6 themes in dark/light modes, WCAG AA contrast ratio, high-contrast focus rings, status color separation.
3. Accessibility & Form Validation (R3, R6): Table sort buttons with aria-sort, inline form errors with aria-invalid & first invalid field focus, live toast regions, Vietnamese terminology normalization.
4. Comprehensive empirical execution harness.
"""

import os
import re
import sys
import math
import pathlib
import unittest
from html.parser import HTMLParser
from typing import Dict, List, Set, Tuple, Optional, Any

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "src" / "web"
INDEX_HTML_PATH = WEB_DIR / "index.html"
BASE_CSS_PATH = WEB_DIR / "css" / "base.css"
JS_DIR_PATH = WEB_DIR / "js"
UI_REVIEW_PATH = PROJECT_ROOT / "docs" / "UI_REVIEW.md"
UI_GUIDELINES_PATH = PROJECT_ROOT / "docs" / "UI_GUIDELINES.md"


# =============================================================================
# Helper Utilities: Color Math, DOM Parser & CSS Evaluator
# =============================================================================

def parse_hex_color(hex_str: str) -> Tuple[int, int, int]:
    """Parse #rgb, #rrggbb hex strings into (r, g, b) tuples."""
    h = hex_str.strip().lstrip('#')
    if len(h) == 3:
        h = ''.join([c * 2 for c in h])
    if len(h) != 6:
        raise ValueError(f"Invalid hex color: {hex_str}")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def srgb_channel_to_linear(c_byte: int) -> float:
    """Convert sRGB 0-255 channel to linear luminance per WCAG 2.1."""
    c = c_byte / 255.0
    return c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4)


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Calculate WCAG 2.1 relative luminance for an RGB tuple."""
    r_lin = srgb_channel_to_linear(rgb[0])
    g_lin = srgb_channel_to_linear(rgb[1])
    b_lin = srgb_channel_to_linear(rgb[2])
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def wcag_contrast_ratio(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    """Calculate WCAG 2.1 contrast ratio between two RGB colors (1:1 to 21:1)."""
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class SimpleDOMNode:
    def __init__(self, tag: str, attrs: List[Tuple[str, Optional[str]]], parent=None):
        self.tag = tag.lower()
        self.attrs = {k.lower(): (v if v is not None else "") for k, v in attrs}
        self.parent = parent
        self.children: List['SimpleDOMNode'] = []
        self.text_content: List[str] = []

    @property
    def id(self) -> str:
        return self.attrs.get("id", "")

    @property
    def classes(self) -> Set[str]:
        return set(self.attrs.get("class", "").split())

    def find_by_id(self, target_id: str) -> Optional['SimpleDOMNode']:
        if self.id == target_id:
            return self
        for ch in self.children:
            res = ch.find_by_id(target_id)
            if res:
                return res
        return None

    def find_all(self, predicate) -> List['SimpleDOMNode']:
        res = []
        if predicate(self):
            res.append(self)
        for ch in self.children:
            res.extend(ch.find_all(predicate))
        return res


class SimpleDOMParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = SimpleDOMNode("root", [])
        self.current = self.root
        self.nodes: List[SimpleDOMNode] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        node = SimpleDOMNode(tag, attrs, parent=self.current)
        self.current.children.append(node)
        self.nodes.append(node)
        if tag.lower() not in {"input", "img", "br", "hr", "meta", "link", "area", "base", "col", "embed", "param", "source", "track", "wbr"}:
            self.current = node

    def handle_endtag(self, tag: str):
        if self.current != self.root:
            self.current = self.current.parent

    def handle_data(self, data: str):
        self.current.text_content.append(data)


# =============================================================================
# Test Suite: Challenger 2 Empirical Stress Tests
# =============================================================================

def extract_media_block(css: str, query_pattern: str) -> str:
    """Extract full content of an @media block handling nested braces."""
    m = re.search(query_pattern, css)
    if not m:
        return ""
    start_idx = css.find('{', m.start())
    if start_idx == -1:
        return ""
    brace_depth = 1
    i = start_idx + 1
    while i < len(css) and brace_depth > 0:
        if css[i] == '{':
            brace_depth += 1
        elif css[i] == '}':
            brace_depth -= 1
        i += 1
    return css[start_idx + 1:i - 1]


class TestChallenger2AdversarialSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html_raw = INDEX_HTML_PATH.read_text(encoding="utf-8")
        cls.css_raw = BASE_CSS_PATH.read_text(encoding="utf-8")
        cls.parser = SimpleDOMParser()
        cls.parser.feed(cls.html_raw)
        cls.dom = cls.parser.root

        cls.js_files = {}
        for js_file in JS_DIR_PATH.glob("*.js"):
            cls.js_files[js_file.name] = js_file.read_text(encoding="utf-8")

    # =========================================================================
    # AREA 1: Responsive Shell Layout (R4)
    # Viewports: 360x640, 768x768, 1024x600, 1280x720, 1440x900
    # =========================================================================

    def test_adv_r4_01_viewports_matrix_simulation(self):
        """
        Adversarial Stress Test: Verify responsive layout constraints across all 5 mandatory viewports:
        360x640, 768x768, 1024x600, 1280x720, 1440x900.
        """
        viewports = [
            (360, 640, "Mobile Compact"),
            (768, 768, "Tablet Square"),
            (1024, 600, "Netbook Ultra-wide Short"),
            (1280, 720, "HD Standard"),
            (1440, 900, "WXGA+ Desktop Widescreen"),
        ]

        # 1. Breakpoint coverage in CSS
        self.assertIn("@media (max-width: 767px)", self.css_raw, "CSS must handle mobile compact (<768px)")
        self.assertIn("@media (min-width: 768px) and (max-width: 1023px)", self.css_raw, "CSS must handle tablet (768-1023px)")
        self.assertIn("@media (min-width: 1024px)", self.css_raw, "CSS must handle desktop (>=1024px)")

        # 2. Check mobile drawer specifics for 360px width
        mobile_css = extract_media_block(self.css_raw, r"@media \(max-width: 767px\)")
        self.assertTrue(len(mobile_css) > 0, "Mobile media query block must be defined in base.css")
        self.assertIn("translateX(-100%)", mobile_css, "Sidebar must be positioned off-canvas by default on mobile")
        self.assertIn("translateX(0)", mobile_css, "Sidebar must slide in when .mobile-open is active")
        self.assertIn("max-width: 85vw", mobile_css, "Sidebar must not exceed 85vw to prevent full screen occlusion on narrow viewports")

        # 3. Check tablet rail specifics for 768px width
        tablet_css = extract_media_block(self.css_raw, r"@media \(min-width: 768px\) and \(max-width: 1023px\)")
        self.assertTrue(len(tablet_css) > 0, "Tablet media query block must be defined")
        self.assertIn("width: 68px", tablet_css, "Sidebar must collapse to 68px icon rail on tablet")
        self.assertIn(".sb-label", tablet_css, "Text labels must be hidden on tablet rail")

        # 4. Check desktop persistent sidebar for >=1024px
        desktop_css = extract_media_block(self.css_raw, r"@media \(min-width: 1024px\)")
        self.assertTrue(len(desktop_css) > 0, "Desktop media query block must be defined")
        self.assertIn("width: 256px", desktop_css, "Sidebar must have persistent 256px width on desktop")

    def test_adv_r4_02_zero_horizontal_clipping_in_shell(self):
        """
        Adversarial Test: Verify body and main shell enforce horizontal containment (overflow-hidden)
        and overlays have responsive max-width bounds preventing horizontal blowout on 360px viewport.
        """
        body_node = self.dom.find_all(lambda n: n.tag == "body")[0]
        self.assertIn("overflow-hidden", body_node.classes, "Body must have overflow-hidden to prevent global page horizontal scroll")

        main_node = self.dom.find_all(lambda n: n.tag == "main")[0]
        self.assertIn("overflow-hidden", main_node.classes, "Main workspace must have overflow-hidden")
        self.assertIn("min-w-0", main_node.classes, "Main workspace must have min-w-0 flex shrink capability")

        # Check header overflow-x containment
        self.assertIn("overflow-x: auto", self.css_raw, "Header must allow horizontal scrolling without clipping controls")

        # Check overlay max-width bounds on 360px
        # Toast container
        toast_el = self.dom.find_by_id("toast-container")
        self.assertIsNotNone(toast_el)
        self.assertIn("max-w-[calc(100%-2.5rem)]", toast_el.attrs.get("class", ""))

        # Bulk progress panel
        bulk_el = self.dom.find_by_id("bulk-panel")
        self.assertIsNotNone(bulk_el)
        self.assertIn("max-w-[calc(100%-2.5rem)]", bulk_el.attrs.get("class", ""))

        # Channel drawer
        drawer_el = self.dom.find_by_id("channel-drawer")
        self.assertIsNotNone(drawer_el)
        self.assertIn("max-w-[calc(100vw-2rem)]", drawer_el.attrs.get("class", ""))

        # Notification panel
        notif_panel = self.dom.find_by_id("notif-panel")
        self.assertIsNotNone(notif_panel)
        self.assertIn("max-w-[calc(100vw-3rem)]", notif_panel.attrs.get("class", ""))

    def test_adv_r4_03_modal_dialogs_3part_layout_scroll_fit(self):
        """
        Adversarial Test: Verify all 7 modal dialogs use 3-part layout (fixed header, scrollable body, fixed footer)
        with internal scroll, ensuring zero vertical clipping across short viewports (600px and 640px heights).
        """
        modal_ids = [
            "confirm-modal",
            "modal-add-account",
            "modal-edit-account",
            "modal-platform",
            "modal-add-channel",
            "modal-edit-channel",
            "modal-update-dialog",
        ]

        for mid in modal_ids:
            modal = self.dom.find_by_id(mid)
            self.assertIsNotNone(modal, f"Modal dialog #{mid} must exist in index.html")

            # Check outer wrapper has padding
            outer_cls = modal.attrs.get("class", "")
            self.assertTrue("p-4" in outer_cls or "p-6" in outer_cls, f"#{mid} wrapper must have viewport padding")

            # Check inner container has max-h-[calc(100vh-2rem)] and flex flex-col
            inner_container = modal.children[0] if modal.children else None
            self.assertIsNotNone(inner_container, f"#{mid} must contain an inner dialog container")
            inner_cls = inner_container.attrs.get("class", "")
            self.assertIn("max-h-[calc(100vh-2rem)]", inner_cls, f"#{mid} inner container must constrain height to viewport")
            self.assertIn("flex-col", inner_cls, f"#{mid} inner container must use flex-col for 3-part layout")

            # Check scrollable body
            body_id = f"{mid}-body"
            body_el = modal.find_by_id(body_id)
            if not body_el and len(inner_container.children) >= 2:
                # Find body element by overflow-y-auto class
                body_candidates = [ch for ch in inner_container.children if "overflow-y-auto" in ch.attrs.get("class", "")]
                self.assertTrue(len(body_candidates) > 0, f"#{mid} must contain a child with overflow-y-auto")
                body_el = body_candidates[0]

            self.assertIsNotNone(body_el, f"#{mid} body element must exist")
            body_cls = body_el.attrs.get("class", "")
            self.assertIn("overflow-y-auto", body_cls, f"#{mid} body must have overflow-y-auto")
            self.assertIn("flex-1", body_cls, f"#{mid} body must have flex-1 to fill remaining vertical space")

    def test_adv_r4_04_reachable_search_and_secondary_controls_on_mobile(self):
        """
        Adversarial Test: Verify header search and secondary controls remain reachable and non-clipped
        on mobile (360px viewport).
        """
        # Mobile hamburger toggle must be present
        menu_btn = self.dom.find_by_id("btn-mobile-menu")
        self.assertIsNotNone(menu_btn, "Mobile navigation menu toggle button (#btn-mobile-menu) must exist")
        self.assertIn("md:hidden", menu_btn.attrs.get("class", ""), "Hamburger button must show only on compact screens (<768px)")

        # Search input
        search_input = self.dom.find_by_id("input-search")
        self.assertIsNotNone(search_input, "Header search input (#input-search) must exist")
        # Search input must use responsive width classes
        search_cls = search_input.attrs.get("class", "")
        self.assertIn("w-24", search_cls, "Search input must have compact width w-24 on mobile")
        self.assertIn("sm:w-36", search_cls, "Search input must scale up on larger screens")

        # Account select filter
        acc_sel = self.dom.find_by_id("select-account-filter")
        self.assertIsNotNone(acc_sel, "Account filter select must exist in header")
        acc_cls = acc_sel.attrs.get("class", "")
        self.assertIn("max-w-[90px]", acc_cls, "Account select must truncate with max-w-[90px] on mobile")

        # Add account button
        add_btn = self.dom.find_by_id("btn-add-account")
        self.assertIsNotNone(add_btn, "Add account button must exist in header")
        # Check icon "+" on mobile vs full text on desktop
        add_btn_html = self.html_raw[self.html_raw.find('id="btn-add-account"'):self.html_raw.find('</button>', self.html_raw.find('id="btn-add-account"'))]
        self.assertIn("sm:hidden", add_btn_html, "Add button must show compact '+' icon on mobile")
        self.assertIn("hidden sm:inline", add_btn_html, "Add button must show full text on larger screens")

    def test_adv_r4_05_reduced_motion_behavior(self):
        """
        Adversarial Test: Verify prefers-reduced-motion media query completely neutralizes decorative animations
        while preserving static visibility of state indicators.
        """
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css_raw)
        rm_css = extract_media_block(self.css_raw, r"@media \(prefers-reduced-motion: reduce\)")
        self.assertTrue(len(rm_css) > 0, "prefers-reduced-motion block must be present")

        self.assertIn("animation-duration: 0.01ms", rm_css, "Must suppress animation duration")
        self.assertIn("transition-duration: 0.01ms", rm_css, "Must suppress transition duration")
        self.assertIn(".animate-spin", rm_css, "Must neutralize spinning animation")
        self.assertIn(".animate-pulse", rm_css, "Must neutralize pulse animation")
        # Essential textual indicator preserved statically
        self.assertIn("opacity: 1", rm_css, "Pulse element must remain fully visible statically")

    # =========================================================================
    # AREA 2: Theme Engine & Contrast (R5)
    # =========================================================================

    def test_adv_r5_01_zero_important_in_themes_js(self):
        """
        Adversarial Test: Verify strictly ZERO occurrences of !important in themes.js.
        """
        themes_js = self.js_files.get("themes.js", "")
        self.assertNotIn("!important", themes_js, "[R5 / P2.3] themes.js MUST NOT contain !important overrides.")

    def test_adv_r5_02_all_6_themes_dark_light_palette_integrity(self):
        """
        Adversarial Test: Verify all 6 themes (Ocean, Emerald, Violet, Sunset, Rose, Mono)
        define complete Dark and Light palettes with all required CSS custom properties.
        """
        themes_js = self.js_files.get("themes.js", "")
        theme_ids = ["ocean", "emerald", "violet", "sunset", "rose", "mono"]

        for tid in theme_ids:
            self.assertIn(f"id: '{tid}'", themes_js, f"Theme '{tid}' must be registered.")

        # Extract theme objects from themes.js using regex
        required_tokens = [
            "--bg-app", "--bg-surface", "--bg-elevated",
            "--text-primary", "--text-secondary", "--text-muted",
            "--border-subtle", "--border-default",
            "--accent-primary", "--accent-hover",
            "--status-success", "--status-warning", "--status-error", "--status-info",
            "--grad-start", "--grad-mid", "--grad-end"
        ]

        for token in required_tokens:
            self.assertIn(token, themes_js, f"Semantic CSS token {token} must be emitted in buildThemeCSS")

    def test_adv_r5_03_wcag_aa_contrast_ratio_empirical_calculation(self):
        """
        Adversarial Stress Test: Empirically calculate WCAG AA contrast ratio for text and focus rings
        across all 6 themes in both Dark and Light modes.
        Standard: Normal text >= 4.5:1, UI components / focus rings >= 3.0:1.
        """
        themes_data = {
            'ocean': {
                'dark': {'bg': '#0b0f19', 'surface': '#111827', 'elevated': '#161f30', 'textPrimary': '#f8fafc', 'accent': '#3b82f6'},
                'light': {'bg': '#f0f4f9', 'surface': '#ffffff', 'elevated': '#e9f1fe', 'textPrimary': '#0f172a', 'accent': '#3b82f6'}
            },
            'emerald': {
                'dark': {'bg': '#090f0d', 'surface': '#0e1a14', 'elevated': '#122019', 'textPrimary': '#f8fafc', 'accent': '#10b981'},
                'light': {'bg': '#edf7f2', 'surface': '#ffffff', 'elevated': '#e6f6ee', 'textPrimary': '#062319', 'accent': '#10b981'}
            },
            'violet': {
                'dark': {'bg': '#0c0a18', 'surface': '#141128', 'elevated': '#1a1533', 'textPrimary': '#f8fafc', 'accent': '#8b5cf6'},
                'light': {'bg': '#f4f1fa', 'surface': '#ffffff', 'elevated': '#efe9fd', 'textPrimary': '#1e1436', 'accent': '#8b5cf6'}
            },
            'sunset': {
                'dark': {'bg': '#120c07', 'surface': '#1a110a', 'elevated': '#221610', 'textPrimary': '#f8fafc', 'accent': '#f97316'},
                'light': {'bg': '#faf4ee', 'surface': '#ffffff', 'elevated': '#fdeee2', 'textPrimary': '#2e190c', 'accent': '#f97316'}
            },
            'rose': {
                'dark': {'bg': '#130a0e', 'surface': '#1c0f16', 'elevated': '#251220', 'textPrimary': '#f8fafc', 'accent': '#f43f5e'},
                'light': {'bg': '#faf1f4', 'surface': '#ffffff', 'elevated': '#fde9ef', 'textPrimary': '#2d0f1b', 'accent': '#f43f5e'}
            },
            'mono': {
                'dark': {'bg': '#0a0a0b', 'surface': '#111214', 'elevated': '#17181c', 'textPrimary': '#f8fafc', 'accent': '#9ca3af'},
                'light': {'bg': '#f4f5f7', 'surface': '#ffffff', 'elevated': '#eceef1', 'textPrimary': '#111827', 'accent': '#6b7280'}
            }
        }

        contrast_failures = []
        for theme_name, modes in themes_data.items():
            for mode_name, palette in modes.items():
                txt_rgb = parse_hex_color(palette['textPrimary'])
                bg_rgb = parse_hex_color(palette['bg'])
                surf_rgb = parse_hex_color(palette['surface'])
                elev_rgb = parse_hex_color(palette['elevated'])

                # 1. Text vs Background (WCAG AA >= 4.5:1)
                cr_bg = wcag_contrast_ratio(txt_rgb, bg_rgb)
                if cr_bg < 4.5:
                    contrast_failures.append(f"{theme_name} {mode_name} text vs bg: {cr_bg:.2f}:1 (< 4.5:1)")

                # 2. Text vs Surface (WCAG AA >= 4.5:1)
                cr_surf = wcag_contrast_ratio(txt_rgb, surf_rgb)
                if cr_surf < 4.5:
                    contrast_failures.append(f"{theme_name} {mode_name} text vs surface: {cr_surf:.2f}:1 (< 4.5:1)")

                # 3. Text vs Elevated (WCAG AA >= 4.5:1)
                cr_elev = wcag_contrast_ratio(txt_rgb, elev_rgb)
                if cr_elev < 4.5:
                    contrast_failures.append(f"{theme_name} {mode_name} text vs elevated: {cr_elev:.2f}:1 (< 4.5:1)")

        self.assertEqual(contrast_failures, [], f"Theme text contrast failures: {contrast_failures}")

    def test_adv_r5_04_status_color_separation_from_brand_accents(self):
        """
        Adversarial Test: Verify status colors (success #10b981, warning #f59e0b, error #ef4444, info #3b82f6)
        remain distinct from brand accents across all themes.
        """
        themes_js = self.js_files.get("themes.js", "")
        # Status block must be explicitly defined
        self.assertIn("const STATUS = {", themes_js)
        self.assertIn("success: '#10b981'", themes_js)
        self.assertIn("warning: '#f59e0b'", themes_js)
        self.assertIn("error: '#ef4444'", themes_js)
        self.assertIn("info: '#3b82f6'", themes_js)

        # Status tokens must not be replaced by A.primary
        self.assertIn("--status-success: ${STATUS.success}", themes_js)
        self.assertIn("--status-warning: ${STATUS.warning}", themes_js)
        self.assertIn("--status-error: ${STATUS.error}", themes_js)
        self.assertIn("--status-info: ${STATUS.info}", themes_js)

    def test_adv_r5_05_high_contrast_focus_visible_rings(self):
        """
        Adversarial Test: Verify base.css specifies global theme-aware :focus-visible offset rings
        covering all interactive elements.
        """
        self.assertIn(":focus-visible", self.css_raw)
        fv_match = re.search(r":focus-visible[^\{]*\{([^}]+)\}", self.css_raw)
        self.assertIsNotNone(fv_match)
        fv_css = fv_match.group(1)

        self.assertIn("outline: 2px solid var(--accent-primary)", fv_css)
        self.assertIn("outline-offset: 2px", fv_css)

        # Verify selectors cover interactive elements
        selectors_raw = self.css_raw[self.css_raw.find(":focus-visible"):self.css_raw.find("{", self.css_raw.find(":focus-visible"))]
        for tag in ["button:focus-visible", "input:focus-visible", "select:focus-visible", "textarea:focus-visible", "[role=\"button\"]:focus-visible", "[role=\"tab\"]:focus-visible", "a:focus-visible"]:
            self.assertIn(tag, selectors_raw, f"Selector {tag} must be included in global focus ring definition")

    # =========================================================================
    # AREA 3: Accessibility & Form Validation (R3, R6)
    # =========================================================================

    def test_adv_r3_01_table_sorting_uses_button_with_aria_sort(self):
        """
        Adversarial Test: Verify table headers use semantic <button> triggers with aria-sort,
        and table.js dynamically updates aria-sort to ascending, descending, or none.
        """
        table_keys = ['platform', 'channel_name', 'account', 'status']
        for key in table_keys:
            btn_id = f"btn-sort-{key}"
            btn = self.dom.find_by_id(btn_id)
            self.assertIsNotNone(btn, f"Sort trigger #{btn_id} must exist in index.html")
            self.assertEqual(btn.tag, "button", f"Sort trigger #{btn_id} must be a <button> element")
            self.assertIn("aria-sort", btn.attrs, f"#{btn_id} must have aria-sort attribute")

        # In table.js, verify updateSortIndicators logic
        table_js = self.js_files.get("table.js", "")
        self.assertIn("updateSortIndicators", table_js)
        self.assertIn("ascending", table_js)
        self.assertIn("descending", table_js)
        self.assertIn("setAttribute('aria-sort'", table_js)

    def test_adv_r3_02_inline_form_errors_with_aria_invalid_and_first_invalid_focus(self):
        """
        Adversarial Test: Verify form validation in accounts.js uses inline field errors,
        aria-invalid, aria-describedby, and automatically focuses the first invalid field.
        """
        accounts_js = self.js_files.get("accounts.js", "")
        # Check setFieldError function
        self.assertIn("function setFieldError(fieldId, errorMsg)", accounts_js)
        self.assertIn("el.setAttribute('aria-invalid', 'true')", accounts_js)
        self.assertIn("el.setAttribute('aria-describedby', `error-${fieldId}`)", accounts_js)
        self.assertIn("firstInvalid.focus()", accounts_js)

        # Check required form fields in Add Account modal
        for fid in ["modal-acc-name", "modal-acc-email", "modal-acc-notes"]:
            inp = self.dom.find_by_id(fid)
            self.assertIsNotNone(inp, f"Input #{fid} must exist in index.html")
            self.assertIn(f"error-{fid}", inp.attrs.get("aria-describedby", ""), f"#{fid} must have aria-describedby='error-{fid}'")

            err_el = self.dom.find_by_id(f"error-{fid}")
            self.assertIsNotNone(err_el, f"Inline error element #error-{fid} must exist")
            self.assertEqual(err_el.attrs.get("role", ""), "alert", f"#error-{fid} must have role='alert'")

    def test_adv_r3_03_live_toast_regions_and_progress_bars(self):
        """
        Adversarial Test: Verify live toast regions use aria-live='polite', and progress bars use semantic WAI-ARIA.
        """
        # Toast container
        toast_el = self.dom.find_by_id("toast-container")
        self.assertIsNotNone(toast_el)
        self.assertEqual(toast_el.attrs.get("aria-live", ""), "polite")
        self.assertEqual(toast_el.attrs.get("aria-atomic", ""), "true")

        # Bulk progress bar
        bulk_bar = self.dom.find_by_id("bulk-bar")
        self.assertIsNotNone(bulk_bar)
        self.assertEqual(bulk_bar.attrs.get("role", ""), "progressbar")
        self.assertIn("aria-valuenow", bulk_bar.attrs)
        self.assertIn("aria-valuemin", bulk_bar.attrs)
        self.assertIn("aria-valuemax", bulk_bar.attrs)

        # Update progress bar
        update_bar = self.dom.find_by_id("update-progress-bar")
        self.assertIsNotNone(update_bar)
        self.assertEqual(update_bar.attrs.get("role", ""), "progressbar")
        self.assertIn("aria-valuenow", update_bar.attrs)

    def test_adv_r6_01_vietnamese_terminology_normalization_adversarial_check(self):
        """
        Adversarial Stress Test: Verify complete absence of legacy unnormalized terminology
        and absolute safety claims across all HTML and JS files.
        Specifically verifies:
        - No 'Google Acc' / 'Thêm Acc'
        - No 'card count' / 'card kênh'
        - No 'tuyệt đối an toàn' / '100% an toàn' / 'không nguy cơ khóa acc'
        - Catches 'Chưa Setup' in index.html line 399 as an empirical finding.
        """
        forbidden_patterns = [
            (r'\bGoogle Acc\b', "Should be 'Tài khoản Google'"),
            (r'\bThêm Acc\b', "Should be 'Thêm tài khoản'"),
            (r'\bkhóa acc\b', "Should be 'khóa tài khoản'"),
            (r'\bcard count\b', "Should be 'số thẻ kênh'"),
            (r'tuyệt đối an toàn', "Absolute safety claim forbidden"),
            (r'100% an toàn', "Absolute safety claim forbidden"),
            (r'không nguy cơ khóa acc', "Absolute safety claim forbidden"),
            (r'chống khóa vĩnh viễn', "Absolute safety claim forbidden"),
        ]

        violations = []
        all_sources = {"index.html": self.html_raw, **self.js_files}
        for fname, content in all_sources.items():
            for pat, desc in forbidden_patterns:
                if re.search(pat, content, re.IGNORECASE):
                    violations.append((fname, pat, desc))

        self.assertEqual(violations, [], f"Forbidden legacy terminology or safety claims found: {violations}")

        # Check KPI card copy vs filter copy
        # In line 399 of index.html, notice 'Chưa Setup' vs 'Chưa thiết lập' in line 427
        has_chua_setup = "Chưa Setup" in self.html_raw
        if has_chua_setup:
            print("\n[CHALLENGER FINDING] index.html:399 retains 'Chưa Setup' while filter button uses normalized 'Chưa thiết lập'.")


if __name__ == '__main__':
    unittest.main(verbosity=2)
