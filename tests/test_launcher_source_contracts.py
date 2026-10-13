"""Source-level launcher guardrails; these do not replace Android lint or device tests."""

import unittest
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "SELMA0_ANDROID_NATIVE_V1" / "app" / "src" / "main"
MANIFEST = MAIN / "AndroidManifest.xml"
LAUNCHER = MAIN / "java" / "ai" / "selma" / "companion" / "LauncherActivity.java"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class SelmaLauncherSourceContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = ElementTree.parse(MANIFEST).getroot()
        cls.source = LAUNCHER.read_text(encoding="utf-8")

    def test_launcher_is_opt_in_home_and_visible_app_icon(self):
        nodes = [
            a for a in self.root.findall(".//activity")
            if a.attrib.get(ANDROID + "name") == ".LauncherActivity"
        ]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].attrib.get(ANDROID + "exported"), "true")
        filters = nodes[0].findall("intent-filter")
        sets = [
            {c.attrib.get(ANDROID + "name")
             for c in f.findall("category")}
            for f in filters
        ]
        self.assertTrue(any({
            "android.intent.category.HOME", "android.intent.category.DEFAULT"
        }.issubset(s) for s in sets))
        self.assertTrue(any("android.intent.category.LAUNCHER" in s for s in sets))

    def test_existing_cloud_companion_stays_available(self):
        self.assertEqual(len([
            a for a in self.root.findall(".//activity")
            if a.attrib.get(ANDROID + "name") == ".MainActivity"
        ]), 1)

    def test_visibility_is_narrow_and_permissions_are_bounded(self):
        permissions = {
            p.attrib.get(ANDROID + "name")
            for p in self.root.findall("uses-permission")
        }
        self.assertEqual(permissions, {"android.permission.INTERNET"})
        queries = self.root.findall("queries/intent")
        self.assertTrue(any(
            c.attrib.get(ANDROID + "name") == "android.intent.category.LAUNCHER"
            for entry in queries for c in entry.findall("category")
        ))

    def test_real_app_discovery_and_safe_settings_paths(self):
        for marker in (
            "queryIntentActivities", "CATEGORY_LAUNCHER", "startActivity",
            "ACTION_OPEN_DOCUMENT", "ACTION_BLUETOOTH_SETTINGS",
            "Settings.Panel.ACTION_WIFI", "ACTION_HOME_SETTINGS",
            "putStringSet(PINNED", "http://127.0.0.1:8765/"
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        for forbidden in ("QUERY_ALL_PACKAGES", "su -c", "Runtime.getRuntime().exec",
                          "android.permission.WRITE_SECURE_SETTINGS"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, self.source)


    def test_workspaces_are_local_and_user_assigned(self):
        for marker in (
            'private static final String WORKSPACE_PREF = "workspace_assignments"',
            'private static final String[] WORKSPACE_NAMES',
            '"Build", "Connect", "Secure", "Daily"',
            'void renderWorkspaces()',
            'void chooseWorkspace(String pkg, String label)',
            'putStringSet(WORKSPACE_PREF, values)',
            'new AlertDialog.Builder(this)',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)
        self.assertIn('navItem("Work", "WORKSPACES")', self.source)
        self.assertNotIn("android.permission.QUERY_ALL_PACKAGES", self.source)

    def test_pin_and_workspace_controls_are_visible_accessible_actions(self):
        for marker in (
            'pin.setMinWidth(dp(48))',
            'pin.setMinHeight(dp(48))',
            'organize.setMinWidth(dp(48))',
            'organize.setMinHeight(dp(48))',
            'cell.addView(pin, new LinearLayout.LayoutParams(dp(48), dp(48)))',
            'cell.addView(organize, new LinearLayout.LayoutParams(dp(48), dp(48)))',
            'pin.setContentDescription',
            'organize.setContentDescription',
            'togglePinned(pkg, label)',
            'chooseWorkspace(pkg, label)',
            'state.putString("workspace", activeWorkspace)',
            'state.putString("section", section)',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)


    def test_navigation_and_workspace_tabs_expose_selected_state(self):
        self.assertIn('item.setSelected(section.equals(target))', self.source)
        self.assertIn('select.setSelected(group.equals(activeWorkspace))', self.source)



    def test_pin_action_synchronizes_row_visible_and_accessible_state(self):
        for marker in (
            'TextView pinState = text(',
            'boolean isPinned = pinned.contains(pkg)',
            'pinState.setText(isPinned ?',
            'cell.setContentDescription(label + ", " + (isPinned ?',
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)



    def test_decorative_app_icon_is_hidden_from_accessibility(self):
        self.assertIn(
            "icon.setImportantForAccessibility(View.IMPORTANT_FOR_ACCESSIBILITY_NO)",
            self.source,
        )


    def test_screen_titles_are_accessibility_headings(self):
        self.assertIn("h.setAccessibilityHeading(true)", self.source)


    def test_app_search_results_are_announced_after_initial_render(self):
        initial = self.source.index("displayApps(results, filter);", self.source.index("search.setSelection"))
        marker = "results.setAccessibilityLiveRegion(View.ACCESSIBILITY_LIVE_REGION_POLITE)"
        self.assertIn(marker, self.source)
        self.assertGreater(self.source.index(marker), initial)

    def test_section_titles_are_accessibility_headings(self):
        start = self.source.index("private void sectionTitle")
        end = self.source.index("private TextView action", start)
        method = self.source[start:end]
        for marker in (
            "TextView h = text(value, 17, foreground(), true)",
            "h.setAccessibilityHeading(true)",
            "main.addView(h, full(24))",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, method)

    def test_long_press_pin_reuses_in_place_state_update(self):
        self.assertIn(
            "cell.setOnLongClickListener(v -> {\n            pin.performClick();\n            return true;",
            self.source,
        )

    def test_section_changes_expose_accessibility_pane_title(self):
        marker = "main.setAccessibilityPaneTitle(sectionLabel())"
        self.assertIn(marker, self.source)
        render = self.source.index("else renderHome();")
        self.assertGreater(self.source.index(marker), render)
        for label in (
            '"SelmaOS Home"',
            '"SelmaOS Applications"',
            '"SelmaOS Workspaces"',
            '"SelmaOS System"',
        ):
            with self.subTest(label=label):
                self.assertIn(label, self.source)

    def test_navigation_change_restores_focus_to_selected_tab(self):
        for marker in (
            "item.setFocusable(true)",
            "showSection();\n            focusSelectedNavigationItem();",
            "private void focusSelectedNavigationItem()",
            "if (child.isSelected())",
            "child.requestFocus()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_workspace_change_restores_focus_to_selected_tab(self):
        for marker in (
            "private LinearLayout workspaceNavigation;",
            "workspaceNavigation = choices;",
            "select.setFocusable(true)",
            "showSection();\n                focusSelectedWorkspaceItem();",
            "private void focusSelectedWorkspaceItem()",
            "if (child.isSelected())",
            "child.requestFocus()",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.source)

    def test_back_navigation_restores_focus_to_home_tab(self):
        start = self.source.index("@Override public void onBackPressed()")
        end = self.source.index("@Override protected void onResume()", start)
        method = self.source[start:end]
        self.assertIn(
            "showSection();\n            focusSelectedNavigationItem();",
            method,
        )


if __name__ == "__main__":
    unittest.main()




