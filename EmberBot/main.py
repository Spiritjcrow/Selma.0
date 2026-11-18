"""EmberBot Mines: Android research companion, NOT an automated wagering client."""
import json
from pathlib import Path

from kivy.app import App
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

from ember_engine import Session, mines_stats, timestamp

BG = (0.025, 0.035, 0.06, 1)
PANEL = (0.08, 0.12, 0.18, 1)
ACCENT = (0, 0.78, 0.48, 1)
TEXT = (0.93, 0.97, 1, 1)
WARNING = (1, 0.67, 0.27, 1)


def label(text, size=16, color=TEXT, height=37):
    widget = Label(text=text, font_size=f'{size}sp', color=color, size_hint_y=None,
                   height=dp(height), halign='left', valign='middle')
    widget.bind(size=lambda obj, _: setattr(obj, 'text_size', (obj.width, None)))
    return widget


def field(value, kind='int'):
    return TextInput(text=str(value), multiline=False, input_filter=kind, font_size='18sp',
                     foreground_color=TEXT, background_color=PANEL, cursor_color=ACCENT,
                     size_hint_y=None, height=dp(46), padding=[dp(10), dp(8)])


def button(text, callback, color=PANEL):
    widget = Button(text=text, bold=True, font_size='16sp', background_normal='',
                    background_color=color, color=TEXT, size_hint_y=None, height=dp(49))
    widget.bind(on_release=lambda *_: callback())
    return widget


class EmberBotApp(App):
    title = 'EmberBot Mines Research'

    def build(self):
        Window.clearcolor = BG
        self.file = Path(self.user_data_dir) / 'mines_session.json'
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.session = self._load()

        scroll = ScrollView(do_scroll_x=False)
        col = BoxLayout(orientation='vertical', padding=dp(16), spacing=dp(9),
                        size_hint_y=None)
        col.bind(minimum_height=col.setter('height'))
        scroll.add_widget(col)
        col.add_widget(label('EMBERBOT  |  MINES', 25, ACCENT, 48))
        col.add_widget(label('Research companion | manual entries only', 13, WARNING, 29))
        col.add_widget(label('No hidden mine locations or guaranteed wins.', 13, WARNING, 33))

        col.add_widget(label('Starting balance (sats)', 15, TEXT, 28))
        self.starting = field(self.session.starting_balance_sats)
        col.add_widget(self.starting)
        col.add_widget(button('Set Starting Balance (before any rounds)', self.set_balance))

        inputs = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(82))
        mine_box = BoxLayout(orientation='vertical', spacing=dp(4))
        mine_box.add_widget(label('Mine count', 14, TEXT, 30))
        self.mines = field(self.session.active['mines'] if self.session.active else 3)
        mine_box.add_widget(self.mines)
        bet_box = BoxLayout(orientation='vertical', spacing=dp(4))
        bet_box.add_widget(label('Stake (sats)', 14, TEXT, 30))
        self.bet = field(self.session.active['bet_sats'] if self.session.active else 10)
        bet_box.add_widget(self.bet)
        inputs.add_widget(mine_box)
        inputs.add_widget(bet_box)
        col.add_widget(inputs)

        col.add_widget(button('START ROUND (LOG ONLY)', self.start, ACCENT))
        self.stats = label('', 16, TEXT, 130)
        col.add_widget(self.stats)

        actions = GridLayout(cols=2, spacing=dp(8), size_hint_y=None, height=dp(107))
        actions.add_widget(button('+ Safe Tile', self.safe))
        actions.add_widget(button('Mine Hit / Loss', self.mine))
        actions.add_widget(button('Cash Out / Log', self.cashout, ACCENT))
        actions.add_widget(button('Discard Round', self.discard))
        col.add_widget(actions)

        col.add_widget(label('Actual payout received (sats)', 15, TEXT, 28))
        self.payout = field('0')
        col.add_widget(self.payout)
        self.summary = label('', 17, ACCENT, 77)
        col.add_widget(self.summary)
        col.add_widget(button('Export JSON Snapshot', self.export))
        col.add_widget(button('Undo Last Completed Round', self.undo))
        self.message = label('Ready. Track actual in-app results manually.', 13, WARNING, 64)
        col.add_widget(self.message)
        col.add_widget(label('Probabilities assume a uniformly random 25-tile board.', 12, TEXT, 44))
        col.add_widget(label('Illustrative multiplier is NOT an Ember payout quote.', 12, WARNING, 44))
        self.refresh()
        return scroll

    def _load(self):
        try:
            return Session.from_dict(json.loads(self.file.read_text(encoding='utf-8')))
        except (OSError, ValueError, KeyError, TypeError):
            return Session()

    def _save(self):
        tmp = self.file.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.session.as_dict(), indent=2), encoding='utf-8')
        tmp.replace(self.file)

    def perform(self, action, success):
        try:
            action()
            self._save()
            self.message.text = success
        except (ValueError, OSError) as exc:
            self.message.text = f'Check input: {exc}'
        self.refresh()

    def set_balance(self):
        def action():
            if self.session.records or self.session.active:
                raise ValueError('Balance may only be changed in an empty session')
            from ember_engine import _int
            self.session.starting_balance_sats = _int(self.starting.text, 'Starting sats', 0, 10**15)
        self.perform(action, 'Starting balance saved locally.')

    def start(self):
        self.perform(lambda: self.session.begin(self.bet.text, self.mines.text),
                     'Round opened for manual logging. No bet was placed.')

    def safe(self):
        self.perform(self.session.mark_safe, 'Safe tile logged (as entered).')

    def mine(self):
        self.perform(lambda: self.session.complete('mine'), 'Mine hit logged; full stake lost.')

    def cashout(self):
        self.perform(lambda: self.session.complete('cashout', self.payout.text),
                     'Actual cash-out amount logged.')

    def discard(self):
        self.perform(self.session.discard_active, 'Open round discarded; no earnings recorded.')

    def undo(self):
        self.perform(self.session.undo_last, 'Last recorded round removed.')

    def export(self):
        def action():
            directory = Path(self.user_data_dir) / 'exports'
            directory.mkdir(parents=True, exist_ok=True)
            name = 'mines-' + timestamp().replace(':', '-').replace('+', '_') + '.json'
            path = directory / name
            path.write_text(json.dumps(self.session.as_dict(), indent=2), encoding='utf-8')
            self.message.text = 'Saved private app-file snapshot: ' + name
        try:
            action()
        except OSError as exc:
            self.message.text = f'Export failed: {exc}'

    def refresh(self):
        active = self.session.active
        try:
            count = active['mines'] if active else int(self.mines.text or '3')
            safe = active['safe_reveals'] if active else 0
            s = mines_stats(count, safe)
            self.stats.text = (
                f'Logged safe tiles: {safe} / {s["board_size"] - count}\n'
                f'Next tile safe chance: {100*s["next_safe_probability"]:.2f}%\n'
                f'Chance of {safe} consecutive safe picks: {100*s["survival_probability"]:.2f}%\n'
                f'Illustrative fair-model multiplier: {s["illustrative_multiplier"]:.3f}x'
            )
        except (ValueError, TypeError, KeyError):
            self.stats.text = 'Enter a mine count from 1 to 24.'
        wins = sum(r['outcome'] == 'cashout' and r['net_sats'] > 0 for r in self.session.records)
        self.summary.text = (
            f'Tracked net: {self.session.net_sats:+,} sats\n'
            f'Tracked balance: {self.session.tracked_balance_sats:,} sats\n'
            f'Completed rounds: {len(self.session.records)} | Profitable: {wins}'
        )

    def on_stop(self):
        self._save()


if __name__ == '__main__':
    EmberBotApp().run()
