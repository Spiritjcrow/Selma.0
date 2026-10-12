"""Static contracts for the standalone, offline SelmaOS recovery desktop."""
from pathlib import Path
import unittest

HTML = Path(__file__).resolve().parents[1] / "sites" / "selmaos" / "selmaos.html"


class SelmaOSBrowserRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = HTML.read_text(encoding="utf-8")

    def test_no_external_dependency(self):
        for value in ('https://', '<script src=', '<link rel='):
            self.assertNotIn(value, self.html)

    def test_required_ui(self):
        for section in ('home', 'notes', 'reminders', 'focus', 'calculator', 'files'):
            self.assertIn('id="' + section + '"', self.html)

    def test_backup_and_safe_output(self):
        for value in ('id="backup"', 'id="restore"', 'id="secondary"',
                      'localStorage.setItem', 'textContent', 'id="taskList"'):
            self.assertIn(value, self.html)
        self.assertNotIn('eval(', self.html)
        self.assertNotIn('new Function(', self.html)


    def test_view_changes_move_focus_to_active_heading(self):
        for value in ("const target=$(id)", "target.querySelector('h1')",
                      "heading.tabIndex=-1", "heading.focus()"):
            self.assertIn(value, self.html)



    def test_reminder_delete_action_has_contextual_accessible_name(self):
        self.assertIn(
            "del.setAttribute('aria-label','Delete '+task.text)", self.html
        )



    def test_reminder_checkbox_action_matches_current_state(self):
        self.assertIn(
            "check.setAttribute('aria-label',(task.done?'Mark incomplete ':'Mark complete ')+task.text)",
            self.html,
        )


    def test_image_preview_identifies_selected_file(self):
        self.assertIn("img.alt='Preview of '+f.name", self.html)


    def test_reminder_updates_are_announced_politely(self):
        self.assertIn(
            '<ul id="taskList" aria-live="polite" aria-label="Reminders"></ul>',
            self.html,
        )

    def test_reminder_toggle_preserves_checkbox_focus(self):
        marker = (
            "check.addEventListener('change',()=>{task.done=check.checked;"
            "li.classList.toggle('done',task.done);"
            "check.setAttribute('aria-label',(task.done?'Mark incomplete ':'Mark complete ')+task.text);"
            "save()})"
        )
        self.assertIn(marker, self.html)

    def test_reminder_delete_returns_focus_to_task_input(self):
        self.assertIn(
            "del.addEventListener('click',()=>{state.tasks=state.tasks.filter(t=>t.id!==task.id);save();renderTasks();$('taskText').focus()})",
            self.html,
        )

    def test_file_preview_outcomes_use_polite_status(self):
        for marker in (
            "say('File exceeds preview limit.')",
            "say('Image preview ready: '+f.name)",
            "say('Text preview ready: '+f.name)",
            "say('Unsupported preview format.')",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.html)

    def test_backup_import_returns_focus_to_import_button(self):
        self.assertIn(
            "finally{e.target.value='';$('restore').focus()}",
            self.html,
        )


if __name__ == "__main__":
    unittest.main()

