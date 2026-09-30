"""Synthetic observation/decision checks. No NLE or gameplay required.

Load Agent methods from their AST because importing the full policy requires
NLE/numba in the arena image. The method bodies are the production source.
"""
import ast
import contextlib
from pathlib import Path
from types import SimpleNamespace as NS
import unittest

from autoascend import jf_config
from autoascend.spell_healing import SpellHealing
from autoascend.nhmodel.incoming_harm import IncomingHarm
from autoascend.nhmodel.prayer import PrayerModel, rnz_cdf


def agent_methods():
    source = Path(__file__).resolve().parents[1] / 'autoascend/agent.py'
    tree = ast.parse(source.read_text())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Agent')
    selected = {'_prayer_model_active', '_prayer_holds_ok', '_hp_prayer_due',
                '_doom_prayer_beats_exits', '_emergency_downstairs_available',
                '_faint_doom_prayer_due', 'emergency_strategy', 'should_try_spell_healing'}
    methods = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in selected]
    for method in methods:
        method.decorator_list = []
    cls.body = methods
    namespace = dict(Character=NS(HEALER=3, MONK=5), A=NS(Command=NS(CAST='cast')), jf_config=jf_config, G=NS(STAIR_DOWN={'> '}), Level=NS(SOKOBAN=4),
                     Hunger=NS(FAINTING=4, WEAK=3), flatten_items=lambda items: items,
                     nh=NS(NLE_BL_CONDITION=0, BL_MASK_STONE=1, BL_MASK_SLIME=2,
                           BL_MASK_STRNGL=4, BL_MASK_FOODPOIS=8, BL_MASK_TERMILL=16))
    exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                 str(source), 'exec'), namespace)
    namespace['Agent'].SAFE_PRAYER_P = rnz_cdf(350, 701)
    return namespace['Agent']


Agent = agent_methods()


def make_agent():
    a = Agent()
    a.blstats = NS(time=1000, hitpoints=20, max_hitpoints=30, armor_class=0,
                   depth=5, experience_level=5, prop_mask=0, hunger_state=0,
                   x=2, y=2, dungeon_number=0, level_number=5, carrying_capacity=0, energy=20)
    a.character = NS(role=0, alignment=1, prop=NS(polymorph=False, blind=False, confusion=False, stun=False, hallu=False),
                     poly_hp_is_buffer=lambda: False)
    a.glyphs = {(2, 2): 123}
    a.level = NS(objects={(2, 2): '.'}, dungeon_number=0)
    a.current_level = lambda: a.level
    a.inventory = NS(engraving_below_me=None, items=[])
    a.global_logic = NS(dive=NS(_ignores_elbereth=lambda mon: False, _retreat_blocked_until=-1))
    a.monsters = []
    a.get_visible_monsters = lambda: a.monsters
    a.can_engrave = lambda: True
    a._message_history = []
    a.step_count = 0
    a.message = ''
    a.prayer_hold_until = -1
    a.last_prayer_turn = 700
    a._last_resort_stairs_turn = -1000
    a.prayer_failed = False
    a.is_safe_to_pray = lambda gap: False
    a._prayer_model_error = lambda: (_ for _ in ()).throw(AssertionError('model error'))
    a.log = lambda msg: None
    a._critically_low_hp = lambda: a.blstats.hitpoints <= 5
    a.last_observation = {'blstats': [0]}
    a.actions = []
    a.move = lambda action: a.actions.append(action)
    a.pray = lambda: a.actions.append('pray')
    a.fainting_prayer_due = lambda: False
    a.threat_prayer_due = lambda: False
    a._weld_prayer_due = lambda: False
    a.spell_healing = SpellHealing()
    a.prayer_model = PrayerModel(a)
    a.prayer_model.timeout_kind = 'pleased'
    a.prayer_model.timeout_turn = 800
    return a


def observe(a, turn, hp, msg=''):
    a.step_count += 1
    a.blstats.time = turn
    a.blstats.hitpoints = hp
    a.message = msg
    a._message_history.append(msg)
    a.prayer_model.observe()


def hurt(a):
    observe(a, 1000, 20)
    observe(a, 1001, 12, 'It hits!')
    observe(a, 1002, 4, 'It hits!')


class HarmTests(unittest.TestCase):
    def test_supported_damage_reaches_final_prayer(self):
        a = make_agent()
        hurt(a)
        self.assertGreater(a.prayer_model.death_probability(), 0.7)
        self.assertEqual(a.prayer_model.hp_decision(a.SAFE_PRAYER_P), 'hp-doom')
        self.assertTrue(a._hp_prayer_due(True, False))
        self.assertIn('hp-doom', a._pray_reason)

    def test_noncombat_loss_is_not_an_unseen_attack(self):
        for msg in ['', 'You feel weaker.', 'You fall into a pit!',
                    'The poison was deadly...', 'You faint from lack of food.',
                    'You hit it.', 'It misses.', 'The arrow hits you!']:
            with self.subTest(msg=msg):
                a = make_agent()
                observe(a, 1000, 20)
                observe(a, 1001, 12, msg)
                observe(a, 1002, 4, msg)
                self.assertEqual(a.prayer_model.death_probability(), 0)
                self.assertFalse(a._hp_prayer_due(True, False))

    def test_attack_message_without_loss_is_not_damage(self):
        a = make_agent()
        observe(a, 1000, 4)
        observe(a, 1001, 4, 'It hits!')
        self.assertEqual(a.prayer_model.unseen_attack_dps(), 0)

    def test_single_supported_hit_is_usable_but_expires(self):
        a = make_agent()
        observe(a, 1000, 12)
        observe(a, 1001, 4, 'Something bites you!')
        self.assertGreater(a.prayer_model.unseen_attack_dps(), 0)
        observe(a, 1002, 4)
        self.assertGreater(a.prayer_model.unseen_attack_dps(), 0)
        observe(a, 1003, 4)
        self.assertEqual(a.prayer_model.unseen_attack_dps(), 0)

    def test_same_turn_observations_do_not_amplify_damage(self):
        a = make_agent()
        hurt(a)
        dps = a.prayer_model.unseen_attack_dps()
        for _ in range(10):
            observe(a, 1002, 4, 'It hits!')
        self.assertEqual(a.prayer_model.unseen_attack_dps(), dps)
        self.assertEqual(len(a.prayer_model.incoming_harm.samples), 3)

    def test_same_turn_split_message_and_hp(self):
        a = make_agent()
        observe(a, 1000, 20)
        observe(a, 1001, 20, 'It hits!')
        observe(a, 1001, 4)
        self.assertEqual(a.prayer_model.unseen_attack_dps(), 16)

    def test_recovery_discards_damage(self):
        a = make_agent()
        hurt(a)
        observe(a, 1002, 10, 'You feel better.')
        self.assertEqual(a.prayer_model.unseen_attack_dps(), 0)

    def test_context_changes_and_long_gaps_discard_damage(self):
        for change in ['level', 'maxhp', 'form', 'gap', 'rewind']:
            with self.subTest(change=change):
                a = make_agent()
                hurt(a)
                if change == 'level':
                    a.blstats.level_number += 1
                if change == 'maxhp':
                    a.blstats.max_hitpoints += 1
                if change == 'form':
                    a.character.prop.polymorph = True
                turn = 1010 if change == 'gap' else 1 if change == 'rewind' else 1003
                observe(a, turn, 2, 'It hits!')
                self.assertEqual(a.prayer_model.unseen_attack_dps(), 0)

    def test_fresh_model_reset_and_adoption(self):
        a = make_agent()
        hurt(a)
        b = make_agent()
        self.assertEqual(b.prayer_model.unseen_attack_dps(), 0)
        a.prayer_model.adopt(b)
        observe(b, 1002, 4)  # b still has its fresh model
        self.assertEqual(b.prayer_model.unseen_attack_dps(), 0)
        b.prayer_model = a.prayer_model
        self.assertGreater(b.prayer_model.unseen_attack_dps(), 0)
        observe(b, 1010, 4)
        self.assertEqual(b.prayer_model.unseen_attack_dps(), 0)

    def test_prayer_feasibility_and_holds(self):
        for gate in ['anger', 'hold', 'gehennom', 'timeout', 'poly_buffer']:
            with self.subTest(gate=gate):
                a = make_agent()
                hurt(a)
                if gate == 'anger':
                    a.prayer_model.p_ugangr = 1
                if gate == 'hold':
                    a.prayer_hold_until = 1100
                if gate == 'gehennom':
                    a.level.dungeon_number = 1
                if gate == 'timeout':
                    a.prayer_model.timeout_kind = 'start'
                    a.prayer_model.timeout_turn = 1000
                self.assertFalse(a._hp_prayer_due(gate != 'poly_buffer', gate == 'poly_buffer'))

    def test_safe_prayer_still_available_without_threat(self):
        a = make_agent()
        observe(a, 1000, 4)
        a.prayer_model.timeout_kind = 'start'
        a.prayer_model.timeout_turn = 1
        self.assertTrue(a._hp_prayer_due(True, False))

    def test_faint_consumer_uses_same_evidence(self):
        a = make_agent()
        hurt(a)
        a.blstats.hunger_state = 4
        a.prayer_model.timeout_kind = 'start'
        a.prayer_model.timeout_turn = 1
        self.assertTrue(a._faint_doom_prayer_due())
        observe(a, 1005, 4)
        self.assertFalse(a._faint_doom_prayer_due())

    def test_stairs_veto_and_actual_execution(self):
        a = make_agent()
        hurt(a)
        a.level.objects[(2, 2)] = '> '
        self.assertFalse(a._hp_prayer_due(True, False))
        self.assertEqual(list(a.emergency_strategy()), [True])
        self.assertEqual(a.actions, ['>'])
        self.assertEqual(a._last_resort_stairs_turn, 1002)

    def test_stairs_do_not_displace_safe_prayer(self):
        a = make_agent()
        hurt(a)
        a.level.objects[(2, 2)] = '> '
        a.prayer_model.timeout_kind = 'start'
        a.prayer_model.timeout_turn = 1
        self.assertEqual(list(a.emergency_strategy()), [True])
        self.assertEqual(a.actions, ['pray'])

    def test_unavailable_stairs_do_not_veto_prayer(self):
        for block in ['burden', 'sokoban', 'recent']:
            with self.subTest(block=block):
                a = make_agent()
                hurt(a)
                a.level.objects[(2, 2)] = '> '
                if block == 'burden':
                    a.blstats.carrying_capacity = 4
                if block == 'sokoban':
                    a.level.dungeon_number = 4
                if block == 'recent':
                    a._last_resort_stairs_turn = 1001
                self.assertTrue(a._hp_prayer_due(True, False))

    def test_visible_threat_retained_and_elbereth_not_assumed_for_unknown(self):
        a = make_agent()
        observe(a, 1000, 4)
        a.monsters = [(1, 2, 3, NS(mname='minotaur'), None)]
        self.assertGreater(a.prayer_model.death_probability(), 0.9)
        a.monsters[0][3].mname = 'jackal'
        a.prayer_model.last_p_hp = 0.3
        self.assertFalse(a._doom_prayer_beats_exits(a.prayer_model))
        hurt(a)
        self.assertTrue(a._doom_prayer_beats_exits(a.prayer_model))
        a.inventory.engraving_below_me = 'Elbereth'
        self.assertGreater(a.prayer_model.death_probability(), 0.7)


class HealingIntegrationTests(unittest.TestCase):
    def test_unseen_critical_prayer_preempts_healing(self):
        a = make_agent()
        a.character.role = 3
        hurt(a)
        self.assertTrue(a.should_try_spell_healing())
        self.assertEqual(list(a.emergency_strategy()), [True])
        self.assertEqual(a.actions, ['pray'])

    def test_unseen_escape_preempts_healing_when_prayer_deferred(self):
        a = make_agent()
        a.character.role = 3
        hurt(a)
        a.level.objects[(2, 2)] = '> '
        self.assertTrue(a.should_try_spell_healing())
        self.assertEqual(list(a.emergency_strategy()), [True])
        self.assertEqual(a.actions, ['>'])

    def test_moderate_wound_cast_clears_harm_and_preserves_menu_dedup(self):
        a = make_agent()
        a.character.role = 3
        observe(a, 1000, 20)
        observe(a, 1001, 12, 'It hits!')
        self.assertEqual(a.prayer_model.unseen_attack_dps(), 8)
        a.events = []
        a.stats_logger = NS(log_event=a.events.append)
        a.atom_operation = contextlib.nullcontext
        a.last_cast_fail_turn = {}
        screens = [('', ['q - healing 1 healing 0% 100%'], 1001, 12),
                   ('In what direction?', [], 1001, 12),
                   ('You feel better.', [], 1002, 25)]

        def step(command, inputs):
            a.actions.append(command)
            for msg, popup, turn, hp in screens:
                a.single_message, a.single_popup = msg, popup
                observe(a, turn, hp, msg)
                if hp == 12:
                    self.assertEqual(a.prayer_model.unseen_attack_dps(), 8)
                try:
                    a.actions.append(next(inputs))
                except StopIteration:
                    return
            self.fail('unexpected extra menu input')

        a.step = step
        self.assertEqual(list(a.emergency_strategy()), [True])
        self.assertEqual(a.actions, ['cast', 'q', '.'])
        self.assertEqual(a.events, ['cast_healing'])
        self.assertEqual(a.prayer_model.unseen_attack_dps(), 0)
        self.assertFalse(a._hp_prayer_due(False, False))
        self.assertFalse(a.should_try_spell_healing())

    def test_recovery_to_still_critical_hp_invalidates_doom(self):
        a = make_agent()
        hurt(a)
        self.assertTrue(a._hp_prayer_due(True, False))
        observe(a, 1002, 5, 'You feel better.')
        self.assertEqual(a.prayer_model.unseen_attack_dps(), 0)
        self.assertFalse(a._hp_prayer_due(True, False))

    def test_worker_restart_preserves_guards_and_new_game_resets(self):
        # Exercise the real driver start method with inert workers; no threads
        # or NLE environment are needed to validate state transfer ordering.
        path = Path(__file__).resolve().parents[1] / 'arena_adapter.py'
        tree = ast.parse(path.read_text())
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef)
                   and n.name == 'AutoAscendDriver')
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef)
                      and n.name == '_start')
        cls.body = [method]
        namespace = dict(ArenaEnvAdapter=lambda: None,
                         autoascend_agent=NS(Agent=lambda *args, **kwargs: make_agent()),
                         threading=NS(Thread=lambda **kwargs: NS(start=lambda: None)))
        exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])),
                     str(path), 'exec'), namespace)
        driver = namespace['AutoAscendDriver']()
        driver._run_agent = lambda agent: None
        # Isolated recovery fixture loads the production class without NLE.
        from test_recovery import Recovery
        original_factory = namespace['autoascend_agent'].Agent
        def with_recovery(*args, **kwargs):
            agent = original_factory(*args, **kwargs)
            agent.recovery = Recovery(agent)
            return agent
        namespace['autoascend_agent'].Agent = with_recovery
        old = driver._agent = with_recovery()
        old.spell_healing.diagnostics.append(dict(reason="interrupted"))
        old.spell_healing.trace_count = 12
        hurt(old)
        old.recovery.blocked_until = 1030
        old.recovery._health = (4, 30, 0)
        old.recovery.sessions = 7
        old.spell_healing.next_check_turn = 1020
        old._last_resort_stairs_turn = 1001
        old.global_logic.dive._retreat_blocked_until = 1021
        driver._start(fresh_game=False)
        resumed = driver._agent
        self.assertIsNot(resumed.recovery, old.recovery)
        self.assertIs(resumed.recovery.agent, resumed)
        self.assertEqual(resumed.recovery.blocked_until, 1030)
        self.assertEqual(resumed.recovery._health, (4, 30, 0))
        self.assertEqual(resumed.recovery.sessions, 7)
        self.assertIs(resumed.prayer_model, old.prayer_model)
        self.assertIs(resumed.prayer_model.agent, resumed)
        self.assertIsNot(resumed.spell_healing, old.spell_healing)
        self.assertEqual(resumed.spell_healing.next_check_turn, 1020)
        self.assertEqual(resumed.spell_healing.trace_count, 12)
        self.assertEqual(list(resumed.spell_healing.diagnostics), [{"reason": "interrupted"}])
        self.assertIsNot(resumed.spell_healing.diagnostics, old.spell_healing.diagnostics)
        self.assertEqual(resumed._last_resort_stairs_turn, 1001)
        self.assertEqual(resumed.global_logic.dive._retreat_blocked_until, 1021)
        observe(resumed, 1002, 4)
        self.assertEqual(resumed.prayer_model.unseen_attack_dps(), 8)
        self.assertFalse(resumed.spell_healing.ready(4, 30, 20, 1002))
        resumed.level.objects[(2, 2)] = '> '
        self.assertFalse(resumed._emergency_downstairs_available())
        observe(resumed, 1002, 15, 'You feel better.')
        self.assertEqual(resumed.prayer_model.unseen_attack_dps(), 0)
        driver._start(fresh_game=True)
        fresh = driver._agent
        self.assertEqual(fresh.recovery.blocked_until, -1)
        self.assertIsNone(fresh.recovery._health)
        self.assertEqual(fresh.recovery.sessions, 0)
        self.assertIsNot(fresh.prayer_model, resumed.prayer_model)
        self.assertEqual(fresh.prayer_model.unseen_attack_dps(), 0)
        self.assertEqual(fresh.spell_healing.next_check_turn, -1)
        self.assertEqual(fresh.spell_healing.trace_count, 0)
        self.assertEqual(list(fresh.spell_healing.diagnostics), [])
        self.assertEqual(fresh._last_resort_stairs_turn, -1000)
        self.assertEqual(fresh.global_logic.dive._retreat_blocked_until, -1)


if __name__ == '__main__':
    unittest.main()
