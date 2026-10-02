"""Synthetic menu exchanges only; no NLE environment or gameplay required."""
import ast
import contextlib
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace
import unittest

from autoascend.spell_healing import SpellHealing, choose_healing_spell, parse_healing_spells

MENU = ['Choose which spell to cast', 'Name Level Category Fail Retention',
        'a - healing             1 healing 0% 100%',
        'b - extra healing       3 healing 10% 75%',
        'c - stone to flesh      3 healing 50% 100%']


class AgentFixture:
    def __init__(self, screens, hp=10, max_hp=30, energy=20, time=100):
        self.screens = iter(screens)
        self.blstats = SimpleNamespace(hitpoints=hp, max_hitpoints=max_hp, energy=energy, time=time)
        self.actions = []
        self.events = []
        self.logs = []
        self.message = 'Old prompt: In what direction?'
        self.stats_logger = SimpleNamespace(log_event=self.events.append)
        self.last_cast_fail_turn = defaultdict(lambda: -100)

    atom_operation = staticmethod(contextlib.nullcontext)

    def log(self, msg):
        self.logs.append(msg)

    def step(self, command, inputs):
        self.actions.append(command)
        for message, popup, turn, hp in self.screens:
            self.single_message, self.single_popup = message, popup
            self.blstats.time, self.blstats.hitpoints = turn, hp
            try:
                self.actions.append(next(inputs))
            except StopIteration:
                return
        raise AssertionError('transaction requested an unexpected extra observation')


def terminal(turn=100, hp=10):
    return ('', [], turn, hp)


class HealingTests(unittest.TestCase):
    def test_menu_and_resource_selection(self):
        spells = parse_healing_spells(MENU)
        self.assertEqual(len(spells), 2)
        self.assertEqual(choose_healing_spell(spells, 20, 30).name, 'extra healing')
        self.assertEqual(choose_healing_spell(spells, 5, 30).name, 'healing')
        self.assertEqual(choose_healing_spell(spells, 20, 12).name, 'healing')
        self.assertIsNone(choose_healing_spell(spells, 4, 30))

    def test_forgotten_and_uncertain_spells_are_rejected(self):
        rows = ['a - healing 1 healing 0% (gone)', 'b - extra healing 3 healing 16% 80%',
                'c - healing 1 healing 0% 0%', 'd - healing 1 healing 21% 100%',
                'e - healing 1 healing ?? 100%', 'f - healing 0 healing 0% 100%']
        self.assertIsNone(choose_healing_spell(parse_healing_spells(rows), 100, 30))

    def test_readiness_and_new_episode(self):
        c = SpellHealing()
        self.assertTrue(c.ready(10, 30, 5, 100))
        self.assertFalse(c.ready(29, 30, 5, 100))
        self.assertFalse(c.ready(20, 30, 5, 100))
        self.assertFalse(c.ready(10, 30, 4, 100))
        c.next_check_turn = 120
        self.assertFalse(c.ready(10, 30, 5, 100))
        self.assertTrue(SpellHealing().ready(10, 30, 5, 1))

    def test_cast_uses_observed_letter_and_self_direction(self):
        menu = [line.replace('a -', 'q -') for line in MENU]
        agent = AgentFixture([('', menu, 100, 10), ('In what direction?', [], 100, 10),
                              terminal(101, 23)])
        c = SpellHealing()
        self.assertTrue(c.cast(agent, 'z'))
        self.assertEqual(agent.actions, ['z', 'q', '.'])
        self.assertEqual(agent.events, ['cast_healing'])
        self.assertEqual(c.next_check_turn, 101)

    def test_unchanged_turn_after_direction_does_not_loop(self):
        agent = AgentFixture([('', MENU, 100, 10), ('In what direction?', [], 100, 10),
                              terminal()])
        c = SpellHealing()
        c.cast(agent, 'z')
        self.assertFalse(c.ready(10, 30, 20, 100))
        self.assertEqual(c.next_check_turn, 120)

    def test_traditional_prompt_requests_menu(self):
        agent = AgentFixture([('Cast which spell? [a-c *?]', [], 100, 10),
                              ('', MENU, 100, 10), ('In what direction?', [], 100, 10),
                              terminal(101, 23)])
        self.assertTrue(SpellHealing().cast(agent, 'z'))
        self.assertEqual(agent.actions, ['z', '*', 'a', '.'])

    def test_high_failure_menu_cancels_without_selecting(self):
        menu = [line.replace('0%', '90%') for line in MENU]
        agent = AgentFixture([('', menu, 100, 10), terminal()])
        c = SpellHealing()
        self.assertFalse(c.cast(agent, 'z'))
        self.assertEqual(agent.actions, ['z', '\x1b'])
        self.assertFalse(c.ready(10, 30, 20, 100))
        self.assertTrue(c.ready(10, 30, 20, 120))

    def test_failed_cast_does_not_answer_old_direction_prompt(self):
        agent = AgentFixture([('', MENU, 100, 10),
                              ('You fail to cast the spell correctly.', [], 101, 10), terminal(101)])
        c = SpellHealing()
        self.assertFalse(c.cast(agent, 'z'))
        self.assertEqual(agent.actions, ['z', 'a', '\x1b'])
        self.assertEqual(agent.events, ['cast_fail_healing'])
        self.assertEqual(agent.last_cast_fail_turn['healing'], 101)
        self.assertFalse(c.ready(10, 30, 20, 101))

    def test_refusal_and_unrecognized_menu_are_bounded(self):
        for message, popup in [('You are too impaired to cast a spell.', []),
                               ('', ['Unknown menu format']), ('You know no spells.', [])]:
            with self.subTest(message=message, popup=popup):
                agent = AgentFixture([(message, popup, 100, 10), terminal()])
                c = SpellHealing()
                self.assertFalse(c.cast(agent, 'z'))
                self.assertEqual(agent.actions, ['z', '\x1b'])
                self.assertEqual(c.next_check_turn, 120)

    def test_interrupt_preserves_backoff(self):
        agent = AgentFixture([])
        c = SpellHealing()
        with self.assertRaises(AssertionError):
            c.cast(agent, 'z')
        self.assertEqual(c.next_check_turn, 120)

    def test_role_and_condition_guards_from_agent(self):
        # Exercise the actual guard without importing NLE/Numba on the host.
        tree = ast.parse(Path('autoascend/agent.py').read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Agent')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == 'should_try_spell_healing')
        namespace = {'Character': SimpleNamespace(HEALER=3), 'Hunger': SimpleNamespace(WEAK=3)}
        exec(compile(ast.Module(body=[method], type_ignores=[]), '<guard>', 'exec'), namespace)
        guard = namespace[method.name]
        agent = AgentFixture([])
        agent.spell_healing = SpellHealing()
        agent.character = SimpleNamespace(role=3, prop=SimpleNamespace(
            confusion=False, stun=False, hallu=False, polymorph=False))
        agent.blstats.hunger_state = 1
        agent.blstats.carrying_capacity = 0
        self.assertTrue(guard(agent))
        for prop in ('confusion', 'stun', 'hallu', 'polymorph'):
            setattr(agent.character.prop, prop, True)
            self.assertFalse(guard(agent))
            setattr(agent.character.prop, prop, False)
        for field, blocked in [('hunger_state', 3), ('carrying_capacity', 2)]:
            old = getattr(agent.blstats, field)
            setattr(agent.blstats, field, blocked)
            self.assertFalse(guard(agent))
            setattr(agent.blstats, field, old)
        agent.character.role = 0
        self.assertFalse(guard(agent))


if __name__ == '__main__':
    unittest.main()
