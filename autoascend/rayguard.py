"""rayguard.py -- the reaction to the first ray hit (spell_port/make_rayguard.py hooks plan()/do() into Agent.emergency_strategy).

Early deaths to fire / cold / lightning bolts (wands used by monsters) have one shape: a full-HP wizard takes a first 6d6 hit (median 22, HP ~43), and a second hit
(a second zap, or the ray bouncing back) kills it. A monster zaps an offensive wand only when it is lined up with the hero within BOLT_LIM (8) squares (muse.c
find_offensive/lined_up) and not scared, and Elbereth scares only an adjacent monster (monmove.c distfleeck), so what helps is to leave the line.
  * a ray hit is seen in the messages ('The bolt of fire hits you', 'You are blinded by the flash', ...);
  * for RAY_ALERT turns after it, while a visible hostile within 8 squares (not adjacent) is lined up with us, plan() steps to a neighbouring square that is lined
    up with none of them and not next to any (scored: unlined, farther);
  * no such monster in view (blinded, or an unseen zapper) or no safe square: the up stairs when they are within STAIR_STEPS and HP < STAIR_HP of the maximum;
  * otherwise None (the normal logic)."""
import re

from .glyph import G

RAY_ALERT = 12
STAIR_STEPS = 4
STAIR_HP = 0.8
MAX_STEPS = 10           # off-line steps per hit
RANGE = 8
RAY = re.compile(r"bolt of (fire|cold|lightning)|You are blinded by the flash|Your [a-z' -]+ (?:smoulders|freezes)")
SESSILE = frozenset(('floating eye', 'lichen', 'brown mold', 'yellow mold', 'green mold', 'red mold', 'shrieker', 'violet fungus', 'blue jelly',
                     'spotted jelly', 'acid blob', 'gas spore'))
_NEIGH = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def _st(agent):
    st = agent.__dict__.get('_ray')
    if st is None:
        st = agent._ray = dict(hit_t=-10 ** 9, alert_until=-1, steps=0, stairs_done=False, hits=0, reacted=0, last_msg_step=-1)
    return st


def _can_zap(p):
    """A monster that can use a wand: has hands (not M1_NOHANDS) and is not tiny (monst.c nohands / verysmall)."""
    try:
        from .glyph.monflag import M1_NOHANDS
        return not (p.mflags1 & M1_NOHANDS) and p.msize > 0 and getattr(p, 'mname', '') not in SESSILE
    except Exception:
        return getattr(p, 'mname', '') not in SESSILE


def _lined(dy, dx):
    return dy == 0 or dx == 0 or abs(dy) == abs(dx)


def _cheb(a, b):
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def _new_hit(agent, st):
    bl = agent.blstats
    if st['last_msg_step'] == agent.step_count:
        return False
    st['last_msg_step'] = agent.step_count
    msg = ' '.join([agent.message or ''] + list(agent._message_history[-2:]))
    if not RAY.search(msg):
        return False
    if bl.time - st['hit_t'] < 3:
        return False
    st['hit_t'] = bl.time
    st['alert_until'] = bl.time + RAY_ALERT
    st['steps'] = 0
    st['stairs_done'] = False
    st['hits'] += 1
    return True


def plan(agent):
    try:
        st = _st(agent)
        bl = agent.blstats
        now = bl.time
        if agent.character.role != agent.character.WIZARD:
            return None
        new = _new_hit(agent, st)
        if now > st['alert_until']:
            return None
        if agent.character.prop.polymorph or bl.depth is None:
            return None
        y, x = int(bl.y), int(bl.x)
        mons = [m for m in agent.get_visible_monsters() if _can_zap(m[3])]
        cand = [m for m in mons if _cheb((y, x), (m[1], m[2])) <= RANGE]
        lined = [m for m in cand if _cheb((y, x), (m[1], m[2])) >= 2 and _lined(m[1] - y, m[2] - x)]
        if lined and st['steps'] < MAX_STEPS and not agent.character.prop.blind:
            dis = agent.bfs()
            best, best_score = None, None
            for dy, dx in _NEIGH:
                ny, nx = y + dy, x + dx
                if not (0 <= ny < dis.shape[0] and 0 <= nx < dis.shape[1]) or dis[ny, nx] != 1:
                    continue
                if agent.glyphs[ny, nx] in G.MONS or agent.glyphs[ny, nx] in G.PETS:
                    continue
                nlined = sum(1 for m in cand if _lined(m[1] - ny, m[2] - nx))
                near = min([_cheb((ny, nx), (m[1], m[2])) for m in mons] or [9])
                if near < 2 and min([_cheb((y, x), (m[1], m[2])) for m in mons] or [9]) >= 2:
                    continue          # never step next to a monster we were not next to
                score = (-nlined, near)
                if best_score is None or score > best_score:
                    best, best_score = (ny, nx), score
            if best is not None and best_score[0] == 0:
                return ('step', best[0], best[1], [m[3].mname for m in lined][:3])
        # stairs: no visible zapper to dodge (blind / unseen / nowhere to step) and hurt
        if bl.depth >= 2 and not st['stairs_done'] and bl.hitpoints < STAIR_HP * bl.max_hitpoints and (new or now - st['hit_t'] <= 3):
            lvl = agent.current_level()
            dis = agent.bfs()
            from . import utils
            ups = [p for p in zip(*utils.isin(lvl.objects, G.STAIR_UP).nonzero()) if 0 <= dis[p] <= STAIR_STEPS]
            if ups:
                p = min(ups, key=lambda q: dis[q])
                return ('stairs', int(p[0]), int(p[1]), [m[3].mname for m in cand][:3])
        return None
    except Exception as e:
        try:
            agent.log('RAYGUARD plan error ' + repr(e)[:100])
        except Exception:
            pass
        return None


def do(agent, p):
    st = _st(agent)
    bl = agent.blstats
    kind = p[0]
    st['reacted'] += 1
    agent.log(f'RAYGUARD {kind} t={bl.time} depth={bl.depth} hp={bl.hitpoints}/{bl.max_hitpoints} at=({bl.y},{bl.x}) -> ({p[1]},{p[2]}) lined={p[3]} hits={st["hits"]}')
    try:
        if kind == 'step':
            st['steps'] += 1
            agent.go_to(p[1], p[2], max_steps=1)
        else:
            st['stairs_done'] = True
            for _ in range(STAIR_STEPS + 2):
                if (agent.blstats.y, agent.blstats.x) == (p[1], p[2]):
                    break
                agent.go_to(p[1], p[2], max_steps=1)
            if (agent.blstats.y, agent.blstats.x) == (p[1], p[2]):
                agent.move('<')
    except Exception as e:
        from .exceptions import AgentChangeStrategy, AgentFinished, AgentPanic
        if isinstance(e, (AgentChangeStrategy, AgentFinished, AgentPanic, KeyboardInterrupt, SystemExit)):
            raise
        st['alert_until'] = -1
        agent.log(f'RAYGUARD failed: {type(e).__name__}: {str(e)[:100]}')
