"""
Automated Behavioral & Structural Test Suite for Milestone 1:
- Clean Token Theme Engine (R5, P2.3)
- Responsive Layout & Shell Navigation (R4, P1.1)
- Motion Controls (R4, P1.8)
- Global Focus Rings (R3.1, P0.3)
- Login Screen Visual Alignment (R5, P2.10)
"""

import re
import pathlib
import unittest
from html.parser import HTMLParser
from typing import Dict, List, Tuple, Optional, Set

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
WEB_DIR = PROJECT_ROOT / "src" / "web"
INDEX_HTML_PATH = WEB_DIR / "index.html"
BASE_CSS_PATH = WEB_DIR / "css" / "base.css"
THEMES_JS_PATH = WEB_DIR / "js" / "themes.js"


class DOMNode:
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


class DocumentTreeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = DOMNode("document-root", [])
        self.current = self.root

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]):
        node = DOMNode(tag, attrs, parent=self.current)
        self.current.children.append(node)
        if tag.lower() not in {"meta", "link", "img", "br", "hr", "input", "col", "area", "base", "source"}:
            self.current = node

    def handle_endtag(self, tag: str):
        if self.current.parent and self.current.tag == tag.lower():
            self.current = self.current.parent

    def handle_data(self, data: str):
        self.current.text_parts.append(data)


def parse_html() -> Tuple[DOMNode, str]:
    content = INDEX_HTML_PATH.read_text(encoding="utf-8")
    parser = DocumentTreeParser()
    parser.feed(content)
    return parser.root, content


class TestMilestone1ThemeEngine(unittest.TestCase):
    """Verifies R5 / P2.3 Clean Token Theme Engine invariants."""

    @classmethod
    def setUpClass(cls):
        cls.themes_code = THEMES_JS_PATH.read_text(encoding="utf-8")
        cls.dom_root, cls.html_raw = parse_html()

    def test_zero_important_in_themes_js(self):
        """Theme engine must not contain any '!important' or '${imp}' overrides."""
        self.assertEqual(
            self.themes_code.count("!important"), 0,
            "themes.js must not contain any '!important' occurrences."
        )
        self.assertNotIn("${imp}", self.themes_code)

    def test_all_14_semantic_tokens_defined(self):
        """Theme engine must define all 14 standard semantic tokens."""
        required_tokens = [
            "--bg-surface", "--bg-elevated", "--bg-app",
            "--text-primary", "--text-secondary", "--text-muted",
            "--border-subtle", "--border-default",
            "--accent-primary", "--accent-hover",
            "--status-success", "--status-warning", "--status-error", "--status-info"
        ]
        for token in required_tokens:
            self.assertIn(token, self.themes_code, f"Missing token: {token}")

    def test_all_6_themes_supported_in_dual_mode(self):
        """All 6 themes must support dual mode (Dark + Light)."""
        expected_themes = ['ocean', 'emerald', 'violet', 'sunset', 'rose', 'mono']
        for tid in expected_themes:
            self.assertIn(f"id: '{tid}'", self.themes_code, f"Theme '{tid}' not found in registry.")

        # Ensure all 6 themes have mode: 'dual'
        dual_count = self.themes_code.count("mode: 'dual'")
        self.assertEqual(dual_count, 6, f"Expected 6 dual-mode themes, got {dual_count}")

    def test_brand_accent_separated_from_status_tokens(self):
        """Status tokens must be independent constants, not alias to brand accent."""
        self.assertIn("success: '#10b981'", self.themes_code)
        self.assertIn("warning: '#f59e0b'", self.themes_code)
        self.assertIn("error: '#ef4444'", self.themes_code)
        self.assertIn("info: '#3b82f6'", self.themes_code)
        self.assertIn("--status-success:", self.themes_code)
        self.assertIn("--status-warning:", self.themes_code)
        self.assertIn("--status-error:", self.themes_code)
        self.assertIn("--status-info:", self.themes_code)

    def test_tailwind_config_maps_tokens_to_css_variables(self):
        """Tailwind config in index.html maps semantic utilities to CSS Custom Properties."""
        self.assertIn("'bg-app': 'var(--bg-app)'", self.html_raw)
        self.assertIn("'bg-surface': 'var(--bg-surface)'", self.html_raw)
        self.assertIn("'bg-elevated': 'var(--bg-elevated)'", self.html_raw)
        self.assertIn("'text-primary': 'var(--text-primary)'", self.html_raw)
        self.assertIn("'border-subtle': 'var(--border-subtle)'", self.html_raw)
        self.assertIn("'accent-primary': 'var(--accent-primary)'", self.html_raw)
        self.assertIn("'status-success': 'var(--status-success)'", self.html_raw)

    def test_light_mode_bridges_configured(self):
        """Theme engine and base.css must actively configure light mode overrides."""
        css_content = BASE_CSS_PATH.read_text(encoding="utf-8")
        self.assertIn("html:not(.dark) body", css_content, "Light mode body bridge must be configured")
        self.assertIn("html:not(.dark) .thm-nav", css_content, "Light mode nav bridge must be configured")
        self.assertIn("html:not(.dark) .bg-slate-50", css_content, "Light mode bg-slate-50 bridge must be configured")
        self.assertIn("html:not(.dark) .border-slate-200", css_content, "Light mode border bridge must be configured")
        self.assertIn("html:not(.dark) .text-slate-800", css_content, "Light mode text bridge must be configured")
        self.assertIn(".bg-blue-600 { background-color: var(--accent-primary); }", css_content)

        # In themes.js, renderThemeCards must adapt preview colors based on isDark
        self.assertIn("const isDark = document.documentElement.classList.contains('dark');", self.themes_code)
        self.assertIn("p = isDark ? t.dark : t.light", self.themes_code)


class TestMilestone1ResponsiveShellAndMotion(unittest.TestCase):
    """Verifies R4 / P1.1 Responsive Shell and P1.8 Motion Controls."""

    @classmethod
    def setUpClass(cls):
        cls.css_raw = BASE_CSS_PATH.read_text(encoding="utf-8")
        cls.dom_root, cls.html_raw = parse_html()

    def test_global_focus_visible_ring(self):
        """Focus-visible offset ring must use --accent-primary with 2px offset."""
        self.assertIn(":focus-visible", self.css_raw)
        self.assertIn("outline: 2px solid var(--accent-primary)", self.css_raw)
        self.assertIn("outline-offset: 2px", self.css_raw)

    def test_prefers_reduced_motion_controls(self):
        """Prefers-reduced-motion must disable pulse, ping, spin and smooth scroll."""
        self.assertIn("@media (prefers-reduced-motion: reduce)", self.css_raw)
        self.assertIn(".animate-pulse", self.css_raw)
        self.assertIn(".animate-ping", self.css_raw)
        self.assertIn(".animate-spin", self.css_raw)
        self.assertIn("scroll-behavior: auto", self.css_raw)

    def test_responsive_sidebar_breakpoints(self):
        """Sidebar styles must support mobile drawer, tablet rail, and desktop collapse."""
        self.assertIn("@media (max-width: 767px)", self.css_raw)
        self.assertIn("@media (min-width: 768px) and (max-width: 1023px)", self.css_raw)
        self.assertIn("@media (min-width: 1024px)", self.css_raw)

    def test_no_hover_only_sidebar_expansion(self):
        """Hover-only sidebar expansion (#sidebar.sb-collapsed:hover) must be removed."""
        hover_expansion = re.search(r'#sidebar\.sb-collapsed:hover', self.css_raw)
        self.assertIsNone(hover_expansion, "Hover expansion must not be present.")

    def test_mobile_menu_button_and_backdrop_present(self):
        """Mobile hamburger button and backdrop must exist with accessible triggers."""
        mobile_btn = self.dom_root.find_by_id("btn-mobile-menu")
        self.assertIsNotNone(mobile_btn, "Button #btn-mobile-menu must exist.")
        self.assertIn("toggleMobileNav()", mobile_btn.attrs.get("onclick", ""))

        backdrop = self.dom_root.find_by_id("sidebar-backdrop")
        self.assertIsNotNone(backdrop, "Element #sidebar-backdrop must exist.")

    def test_header_search_input_reachable(self):
        """Header search input and container must exist."""
        search_wrap = self.dom_root.find_by_id("header-search-input")
        self.assertIsNotNone(search_wrap, "#header-search-input container must exist.")
        search_input = self.dom_root.find_by_id("input-search")
        self.assertIsNotNone(search_input, "#input-search input must exist.")


class TestMilestone1LoginVisualAlignment(unittest.TestCase):
    """Verifies R5 / P2.10 Login Screen visual alignment and R3.1 text selection."""

    @classmethod
    def setUpClass(cls):
        cls.dom_root, cls.html_raw = parse_html()

    def test_body_level_select_none_removed(self):
        """Body tag must not contain 'select-none'."""
        body_node = self.dom_root.find_by_tag("body")[0]
        self.assertNotIn("select-none", body_node.classes)

    def test_login_glow_balls_removed(self):
        """Decorative blur-[120px] glow balls must be retired."""
        self.assertNotIn("blur-[120px]", self.html_raw)

    def test_login_rainbow_gradient_text_removed(self):
        """Rainbow gradient text on login screen must be retired."""
        self.assertNotIn("from-blue-400 via-indigo-400 to-purple-400", self.html_raw)

    def test_login_container_aligns_with_dashboard(self):
        """Auth gate container uses semantic classes matching operator dashboard."""
        auth_overlay = self.dom_root.find_by_id("auth-gate-overlay")
        self.assertIsNotNone(auth_overlay, "#auth-gate-overlay must exist.")
        # Ensure it supports dark and light modes
        self.assertIn("dark:bg-dark-bg", auth_overlay.attrs.get("class", ""))

    def test_interactive_hit_targets_min_36px(self):
        """Buttons such as sidebar pin and scroll controls must be at least 36x36px."""
        pin_btn = self.dom_root.find_by_id("sidebar-pin-btn")
        self.assertIsNotNone(pin_btn)
        self.assertIn("w-9", pin_btn.classes)
        self.assertIn("h-9", pin_btn.classes)


if __name__ == "__main__":
    unittest.main()
