"""Raw terminal observations through production Agent.step/update and casting.

Only unrelated inventory/map/callback dependencies are inert. No NLE gameplay.
Retention forms follow NLE src/spell.c:spellretention (exact, range, gone).
"""
import ast
import contextlib
import io
import re
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from autoascend.spell_healing import SpellHealing, parse_healing_spells
from autoascend.exceptions import AgentPanic


class Array(list):
    def copy(self):
        return Array(self)

    def reshape(self, *_):
        return b''.join(bytes(r) for r in self)


def observation(rows=(), message='', marker='(end)', hp=10, energy=20, turn=100):
    # A right-aligned terminal menu over the map, with its marker at the same
    # left column. Normal messages/prompt observations have no menu marker.
    lines = ([message] if message else [])
    if rows:
        lines += [' ' * 10 + row for row in rows]
        lines += [' ' * 10 + marker]
    return dict(message=bytearray(message.encode()),
                tty_chars=Array(bytearray(line.ljust(80).encode()) for line in lines + [''] * (24-len(lines))),
                tty_cursor=Array([1, 0]), misc=Array([0, 0, 0]), glyphs=Array([]),
                blstats=Array([hp, 30, energy, turn]))


def more(message, **kwargs):
    obs = observation(message=message, **kwargs)
    obs['tty_chars'][0] = bytearray((message + ' --More--').ljust(80).encode())
    obs['misc'][2] = 1
    return obs


def load_agent():
    path = Path(__file__).resolve().parents[1] / 'autoascend/agent.py'
    tree = ast.parse(path.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Agent')
    names = {'atom_operation', '_find_marker', 'get_message_and_popup', 'update_message_and_popup', 'step', 'update'}
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    ns = dict(re=re, contextlib=contextlib, A=NS(ACTIONS=list(range(256)), TextCharacters=NS(SPACE=32), Command=NS(ESC=27)),
              nh=NS(COIN_CLASS=1), flatten_items=lambda items: items,
              AgentFinished=RuntimeError,
              BLStats=lambda hp, max_hp, energy, time: NS(hitpoints=hp, max_hitpoints=max_hp,
                                                        energy=energy, time=time, x=1, y=1, monster_level=0))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), str(path), 'exec'), ns)
    return ns['Agent']


Agent = load_agent()


def fixture(screens):
    a = Agent()
    stream = iter(screens)
    a.actions = []

    def step(action):
        a.actions.append(chr(action))
        try:
            return next(stream), 0, False, {}
        except StopIteration:
            raise AssertionError('unexpected input beyond supplied observations')

    a.env = NS(step=step)
    a._no_step_calls = False
    a._recovery_response_steps = None
    a.recovery = NS(observe=lambda stats: None)
    a._is_reading_message_or_popup = False
    a.message = 'Old In what direction?'
    a.popup = ['x - healing 1 healing 0% 100%']
    a.single_message, a.single_popup = '', []
    a.step_count = a.score = 0
    a._hb_actions = Counter()
    a.inventory = NS(items=[])
    a.events = []
    a.stats_logger = NS(log_event=a.events.append, log_gold=lambda *_: None,
                        log_cumulative_value=lambda *args, **kwargs: None)
    a._text_prompt_escapes = a._teleport_prompt_escapes = 0
    a._message_history = []
    a.last_observation = None
    a._prayer_model_active = lambda: False
    a.current_level = lambda: NS(dungeon_number=0, level_number=1)
    a._inactivity_counter = 0
    a._last_turn = 100
    a._atom_operation_allow_update = False
    a.in_atom_operation = True
    a.update_state = lambda **kwargs: None
    a.atom_operation = contextlib.nullcontext
    a.last_cast_fail_turn = defaultdict(lambda: -100)
    a.log = lambda *_: None
    a.blstats = NS(hitpoints=10, max_hitpoints=30, energy=20, time=100)
    return a


class ObservationTests(unittest.TestCase):
    def setUp(self):
        self.stderr = contextlib.redirect_stderr(io.StringIO())
        self.stderr.__enter__()
        self.addCleanup(self.stderr.__exit__, None, None, None)

    def cast(self, screens):
        a = fixture(screens)
        c = SpellHealing()
        result = c.cast(a, 'Z')
        return a, c, result

    def test_ranged_retention_through_actual_observation_and_prompt_path(self):
        a, c, ok = self.cast([
            observation(['Choose which spell to cast', 'Name Level Category Fail Retention',
                         'q - healing 1 healing 0% 91%-100%']),
            observation(message='In what direction?'),
            observation(message='You feel better.', hp=23, energy=15, turn=101)])
        self.assertTrue(ok)
        self.assertEqual(a.actions, ['Z', 'q', '.'])
        self.assertEqual(a.events, ['cast_healing'])
        record = c.diagnostics[-1]
        self.assertEqual(record['spell']['retention'], 91)
        self.assertEqual((record['hp_before'], record['hp'], record['energy']), (10, 23, 15))
        self.assertEqual(c.next_check_turn, 101)

    def test_intervening_messages_finish_before_self_targeting(self):
        a, c, ok = self.cast([
            observation(['q - healing 1 healing 0% 31%-40%']),
            more('You are beginning to feel hungry.', energy=15),
            more('Your knowledge of this spell is growing faint.', energy=15),
            observation(message='In what direction?', energy=15),
            more('You feel better.', hp=23, energy=15, turn=101),
            observation(hp=23, energy=15, turn=101)])
        self.assertTrue(ok)
        self.assertEqual(a.actions, ['Z', 'q', ' ', ' ', '.', ' '])
        self.assertEqual(c.diagnostics[-1]['message_pages'], 3)
        self.assertTrue(c.diagnostics[-1]['completed'])
        self.assertEqual(c.next_check_turn, 101)

    def test_message_before_menu_is_acknowledged(self):
        a, _, ok = self.cast([
            more('You hear some noises in the distance.'),
            observation(['q - healing 1 healing 0% 91%-100%']),
            observation(message='In what direction?'),
            observation(hp=23, energy=15, turn=101)])
        self.assertTrue(ok)
        self.assertEqual(a.actions, ['Z', ' ', 'q', '.'])

    def test_failure_after_more_never_sends_self_direction(self):
        a, c, ok = self.cast([
            observation(['q - healing 1 healing 0% 91%-100%']),
            more('Your knowledge of this spell is growing faint.'),
            observation(message='You fail to cast the spell correctly.', energy=18, turn=101),
            observation(energy=18, turn=101)])
        self.assertFalse(ok)
        self.assertEqual(a.actions, ['Z', 'q', ' ', '\x1b'])
        self.assertFalse(c.diagnostics[-1]['completed'])
        self.assertEqual(c.next_check_turn, 120)

    def test_energy_spending_without_prompt_is_not_completion(self):
        a, c, ok = self.cast([
            observation(['q - healing 1 healing 0% 91%-100%']),
            observation(message='You feel hungry.', energy=15),
            observation(message='In what direction?', energy=15),
            observation(energy=15)])
        self.assertFalse(ok)
        # An unmarked unexpected message is cancelled, and a newly exposed
        # prompt is also cancelled before unrelated strategy code can run.
        self.assertEqual(a.actions, ['Z', 'q', '\x1b', '\x1b'])
        self.assertEqual(c.diagnostics[-1]['energy'], 15)
        self.assertFalse(c.diagnostics[-1]['directed'])
        self.assertEqual(c.next_check_turn, 120)

    def test_unanswered_self_direction_is_cancelled_not_counted(self):
        a, c, ok = self.cast([
            observation(['q - healing 1 healing 0% 91%-100%']),
            observation(message='In what direction?'),
            observation(message='In what direction?'), observation()])
        self.assertFalse(ok)
        self.assertEqual(a.actions, ['Z', 'q', '.', '\x1b'])
        self.assertTrue(c.diagnostics[-1]['directed'])
        self.assertFalse(c.diagnostics[-1]['completed'])
        self.assertEqual(a.events, ['cast_fail_healing'])

    def test_completion_does_not_require_net_hp_gain(self):
        a, c, ok = self.cast([
            observation(['q - healing 1 healing 0% 91%-100%']),
            observation(message='In what direction?'),
            observation(message='You feel better. The jackal bites!', hp=9, energy=15, turn=101)])
        self.assertTrue(ok)
        self.assertTrue(c.diagnostics[-1]['completed'])
        self.assertLess(c.diagnostics[-1]['hp'], c.diagnostics[-1]['hp_before'])

    def test_message_chain_limit_requests_resynchronization(self):
        a = fixture([observation(['q - healing 1 healing 0% 91%-100%'])] +
                    [more('You feel hungry.')] * (SpellHealing.MAX_MESSAGES + 1))
        c = SpellHealing()
        with self.assertRaises(AgentPanic):
            c.cast(a, 'Z')
        self.assertEqual(c.diagnostics[-1]['reason'], 'message_limit')
        self.assertEqual(len(a.actions), 2 + SpellHealing.MAX_MESSAGES)
        self.assertEqual(c.next_check_turn, 120)

    def test_uncancellable_prompt_is_bounded(self):
        a = fixture([observation(message='You know no spells.')] +
                    [observation(message='In what direction?')] * SpellHealing.MAX_CANCELS)
        c = SpellHealing()
        with self.assertRaises(AgentPanic):
            c.cast(a, 'Z')
        self.assertEqual(a.actions, ['Z'] + ['\x1b'] * SpellHealing.MAX_CANCELS)
        self.assertEqual(c.diagnostics[-1]['reason'], 'cancel_stalled')
        self.assertEqual(c.next_check_turn, 120)

    def test_cast_observation_updates_receiver_recovery(self):
        from test_recovery import Recovery
        a = fixture([
            observation(['q - healing 1 healing 0% 91%-100%']),
            more('You feel hungry.'), observation(message='In what direction?'),
            observation(hp=23, energy=15, turn=101)])
        a.recovery = Recovery(a)
        a.blstats.monster_level = 0
        a.recovery.observe(a.blstats)
        c = SpellHealing()
        self.assertTrue(c.cast(a, 'Z'))
        self.assertEqual(a.recovery._health, (23, 30, 0))
        self.assertEqual(a.recovery.blocked_until, -1)
        self.assertFalse(c.ready(23, 30, 15, 101))

    def test_survival_callbacks_resume_only_after_completed_cast(self):
        a = fixture([
            observation(['q - healing 1 healing 0% 91%-100%']),
            more('You feel hungry.'), observation(message='In what direction?'),
            observation(hp=23, energy=15, turn=101)])
        a.turns_in_atom_operation = None
        a.atom_operation = lambda: Agent.atom_operation(a)
        callbacks = []
        c = SpellHealing()

        def update_state(allow_update=True, allow_callbacks=True):
            if allow_callbacks:
                # Production atomic exit runs survival/recovery arbitration.
                # The command record must exist and its prompt be consumed.
                self.assertTrue(c.diagnostics[-1]['completed'])
                self.assertEqual(a.single_message, '')
                callbacks.append(a.blstats.hitpoints)

        a.update_state = update_state
        self.assertTrue(c.cast(a, 'Z'))
        self.assertEqual(callbacks, [23])
        self.assertIsNone(a.turns_in_atom_operation)

    def test_numpy_observation_scalars_are_json_serializable(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest('optional host NumPy unavailable; supplied by arena')
        screens = [observation(['q - healing 1 healing 0% 91%-100%']),
                   observation(message='In what direction?'),
                   observation(message='You feel better.', hp=23, energy=15, turn=101)]
        for obs in screens:
            obs['blstats'] = np.array(obs['blstats'], dtype=np.int64)
        a = fixture(screens)
        for name in ('hitpoints', 'max_hitpoints', 'energy', 'time'):
            setattr(a.blstats, name, np.int64(getattr(a.blstats, name)))
        c = SpellHealing()
        self.assertTrue(c.cast(a, 'Z'))
        import json
        self.assertEqual(json.loads(json.dumps(c.diagnostics[-1]))['hp'], 23)

    def test_range_validation(self):
        for value, expected in [('100%', 100), ('91%-100%', 91), ('1%-10%', 1),
                                ('(gone)', 0), ('0%', 0), ('100%-91%', None),
                                ('91%-101%', None), ('1-10%', None), ('unknown', None)]:
            with self.subTest(value=value):
                parsed = parse_healing_spells(['a - healing 1 healing 0% ' + value])
                self.assertEqual(parsed[0].retention if parsed else None, expected)

    def test_traditional_prompt_then_second_page_uses_current_letter(self):
        a, c, ok = self.cast([
            observation(message='Cast which spell? [a-zA *?]'),
            observation(['a - healing 1 healing 0% (gone)'], marker='(1 of 2)'),
            observation(['Q - healing 1 healing 10% 1%-10%'], marker='(2 of 2)'),
            observation(message='In what direction?'),
            observation(message='You feel better.', hp=20, energy=15, turn=101)])
        self.assertTrue(ok)
        self.assertEqual(a.actions, ['Z', '*', ' ', 'Q', '.'])
        self.assertEqual(c.diagnostics[-1]['pages'][0]['spells'][0]['rejection'], 'forgotten')

    def test_repeated_page_cancels_and_retains_backoff(self):
        page = observation(['a - healing 1 healing 90% 91%-100%'], marker='(1 of 2)')
        a, c, ok = self.cast([page, page, observation()])
        self.assertFalse(ok)
        self.assertEqual(a.actions, ['Z', ' ', '\x1b'])
        self.assertEqual(c.diagnostics[-1]['reason'], 'repeated_page')
        self.assertEqual(c.next_check_turn, 120)

    def test_oversized_pagination_cancels(self):
        a, c, ok = self.cast([
            observation(['a - healing 1 healing 90% 91%-100%'], marker='(1 of 99)'), observation()])
        self.assertFalse(ok)
        self.assertEqual(a.actions, ['Z', '\x1b'])

    def test_refusal_missing_rows_and_rejections_are_distinguishable(self):
        cases = [(observation(message='You are too impaired to cast a spell.'), 'no_menu', None),
                 (observation(['a - healing 1 healing 0% ???']), 'unparsed_menu', None),
                 (observation(['a - healing 1 healing 90% 91%-100%']), 'ineligible', 'unreliable'),
                 (observation(['a - healing 1 healing 0% (gone)']), 'ineligible', 'forgotten')]
        for first, reason, rejection in cases:
            with self.subTest(reason=reason, rejection=rejection):
                a, c, ok = self.cast([first, observation()])
                self.assertFalse(ok)
                self.assertEqual(a.actions, ['Z', '\x1b'])
                record = c.diagnostics[-1]
                self.assertEqual(record['reason'], reason)
                if rejection:
                    self.assertEqual(record['pages'][0]['spells'][0]['rejection'], rejection)
                self.assertEqual(c.next_check_turn, 120)

    def test_current_energy_excludes_expensive_spell(self):
        a = fixture([observation(['b - extra healing 3 healing 0% 91%-100%']), observation()])
        a.blstats.hitpoints = 4
        a.blstats.energy = 10
        c = SpellHealing()
        self.assertFalse(c.cast(a, 'Z'))
        self.assertEqual(c.diagnostics[-1]['pages'][0]['spells'][0]['rejection'], 'energy')

    def test_failure_never_answers_accumulated_direction_prompt(self):
        a, c, ok = self.cast([
            observation(['q - healing 1 healing 0% 91%-100%']),
            observation(message='You fail to cast the spell correctly.', energy=18, turn=101),
            observation(energy=18, turn=101)])
        self.assertFalse(ok)
        self.assertEqual(a.actions, ['Z', 'q', '\x1b'])
        self.assertEqual(c.diagnostics[-1]['reason'], 'no_direction')
        self.assertIn('fail to cast', c.diagnostics[-1]['prompt'])
        self.assertEqual(c.next_check_turn, 120)

    def test_outcome_is_captured_before_atomic_exit_updates(self):
        a = fixture([
            observation(['q - healing 1 healing 0% 91%-100%']),
            observation(message='In what direction?'),
            observation(message='You feel better.', hp=23, energy=15, turn=101)])

        @contextlib.contextmanager
        def atom():
            yield
            # Production atomic exit may update inventory and invoke callbacks.
            a.blstats.hitpoints = 3
            a.single_message = 'Later unrelated observation'

        a.atom_operation = atom
        c = SpellHealing()
        self.assertTrue(c.cast(a, 'Z'))
        self.assertEqual(c.diagnostics[-1]['hp'], 23)
        self.assertEqual(c.diagnostics[-1]['message'], 'You feel better.')
        self.assertEqual(a.blstats.hitpoints, 3)

    def test_diagnostics_bounded_and_restart_does_not_renew_output_budget(self):
        c = SpellHealing()
        for turn in range(100):
            c._record(dict(turn=turn))
        self.assertEqual(len(c.diagnostics), 64)
        self.assertEqual(c.trace_count, 64)
        resumed = SpellHealing()
        resumed.adopt(c)
        resumed._record(dict(turn=101))
        self.assertEqual(resumed.trace_count, 64)
        self.assertEqual(c.diagnostics[-1]['turn'], 99)
        self.assertEqual(SpellHealing().trace_count, 0)


if __name__ == '__main__':
    unittest.main()
