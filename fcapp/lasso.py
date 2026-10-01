"""Coach Lasso's personal post-match notes (the push notification).

Every note is built for one player's one performance:
  * facts carry context from that player's own history: vs their usual,
    personal bests, scoring streaks, the opponent, the score
  * each kind of line has several Ted-style variants, and a player never gets
    the same phrasing again within their next few notes (teammates in the same
    match get different phrasing too)
  * 6-10 bullets, every one tied to a number

Built in coach.annotate() so the choice of words is stable across rebuilds.
"""
import random
import re
import zlib

from . import playbook as pb

COACH = "Coach Lasso"
RECENT_NOTES = 4  # don't reuse a phrase within a player's last N notes


# ------------------------------------------------------------------ helpers

def _plural(n, word, plural=None):
    return f"{n} {word if n == 1 else (plural or word + 's')}"


class Picker:
    """Chooses phrase variants, avoiding ones this player heard recently and
    ones already used in this match (by them or a teammate)."""

    def __init__(self, seed, avoid):
        self.rng = random.Random(zlib.crc32(seed.encode()))
        self.avoid = avoid
        self.used = set()

    def __call__(self, key, options):
        ids = range(len(options))
        fresh = [i for i in ids if f"{key}:{i}" not in self.avoid and f"{key}:{i}" not in self.used]
        pool = fresh or [i for i in ids if f"{key}:{i}" not in self.used] or list(ids)
        i = self.rng.choice(pool)
        self.used.add(f"{key}:{i}")
        return options[i]


class Context:
    """What makes this performance different from the player's others."""

    def __init__(self, m, p, history):
        self.s = p["stats"]
        self.prev = [h["stats"] for h in history][-10:]
        self.opp = m["opponent"]["name"]
        self.score = f"{m['gf']}-{m['ga']}"
        self.result = m["result"]
        streak = 0
        for h in reversed(history):
            if h["stats"]["goals"]:
                streak += 1
            else:
                break
        self.goal_streak = streak + 1 if self.s["goals"] else 0
        self.motm_count = sum(1 for h in history if h["stats"]["mom"]) + (1 if self.s["mom"] else 0)

    def avg(self, key):
        vals = [h[key] for h in self.prev if h.get(key) is not None]
        return sum(vals) / len(vals) if len(vals) >= 3 else None

    def best(self, key):
        vals = [h[key] for h in self.prev if h.get(key) is not None]
        return max(vals) if len(vals) >= 3 else None

    def usual(self, key, pct=False):
        """'up from your usual 61%' when the gap is worth mentioning, else ''."""
        cur, avg = self.s.get(key), self.avg(key)
        if cur is None or avg is None or abs(cur - avg) < (6 if pct else 1.5):
            return ""
        return f"{'up from' if cur > avg else 'down from'} your usual {avg:.0f}{'%' if pct else ''}"

    def vs_usual(self, key, pct=False):
        u = self.usual(key, pct)
        return f" ({u})" if u else ""

    def season_high(self, key):
        cur, best = self.s.get(key), self.best(key)
        return cur is not None and best is not None and cur > best and cur > 0


def _ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ------------------------------------------------------------- the phrases

OPENERS = {
    "Top 10%": [
        "{name}, a {r} against {opp}. That's top-ten-percent {pos} play anywhere in this league. I'd frame it if I knew how frames worked.",
        "Well, butter my biscuit, {name}. A {r}. Folks in the top 10% of {pos}s don't play much better than that.",
        "{name}, I've seen sunsets in Kansas less beautiful than that {r}. Top 10% for a {pos}.",
        "A {r} against {opp}, {name}. If I had a hat I'd tip it, then I'd buy a second hat just to tip that one too.",
        "{name}, that {r} is the kind of night that makes an old coach believe in magic. Top 10% of {pos}s.",
    ],
    "Top 25%": [
        "Now that's what I'm talking about, {name}. A {r} puts you in the top quarter of {pos}s.",
        "{name}, a {r} against {opp}. That's top-25% {pos} work, and it didn't happen by accident.",
        "Hoo-wee, {name}. A {r}. You played like someone who ate their vegetables.",
        "{name}, a {r} is a whole lotta good. Top quarter of {pos}s, and you made it look easy.",
        "A {r} against {opp}, {name}. That's the good stuff, the kind you tell your dog about on the drive home.",
    ],
    "Above average": [
        "Solid shift, {name}. A {r} clears the bar for a {pos}, and solid is the soil good things grow in.",
        "{name}, a {r} against {opp}. Above average for a {pos}. A good day at the office, and the office had snacks.",
        "A {r}, {name}. That's a sturdy front porch of a performance. We can build a house on it.",
        "{name}, a {r} is better than most {pos}s managed tonight. Let's go find the next gear.",
        "Good stuff, {name}. A {r} against {opp}. Not fireworks, but a nice warm campfire.",
    ],
    "Below average": [
        "{name}, a {r} is a touch under par for a {pos}. That's alright. Even the best tomatoes have a bruise or two.",
        "A {r} against {opp}, {name}. Little below the line for a {pos}, but there's good stuff in here to work with.",
        "{name}, a {r}. Not your best, not your worst, and definitely not your last. Let's dig in.",
        "{name}, a {r} is a quiet night for a {pos}. Quiet nights teach the loudest lessons.",
        "A {r}, {name}. Think of it like a first pancake. Next one's gonna be golden.",
    ],
    "Bottom 25%": [
        "Tough one, {name}. A {r} against {opp}. Be a goldfish about the scoreline and hang onto the lessons.",
        "{name}, a {r} isn't who you are. It's one night. Let's figure out what it's trying to teach us.",
        "A {r}, {name}. Rough patch. But you know what grows in rough patches? Wildflowers.",
        "{name}, a {r} stings. Good. It means you care. Now let's turn that sting into a plan.",
        "{name}, the {r} doesn't tell the whole story. It's one chapter, and you're still writing the book.",
    ],
}

GOOD = {  # framing that follows the fact
    "goal_threat": ["Never gets old, and I hope it never does.", "You put it where the keeper ain't. That's the whole trick.",
                    "The net said thank you, and so do I.", "That's the stuff they write songs about. Bad songs, but songs.",
                    "Scoring's a lot like karaoke: confidence is half of it."],
    "creativity": ["Making your teammates look good is the most generous thing in football.", "You were handing out chances like Halloween candy.",
                   "That's what I call neighborly football.", "Selfless as a church potluck, and twice as filling.",
                   "Chances like that are gifts. You were Santa out there."],
    "passing_accuracy": ["You kept that ball like it owed you money.", "Tidier than my mama's guest bathroom.",
                         "Every pass had a return address on it.", "Smooth as a fresh jar of peanut butter.",
                         "Possession is nine-tenths of the law, and you were the sheriff."],
    "involvement": ["The team ran through you like a highway through a small town.", "You were more involved than a church bake-sale committee.",
                    "Everybody wanted the ball at your feet, and for good reason.", "You were the busiest person on the pitch. I'm tired just watching.",
                    "You were the hub, and hubs keep wheels turning."],
    "tackle_timing": ["Clean as a whistle and twice as loud.", "You picked your moment like a ripe peach.",
                      "Patient, then pounced. That's textbook.", "You read it like a bedtime story.",
                      "Their attackers are gonna have nightmares about you, and I mean that kindly."],
    "defensive_work_rate": ["You did the dirty work nobody claps for. Well, I'm clapping.", "You chased like a golden retriever after a tennis ball, and I mean that as a compliment.",
                            "Defending's a mood, and your mood was 'not today'.", "You got stuck in like a boot in Missouri mud.",
                            "That's the kind of effort that wins tight matches."],
    "shot_volume": ["Can't score 'em if you don't take 'em.", "You kept knocking on that door like a Girl Scout with a quota.",
                    "The keeper's arms are probably still sore.", "Fortune favors the folks who shoot."],
    "shot_selection": ["Smart picks beat big swings.", "You made that keeper earn his paycheck.",
                       "On target is half the battle. You won that half.", "That's patience and aim, the dynamic duo."],
    "finishing": ["Clinical, like a dentist, but fun.", "When you hit it true, it went in. That's finishing.",
                  "Ice in the veins, honey in the heart.", "You made the hard part look like a Sunday stroll."],
    "shot_stopping": ["A brick wall with gloves on.", "You stopped the ones you should and a couple you shouldn't.",
                      "Their strikers are gonna need a hug.", "You were a whole fence, not just a post."],
    "busy_keeper": ["You kept us in it, plain and simple.", "Busiest person on the pitch, and you didn't blink.",
                    "The scoreline isn't on you. The saves were all you."],
    "clean_sheet": ["Nobody got by, and you were a big part of that.", "Zero goals against. My favorite number after biscuits.",
                    "Clean as fresh laundry on a line."],
    "leadership": ["Frame it, then hang it where your mama can see it.", "The game noticed, and so did I.",
                   "That's leadership you can't fake.", "Put that one on the fridge."],
}

WORK_LEADIN = ["Here's the fix:", "Tell you what:", "Coach's secret:", "Try this:", "Between you and me:",
               "Little homework:", "Next match:", "Here's a thought:"]

TEAMMATE_GOOD = [
    "You and {mate} linked up like peanut butter and jelly. Keep making sandwiches.",
    "That connection with {mate} is the real deal. Find 'em early and often.",
    "You & {mate} clicked. That partnership's got more legs than a centipede in a sack race.",
    "You found {mate} and {mate} found the net. That's chemistry you can't buy at the store.",
    "You and {mate} were on the same wavelength, like two radios tuned to the good station.",
    "{mate} scored and you helped make it happen. Keep feeding those runs.",
]
TEAMMATE_WORK = [
    "You and {mate} were both flagged for {issue}. Fix it as a pair: {fix}.",
    "{mate} had the same {issue} trouble. Team up on it: {fix}.",
    "You and {mate}, same {issue} homework. Partners: {fix}.",
    "Funny thing: {mate} wrestled with {issue} too. Two heads, one fix: {fix}.",
    "{issue} snagged you and {mate} both. Buddy system: {fix}.",
]
TOGETHER = {
    "forcing_passes": "give each other short options", "passing_accuracy": "give each other short options",
    "tackle_timing": "one presses, one covers", "defensive_work_rate": "pass runners off and track them into the box",
    "involvement": "make triangles, 1-2 touch", "shot_selection": "cut it back to each other",
    "finishing": "square it when the keeper commits", "progression": "make the run for each other",
}
FORM_UP = ["{x} above your usual rating. That's growth, and growth is the whole point.",
           "{x} better than your average. You're trending like a cat video.",
           "{x} over your norm. Keep stacking days like this.",
           "{x} above your average. Somebody's been doing their homework.",
           "{x} better than usual. That's a staircase, and you're climbing it."]
FORM_DOWN = ["{x} below your usual rating. One match doesn't define you. We go again.",
             "{x} under your average. Every player has those. The great ones answer back.",
             "{x} off your norm. Let it go like a bad haircut. It'll grow back.",
             "{x} below your average. Even the sun takes a cloudy day off.",
             "{x} under your usual. That's a dip, not a trend. Promise."]
DRIVER_GOOD = ["{what} added +{x} to your rating. Little things add up.",
               "{what} chipped in +{x}. Pennies make dollars.",
               "{what} was worth +{x} on its own. That's the quiet stuff that wins.",
               "{what} nudged you up +{x}. Every bit counts.",
               "{what}: +{x}. Like finding a twenty in last winter's coat.",
               "{what} bought you +{x}. Sprinkles on the sundae.",
               "{what} kicked in +{x}. Small hinges swing big doors."]
DRIVER_WORK = ["{what} cost you {x}. Tidy those and the number climbs.",
               "{what} took {x} off your rating. Easy points to win back.",
               "{what} shaved {x} off. Clean that up and you're flying.",
               "{what} pulled you down {x}. That's the low-hanging fruit.",
               "{what}: -{x}. Leaky faucet stuff. Small drips, big bill.",
               "{what} docked you {x}. Nothing a little focus can't fix.",
               "{what} cost {x}. Think of it as a pebble in your boot. Shake it out."]
BENCHMARK = ["{label}: {val}. Middle of the pack for a {role}; the top quarter hits {target}+. Room to climb.",
             "{label}: {val}. Decent, but top-quarter {role}s get to {target}+. That's the next rung.",
             "{label}: {val}. Solid ground. The best {role}s push it to {target}+."]
TEAM_W = ["Team won {score}. Being part of a winning group is a habit worth keeping.",
          "We beat {opp} {score}. Wins taste better when everybody chipped in.",
          "{score} win over {opp}. Enjoy it tonight, hunt the next one tomorrow.",
          "Three points off {opp}, {score}. Put 'em in the bank and let 'em earn interest.",
          "{score} over {opp}. Winning's like a good porch swing: easy to get used to.",
          "Beat {opp} {score}. That's a W you were part of, and W's are contagious."]
TEAM_D = ["Drew {score} with {opp}. A point earned is a point we didn't have.",
          "{score} with {opp}. A draw is a win that hasn't figured itself out yet.",
          "Split it {score} with {opp}. Half a pie is still pie.",
          "{score} with {opp}. Not the ending we wanted, but the story's still going."]
TEAM_L = ["Lost {score} to {opp}. Be a goldfish about the score, hang onto the lessons.",
          "{score} to {opp}. Chins up. Losses are tuition, and we're getting smarter.",
          "Fell {score} to {opp}. The scoreboard keeps score; I keep track of growth."]
BAND_LINE = ["{r} puts you in the {band} of {role}s league-wide.", "League-wide, a {r} is {band} territory for a {role}.",
             "Stack that {r} against every {role} out there: {band}."]
MINUTES = ["Played all {mins} minutes. Showing up is half of it, and you did.",
           "{mins} minutes on the pitch. Availability is an ability.",
           "You gave us {mins} minutes. That's a full tank, and I noticed."]
ONE_THING = ["Pick ONE of these to own next match. Just one. That's how habits stick.",
             "Don't fix it all at once. Choose one, nail it, then come back for the next.",
             "One thing at a time. Rome wasn't built in a day, and neither was a midfield."]
DRILL_LEAD = ["Coach's drill:", "This week's homework:", "Practice this:", "Training-ground special:"]
CLOSERS_GOOD = [
    "Keep that up and I'll have to start buying bigger biscuit tins.", "Proud of you. Now go drink some water.",
    "That's the stuff. Same time next match?", "You make this job too easy. Don't tell the gaffer.",
    "Believe. And maybe stretch.", "Go tell somebody you love about that one.",
]
CLOSERS_MIXED = [
    "Pick one thing from that list and own it next match. Just one.",
    "Growth isn't a straight line. It's more like a squiggle. We're squiggling in the right direction.",
    "I believe in you. More importantly, I need you to believe in you.",
    "Go easy on yourself tonight. Go hard at it tomorrow.",
    "Tomorrow's a fresh pitch. Let's go make some divots.",
    "Every great player has nights like this. Most of 'em just don't get a note from me.",
]


# ------------------------------------------------------------- the facts

def _good_fact(tag, s, c):
    g, kp = s["goals"], s.get("key_passes") or 0
    if tag == "goal_threat":
        base = {1: "A goal", 2: "A brace", 3: "A hat trick"}.get(g, f"{g} goals") + f" against {c.opp}"
        if c.goal_streak >= 2:
            base += f", your {_ordinal(c.goal_streak)} straight match scoring"
        elif c.season_high("goals") and g > 1:
            base += ", a new personal best"
        return base
    if tag == "creativity":
        base = _plural(kp, "key pass", "key passes") if kp else _plural(s["assists"], "assist")
        if kp and c.season_high("key_passes"):
            return base + ", the most you've made for us"
        return base + c.vs_usual("key_passes")
    if tag == "passing_accuracy":
        u = c.usual("pass_pct", pct=True)
        return f"{s['pass_pct']:.0f}% passing on {s['passes_att']} attempts" + (f", {u}" if u else "")
    if tag == "involvement":
        return f"{s['passes_att']} passes" + (", your busiest match yet" if c.season_high("passes_att") else c.vs_usual("passes_att"))
    if tag == "tackle_timing":
        return f"Won {s['tackles_made']} of {s['tackles_att']} tackles" + c.vs_usual("tackle_pct", pct=True)
    if tag == "defensive_work_rate":
        return f"{s['tackles_att']} tackles attempted" + c.vs_usual("tackles_att")
    if tag == "shot_volume":
        return _plural(s["shots"], "shot") + f" at {c.opp}'s goal"
    if tag == "shot_selection":
        return f"{s['shots_on']} of {s['shots']} shots on target"
    if tag == "finishing":
        return f"{_plural(g, 'goal')} from {s['shots_on']} on target"
    if tag in ("shot_stopping", "busy_keeper"):
        return f"{_plural(s['saves'], 'save')}" + (f" ({s['save_pct']:.0f}% stopped)" if s.get("save_pct") is not None else "")
    if tag == "clean_sheet":
        return f"Clean sheet against {c.opp}"
    if tag == "leadership":
        return "Man of the Match" + (f", your {_ordinal(c.motm_count)} for us" if c.motm_count > 1 else "")
    return ""


def _work_fact(tag, s, c, gap):
    if tag in ("forcing_passes", "passing_accuracy"):
        u = c.usual("pass_pct", pct=True)
        return f"{s['pass_pct']:.0f}% passing ({s['passes_made']} of {s['passes_att']}{', ' + u if u else ''})"
    if tag == "involvement":
        return f"Only {s['passes_att']} passes" + c.vs_usual("passes_att")
    if tag == "progression":
        return f"No key passes from {s['passes_att']} passes"
    if tag == "tackle_timing":
        return f"Won {s['tackles_made']} of {s['tackles_att']} tackles" + c.vs_usual("tackle_pct", pct=True)
    if tag == "defensive_work_rate":
        return ("No tackles attempted" if not s["tackles_att"] else f"Only {_plural(s['tackles_att'], 'tackle')} attempted") + c.vs_usual("tackles_att")
    if tag == "shot_volume":
        return "No shots" if not s["shots"] else f"Only {_plural(s['shots'], 'shot')}"
    if tag == "shot_selection":
        return f"{s['shots_on']} of {s['shots']} shots on target"
    if tag == "finishing":
        return f"{_plural(s['goals'], 'goal')} from {s['shots_on']} on target"
    if tag == "shot_stopping":
        return f"{s['save_pct']:.0f}% of shots stopped"
    if tag == "positioning":
        return f"Rating came in {gap} below what your on-ball stats earned"
    if tag == "discipline":
        return "Red card"
    if tag == "idle":
        return f"Idle for {s.get('idle_share', 0) * 100:.0f}% of the match"
    return ""


SINGULAR = {"Goals": "goal", "Assists": "assist", "Key passes": "key pass", "Shots on target": "shot on target",
            "Shots off target": "shot off target", "Completed passes": "completed pass", "Misplaced passes": "misplaced pass",
            "Tackles won": "tackle won", "Missed tackles": "missed tackle", "Saves": "save", "Goals conceded": "goal conceded"}
TAG_KEYS = {
    "goal_threat": {"goals"}, "creativity": {"key_passes", "assists"}, "finishing": {"goals", "shots_on"},
    "passing_accuracy": {"passes_made", "passes_missed", "pass_pct"}, "forcing_passes": {"passes_made", "passes_missed", "pass_pct"},
    "involvement": {"passes_made", "passes_missed", "passes_att"}, "progression": {"key_passes"},
    "tackle_timing": {"tackles_made", "missed_tackles", "tackle_pct"}, "defensive_work_rate": {"tackles_made", "missed_tackles", "tackles_att"},
    "shot_volume": {"shots_on", "shots_off", "shots"}, "shot_selection": {"shots_on", "shots_off", "shot_accuracy"},
    "shot_stopping": {"saves", "conceded", "save_pct"}, "busy_keeper": {"saves", "conceded"},
}


def _driver_what(d):
    n = d["count"]
    noun = SINGULAR.get(d["label"], d["label"].lower()) if n == 1 else d["label"].lower()
    return f"{n} {noun}".capitalize()


# --------------------------------------------------------------- the note

def build(m, p, history, avoid):
    """Returns (title, body, used_phrase_ids) for one player's note."""
    s = p["stats"]
    c = Context(m, p, history)
    pick = Picker(f"{m['id']}|{p['name']}|lasso", avoid)
    mates = [q for q in m["players"] if q["name"] != p["name"]]
    role = pb.LABELS[p["pos"]].lower()
    gap = next((f"{abs(d['impact']):.1f}" for d in p["impact"]["drivers"] if d["key"] == "other"), "0")
    good, work, used = [], [], set()  # (priority, text)

    for x in p["strengths"]:
        fact = _good_fact(x["tag"], s, c)
        if fact and x["tag"] in GOOD:
            good.append((10, f"{fact}. {pick('g_' + x['tag'], GOOD[x['tag']])}"))
            used |= TAG_KEYS.get(x["tag"], set())
    weak = [w for w in p["weaknesses"] if _work_fact(w["tag"], s, c, gap)]
    drill_tag = weak[0]["tag"] if weak else None
    for w in weak:
        tips = pb.tips_for(w["tag"], p["pos"], limit=12)
        tip = pick("t_" + w["tag"], tips) if tips else ""
        lead = pick("lead", WORK_LEADIN) + " " if pick.rng.random() < 0.5 else ""
        work.append((10, f"{_work_fact(w['tag'], s, c, gap)}. {lead}{tip}".strip()))
        used |= TAG_KEYS.get(w["tag"], set())

    scorer = max(mates, key=lambda q: q["stats"]["goals"], default=None)
    if scorer and scorer["stats"]["goals"] and ((s.get("key_passes") or 0) + s["assists"]):
        good.append((9, pick("mate_g", TEAMMATE_GOOD).format(mate=scorer["name"])))
    for w in weak:
        mate = next((q for q in mates if any(x["tag"] == w["tag"] for x in q["weaknesses"])), None)
        if mate and w["tag"] in TOGETHER:
            work.append((8, pick("mate_w", TEAMMATE_WORK).format(mate=mate["name"], issue=pb.TAG_TITLES[w["tag"]].lower(), fix=TOGETHER[w["tag"]])))
            break

    va = p.get("vs_average")
    if va is not None and va >= 0.3:
        good.append((7, pick("form_up", FORM_UP).format(x=f"{va:.1f}")))
    elif va is not None and va <= -0.3:
        work.append((7, pick("form_down", FORM_DOWN).format(x=f"{abs(va):.1f}")))

    drivers = [d for d in p["impact"]["drivers"] if d["key"] not in ("other", "result_val") and d.get("count") and d["key"] not in used]
    for d in drivers:
        if d["impact"] > 0:
            good.append((5, pick("drv_g", DRIVER_GOOD).format(what=_driver_what(d), x=f"{d['impact']:.1f}")))
    for d in reversed(drivers):
        if d["impact"] < 0:
            work.append((5, pick("drv_w", DRIVER_WORK).format(what=_driver_what(d), x=f"{abs(d['impact']):.1f}")))

    for metric, (top, poor, gate) in pb.BENCHMARKS[p["pos"]].items():
        val = s.get(metric)
        if val is None or metric in used or (gate and (s.get(gate[0]) or 0) < gate[1]) or val >= top or (poor is not None and val <= poor):
            continue
        pct = metric in pb.PERCENT_METRICS
        work.append((4, pick("bench", BENCHMARK).format(label=pb.METRIC_LABELS[metric], role=role,
                                                         val=f"{val:.0f}%" if pct else f"{val:.0f}", target=f"{top}%" if pct else top)))

    if p["band"].startswith("Top"):
        good.append((3, pick("band", BAND_LINE).format(r=f"{s['rating']:.1f}", band=p["band"].lower(), role=role)))
    team = {"W": ("team_w", TEAM_W, good), "D": ("team_d", TEAM_D, good), "L": ("team_l", TEAM_L, work)}[m["result"]]
    team[2].append((2, pick(team[0], team[1]).format(score=c.score, opp=c.opp)))
    good.append((1, pick("mins", MINUTES).format(mins=s["minutes"])))
    work.append((1, pick("one", ONE_THING)))

    # 6-10 bullets: up to 5 per side, top up the thin side, trim fillers
    good.sort(key=lambda x: -x[0])
    work.sort(key=lambda x: -x[0])
    g, w = good[:5], work[:5]
    if len(g) + len(w) < 6:
        g, w = good[:max(5, 6 - len(w))], work[:max(5, 6 - len(g))]

    def weakest():
        last = lambda side: side[-1][0] if side else 99
        return g if last(g) <= last(w) else w

    while len(g) + len(w) > 10:
        weakest().pop()
    while len(g) + len(w) > 6 and min((x[-1][0] for x in (g, w) if x), default=99) <= 1:
        weakest().pop()

    opener = pick(f"open_{p['band']}", OPENERS[p["band"]]).format(
        name=p["name"], r=f"{s['rating']:.1f}", pos=role, opp=c.opp)
    lines = [opener, "", "DID WELL"] + [f"+ {t}" for _, t in g] + ["", "WORK ON"] + [f"- {t}" for _, t in w]
    if drill_tag:
        bullet_text = "\n".join(t for _, t in w)
        drills = [t for t in pb.tips_for(drill_tag, p["pos"], limit=12) if t not in bullet_text]
        if drills:
            lines += ["", f"{pick('drill', DRILL_LEAD)} {pick('t_' + drill_tag, drills)}"]
    closer = pick("close_good", CLOSERS_GOOD) if (not p["weaknesses"] or p["band"].startswith("Top")) else pick("close_mixed", CLOSERS_MIXED)
    lines += ["", f"{closer} - {COACH}"]
    band = f"{p['band'].lower()} {pb.LABELS[p['pos']][:3].upper()}"
    title = f"{m['result']} {c.score} vs {c.opp} | You: {s['rating']:.1f} ({band})"
    body = re.sub(r"\b([Aa]) (?=(8|11|18)(\.\d)?\b)", lambda mm: mm.group(1) + "n ", "\n".join(lines))
    return title, body, pick.used


def annotate(matches):
    """Attach p['push'] = {'title', 'body'} to every player in every match,
    walking matches in order so phrasing doesn't repeat for a player."""
    history, recent = {}, {}
    for m in sorted(matches, key=lambda x: x["ts"]):
        match_used = set()
        for p in m["players"]:
            hist = history.setdefault(p["name"], [])
            avoid = set().union(*recent.get(p["name"], [])) | match_used
            title, body, used = build(m, p, hist, avoid)
            p["push"] = {"title": title, "body": body}
            match_used |= used
            recent.setdefault(p["name"], []).append(used)
            recent[p["name"]] = recent[p["name"]][-RECENT_NOTES:]
            hist.append(p)
