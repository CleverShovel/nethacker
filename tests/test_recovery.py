"""Production recovery and scheduler checks with observation fixtures, no NLE."""
import ast
import contextlib
from dataclasses import dataclass, replace
from functools import partial
from collections import Counter
import importlib.util
import io
import re
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
import unittest

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
PREFIX = '_recovery_test'
package = ModuleType(PREFIX)
package.__path__ = []
sys.modules[PREFIX] = package
for name in ('glyph', 'utils'):
    module = ModuleType(PREFIX + '.' + name)
    sys.modules[module.__name__] = module
sys.modules[PREFIX + '.glyph'].G = SimpleNamespace(SWALLOW={90}, TRAPS={80}, WARNING={91}, INVISIBLE_MON={92})
sys.modules[PREFIX + '.glyph'].SS = SimpleNamespace(S_pool=93, S_water=94, S_lava=95)
sys.modules[PREFIX + '.glyph'].Hunger = SimpleNamespace(HUNGRY=2)
sys.modules[PREFIX + '.utils'].any_in = lambda grid, *values: np.isin(grid, [v for group in values for v in group]).any()


def load(name):
    spec = importlib.util.spec_from_file_location(PREFIX + '.' + name, ROOT / 'autoascend' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


Strategy = load('strategy').Strategy
exceptions = load('exceptions')
AgentChangeStrategy = exceptions.AgentChangeStrategy
recovery_module = load('recovery')
Recovery = recovery_module.Recovery
SearchResult = recovery_module.SearchResult
SearchStalled = recovery_module.SearchStalled

# Exercise production search, step, parsing, atomic updates and preemption
# without importing NLE's object tables. Only peripheral map/inventory services
# and the environment are fixtures.
tree = ast.parse((ROOT / 'autoascend/agent.py').read_text())
agent_class = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Agent')
methods = {'preempt', 'add_on_update', 'call_update_functions', 'disallow_step_calling',
           'atom_operation', 'panic_if_position_changes', 'search', 'step', 'update',
           'update_state', 'update_message_and_popup', 'get_message_and_popup', '_find_marker'}
agent_class.body = [n for n in agent_class.body if isinstance(n, ast.FunctionDef) and n.name in methods]
actions = SimpleNamespace(Command=SimpleNamespace(SEARCH=115, ESC=27),
                          TextCharacters=SimpleNamespace(SPACE=32))
namespace = dict(contextlib=contextlib, partial=partial, Strategy=Strategy, re=re,
                 AgentChangeStrategy=AgentChangeStrategy,
                 AgentPanic=exceptions.AgentPanic, SearchResult=SearchResult, SearchStalled=SearchStalled,
                 A=actions, flatten_items=lambda items: items, nh=SimpleNamespace(COIN_CLASS=0))
exec(compile(ast.Module(body=[agent_class], type_ignores=[]), 'autoascend/agent.py', 'exec'), namespace)
Scheduler = namespace['Agent']


@dataclass(frozen=True)
class Stats:
    hitpoints: int = 10
    max_hitpoints: int = 30
    time: int = 100
    hunger_state: int = 1
    carrying_capacity: int = 0
    dungeon_number: int = 0
    level_number: int = 1
    y: int = 2
    x: int = 2
    monster_level: int = 0


namespace['BLStats'] = Stats


class Fixture(Scheduler):
    def __init__(self):
        self.blstats = Stats()
        self.character = SimpleNamespace(role=0, prop=SimpleNamespace(
            blind=False, hallu=False, confusion=False, stun=False, polymorph=False))
        self.monster_tracker = SimpleNamespace(monster_mask=np.zeros((5, 5), bool),
                                               peaceful_monster_mask=np.zeros((5, 5), bool))
        self.glyphs = np.zeros((5, 5), int)
        self.level = SimpleNamespace(objects=np.zeros((5, 5), int),
                                     search_count=np.zeros((5, 5), int),
                                     dungeon_number=0, level_number=1)
        self.events = []
        self.stats_logger = SimpleNamespace(log_event=self.events.append,
                                            log_gold=lambda *a: None,
                                            log_cumulative_value=lambda *a, **k: None)
        self.step_count = 0
        self._recovery_response_steps = None
        self._hb_actions = Counter()
        self._text_prompt_escapes = 0
        self._teleport_prompt_escapes = 0
        self._suppressed_updates = {}
        self._update_failures = {}
        self._prayer_model_active = lambda: False
        self.on_update = []
        self._no_step_calls = False
        self.after_search = lambda: self.set_stats(hitpoints=self.blstats.hitpoints + 1)
        self.recovery = Recovery(self)
        self.recovery.observe(self.blstats)
        self.score = 0
        self.inventory = SimpleNamespace(items=[], update=lambda: None)
        self.character.update = lambda: None
        self.monster_tracker.update = lambda: None
        self.global_logic = SimpleNamespace(update=lambda: None, dive=SimpleNamespace(
            diving=False, _in_own_pit=lambda: False,
            digging_tool=lambda: None, digging_wand=lambda: None))
        self.check_terrain = lambda **kwargs: None
        self.update_level = lambda: None
        self.turns_in_atom_operation = None
        self._atom_operation_allow_update = None
        self._is_updating_state = False
        self._is_reading_message_or_popup = False
        self._last_turn = self.blstats.time
        self._inactivity_counter = 0
        self._message_history = []
        self.message = self.single_message = ''
        self.popup = self.single_popup = []
        self.next_message = ''
        self.misc = np.zeros(3, dtype=np.int32)
        self.turn_delta = 1
        self._responding = False
        self.commands = []
        self.env = SimpleNamespace(step=self.env_step)
        self._observation = self.last_observation = self.observation()

    @property
    def in_atom_operation(self):
        return self.turns_in_atom_operation is not None

    def observation(self):
        message = np.zeros(256, dtype=np.uint8)
        encoded = self.next_message.encode()
        message[:len(encoded)] = list(encoded)
        tty = np.full((24, 80), ord(' '), dtype=np.uint8)
        tty[0, :len(encoded)] = list(encoded)
        return dict(blstats=np.array(list(vars(self.blstats).values())),
                    glyphs=self.glyphs.copy(), message=message, tty_chars=tty,
                    tty_cursor=np.array([1, 0]), misc=self.misc.copy())

    def env_step(self, action):
        self.commands.append(action)
        previous_stats = self.blstats
        self._responding = True
        try:
            if action == actions.Command.SEARCH:
                self.set_stats(time=self.blstats.time + self.turn_delta)
                self.after_search()
            else:
                # Simulate a prompt dismissal; it is not a completed search.
                self.misc.fill(0)
                self.next_message = ''
            return self.observation(), 0, False, {}
        finally:
            # Only production Agent.update may publish the returned stats and
            # notify Recovery.observe, including during same-turn responses.
            self.blstats = previous_stats
            self._responding = False

    def type_text(self, text):
        for char in text:
            self.step(ord(char))

    def current_level(self):
        return self.level

    def set_stats(self, **kwargs):
        self.blstats = replace(self.blstats, **kwargs)
        if not self._responding:
            self.recovery.observe(self.blstats)

    def run_rest(self):
        with contextlib.redirect_stderr(io.StringIO()):
            return self.recovery.rest().run(return_condition=True)


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.agent = Fixture()

    def test_recovers_then_returns_to_exploration(self):
        self.assertTrue(self.agent.run_rest())
        self.assertEqual(self.agent.blstats.hitpoints, 27)
        self.assertEqual(self.agent.step_count, 17)
        self.assertIn('recovery_completed', self.agent.events)
        self.assertFalse(self.agent.run_rest())

    def test_healthy_character_does_not_rest(self):
        self.agent.set_stats(hitpoints=25)
        self.assertFalse(self.agent.run_rest())
        self.assertEqual(self.agent.step_count, 0)

    def test_guards_for_hunger_burden_and_impaired_observation(self):
        for field, value in [('hunger_state', 2), ('carrying_capacity', 1)]:
            agent = Fixture()
            agent.set_stats(**{field: value})
            self.assertFalse(agent.run_rest())
        for field in ['blind', 'hallu', 'confusion', 'stun', 'polymorph']:
            agent = Fixture()
            setattr(agent.character.prop, field, True)
            self.assertFalse(agent.run_rest())

    def test_monster_or_warning_anywhere_blocks_rest(self):
        self.agent.monster_tracker.monster_mask[0, 0] = True
        self.assertFalse(self.agent.run_rest())
        self.agent.monster_tracker.peaceful_monster_mask[0, 0] = True
        self.assertTrue(self.agent.run_rest())

    def test_engulfing_and_known_trap_block_rest(self):
        self.agent.glyphs[2, 3] = 90
        self.assertFalse(self.agent.run_rest())
        self.agent.glyphs.fill(0)
        self.agent.level.objects[2, 2] = 80
        self.assertFalse(self.agent.run_rest())

    def test_new_monster_stops_after_one_search(self):
        self.agent.after_search = lambda: self.agent.monster_tracker.monster_mask.__setitem__((0, 0), True)
        self.agent.run_rest()
        self.assertEqual(self.agent.step_count, 1)

    def test_new_hunger_stops_after_one_search(self):
        self.agent.after_search = lambda: self.agent.set_stats(hunger_state=2)
        self.agent.run_rest()
        self.assertEqual(self.agent.step_count, 1)

    def test_unseen_damage_stops_rest_and_same_turn_menus_do_not_clear_backoff(self):
        self.agent.after_search = lambda: self.agent.set_stats(hitpoints=9)
        self.agent.run_rest()
        self.assertEqual(self.agent.step_count, 1)
        for _ in range(10):
            self.agent.set_stats()
        self.assertFalse(self.agent.run_rest())
        self.agent.set_stats(time=self.agent.blstats.time + 5)
        self.assertTrue(self.agent.recovery.rest().check_condition())

    def test_recent_damage_before_entry_blocks_rest(self):
        self.agent.set_stats(hitpoints=8)
        self.assertFalse(self.agent.run_rest())

    def test_hp_pool_change_is_not_incoming_damage(self):
        self.agent.set_stats(hitpoints=5, max_hitpoints=20)
        self.assertTrue(self.agent.recovery.rest().check_condition())

    def test_no_healing_abandons_rest_and_backs_off(self):
        self.agent.after_search = lambda: None
        self.agent.run_rest()
        self.assertEqual(self.agent.step_count, 30)
        self.assertFalse(self.agent.run_rest())
        self.agent.set_stats(time=self.agent.blstats.time + 30)
        self.assertTrue(self.agent.recovery.rest().check_condition())

    def test_total_budget_even_when_slowly_healing(self):
        self.agent.set_stats(hitpoints=10, max_hitpoints=1000)
        self.agent.after_search = lambda: self.agent.set_stats(
            hitpoints=self.agent.blstats.hitpoints + (self.agent.blstats.time % 20 == 0))
        self.agent.run_rest()
        self.assertEqual(self.agent.step_count, 200)
        self.assertFalse(self.agent.run_rest())

    def test_identical_fresh_observations_are_bounded(self):
        self.agent.turn_delta = 0
        self.agent.after_search = lambda: None
        self.agent.run_rest()
        self.assertEqual(self.agent.step_count, 4)
        self.assertEqual(self.agent.events.count('recovery_search_same_turn'), 4)
        self.assertFalse(self.agent.run_rest())

    def test_successive_same_turn_searches_then_time_advances(self):
        agent = self.agent
        agent.turn_delta = 0
        def response():
            if len(agent.commands) % 3 == 0:
                agent.set_stats(time=agent.blstats.time + 1,
                                hitpoints=agent.blstats.hitpoints + 1)
        agent.after_search = response
        agent.run_rest()
        self.assertEqual(agent.blstats.hitpoints, 27)
        self.assertEqual(agent.step_count, 51)
        self.assertEqual(agent.events.count('recovery_search_confirmed'), 51)
        self.assertEqual(agent.events.count('recovery_search_same_turn'), 34)
        self.assertIn('recovery_completed', agent.events)

    def test_same_turn_damage_and_hunger_interrupt(self):
        for change in [dict(hitpoints=9), dict(hunger_state=2)]:
            agent = Fixture()
            agent.turn_delta = 0
            agent.after_search = lambda: agent.set_stats(**change)
            agent.run_rest()
            self.assertEqual(agent.step_count, 1)

    def test_same_turn_unknown_or_refused_message_stops(self):
        for message in ["Unknown command 's'.", "You can't do that!", "Please wait."]:
            agent = Fixture()
            agent.turn_delta = 0
            agent.next_message = message
            agent.after_search = lambda: None
            agent.run_rest()
            self.assertEqual(agent.step_count, 1)
            self.assertNotIn('recovery_search_confirmed', agent.events)
            self.assertFalse(agent.run_rest())

    def test_discovery_same_turn_is_completed(self):
        self.agent.turn_delta = 0
        self.agent.next_message = 'You find a hidden door.'
        self.agent.after_search = lambda: None
        result = self.agent.search(return_result=True)
        self.assertEqual(result.status, 'completed')

    def test_pending_prompt_does_not_dispatch_search(self):
        for flag in range(3):
            agent = Fixture()
            agent._observation['misc'][flag] = 1
            result = agent.search(return_result=True)
            self.assertEqual(result.status, 'prompt')
            self.assertFalse(result.sent)
            self.assertEqual(agent.step_count, 0)

    def test_response_prompt_does_not_confirm_search_after_dismissal(self):
        for flag in range(3):
            agent = Fixture()
            agent.turn_delta = 0
            agent.after_search = lambda: agent.misc.__setitem__(flag, 1)
            agent.run_rest()
            self.assertEqual(agent.commands.count(actions.Command.SEARCH), 1)
            self.assertNotIn('recovery_search_confirmed', agent.events)
            self.assertFalse(agent.run_rest())

    def test_persistent_prompt_is_bounded_and_unwinds_for_resynchronization(self):
        agent = self.agent
        def stuck_response(action):
            agent.commands.append(action)
            agent.misc[2] = 1
            return agent.observation(), 0, False, {}
        agent.env.step = stuck_response
        with self.assertRaises(SearchStalled):
            agent.run_rest()
        self.assertEqual(agent.step_count, 8)
        self.assertEqual(agent.commands.count(actions.Command.SEARCH), 1)
        self.assertEqual(agent.on_update, [])
        self.assertIsNone(agent.turns_in_atom_operation)
        self.assertIsNone(agent._recovery_response_steps)
        self.assertFalse(agent.run_rest())

    def test_time_reversal_is_not_completion(self):
        self.agent.turn_delta = -1
        self.agent.after_search = lambda: None
        self.agent.run_rest()
        self.assertEqual(self.agent.step_count, 1)
        self.assertNotIn('recovery_search_confirmed', self.agent.events)
        self.assertFalse(self.agent.run_rest())

    def test_stale_or_unparsed_response_does_not_confirm(self):
        for stale in [True, False]:
            agent = Fixture()
            if stale:
                agent.step = lambda action: agent.last_observation
            else:
                agent.update = lambda *args: None
            agent.run_rest()
            self.assertLessEqual(agent.step_count, 1)
            self.assertNotIn('recovery_search_confirmed', agent.events)
            self.assertFalse(agent.run_rest())

    def test_healing_cannot_reset_same_turn_stall_bound(self):
        self.agent.turn_delta = 0
        self.agent.run_rest()
        self.assertEqual(self.agent.step_count, 4)
        self.assertFalse(self.agent.run_rest())

    def test_legacy_search_returns_bool_and_supports_count(self):
        self.assertIs(self.agent.search(), True)
        counts = []
        self.agent.type_text = counts.append
        self.assertIs(self.agent.search(5), True)
        self.assertEqual(counts, ['5'])

    def test_housekeeping_observation_is_not_used_as_search_receipt(self):
        # Production atom_operation exits through update_state. An inventory
        # query there can replace last_observation without invalidating the
        # receipt already captured for the direct search response.
        self.agent.inventory.update = lambda: self.agent.step(actions.Command.ESC)
        result = self.agent.search(return_result=True)
        self.assertEqual(result.status, 'completed')
        self.assertEqual(self.agent.step_count, 2)

    def test_level_or_position_change_aborts_rest(self):
        for field in ['level_number', 'x']:
            agent = Fixture()
            agent.after_search = lambda: agent.set_stats(**{field: 3})
            if field == 'x':
                with self.assertRaises(namespace['AgentPanic']):
                    agent.run_rest()
            else:
                agent.run_rest()
            self.assertEqual(agent.step_count, 1)

    def test_real_scheduler_emergency_preempts_rest(self):
        triggered = []
        agent = self.agent
        agent.turn_delta = 0

        @Strategy.wrap
        def emergency():
            yield agent.blstats.hitpoints < 8
            triggered.append('emergency')

        agent.after_search = lambda: agent.set_stats(hitpoints=5)
        strategy = agent.recovery.rest().preempt(agent, [emergency()], continue_after_preemption=False)
        with contextlib.redirect_stderr(io.StringIO()):
            strategy.run()
        self.assertEqual(triggered, ['emergency'])
        self.assertEqual(agent.step_count, 1)
        self.assertEqual(agent.on_update, [])

    def test_fresh_game_has_no_previous_backoff(self):
        self.agent.set_stats(hitpoints=5)
        fresh = Fixture()
        self.assertTrue(fresh.recovery.rest().check_condition())
        self.assertEqual(fresh.recovery.sessions, 0)


    def test_tool_dives_and_unfinished_pits_keep_descent_ownership(self):
        for resource in ['digging_tool', 'digging_wand']:
            agent = Fixture()
            agent.global_logic.dive.diving = True
            setattr(agent.global_logic.dive, resource, lambda: object())
            self.assertFalse(agent.run_rest())
            # A tool in the pack during ordinary preparation is not a dive.
            agent.global_logic.dive.diving = False
            self.assertTrue(agent.recovery.rest().check_condition())
        agent = Fixture()
        agent.global_logic.dive._in_own_pit = lambda: True
        self.assertFalse(agent.run_rest())

    def test_warning_invisible_and_wet_terrain_are_not_quiet(self):
        for glyph in [91, 92]:
            agent = Fixture()
            agent.glyphs[0, 0] = glyph
            # Even a receiver mask that guesses 'peaceful' is insufficient.
            agent.monster_tracker.peaceful_monster_mask[0, 0] = True
            self.assertFalse(agent.run_rest())
        for glyph in [93, 94, 95]:
            agent = Fixture()
            agent.level.objects[2, 2] = glyph
            self.assertFalse(agent.run_rest())

    def test_hp_pool_and_form_changes_end_active_session(self):
        for change in [dict(max_hitpoints=40), dict(monster_level=5)]:
            agent = Fixture()
            agent.after_search = lambda: agent.set_stats(**change)
            agent.run_rest()
            self.assertEqual(agent.step_count, 1)
            self.assertNotIn('recovery_completed', agent.events)

    def test_form_change_does_not_count_as_damage(self):
        self.agent.set_stats(hitpoints=5, monster_level=7)
        self.assertEqual(self.agent.recovery.blocked_until, -1)

    def test_global_survival_hooks_interrupt_quiet_recovery(self):
        # Execute the receiver's actual nested global strategy, with inert
        # peripheral skills. Activating a named outer hook must unwind rest
        # before another search, including when the displayed turn is unchanged.
        source = ROOT / 'autoascend/global_logic.py'
        tree = ast.parse(source.read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'GlobalLogic')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'global_strategy')
        cls.body = [method]
        from autoascend import jf_config
        ns = dict(jf_config=jf_config, Milestone=SimpleNamespace(SOLVE_SOKOBAN=10),
                  Level=SimpleNamespace(SOKOBAN=4),
                  Hunger=SimpleNamespace(NOT_HUNGRY=1, HUNGRY=2),
                  castle_power=SimpleNamespace(deep_poly_escape_strategy=lambda dive: inactive()))
        exec(compile(ast.Module(body=[cls], type_ignores=[]), str(source), 'exec'), ns)

        @Strategy.wrap
        def inactive():
            yield False

        class Skills:
            def __getattr__(self, name):
                return lambda *args, **kwargs: inactive()

        class StopScenario(Exception):
            pass

        for owner, name in [('agent', 'emergency_strategy'), ('agent', 'fight2'),
                            ('agent', 'eat_corpses_from_ground'), ('dive', 'dig_first'),
                            ('dive', 'elbereth_rest'), ('dive', 'retreat_upstairs')]:
            with self.subTest(skill=name):
                agent = Fixture()
                agent.turn_delta = 0
                dive = Skills()
                dive.diving = True
                dive._in_own_pit = lambda: False
                dive.digging_tool = dive.digging_wand = lambda: None
                dive.castle = Skills()
                global_logic = ns['GlobalLogic']()
                global_logic.agent, global_logic.dive = agent, dive
                global_logic.milestone = -1
                # Fill only peripheral skills, preserving real agent mechanics.
                for container, names in [(global_logic, ['current_strategy', 'solve_sokoban_strategy',
                        'offer_corpses', 'wait_out_unexpected_state_strategy', 'follow_guard']),
                        (agent, ['eat_corpses_from_ground', 'eat_from_inventory', 'cure_disease',
                        'unsqueeze', 'escape_bear_trap', 'fight2', 'were_unload',
                        'engulfed_fight', 'emergency_strategy'])]:
                    for skill in names:
                        setattr(container, skill, lambda *a, **k: inactive())
                agent.inventory.buy_food = agent.inventory.sell_price_identify = lambda: inactive()
                agent.global_logic = global_logic
                global_logic.update = lambda: None
                agent.prayer_failed = False
                triggered = []

                @Strategy.wrap
                def survival(*args, **kwargs):
                    yield agent.recovery.sessions > 0 and agent.step_count >= 2
                    triggered.append(name)
                    raise StopScenario()

                @Strategy.wrap
                def explore():
                    yield True
                    # The global recovery hook must interrupt real exploration.
                    for _ in range(10):
                        agent.search()
                    self.fail('global recovery/survival failed to take ownership')

                setattr(agent if owner == 'agent' else dive, name, survival)
                global_logic.current_strategy = explore
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(StopScenario):
                    global_logic.global_strategy().run()
                self.assertEqual(triggered, [name])
                self.assertEqual(agent.recovery.sessions, 1)
                self.assertEqual(agent.step_count, 2)
                self.assertEqual(agent.on_update, [])


if __name__ == '__main__':
    unittest.main()
