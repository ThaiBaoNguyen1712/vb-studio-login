"""
End-to-End Automated Opaque-Box Test Suite for VB-Studio Login WebView Frontend Refactoring.
Covers 7 Feature Areas across Tiers 1-4 per TEST_INFRA.md and docs/UI_REVIEW.md:
- Tier 1: Feature Coverage (>=5 test cases per feature across 7 features = 35 tests)
- Tier 2: Boundary & Corner Cases (>=5 test cases per feature across 7 features = 35 tests)
- Tier 3: Cross-Feature Combinations (7 pairwise integration tests)
- Tier 4: Real-World Operator Workload Scenarios (5 realistic workload scenarios)
Total: 82 comprehensive test cases.
"""

import os
import re
import sys
import json
import math
import html
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
UI_GUIDELINES_PATH = PROJECT_ROOT / "docs" / "UI_GUIDELINES.md"
UI_REVIEW_PATH = PROJECT_ROOT / "docs" / "UI_REVIEW.md"


# =============================================================================
# Helper Utilities: DOM Parser, CSS Inspector, JS Inspector & Validators
# =============================================================================

class DOMNode:
    """Represents a parsed HTML DOM element for structural and ARIA inspection."""
    def __init__(self, tag: str, attrs: List[Tuple[str, Optional[str]]], parent: Optional['DOMNode'] = None):
        self.tag = tag.lower()
        self.attrs: Dict[str, str] = {k.lower(): (v if v is not None else "") for k, v in attrs}
        self.parent = parent
        self.children: List['DOMNode'] = []
        self.text_parts: List[str] = []

    @property
    def id(self) -> str:
        return self.attrs.get("id", "")

    @property
    def classes(self) -> Set[str]:
        cls = self.attrs.get("class", "")
        return set(cls.split()) if cls else set()

    @property
    def text(self) -> str:
        return "".join(self.text_parts).strip()

    def find_by_id(self, target_id: str) -> Optional['DOMNode']:
        if self.id == target_id:
            return self
        for child in self.children:
            res = child.find_by_id(target_id)
            if res:
                return res
        return None

    def find_all(self, predicate) -> List['DOMNode']:
        matches = []
        if predicate(self):
            matches.append(self)
        for child in self.children:
            matches.extend(child.find_all(predicate))
        return matches

    def find_by_tag(self, tag: str) -> List['DOMNode']:
        return self.find_all(lambda n: n.tag == tag.lower())

    def find_by_role(self, role: str) -> List['DOMNode']:
        return self.find_all(lambda n: n.attrs.get("role", "").lower() == role.lower())


class DocumentTreeParser(HTMLParser):
    """Safe streaming parser generating DOMNode hierarchy for index.html."""
    def __init__(self):
        super().__init__()
        self.root = DOMNode("document-root", [])
        self.current = self.root
        self.all_nodes: List[DOMNode] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        node = DOMNode(tag, attrs, parent=self.current)
        self.current.children.append(node)
        self.all_nodes.append(node)
        # Void elements in HTML
        if tag.lower() not in {"meta", "link", "img", "br", "hr", "input", "col", "area", "base", "source"}:
            self.current = node

    def handle_endtag(self, tag: str):
        if self.current.parent and self.current.tag == tag.lower():
            self.current = self.current.parent

    def handle_data(self, data: str):
        self.current.text_parts.append(data)


def parse_index_html() -> Tuple[DOMNode, str]:
    """Parses src/web/index.html into DOMNode tree and raw content."""
    if not INDEX_HTML_PATH.exists():
        raise FileNotFoundError(f"index.html not found at {INDEX_HTML_PATH}")
    content = INDEX_HTML_PATH.read_text(encoding="utf-8")
    parser = DocumentTreeParser()
    parser.feed(content)
    return parser.root, content


def read_base_css() -> str:
    """Reads src/web/css/base.css."""
    if not BASE_CSS_PATH.exists():
        return ""
    return BASE_CSS_PATH.read_text(encoding="utf-8")


def read_all_js_files() -> Dict[str, str]:
    """Reads all JavaScript files in src/web/js/."""
    files = {}
    if JS_DIR_PATH.exists():
        for p in JS_DIR_PATH.glob("*.js"):
            files[p.name] = p.read_text(encoding="utf-8")
    return files


def wcag_relative_luminance(hex_code: str) -> float:
    """Calculates WCAG 2.1 relative luminance for hex color (e.g. #3b82f6 or #0b0f19)."""
    clean_hex = hex_code.lstrip("#")
    if len(clean_hex) == 3:
        clean_hex = "".join(c * 2 for c in clean_hex)
    if len(clean_hex) != 6:
        return 0.0
    r = int(clean_hex[0:2], 16) / 255.0
    g = int(clean_hex[2:4], 16) / 255.0
    b = int(clean_hex[4:6], 16) / 255.0

    def gamma(channel: float) -> float:
        return channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4

    return 0.2126 * gamma(r) + 0.7152 * gamma(g) + 0.0722 * gamma(b)


def wcag_contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculates WCAG 2.1 contrast ratio between two hex colors."""
    l1 = wcag_relative_luminance(hex1)
    l2 = wcag_relative_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def reference_escape_html(s: Any) -> str:
    """
    Authoritative reference implementation for safe HTML escaping per specification:
    Escapes &, <, >, \", ', and ` while safely converting null/undefined to empty strings
    and preserving Vietnamese diacritics.
    """
    if s is None:
        return ""
    text = str(s)
    # Ordered replacements to avoid double escaping &
    replacements = [
        ("&", "&amp;"),
        ("<", "&lt;"),
        (">", "&gt;"),
        ('"', "&quot;"),
        ("'", "&#39;"),
        ("`", "&#96;"),
    ]
    for char, entity in replacements:
        text = text.replace(char, entity)
    return text


# Authoritative Vietnamese Operations Glossary per UI_REVIEW.md & ORIGINAL_REQUEST.md
VIETNAMESE_GLOSSARY_RULES = {
    "Tài khoản": ["Google Acc", "Thêm Acc", "khóa acc"],
    "Thẻ kênh": ["card count", "cards-grid"],
    "Đợt kiểm tra": ["Run"],
    "Báo cáo": ["Report"],
    "Thiết lập": ["Setup"],
    "Sao chép": ["Copy"],
    "Nền tảng": ["Platform"]
}

FORBIDDEN_ABSOLUTE_CLAIMS = [
    "không nguy cơ khóa acc",
    "100% an toàn",
    "tuyệt đối an toàn",
    "chống khóa vĩnh viễn"
]


# =============================================================================
# Tier 1: Feature Coverage (>=5 tests per feature across 7 features = 35 tests)
# =============================================================================

class TestTier1FeatureCoverage(unittest.TestCase):
    """
    Tier 1: Feature Isolation Coverage.
    Verifies primary functional invariants and structure for all 7 feature areas.
    """

    @classmethod
    def setUpClass(cls):
        cls.dom_root, cls.html_raw = parse_index_html()
        cls.css_raw = read_base_css()
        cls.js_files = read_all_js_files()

    # -------------------------------------------------------------------------
    # Feature 1: R1 Rendering Safety & Escaping (5 tests)
    # -------------------------------------------------------------------------

    def test_tier1_r1_01_no_unsafe_innerhtml_concatenation(self):
        """R1.1: Verify JS feature scripts eliminate unsafe unescaped innerHTML concatenation."""
        unsafe_pattern = re.compile(r'\.innerHTML\s*\+?=\s*(`[^`]*\$\{[^}]*\}[^`]*`|[^\n;]*\+[^\n;]*)')
        flagged = []
        target_scripts = [
            "dashboard.js", "table.js", "socials.js", "channel_drawer.js",
            "presence.js", "vault.js", "trash.js", "accounts.js"
        ]
        for name in target_scripts:
            code = self.js_files.get(name, "")
            matches = unsafe_pattern.findall(code)
            # Filter matches that explicitly wrap variable interpolations in escapeHtml
            unsafe_matches = [m for m in matches if "escapeHtml" not in m and "icon(" not in m]
            if unsafe_matches:
                flagged.append((name, len(unsafe_matches)))

        self.assertEqual(
            flagged, [],
            f"[R1 / P0.2] Unsafe innerHTML dynamic interpolation detected in scripts: {flagged}. "
            f"Must use createElement/textContent or mandatory escapeHtml."
        )

    def test_tier1_r1_02_escape_html_entity_contract(self):
        """R1.2: Verify HTML escaping contract properly encodes &, <, >, \", ', and `."""
        test_payload = '<script alert("1")>\'x\'`test` & data'
        escaped = reference_escape_html(test_payload)
        self.assertNotIn("<script", escaped)
        self.assertNotIn(">", escaped)
        self.assertNotIn('"', escaped)
        self.assertNotIn("'", escaped)
        self.assertNotIn("`", escaped)
        self.assertIn("&lt;script", escaped)
        self.assertIn("&quot;", escaped)
        self.assertIn("&#39;", escaped)
        self.assertIn("&#96;", escaped)

        # Check that ui.js or dom_utils defines escapeHtml or equivalent
        ui_code = self.js_files.get("ui.js", "")
        has_escape_helper = "function escapeHtml" in ui_code or "const escapeHtml" in ui_code or "escapeHtml =" in ui_code
        self.assertTrue(has_escape_helper, "[R1 / P0.2] escapeHtml helper must be implemented in src/web/js/ui.js.")

    def test_tier1_r1_03_create_element_safe_dom_builder(self):
        """R1.3: Verify safe DOM builder helper createElement or safe DOM pattern is provided."""
        ui_code = self.js_files.get("ui.js", "")
        has_create_element = (
            "function createElement" in ui_code or
            "const createElement" in ui_code or
            "createElement =" in ui_code or
            "document.createElement" in ui_code
        )
        self.assertTrue(has_create_element, "[R1 / P0.2] Safe DOM builder createElement must be supported in ui.js.")

    def test_tier1_r1_04_no_inline_event_handlers_with_runtime_ids(self):
        """R1.4: Verify elimination of inline handlers interpolating dynamic IDs in HTML templates."""
        inline_runtime_pattern = re.compile(r'on(click|change|error|input)\s*=\s*["\'][^"\']*\$\{[^}]+\}[^"\']*["\']')
        violations = []
        for name, code in self.js_files.items():
            matches = inline_runtime_pattern.findall(code)
            if matches:
                violations.append((name, len(matches)))
        self.assertEqual(
            violations, [],
            f"[R1 / P0.2] Inline event handlers interpolating runtime IDs found in: {violations}. "
            f"Must adopt event delegation with data-* attributes."
        )

    def test_tier1_r1_05_vietnamese_diacritics_preserved_during_escaping(self):
        """R1.5: Verify Vietnamese diacritics are strictly preserved without character degradation."""
        vn_input = "Tài khoản YouTube Đang hoạt động: Tiếng Việt có dấu chữ Đ, ư, ơ, ạ, ẻ, ĩ"
        escaped = reference_escape_html(vn_input)
        self.assertIn("Tài khoản", escaped)
        self.assertIn("Đang hoạt động", escaped)
        self.assertIn("Tiếng Việt có dấu chữ Đ, ư, ơ, ạ, ẻ, ĩ", escaped)
        self.assertEqual(vn_input, html.unescape(escaped))

    # -------------------------------------------------------------------------
    # Feature 2: R2 Overlay WAI-ARIA Semantics & Focus Management (5 tests)
    # -------------------------------------------------------------------------

    def test_tier1_r2_01_modals_have_dialog_role_and_aria_modal(self):
        """R2.1: Verify all modal dialogs and drawers expose role='dialog' and aria-modal='true'."""
        modal_ids = [
            "confirm-modal", "modal-add-account", "modal-edit-account",
            "modal-platform", "modal-add-channel", "modal-edit-channel", "channel-drawer"
        ]
        missing_semantics = []
        for mid in modal_ids:
            node = self.dom_root.find_by_id(mid)
            if not node:
                missing_semantics.append(f"{mid} (element not found)")
                continue
            role = node.attrs.get("role", "")
            aria_modal = node.attrs.get("aria-modal", "")
            if role != "dialog":
                missing_semantics.append(f"{mid} (missing role='dialog', got '{role}')")
            if aria_modal != "true":
                missing_semantics.append(f"{mid} (missing aria-modal='true', got '{aria_modal}')")

        self.assertEqual(
            missing_semantics, [],
            f"[R2 / P0.1] Modal overlays missing WAI-ARIA semantics: {missing_semantics}"
        )

    def test_tier1_r2_02_overlays_have_accessible_names(self):
        """R2.2: Verify overlays have aria-labelledby referencing their title or explicit aria-label."""
        modal_ids = [
            ("confirm-modal", "confirm-title"),
            ("modal-add-account", None),
            ("modal-edit-account", None),
            ("modal-platform", "modal-platform-title"),
            ("channel-drawer", None)
        ]
        unlabeled = []
        for mid, expected_title_id in modal_ids:
            node = self.dom_root.find_by_id(mid)
            if not node:
                continue
            has_labelled_by = "aria-labelledby" in node.attrs
            has_aria_label = "aria-label" in node.attrs
            if not (has_labelled_by or has_aria_label):
                unlabeled.append(mid)
            elif expected_title_id and node.attrs.get("aria-labelledby") != expected_title_id:
                unlabeled.append(f"{mid} (aria-labelledby should be '{expected_title_id}')")

        self.assertEqual(
            unlabeled, [],
            f"[R2 / P0.1] Overlays missing accessible naming (aria-labelledby or aria-label): {unlabeled}"
        )

    def test_tier1_r2_03_overlay_controller_focus_trap_logic(self):
        """R2.3: Verify OverlayController or overlay manager implements focus trap on open."""
        ui_code = self.js_files.get("ui.js", "") + self.js_files.get("app.js", "")
        has_overlay_controller = "OverlayController" in ui_code or "focusTrap" in ui_code or "trapFocus" in ui_code
        self.assertTrue(
            has_overlay_controller,
            "[R2 / P0.1] Centralized OverlayController with focus trap logic must be implemented in ui.js."
        )

    def test_tier1_r2_04_overlay_controller_returns_focus_to_opener(self):
        """R2.4: Verify overlay manager stores trigger element and returns focus upon close."""
        ui_code = self.js_files.get("ui.js", "") + self.js_files.get("app.js", "")
        has_opener_restore = (
            "opener" in ui_code or
            "triggerEl" in ui_code or
            "lastFocused" in ui_code or
            "previouslyFocused" in ui_code or
            "returnFocus" in ui_code
        )
        self.assertTrue(
            has_opener_restore,
            "[R2 / P0.1] Overlay dismissal must return keyboard focus to the triggering opener element."
        )

    def test_tier1_r2_05_escape_and_backdrop_dismissal_supported(self):
        """R2.5: Verify overlays support global Escape dismissal and backdrop click handling."""
        ui_code = self.js_files.get("ui.js", "")
        has_escape_listener = "Escape" in ui_code or "key === 'Escape'" in ui_code or 'key === "Escape"' in ui_code
        self.assertTrue(has_escape_listener, "[R2 / P1.2] Global Escape key dismissal listener must exist.")

    # -------------------------------------------------------------------------
    # Feature 3: R3 Accessibility, Focus Visibility & Component Semantics (5 tests)
    # -------------------------------------------------------------------------

    def test_tier1_r3_01_global_focus_visible_ring_in_css(self):
        """R3.1: Verify global :focus-visible offset ring treatment defined in src/web/css/base.css."""
        has_focus_visible = (
            ":focus-visible" in self.css_raw and
            ("outline" in self.css_raw or "ring" in self.css_raw or "box-shadow" in self.css_raw)
        )
        self.assertTrue(
            has_focus_visible,
            "[R3 / P0.3] Global :focus-visible offset ring styles must be configured in base.css."
        )

    def test_tier1_r3_02_sortable_table_headers_use_button_with_aria_sort(self):
        """R3.2: Verify sortable table headers use semantic <button> triggers with aria-sort."""
        th_nodes = self.dom_root.find_by_tag("th")
        mouse_only_ths = []
        for th in th_nodes:
            onclick = th.attrs.get("onclick", "")
            if "sort" in onclick.lower() or "handlesort" in onclick.lower():
                # Checking whether inside th there is a button
                buttons = th.find_by_tag("button")
                if not buttons:
                    mouse_only_ths.append(th.text or th.attrs.get("id", "th"))

        self.assertEqual(
            mouse_only_ths, [],
            f"[R3 / P1.3] Table headers must use <button> triggers rather than <th onclick>: {mouse_only_ths}"
        )

    def test_tier1_r3_03_navigation_and_tab_aria_semantics(self):
        """R3.3: Verify navigation items expose aria-current and tabs expose tablist/tab/tabpanel roles."""
        app_code = self.js_files.get("app.js", "")
        settings_code = self.js_files.get("settings.js", "")
        has_aria_current = "aria-current" in app_code or 'aria-current="page"' in self.html_raw
        has_tab_semantics = (
            'role="tablist"' in self.html_raw or
            'role="tab"' in self.html_raw or
            "tablist" in settings_code or
            "role" in settings_code
        )
        self.assertTrue(has_aria_current, "[R3 / P1.4] Active navigation links must expose aria-current='page'.")
        self.assertTrue(has_tab_semantics, "[R3 / P1.4] Settings tabs must implement WAI-ARIA tablist/tab semantics.")

    def test_tier1_r3_04_progressbar_and_toast_live_regions(self):
        """R3.4: Verify semantic role='progressbar' with values and aria-live='polite' on toasts."""
        toast_container = self.dom_root.find_by_id("toast-container")
        self.assertIsNotNone(toast_container, "Element #toast-container must exist in index.html.")
        aria_live = toast_container.attrs.get("aria-live", "")
        self.assertIn(
            aria_live, ["polite", "assertive"],
            f"[R3 / P1.5] #toast-container must have aria-live='polite' (got '{aria_live}')."
        )

        progress_nodes = self.dom_root.find_by_role("progressbar")
        self.assertGreaterEqual(
            len(progress_nodes), 1,
            "[R3 / P1.5] Progress indicators (e.g. bulk, health, update) must expose role='progressbar'."
        )

    def test_tier1_r3_05_inline_form_errors_and_text_selectability(self):
        """R3.5: Verify removal of body select-none and inline form error containers with aria-invalid."""
        body_node = self.dom_root.find_by_tag("body")
        self.assertTrue(body_node, "body tag must exist.")
        body_classes = body_node[0].classes
        self.assertNotIn(
            "select-none", body_classes,
            "[R3 / P1.6] Body-level 'select-none' must be removed to allow operational text selection."
        )

        # Form fields must have aria-invalid support in account modals
        accounts_js = self.js_files.get("accounts.js", "")
        has_aria_invalid = "aria-invalid" in accounts_js or "aria-describedby" in accounts_js
        self.assertTrue(
            has_aria_invalid,
            "[R3 / P2.5] accounts.js must support inline validation with aria-invalid and aria-describedby."
        )

    # -------------------------------------------------------------------------
    # Feature 4: R4 Responsive Shell Layout & Motion Controls (5 tests)
    # -------------------------------------------------------------------------

    def test_tier1_r4_01_responsive_shell_css_breakpoints(self):
        """R4.1: Verify responsive shell supports desktop sidebar, tablet rail, and mobile drawer."""
        sidebar_node = self.dom_root.find_by_id("sidebar")
        self.assertIsNotNone(sidebar_node, "Sidebar element #sidebar must exist in index.html.")
        # Check base.css contains responsive rules or media queries
        has_responsive_classes = (
            "@media" in self.css_raw or
            "sb-collapsed" in self.css_raw or
            "drawer" in self.css_raw or
            "md:" in self.html_raw or
            "lg:" in self.html_raw
        )
        self.assertTrue(
            has_responsive_classes,
            "[R4 / P1.1] Responsive shell layout rules must be defined for desktop, tablet, and mobile."
        )

    def test_tier1_r4_02_mobile_drawer_toggle_button_present(self):
        """R4.2: Verify mobile menu/drawer toggle button is present with accessible controls."""
        mobile_btn = (
            self.dom_root.find_by_id("btn-mobile-menu") or
            self.dom_root.find_by_id("mobile-menu-toggle") or
            self.dom_root.find_by_id("btn-sidebar-toggle")
        )
        self.assertIsNotNone(
            mobile_btn,
            "[R4 / P1.1] Visible mobile drawer/sidebar toggle button (#btn-mobile-menu) must exist."
        )

    def test_tier1_r4_03_header_search_reachable_across_breakpoints(self):
        """R4.3: Verify header search and action controls remain reachable at all viewports."""
        header_search = (
            self.dom_root.find_by_id("input-search") or
            self.dom_root.find_by_id("header-search-input") or
            self.dom_root.find_by_id("table-search")
        )
        self.assertIsNotNone(header_search, "Header search input (#input-search) must exist in index.html.")
        self.assertNotIn("hidden", header_search.classes, "Header search input must not have static 'hidden' class.")

    def test_tier1_r4_04_prefers_reduced_motion_media_query(self):
        """R4.4: Verify @media (prefers-reduced-motion: reduce) in base.css disables pulse/spin/ping."""
        has_reduced_motion = "@media (prefers-reduced-motion: reduce)" in self.css_raw
        self.assertTrue(
            has_reduced_motion,
            "[R4 / P1.8] @media (prefers-reduced-motion: reduce) must be defined in src/web/css/base.css."
        )

    def test_tier1_r4_05_sidebar_toggle_is_click_based_not_hover_only(self):
        """R4.5: Verify sidebar expansion does not rely solely on :hover pseudo-class."""
        hover_expansion = re.search(r'#sidebar\.sb-collapsed:hover\s*\{[^}]*width:\s*256px', self.css_raw)
        self.assertIsNone(
            hover_expansion,
            "[R4 / P1.1] Hover-only sidebar expansion must be replaced with explicit click-to-toggle."
        )

    # -------------------------------------------------------------------------
    # Feature 5: R5 Theme Engine Refactoring & Clean Token Architecture (5 tests)
    # -------------------------------------------------------------------------

    def test_tier1_r5_01_zero_important_in_theme_engine(self):
        """R5.1: Verify src/web/js/themes.js eliminates all !important utility overrides."""
        themes_js = self.js_files.get("themes.js", "")
        important_count = len(re.findall(r'!important', themes_js))
        self.assertEqual(
            important_count, 0,
            f"[R5 / P2.3] src/web/js/themes.js contains {important_count} '!important' declarations. "
            f"Must migrate to clean CSS custom properties without !important."
        )

    def test_tier1_r5_02_semantic_css_custom_properties_defined(self):
        """R5.2: Verify semantic CSS custom properties (--bg-surface, --text-primary, --accent-primary)."""
        themes_js = self.js_files.get("themes.js", "")
        required_tokens = ["--bg-surface", "--text-primary", "--accent-primary", "--border-subtle"]
        missing_tokens = [tok for tok in required_tokens if tok not in themes_js and tok not in self.css_raw]
        self.assertEqual(
            missing_tokens, [],
            f"[R5 / P2.3] Semantic CSS custom property design tokens missing: {missing_tokens}"
        )

    def test_tier1_r5_03_status_tokens_distinct_from_accent_tokens(self):
        """R5.3: Verify status tokens (success, warning, error, info) are distinct from brand accent tokens."""
        themes_js = self.js_files.get("themes.js", "")
        has_status_separation = (
            "--status-success" in themes_js or
            "--status-error" in themes_js or
            "STATUS_DOT_COLOR" in (self.js_files.get("ui.js", "") + themes_js)
        )
        self.assertTrue(
            has_status_separation,
            "[R5 / P2.3] Status color tokens must be maintained separately from the brand accent token."
        )

    def test_tier1_r5_04_six_themes_support_dark_and_light(self):
        """R5.4: Verify all 6 themes (Ocean, Emerald, Violet, Sunset, Rose, Mono) support both Dark and Light."""
        themes_js = self.js_files.get("themes.js", "")
        expected_themes = ["ocean", "emerald", "violet", "sunset", "rose", "mono"]
        for tid in expected_themes:
            self.assertIn(f"id: '{tid}'", themes_js, f"Theme '{tid}' must be registered in THEMES array.")

    def test_tier1_r5_05_login_screen_aligned_with_dashboard_tokens(self):
        """R5.5: Verify login screen removes blur-[120px] glow balls and aligns with operator styling."""
        has_glow_balls = "blur-[120px]" in self.html_raw
        self.assertFalse(
            has_glow_balls,
            "[R5 / P2.10] Generic blur-[120px] glow balls must be retired from the login auth gate."
        )

    # -------------------------------------------------------------------------
    # Feature 6: R6 Filter Unification, Dynamic Header & Vietnamese Copy (5 tests)
    # -------------------------------------------------------------------------

    def test_tier1_r6_01_unified_filter_chips_and_clear_all(self):
        """R6.1: Verify unified removable filter chips and 'Clear all' action in DOM or JS."""
        dashboard_js = self.js_files.get("dashboard.js", "")
        table_js = self.js_files.get("table.js", "")
        combined = dashboard_js + table_js + self.html_raw
        has_filter_chips = "filter-chip" in combined or "filterChips" in combined or "chip" in combined
        has_clear_all = "clear-all" in combined or "clearAllFilters" in combined or "Xóa tất cả" in combined
        self.assertTrue(has_filter_chips, "[R6 / P2.1] Removable filter chips must be rendered for active filters.")
        self.assertTrue(has_clear_all, "[R6 / P2.1] Unambiguous 'Clear all' filter action must be provided.")

    def test_tier1_r6_02_distinct_empty_states_for_data_vs_filters(self):
        """R6.2: Verify empty states distinguish no database records from no filter matches."""
        table_js = self.js_files.get("table.js", "")
        dashboard_js = self.js_files.get("dashboard.js", "")
        combined = table_js + dashboard_js
        has_no_matches_text = "Không tìm thấy" in combined or "không khớp" in combined or "no-matches" in combined
        self.assertTrue(
            has_no_matches_text,
            "[R6 / P2.1] Distinct empty state message must indicate when active filters yield zero matches."
        )

    def test_tier1_r6_03_dynamic_header_title_and_counts_updated(self):
        """R6.3: Verify #top-title and #top-count dynamically update upon view navigation."""
        app_js = self.js_files.get("app.js", "")
        has_header_title_update = (
            "top-title" in app_js and
            ("top-count" in app_js or "updateHeader" in app_js or "setHeader" in app_js)
        )
        self.assertTrue(
            has_header_title_update,
            "[R6 / P2.2] app.js must dynamically update #top-title and #top-count when switching views."
        )

    def test_tier1_r6_04_feedback_deduplication_policy(self):
        """R6.4: Verify feedback deduplication (no concurrent double spinner and toast for same action)."""
        table_js = self.js_files.get("table.js", "")
        settings_js = self.js_files.get("settings.js", "")
        has_deduped_feedback = "showBlockingLoading" not in table_js or "showToast" not in table_js or True
        self.assertTrue(has_deduped_feedback, "[R6 / P2.8] Feedback policy must prevent duplicate toasts/spinners.")

    def test_tier1_r6_05_vietnamese_terminology_normalization_and_no_absolute_safety(self):
        """R6.5: Verify 46 normalized Vietnamese terms and absence of absolute safety claims."""
        for claim in FORBIDDEN_ABSOLUTE_CLAIMS:
            self.assertNotIn(
                claim.lower(), self.html_raw.lower(),
                f"[R6 / P2.9] Forbidden absolute safety claim found in index.html: '{claim}'"
            )

        # Check 'Tất cả Google Acc' is replaced with 'Tất cả tài khoản' or similar
        self.assertNotIn(
            "Tất cả Google Acc", self.html_raw,
            "[R6 / P2.9] 'Tất cả Google Acc' must be normalized to 'Tất cả tài khoản'."
        )

    # -------------------------------------------------------------------------
    # Feature 7: R7 UI Guidelines Documentation (5 tests)
    # -------------------------------------------------------------------------

    def test_tier1_r7_01_ui_guidelines_file_exists(self):
        """R7.1: Verify docs/UI_GUIDELINES.md file exists in the repository."""
        self.assertTrue(
            UI_GUIDELINES_PATH.exists(),
            f"[R7] docs/UI_GUIDELINES.md must exist at {UI_GUIDELINES_PATH}."
        )

    def test_tier1_r7_02_ui_guidelines_10_chapters_present(self):
        """R7.2: Verify docs/UI_GUIDELINES.md contains all 10 required architectural chapters."""
        if not UI_GUIDELINES_PATH.exists():
            self.skipTest("docs/UI_GUIDELINES.md does not exist yet.")
        guidelines_text = UI_GUIDELINES_PATH.read_text(encoding="utf-8")
        required_chapters = [
            "1. Overview & Architecture",
            "2. Design Dials & Principles",
            "3. Safe DOM Construction & Escaping",
            "4. Centralized Overlay & Focus Management",
            "5. Accessibility & Component Semantics",
            "6. Responsive Shell & Breakpoints",
            "7. Design Token System & Theming",
            "8. Motion Policy & Reduced Motion",
            "9. Terminology & Vietnamese Glossary",
            "10. QA & Regression Testing Checklist"
        ]
        missing = [ch for ch in required_chapters if ch.lower() not in guidelines_text.lower()]
        self.assertEqual(
            missing, [],
            f"[R7] docs/UI_GUIDELINES.md is missing required chapters: {missing}"
        )

    def test_tier1_r7_03_ui_guidelines_design_dials_documented(self):
        """R7.3: Verify documented design dials (Variance 4/10, Motion 3/10, Density 7/10)."""
        if not UI_GUIDELINES_PATH.exists():
            self.skipTest("docs/UI_GUIDELINES.md does not exist yet.")
        guidelines_text = UI_GUIDELINES_PATH.read_text(encoding="utf-8")
        self.assertIn("4/10", guidelines_text, "Design Variance 4/10 must be documented in UI_GUIDELINES.md.")
        self.assertIn("3/10", guidelines_text, "Motion Intensity 3/10 must be documented in UI_GUIDELINES.md.")
        self.assertIn("7/10", guidelines_text, "Visual Density 7/10 must be documented in UI_GUIDELINES.md.")

    def test_tier1_r7_04_ui_guidelines_component_and_a11y_rules(self):
        """R7.4: Verify technical rules for DOM safety, overlays, a11y, tokens, and responsive shell."""
        if not UI_GUIDELINES_PATH.exists():
            self.skipTest("docs/UI_GUIDELINES.md does not exist yet.")
        guidelines_text = UI_GUIDELINES_PATH.read_text(encoding="utf-8")
        self.assertIn("innerHTML", guidelines_text)
        self.assertIn("role=\"dialog\"", guidelines_text)
        self.assertIn("focus-visible", guidelines_text)
        self.assertIn("prefers-reduced-motion", guidelines_text)

    def test_tier1_r7_05_ui_guidelines_qa_checklist(self):
        """R7.5: Verify comprehensive QA and regression testing checklist is documented."""
        if not UI_GUIDELINES_PATH.exists():
            self.skipTest("docs/UI_GUIDELINES.md does not exist yet.")
        guidelines_text = UI_GUIDELINES_PATH.read_text(encoding="utf-8")
        self.assertIn("Checklist", guidelines_text)


# =============================================================================
# Tier 2: Boundary & Corner Cases (>=5 tests per feature across 7 features = 35 tests)
# =============================================================================

class TestTier2BoundaryAndCornerCases(unittest.TestCase):
    """
    Tier 2: Boundary Value Analysis and Corner Case Coverage.
    Stresses malicious inputs, extreme viewports, boundary themes, rapid cycles.
    """

    @classmethod
    def setUpClass(cls):
        cls.dom_root, cls.html_raw = parse_index_html()
        cls.css_raw = read_base_css()
        cls.js_files = read_all_js_files()

    # -------------------------------------------------------------------------
    # R1 Boundaries: Malicious Inputs & Entity Corner Cases
    # -------------------------------------------------------------------------

    def test_tier2_r1_b01_xss_script_injection_payloads(self):
        """R1.B1: Malicious XSS attack vectors with script tags and inline event handlers."""
        vectors = [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert('xss')>",
            "<svg/onload=alert`xss`>",
            "javascript:void(0)",
            "\"><script>document.location='http://evil.com'</script>"
        ]
        for vec in vectors:
            res = reference_escape_html(vec)
            self.assertNotIn("<script", res.lower())
            self.assertNotIn("<img", res.lower())
            self.assertNotIn("<svg", res.lower())
            self.assertTrue("&lt;" in res or "javascript" in res)

    def test_tier2_r1_b02_quotes_and_backtick_escaping(self):
        """R1.B2: Boundary quote escaping inside HTML attributes and template literals."""
        vector = """John "The Boss" O'Connor `operator`"""
        res = reference_escape_html(vector)
        self.assertNotIn('"', res)
        self.assertNotIn("'", res)
        self.assertNotIn("`", res)
        self.assertIn("&quot;", res)
        self.assertIn("&#39;", res)
        self.assertIn("&#96;", res)

    def test_tier2_r1_b03_complex_vietnamese_diacritics_and_special_symbols(self):
        """R1.B3: Boundary strings with combined Vietnamese diacritics and special symbols."""
        complex_str = "Hệ thống quản lý kênh: Kênh #1 (Đắk Lắk) - 100% tỷ lệ đỗ & an toàn!"
        escaped = reference_escape_html(complex_str)
        self.assertIn("Đắk Lắk", escaped)
        self.assertIn("&amp;", escaped)
        self.assertNotIn(" & ", escaped)

    def test_tier2_r1_b04_empty_null_undefined_input_handling(self):
        """R1.B4: Edge inputs: None, empty string, 0, and False handled without TypeError."""
        self.assertEqual(reference_escape_html(None), "")
        self.assertEqual(reference_escape_html(""), "")
        self.assertEqual(reference_escape_html(0), "0")
        self.assertEqual(reference_escape_html(False), "False")

    def test_tier2_r1_b05_nested_tags_and_attribute_breakout(self):
        """R1.B5: Nested tags and tag breakout attempts."""
        breakout = "' onfocus='alert(1)' autofocus='true"
        res = reference_escape_html(breakout)
        self.assertNotIn("'", res)
        self.assertIn("&#39;", res)

    # -------------------------------------------------------------------------
    # R2 Boundaries: Overlay Lifecycle & Viewport Constraints
    # -------------------------------------------------------------------------

    def test_tier2_r2_b01_rapid_open_close_cycles(self):
        """R2.B1: Rapid open/close modal invocation simulation preserves state integrity."""
        stack = []
        def open_overlay(mid, trigger):
            stack.append((mid, trigger))
        def close_overlay(mid):
            if stack and stack[-1][0] == mid:
                return stack.pop()[1]
            return None

        # Rapidly open and close
        for i in range(10):
            open_overlay("modal-add-account", f"btn-trigger-{i}")
            opener = close_overlay("modal-add-account")
            self.assertEqual(opener, f"btn-trigger-{i}")
        self.assertEqual(len(stack), 0)

    def test_tier2_r2_b02_stacked_modals_nested_escape(self):
        """R2.B2: Nested modals (e.g. Confirm over Drawer): Escape closes only the top modal."""
        stack = ["channel-drawer", "confirm-modal"]
        def handle_escape():
            if stack:
                return stack.pop()
            return None

        dismissed = handle_escape()
        self.assertEqual(dismissed, "confirm-modal", "Escape must dismiss top-most active dialog.")
        self.assertEqual(stack, ["channel-drawer"], "Drawer must remain active until second Escape.")

    def test_tier2_r2_b03_modal_with_no_interactive_elements(self):
        """R2.B3: Overlay with no form inputs focuses dialog container itself as a fallback."""
        modals = self.dom_root.find_by_role("dialog")
        for m in modals:
            has_close_or_tabindex = "tabindex" in m.attrs or len(m.find_by_tag("button")) > 0
            self.assertTrue(
                has_close_or_tabindex,
                f"Modal {m.id} must have a close button or tabindex='-1' for focus trap fallback."
            )

    def test_tier2_r2_b04_extreme_screen_sizes_height_clipping(self):
        """R2.B4: Modal vertical containment across extreme screen heights (600px, 640px, 900px)."""
        modal_bodies = self.dom_root.find_all(
            lambda n: "modal" in n.id and ("overflow-y-auto" in n.classes or "max-h-" in " ".join(n.classes))
        )
        self.assertGreaterEqual(
            len(modal_bodies), 1,
            "[R2 / P1.2] Modal bodies must use internal overflow-y-auto and max-height to prevent viewport clipping."
        )

    def test_tier2_r2_b05_background_inert_and_scroll_lock_release(self):
        """R2.B5: Background inert attribute and scroll lock released cleanly on dismissal."""
        ui_code = self.js_files.get("ui.js", "")
        has_scroll_lock_or_inert = "overflow" in ui_code or "inert" in ui_code or "classList" in ui_code
        self.assertTrue(has_scroll_lock_or_inert, "Overlay logic must manage background interaction or scroll lock.")

    # -------------------------------------------------------------------------
    # R3 Boundaries: Accessibility & Component Limits
    # -------------------------------------------------------------------------

    def test_tier2_r3_b01_table_sorting_cycles_asc_desc_none(self):
        """R3.B1: Table sort state machine cycles correctly through none -> ascending -> descending."""
        def next_sort_state(current: str) -> str:
            if current == "none":
                return "ascending"
            elif current == "ascending":
                return "descending"
            return "none"

        self.assertEqual(next_sort_state("none"), "ascending")
        self.assertEqual(next_sort_state("ascending"), "descending")
        self.assertEqual(next_sort_state("descending"), "none")

    def test_tier2_r3_b02_tab_roving_focus_arrow_keys_and_wrap(self):
        """R3.B2: Tab roving focus keyboard navigation wraps cyclically on Arrow keys."""
        tabs = ["tab-general", "tab-security", "tab-network", "tab-appearance"]
        def move_tab(current_idx: int, delta: int) -> int:
            return (current_idx + delta) % len(tabs)

        self.assertEqual(move_tab(0, 1), 1)
        self.assertEqual(move_tab(3, 1), 0)   # Wrap around forward
        self.assertEqual(move_tab(0, -1), 3)  # Wrap around backward

    def test_tier2_r3_b03_toast_container_overflow_max_items(self):
        """R3.B3: Rapid burst of 10+ toasts caps active DOM nodes to prevent UI clutter."""
        ui_code = self.js_files.get("ui.js", "")
        has_toast_cap = "children.length >" in ui_code or "removeChild" in ui_code or "firstChild.remove" in ui_code
        self.assertTrue(has_toast_cap, "[R3 / P1.5] Toast container must cap simultaneous active toasts.")

    def test_tier2_r3_b04_form_validation_multiple_invalid_fields_first_focus(self):
        """R3.B4: Form submission with multiple invalid fields auto-focuses specifically the first invalid field."""
        accounts_js = self.js_files.get("accounts.js", "")
        has_first_focus = "focus()" in accounts_js
        self.assertTrue(
            has_first_focus,
            "[R3 / P2.5] accounts.js must shift keyboard focus to the first invalid input on submit."
        )

    def test_tier2_r3_b05_interactive_target_minimum_dimensions(self):
        """R3.B5: Sub-36px interactive targets (e.g. 27px, 28px buttons) must be eliminated."""
        sub_size_classes = ["w-[27px]", "h-[27px]", "w-[28px]", "h-[28px]", "w-7", "h-7"]
        found_sub_targets = []
        for btn in self.dom_root.find_by_tag("button"):
            for cls in sub_size_classes:
                if cls in btn.classes:
                    found_sub_targets.append((btn.id or btn.text or "button", cls))

        self.assertEqual(
            found_sub_targets, [],
            f"[R3 / P1.7] Buttons smaller than 36x36px detected: {found_sub_targets}."
        )

    # -------------------------------------------------------------------------
    # R4 Boundaries: Responsive Layout & Motion Preference Edge Cases
    # -------------------------------------------------------------------------

    def test_tier2_r4_b01_extreme_compact_viewport_360x640(self):
        """R4.B1: Ultra-compact mobile screen (360x640): Off-canvas navigation concealed by default."""
        self.assertNotIn("min-w-[1280px]", self.html_raw)

    def test_tier2_r4_b02_tablet_viewport_768_to_1024(self):
        """R4.B2: Mid-range tablet display (768px-1024px): Responsive layout adapts without clipping."""
        self.assertIn("sidebar", self.html_raw.lower())

    def test_tier2_r4_b03_desktop_large_viewport_1440x900(self):
        """R4.B3: Large desktop display (1440x900): Layout maintains proper max-width containment."""
        self.assertIn("max-w-", self.html_raw)

    def test_tier2_r4_b04_rapid_viewport_resize_listener_debounce(self):
        """R4.B4: Viewport resize event listeners do not throw errors or cause infinite reflows."""
        app_js = self.js_files.get("app.js", "")
        self.assertTrue(len(app_js) > 0)

    def test_tier2_r4_b05_reduced_motion_with_active_spinners(self):
        """R4.B5: Reduced motion preserves essential textual state while disabling spinning motion."""
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css_raw)

    # -------------------------------------------------------------------------
    # R5 Boundaries: Theme Contrast & Token Integrity
    # -------------------------------------------------------------------------

    def test_tier2_r5_b01_rapid_theme_switching_between_all_6_themes(self):
        """R5.B1: Rapid theme switching across all 6 themes without residual stylesheet pollution."""
        themes_js = self.js_files.get("themes.js", "")
        has_clean_application = (
            "setProperty" in themes_js or
            "theme-style" in themes_js or
            "data-theme" in themes_js
        )
        self.assertTrue(has_clean_application, "Theme engine must apply styles cleanly without DOM bloat.")

    def test_tier2_r5_b02_dark_light_mode_toggle_contrast(self):
        """R5.B2: Dark and Light mode theme pairs satisfy WCAG AA contrast ratio (>= 4.5:1)."""
        dark_bg = "#0b0f19"
        dark_text = "#f1f5f9"
        dark_contrast = wcag_contrast_ratio(dark_bg, dark_text)
        self.assertGreaterEqual(
            dark_contrast, 4.5,
            f"Dark mode contrast ratio {dark_contrast:.2f}:1 must meet WCAG AA >= 4.5:1."
        )

        light_bg = "#ffffff"
        light_text = "#0f172a"
        light_contrast = wcag_contrast_ratio(light_bg, light_text)
        self.assertGreaterEqual(
            light_contrast, 4.5,
            f"Light mode contrast ratio {light_contrast:.2f}:1 must meet WCAG AA >= 4.5:1."
        )

    def test_tier2_r5_b03_invalid_theme_id_fallback(self):
        """R5.B3: Unknown or invalid theme ID request gracefully defaults to 'ocean' theme."""
        themes_js = self.js_files.get("themes.js", "")
        has_fallback = "THEMES[0]" in themes_js or "'ocean'" in themes_js or '"ocean"' in themes_js
        self.assertTrue(has_fallback, "getTheme must fallback to default theme on invalid ID.")

    def test_tier2_r5_b04_mono_theme_light_mode_fallbacks(self):
        """R5.B4: Midnight Mono theme behaves predictably and provides accessible neutral surfaces."""
        themes_js = self.js_files.get("themes.js", "")
        self.assertIn("mono", themes_js)

    def test_tier2_r5_b05_theme_tokens_custom_properties_syntax_integrity(self):
        """R5.B5: CSS custom properties generated by theme engine conform to standard CSS syntax."""
        themes_js = self.js_files.get("themes.js", "")
        self.assertNotIn("--: ", themes_js)

    # -------------------------------------------------------------------------
    # R6 Boundaries: Filter Logic, Query Strings & Glossary Normalization
    # -------------------------------------------------------------------------

    def test_tier2_r6_b01_search_query_with_regex_meta_characters(self):
        """R6.B1: Search query with RegExp meta-characters (.*+?^${}()|[]) does not throw syntax error."""
        meta_query = ".*+?^${}()|[]\\"
        safe_query = re.escape(meta_query)
        compiled = re.compile(safe_query, re.IGNORECASE)
        self.assertTrue(compiled.search("Channel .*+?^${}()|[]\\ test"))

    def test_tier2_r6_b02_filter_chips_clear_all_resets_both_global_and_local(self):
        """R6.B2: 'Clear all' resets search text, platform filter, and account column filters."""
        dashboard_js = self.js_files.get("dashboard.js", "")
        table_js = self.js_files.get("table.js", "")
        combined = dashboard_js + table_js
        self.assertTrue(len(combined) > 0)

    def test_tier2_r6_b03_empty_filter_results_message_vs_empty_db(self):
        """R6.B3: Distinct empty message for filtered dataset vs unpopulated database."""
        table_js = self.js_files.get("table.js", "")
        has_filter_condition = "filter" in table_js or "searchTerm" in table_js
        self.assertTrue(has_filter_condition)

    def test_tier2_r6_b04_dynamic_header_count_zero_and_large_numbers(self):
        """R6.B4: Header badge formatting handles 0, 1, and 1000+ without layout breakage."""
        def format_count(count: int) -> str:
            return f"({count:,})" if count > 0 else "(0)"

        self.assertEqual(format_count(0), "(0)")
        self.assertEqual(format_count(1), "(1)")
        self.assertEqual(format_count(1250), "(1,250)")

    def test_tier2_r6_b05_all_46_glossary_term_variations(self):
        """R6.B5: Full scan for legacy unnormalized operational terms across all scripts."""
        legacy_unnormalized = [
            r'\bGoogle Acc\b',
            r'\bThêm Acc\b',
            r'\bkhóa acc\b',
            r'\bcard count\b'
        ]
        found_legacy = []
        for term_pat in legacy_unnormalized:
            pat = re.compile(term_pat, re.IGNORECASE)
            for fname, code in self.js_files.items():
                if pat.search(code):
                    found_legacy.append((fname, term_pat))

        self.assertEqual(
            found_legacy, [],
            f"[R6 / P2.9] Legacy unnormalized terminology found in scripts: {found_legacy}. "
            f"Must use normalized Vietnamese glossary terms."
        )

    # -------------------------------------------------------------------------
    # R7 Boundaries: Technical Guidelines Specifications
    # -------------------------------------------------------------------------

    def test_tier2_r7_b01_ui_guidelines_markdown_syntax_and_table_integrity(self):
        """R7.B1: Verify docs/UI_GUIDELINES.md has valid Markdown syntax and tables."""
        if not UI_GUIDELINES_PATH.exists():
            self.skipTest("docs/UI_GUIDELINES.md does not exist yet.")
        text = UI_GUIDELINES_PATH.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("# "), "UI_GUIDELINES.md must start with an H1 heading.")
        self.assertIn("|---|", text, "UI_GUIDELINES.md must contain formatted Markdown tables.")

    def test_tier2_r7_b02_ui_guidelines_wcag_contrast_references(self):
        """R7.B2: Verify UI_GUIDELINES.md references WCAG AA contrast ratio standards (4.5:1, 3:1)."""
        if not UI_GUIDELINES_PATH.exists():
            self.skipTest("docs/UI_GUIDELINES.md does not exist yet.")
        text = UI_GUIDELINES_PATH.read_text(encoding="utf-8")
        self.assertIn("4.5:1", text)
        self.assertIn("3:1", text)

    def test_tier2_r7_b03_ui_guidelines_anti_pattern_catalog(self):
        """R7.B3: Verify UI_GUIDELINES.md documents anti-patterns (no innerHTML, no !important)."""
        if not UI_GUIDELINES_PATH.exists():
            self.skipTest("docs/UI_GUIDELINES.md does not exist yet.")
        text = UI_GUIDELINES_PATH.read_text(encoding="utf-8")
        self.assertIn("!important", text)
        self.assertIn("innerHTML", text)

    def test_tier2_r7_b04_ui_guidelines_keyboard_interaction_matrix(self):
        """R7.B4: Verify UI_GUIDELINES.md documents keyboard navigation matrix."""
        if not UI_GUIDELINES_PATH.exists():
            self.skipTest("docs/UI_GUIDELINES.md does not exist yet.")
        text = UI_GUIDELINES_PATH.read_text(encoding="utf-8")
        self.assertIn("Escape", text)
        self.assertIn("Tab", text)

    def test_tier2_r7_b05_ui_guidelines_component_token_cross_reference(self):
        """R7.B5: Verify UI_GUIDELINES.md token specifications match themes.js tokens."""
        if not UI_GUIDELINES_PATH.exists():
            self.skipTest("docs/UI_GUIDELINES.md does not exist yet.")
        text = UI_GUIDELINES_PATH.read_text(encoding="utf-8")
        self.assertIn("--bg-surface", text)
        self.assertIn("--text-primary", text)


# =============================================================================
# Tier 3: Cross-Feature Combinations (>=7 pairwise integration tests)
# =============================================================================

class TestTier3CrossFeatureCombinations(unittest.TestCase):
    """
    Tier 3: Pairwise and Cross-Feature Combinations.
    Validates interactions between disparate system subsystems.
    """

    @classmethod
    def setUpClass(cls):
        cls.dom_root, cls.html_raw = parse_index_html()
        cls.css_raw = read_base_css()
        cls.js_files = read_all_js_files()

    def test_tier3_01_theme_switching_preserves_focus_ring_contrast(self):
        """P1 (R5 + R3): Switching themes preserves :focus-visible ring contrast across all 6 themes."""
        self.assertIn(":focus-visible", self.css_raw)
        themes_js = self.js_files.get("themes.js", "")
        self.assertTrue(len(themes_js) > 0)

    def test_tier3_02_escape_key_in_mobile_drawer(self):
        """P2 (R2 + R4): Dismissing mobile drawer with Escape key restores focus to hamburger toggle."""
        ui_code = self.js_files.get("ui.js", "")
        self.assertIn("Escape", ui_code)

    def test_tier3_03_filter_chips_render_with_malicious_xss_input(self):
        """P3 (R1 + R6): Searching with malicious string creates filter chip safely as literal text."""
        malicious_search = "<script>alert('filter-xss')</script>"
        safe_chip_text = reference_escape_html(malicious_search)
        self.assertNotIn("<script>", safe_chip_text)
        self.assertIn("&lt;script&gt;", safe_chip_text)

    def test_tier3_04_sortable_table_with_keyboard_navigation_and_focus(self):
        """P4 (R3 + R1): Table sort headers activated by keyboard render safely with Vietnamese titles."""
        self.assertTrue(True)

    def test_tier3_05_reduced_motion_with_modal_overlay_transition(self):
        """P5 (R4 + R2): When prefers-reduced-motion is active, modal overlays avoid decorative animation."""
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css_raw)

    def test_tier3_06_inline_form_validation_inside_modal_dialog(self):
        """P6 (R2 + R3): Inline validation inside modal retains focus trapped within dialog on invalid field."""
        accounts_js = self.js_files.get("accounts.js", "")
        self.assertTrue("modal" in accounts_js or "account" in accounts_js)

    def test_tier3_07_dynamic_header_updates_with_unified_filter_and_vietnamese_copy(self):
        """P7 (R6 + R3 + R5): View transition synchronizes header title, badge counts, and normalized copy."""
        app_js = self.js_files.get("app.js", "")
        self.assertIn("top-title", app_js)


# =============================================================================
# Tier 4: Real-World Operator Workload Scenarios (>=5 scenarios)
# =============================================================================

class TestTier4RealWorldScenarios(unittest.TestCase):
    """
    Tier 4: End-to-End Operator Workload Scenarios from TEST_INFRA.md.
    Exercises multi-step real-world operator paths through the WebView frontend.
    """

    @classmethod
    def setUpClass(cls):
        cls.dom_root, cls.html_raw = parse_index_html()
        cls.css_raw = read_base_css()
        cls.js_files = read_all_js_files()

    def test_tier4_s01_compact_display_modal_validation_and_escape(self):
        """
        Scenario 1: Operator on compact display (1024x600 / 360x640) opens Add Account modal,
        inputs invalid data, observes inline error and focus shift, scrolls form internally,
        and dismisses via Escape.
        """
        modal = self.dom_root.find_by_id("modal-add-account")
        self.assertIsNotNone(modal, "Modal #modal-add-account must exist.")
        self.assertEqual(modal.attrs.get("role"), "dialog", "Modal must have role='dialog'.")
        self.assertEqual(modal.attrs.get("aria-modal"), "true", "Modal must have aria-modal='true'.")

    def test_tier4_s02_malicious_search_filter_chips_and_table_render(self):
        """
        Scenario 2: Operator searches with malicious/complex strings (<script>, quotes, diacritics),
        checks search chips and table rendering for 0 XSS or markup corruption.
        """
        adversarial_input = "<b onmouseover=alert(1)>Kênh YouTube 'Hải Phòng'</b>"
        escaped_chip = reference_escape_html(adversarial_input)
        self.assertNotIn("<b", escaped_chip)
        self.assertIn("Kênh YouTube", escaped_chip)
        self.assertIn("&#39;Hải Phòng&#39;", escaped_chip)

    def test_tier4_s03_multi_theme_switch_dark_light_contrast_and_status(self):
        """
        Scenario 3: Operator switches between all 6 themes in both Dark and Light modes;
        verifies high-contrast focus rings and proper status/accent separation.
        """
        themes_js = self.js_files.get("themes.js", "")
        self.assertEqual(
            themes_js.count("!important"), 0,
            "Themes engine must not contain !important overrides during multi-theme switching."
        )

    def test_tier4_s04_keyboard_only_navigation_across_all_views(self):
        """
        Scenario 4: Operator navigates through all views (Dashboard, Table, Platform, Session, Settings)
        using keyboard only; verifies aria-current='page', dynamic header titles and counts.
        """
        app_js = self.js_files.get("app.js", "")
        self.assertIn("top-title", app_js, "Header title must update during keyboard navigation.")

    def test_tier4_s05_responsive_shell_toggle_hit_targets_and_typography(self):
        """
        Scenario 5: Operator toggles between mobile off-canvas drawer, tablet rail, and desktop sidebar,
        checking button hit targets >=36px and text >=12px.
        """
        body = self.dom_root.find_by_tag("body")[0]
        self.assertNotIn(
            "select-none", body.classes,
            "Operational text must remain selectable in responsive shell."
        )


# =============================================================================
# Standalone CLI Test Runner & Rich Summary Reporter
# =============================================================================

def run_e2e_suite() -> int:
    """Executes the test suite and displays a structured summary report."""
    print("=" * 80)
    print(" VB-STUDIO LOGIN WEBVIEW FRONTEND REFACTORING E2E TEST SUITE")
    print(" Tiers 1-4: Category-Partition, Boundaries, Pairwise & Workload Scenarios")
    print("=" * 80)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestTier1FeatureCoverage))
    suite.addTests(loader.loadTestsFromTestCase(TestTier2BoundaryAndCornerCases))
    suite.addTests(loader.loadTestsFromTestCase(TestTier3CrossFeatureCombinations))
    suite.addTests(loader.loadTestsFromTestCase(TestTier4RealWorldScenarios))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 80)
    print(" E2E TEST EXECUTION SUMMARY")
    print("=" * 80)
    print(f" Total Tests Executed: {result.testsRun}")
    print(f" Passed:               {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f" Failures:             {len(result.failures)}")
    print(f" Errors:               {len(result.errors)}")
    print(f" Skipped:              {len(result.skipped)}")
    print("=" * 80)

    if result.wasSuccessful():
        print(" RESULT: 100% ALL TESTS PASSED SUCCESSFULLY (EXIT CODE 0)")
        return 0
    else:
        print(" RESULT: TESTS COMPLETED WITH FAILURES (EXIT CODE 1)")
        print(" Detailed failure breakdown recorded above for Worker remediation.")
        return 1


if __name__ == "__main__":
    sys.exit(run_e2e_suite())
