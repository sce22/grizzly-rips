"""The coach: turns the analysis into a Ted Lasso-style voice - warm, folksy,
relentlessly positive, but always grounded in the numbers.

Adds, without changing the analysis itself:
  match["talk"]            team talk: opener, 3 things we did well, 3 to work on, closer
  player["coach"]          personal note: opener + closer
  strength/weakness["coach"]  one coach line per item
  profile["coach"]         season-long intro and a line per theme

Wording is picked deterministically per match/player, so rebuilding the site
never reshuffles what was already said.
"""
import random
import zlib

from . import playbook as pb

COACH_NAME = "Coach Lasso"


def _rng(*keys):
    return random.Random(zlib.crc32("|".join(map(str, keys)).encode()))


def _pick(rng, options, **kw):
    return rng.choice(options).format(**kw)


def _plural(n, word, plural=None):
    return f"{n} {word if n == 1 else (plural or word + 's')}"


# ------------------------------------------------------------ player lines

OPENERS = {
    "Top 10%": [
        "{name}, that was a {r}. Top-ten-percent stuff for a {pos} anywhere in this league. I'd frame it if I knew how.",
        "Well, {name}, a {r} is the kind of night you tell your grandkids about. Top 10% of {pos}s, and you earned every bit.",
    ],
    "Top 25%": [
        "Now that's what I'm talking about, {name}. A {r} puts you in the top quarter of {pos}s.",
        "{name}, a {r}. That's top-25% {pos} work, and it didn't happen by accident.",
    ],
    "Above average": [
        "Solid shift, {name}. A {r} clears the bar for a {pos}, and solid is the soil good things grow in.",
        "{name}, a {r} is above average for a {pos}. A good day at the office, and we can build on it.",
    ],
    "Below average": [
        "{name}, a {r} is a touch under par for a {pos}. That's alright. Even the best tomatoes have a bruise or two.",
        "A {r} today, {name}. Little below the line for a {pos}, but there's good stuff in here to work with.",
    ],
    "Bottom 25%": [
        "Tough one, {name}. A {r}. Be a goldfish about the scoreline and hang onto the lessons.",
        "{name}, a {r} isn't who you are. It's one night. Let's figure out what it's trying to teach us.",
    ],
}

CLOSERS_GOOD = [
    "Keep that up and I'll have to start buying bigger biscuit tins.",
    "Proud of you. Now go drink some water.",
    "That's the stuff. Same time next match?",
]
CLOSERS_MIXED = [
    "Pick one thing from that list and own it next match. Just one.",
    "Growth isn't a straight line. It's more like a squiggle. We're squiggling in the right direction.",
    "I believe in you. More importantly, I need you to believe in you.",
]

STRENGTH_LINES = {
    "passing_accuracy": "Kept the ball like it owed you money.",
    "involvement": "You were everywhere. Teammates looked for you because they trust you.",
    "tackle_timing": "When you went in, you came out with the ball. That's timing.",
    "defensive_work_rate": "You put your foot in and did the dirty work. That doesn't make highlight reels, but it wins matches.",
    "shot_volume": "You kept finding ways to get shots off. Can't score 'em if you don't take 'em.",
    "shot_selection": "Picked your moments and hit the target. Good decisions before good finishes.",
    "finishing": "Clinical. When you hit the target, the keeper was just a spectator.",
    "shot_stopping": "Stood tall between the sticks. You stopped the ones you should and then some.",
    "goal_threat": "Found the back of the net. Never gets old, does it?",
    "creativity": "Made chances for your teammates. Unselfish football is the best kind.",
    "clean_sheet": "Clean sheet. Nobody got past us on your watch.",
    "leadership": "Man of the Match. The game noticed, and so did I.",
    "busy_keeper": "Kept us in it while the shots kept coming. The scoreline isn't all on you.",
}

WEAKNESS_LINES = {
    "passing_accuracy": "The passing got a little loose out there.",
    "forcing_passes": "We tried to force a few too many. Not every pass has to be a love letter.",
    "involvement": "We didn't see enough of you on the ball. I want you in the thick of it.",
    "progression": "Plenty of the ball, but not much going forward. Let's hurt 'em with it.",
    "tackle_timing": "Diving in a bit too eager. Patience in the tackle.",
    "defensive_work_rate": "Need more bite without the ball. Defending is everybody's job.",
    "shot_volume": "Didn't get many shots off. Let's get you in better spots.",
    "shot_selection": "A few too many shots went wide or over. Better looks, better results.",
    "finishing": "You're hitting the target, so now let's beat the keeper.",
    "shot_stopping": "A couple got by that we'd want back.",
    "positioning": "The stats say you did more than the rating gives you credit for. That gap is off-ball positioning.",
    "discipline": "The red card hurt us. Let's keep 11 on the pitch.",
    "idle": "Looked like we lost you for a stretch. Connection trouble?",
}


def _player(m, p):
    rng = _rng(m["id"], p["name"])
    s = p["stats"]
    p["coach"] = {
        "name": COACH_NAME,
        "opener": _pick(rng, OPENERS[p["band"]], name=p["name"], r=f"{s['rating']:.1f}", pos=pb.LABELS[p["pos"]].lower()),
        "closer": rng.choice(CLOSERS_GOOD if not p["weaknesses"] or p["band"].startswith("Top") else CLOSERS_MIXED),
    }
    for x in p["strengths"]:
        x["coach"] = STRENGTH_LINES.get(x["tag"], x.get("note", ""))
    for w in p["weaknesses"]:
        w["coach"] = WEAKNESS_LINES.get(w["tag"], "")


# ------------------------------------------------------------- team talk

RESULT_OPENERS = {
    "W": [
        "Three points, y'all. {gf}-{ga} over {opp}.",
        "That's a W. {gf}-{ga} against {opp}, and I'm smiling so big it hurts.",
    ],
    "D": [
        "{gf}-{ga} with {opp}. A draw is a win that hasn't figured itself out yet.",
        "We shared the points with {opp}, {gf}-{ga}. Not a loss, and there's plenty to learn from.",
    ],
    "L": [
        "{ga}-{gf} to {opp}. Be a goldfish about the result, keep the lessons.",
        "Lost {gf}-{ga} to {opp}. Chins up. One match doesn't define a team.",
    ],
}
TEXT_SIGNOFFS = ["Believe.", "Proud of y'all.", "Onward.", "Biscuits on me."]


def _team_candidates(m):
    t, ps = m["team"], m["players"]
    gf, ga = m["gf"], m["ga"]
    good, work = [], []
    shots, on = t.get("shots", 0), t.get("shots_on") or 0
    acc = t.get("shot_accuracy")
    pp, tp = t.get("pass_pct"), t.get("tackle_pct")
    kp = t.get("key_passes") or 0

    # --- did well
    if ga == 0:
        good.append((3.0, "Clean sheet", f"Clean sheet. Nobody got past us - that's eleven people defending, not just the back line."))
    if gf >= 3:
        good.append((2 + (gf - 3) * 0.5, "Scoring", f"Put away {gf} goals from {_plural(shots, 'shot')}. When we get bodies in the box, good things happen."))
    if acc is not None and shots >= 4 and acc >= 65:
        good.append((1.5 + (acc - 65) / 20, "Shot accuracy", f"{on} of {shots} shots on target ({acc:.0f}%). We picked our moments instead of swinging at everything."))
    if pp is not None and pp >= 82:
        good.append((1.5 + (pp - 82) / 5, "Passing", f"Passing at {pp:.0f}%. We kept that ball like it owed us money."))
    if tp is not None and t.get("tackles_att", 0) >= 6 and tp >= 45:
        good.append((1.5 + (tp - 45) / 15, "Winning duels", f"Won {t['tackles_made']} of {t['tackles_att']} tackles ({tp:.0f}%). First to the ball, and we meant it."))
    if kp >= 4:
        good.append((1.4 + (kp - 4) * 0.2, "Creating chances", f"{kp} key passes. We made chances for each other - that's a team that likes each other."))
    star = ps[0] if ps else None
    if star and star["band"] in ("Top 10%", "Top 25%"):
        good.append((2.6 if star["band"] == "Top 10%" else 2.0, f"{star['name']}", _star_line(star)))

    # --- work on
    if ga >= 3:
        work.append((2 + (ga - 3) * 0.5, "Defending as a unit", f"Conceded {ga}. When we lose it, everybody gets compact and goal-side - shape before chase."))
    if pp is not None and pp < pb.PASS_BREAK_EVEN:
        work.append((2 + (pb.PASS_BREAK_EVEN - pp) / 5, "Passing", f"Passing at {pp:.0f}%, under the ~72% line where extra passes start hurting us. Simple and on the ground."))
    if acc is not None and shots >= 4 and acc < 45:
        work.append((1.8 + (45 - acc) / 20, "Shot selection", f"Only {on} of {shots} shots on target. Work it into the box, set your feet, hit the frame."))
    if tp is not None and t.get("tackles_att", 0) >= 6 and tp < 30:
        work.append((1.8 + (30 - tp) / 15, "Tackling", (f"Won just {t['tackles_made']} of {t['tackles_att']} tackles." if t['tackles_made'] else f"Didn't win any of our {t['tackles_att']} tackles.") + " Stay on your feet, jockey, pounce on the heavy touch."))
    if shots <= 3:
        work.append((1.6, "Getting shots off", f"Only {_plural(shots, 'shot')} all match. More runners in the box means more looks at goal."))
    if kp <= 1 and t.get("passes_att", 0) >= 40:
        work.append((1.4, "Playing forward", f"{_plural(kp, 'key pass', 'key passes')} from {t['passes_att']} passes. We had the ball but didn't hurt 'em with it - look forward first."))
    for p in ps:
        if p["stats"]["red_cards"]:
            work.append((3.0, "Discipline", f"{p['name']} saw red. We can't play a man down - stay on your feet as the last line."))

    # Individual patterns not already covered at team level
    covered = {"Passing": {"passing_accuracy", "forcing_passes"}, "Shot selection": {"shot_selection"},
               "Tackling": {"tackle_timing"}, "Getting shots off": {"shot_volume"}, "Discipline": {"discipline"},
               "Playing forward": {"progression"}}
    skip = set().union(*(covered.get(w[1], set()) for w in work))
    by_tag = {}
    for p in ps:
        for w in p["weaknesses"]:
            if w["tag"] not in skip:
                by_tag.setdefault(w["tag"], []).append(p["name"])
    for tag, names in by_tag.items():
        tip = pb.tips_for(tag, "_", limit=1)
        work.append((0.8 + 0.4 * len(names), pb.TAG_TITLES[tag],
                     f"{' & '.join(names)}: {WEAKNESS_LINES.get(tag, pb.TAG_TITLES[tag])}", tip[0] if tip else None))
    s_tags = {}
    for p in ps[1:] if star and star["band"] in ("Top 10%", "Top 25%") else ps:
        for x in p["strengths"]:
            s_tags.setdefault(x["tag"], []).append(p["name"])
    for tag, names in s_tags.items():
        good.append((0.6 + 0.4 * len(names), pb.TAG_TITLES[tag], f"{' & '.join(names)}: {STRENGTH_LINES.get(tag, pb.TAG_TITLES[tag])}"))
    # Fallbacks: each player's biggest rating swing, so there are always three of each
    for p in ps:
        drivers = [d for d in p["impact"]["drivers"] if d["key"] not in ("other", "result_val")]
        if drivers and drivers[0]["impact"] > 0:
            d = drivers[0]
            good.append((0.3, f"{p['name']} {d['label']}", f"{p['name']}: {_count(d)} added about +{d['impact']:.1f} to their rating."))
        if drivers and drivers[-1]["impact"] < 0:
            d = drivers[-1]
            work.append((0.3, f"{p['name']} {d['label']}", f"{p['name']}: {_count(d)} cost about {d['impact']:.1f} rating.", None))
    return good, work


def _count(d):
    if d["key"] == "clean_sheet":
        return "the clean sheet"
    return f"{d['count']} {d['label'].lower()}"


def _star_line(p):
    s = p["stats"]
    bits = []
    if s["goals"]:
        bits.append(_plural(s["goals"], "goal"))
    if s["assists"]:
        bits.append(_plural(s["assists"], "assist"))
    if s.get("key_passes"):
        bits.append(_plural(s["key_passes"], "key pass", "key passes"))
    if s["tackles_made"] >= 3:
        bits.append(f"{s['tackles_made']} tackles won")
    if s.get("pass_pct") and s["pass_pct"] >= 80 and len(bits) < 3:
        bits.append(f"{s['pass_pct']:.0f}% passing")
    if p["pos"] == "goalkeeper" and s["saves"]:
        bits.append(_plural(s["saves"], "save"))
    r = f"{s['rating']:.1f}"
    article = "an" if r.startswith(("8", "11", "18")) else "a"
    return f"{p['name']} led the way with {article} {r}" + (f": {', '.join(bits[:3])}." if bits else ".")


TEAM_TIP_TAGS = {"Defending as a unit": "defensive_work_rate", "Passing": "passing_accuracy", "Shot selection": "shot_selection",
                 "Tackling": "tackle_timing", "Getting shots off": "shot_volume", "Playing forward": "progression",
                 "Discipline": "discipline"}


def _top3(items, with_tips=False):
    seen, out = set(), []
    for score, title, line, *rest in sorted(items, key=lambda x: -x[0]):
        if title in seen:
            continue
        seen.add(title)
        item = {"title": title, "line": line}
        if with_tips:
            tip = rest[0] if rest and rest[0] else next(iter(pb.tips_for(TEAM_TIP_TAGS.get(title, ""), "_", 1)), None)
            if tip:
                item["tip"] = tip
        out.append(item)
        if len(out) == 3:
            break
    return out


def _talk(m, club):
    rng = _rng(m["id"], "talk")
    good, work = _team_candidates(m)
    well, improve = _top3(good), _top3(work, with_tips=True)
    if not improve:
        improve = [{"title": "Keep it rolling", "line": "Honestly? Not much. Bottle whatever that was and bring it next match."}]
    return {
        "opener": _pick(rng, RESULT_OPENERS[m["result"]], gf=m["gf"], ga=m["ga"], opp=m["opponent"]["name"]),
        "well": well,
        "work_on": improve,
        "signoff": rng.choice(TEXT_SIGNOFFS),
        "coach": COACH_NAME,
    }


# ---------------------------------------------------------------- profiles

DIRECTION = {
    "improving": "and it's getting better - keep at it.",
    "worsening": "and it's crept up lately, so let's make it our focus.",
    "steady": "and it's been pretty steady.",
}


def _profile(p):
    rng = _rng("profile", p["name"], p["matches"])
    c = {"intro": _pick(rng, [
        "{name}, I've watched all {n} of your matches. Here's what the tape and the numbers are telling me.",
        "Alright {name}, {n} matches in. Let's talk about the patterns, the good and the growing.",
    ], name=p["name"], n=p["matches"])}
    if p.get("themes"):
        for t in p["themes"]["improve"]:
            t["coach"] = f"{WEAKNESS_LINES.get(t['tag'], t['title'])} It's shown up in {t['rate']}% of your matches, {DIRECTION[t['direction']]}"
        for s in p["themes"]["strengths"]:
            s["coach"] = STRENGTH_LINES.get(s["tag"], s.get("note", ""))
    p["coach"] = c


def annotate(matches, players, config):
    club = config["club"]["name"]
    for m in matches:
        for p in m["players"]:
            _player(m, p)
        m["talk"] = _talk(m, club)
    for p in players.values():
        _profile(p)


# ------------------------------------------------------------ player texts


def _fmt_vals(s):
    return {
        "goals": s["goals"], "goals_txt": _plural(s["goals"], "goal"),
        "kp": s.get("key_passes") or 0,
        "kp_txt": _plural(s.get("key_passes") or s["assists"], *(("key pass", "key passes") if s.get("key_passes") else ("assist",))),
        "pp": f"{s['pass_pct']:.0f}" if s.get("pass_pct") is not None else "-", "pa": s["passes_att"],
        "tm": s["tackles_made"], "ta": s["tackles_att"], "ta_txt": _plural(s["tackles_att"], "tackle") + (" tried" if s["tackles_att"] else ""),
        "shots": s["shots"], "shots_txt": _plural(s["shots"], "shot"), "on": s.get("shots_on") or 0,
        "saves": s["saves"], "svp": f"{s['save_pct']:.0f}" if s.get("save_pct") is not None else "-",
        "idle": f"{s.get('idle_share', 0) * 100:.0f}",
    }


# ------------------------------------------------------- one-message text
# Email-to-text gateways deliver one message of ~125 usable characters and drop
# follow-ups, so the text is a single short paragraph that is trimmed to fit.

GOOD_SHORT = {
    "goal_threat": lambda v: "the goal" if v["goals"] == 1 else f"{v['goals']} goals",
    "creativity": lambda v: f"{v['kp']} key pass{'es' * (v['kp'] != 1)}" if v["kp"] else "the assist",
    "passing_accuracy": lambda v: f"{v['pp']}% passing",
    "involvement": lambda v: "being on the ball",
    "tackle_timing": lambda v: f"winning {v['tm']}/{v['ta']} tackles",
    "defensive_work_rate": lambda v: "the bite",
    "shot_volume": lambda v: f"{v['shots']} shots",
    "shot_selection": lambda v: f"{v['on']}/{v['shots']} on target",
    "finishing": lambda v: "the finishing",
    "shot_stopping": lambda v: f"{v['saves']} saves",
    "busy_keeper": lambda v: f"{v['saves']} saves",
    "clean_sheet": lambda v: "the clean sheet",
    "leadership": lambda v: "MOTM",
}
WORK_SHORT = {
    "forcing_passes": lambda v: f"{v['pp']}% passing",
    "passing_accuracy": lambda v: f"{v['pp']}% passing",
    "involvement": lambda v: f"only {v['pa']} passes",
    "progression": lambda v: "no key passes",
    "tackle_timing": lambda v: f"{v['tm']}/{v['ta']} tackles",
    "defensive_work_rate": lambda v: f"only {v['ta']} tackle{'s' * (v['ta'] != 1)}" if v["ta"] else "no tackles",
    "shot_volume": lambda v: f"{v['shots']} shot{'s' * (v['shots'] != 1)}",
    "shot_selection": lambda v: f"{v['on']}/{v['shots']} on target",
    "finishing": lambda v: f"{v['goals']} of {v['on']} on target scored",
    "shot_stopping": lambda v: f"{v['svp']}% saved",
    "positioning": lambda v: "positioning",
    "discipline": lambda v: "the red",
    "idle": lambda v: "idle time",
}
TIP_SHORT = {
    "forcing_passes": "Keep it simple", "passing_accuracy": "Scan, then pass", "involvement": "Show for it",
    "progression": "Look forward", "tackle_timing": "Jockey, then pounce", "defensive_work_rate": "Get stuck in",
    "shot_volume": "Get in the box", "shot_selection": "Set your feet", "finishing": "Aim for corners",
    "shot_stopping": "Hold your spot", "positioning": "Hold your shape", "discipline": "Stay on your feet",
    "idle": "Check your connection",
}
OPENER_SHORT = {"Top 10%": "What a night!", "Top 25%": "Heck yeah!", "Above average": "Solid!",
                "Below average": "Good effort.", "Bottom 25%": "Be a goldfish."}


def text_paragraph(m, p, budget):
    """One Ted-style sentence pair about this player that fits in `budget` chars."""
    s = p["stats"]
    v = _fmt_vals(s)
    good = [GOOD_SHORT[x["tag"]](v) for x in p["strengths"] if x["tag"] in GOOD_SHORT]
    mates = [q for q in m["players"] if q["name"] != p["name"]]
    scorer = max(mates, key=lambda q: q["stats"]["goals"], default=None)
    if scorer and scorer["stats"]["goals"] and ((s.get("key_passes") or 0) + s["assists"]):
        good.insert(1, f"linking w/ {scorer['name']}")
    weak = [w for w in p["weaknesses"] if w["tag"] in WORK_SHORT]
    work = [WORK_SHORT[w["tag"]](v) for w in weak]
    tip = TIP_SHORT.get(weak[0]["tag"]) if weak else None
    head = f"{m['result']} {m['gf']}-{m['ga']}, {s['rating']:.1f}."
    opener = OPENER_SHORT[p["band"]]

    def build(n_good, n_work, with_opener, with_tip):
        g, w = good[:n_good], work[:n_work]
        parts = [head]
        if with_opener:
            parts.append(opener)
        if g and w:
            parts.append(f"Loved {' & '.join(g)}, but {' & '.join(w)}.")
        elif g:
            parts.append(f"Loved {' & '.join(g)}.")
        elif w:
            parts.append(f"{' & '.join(w).capitalize()} hurt.")
        sign = f"- {COACH_NAME}"
        parts.append(f"{tip}! {sign}" if (with_tip and tip) else (f"Bottle it! {sign}" if with_tip and not w else sign))
        return " ".join(parts)

    for args in [(2, 2, True, True), (1, 2, True, True), (2, 1, True, True), (1, 1, True, True),
                 (1, 1, False, True), (1, 1, False, False), (1, 0, False, False), (0, 1, False, False), (0, 0, False, False)]:
        text = build(*args)
        if len(text) <= budget:
            return text
    return build(0, 0, False, False)[:budget]



# ------------------------------------------------------- push notifications
# Personal notes for each player: 6-10 bullets, every one tied to a number.

def _g(v):
    return "The goal" if v["goals"] == 1 else f"{v['goals']} goals"


def _kp(v):
    return _plural(v["kp"], "key pass", "key passes") if v["kp"] else _plural(v["assists"], "assist")


GOOD_LINES = {
    "goal_threat": ["{G}. Never gets old, and I hope it never does.",
                    "{G}. You put it where the keeper ain't. That's the whole trick."],
    "creativity": ["{KP}. Making your teammates look good is the most generous thing in football.",
                   "{KP}. You were handing out chances like Halloween candy."],
    "passing_accuracy": ["{pp}% passing. You kept that ball like it owed you money.",
                         "{pp}% passing. Tidier than my mama's guest bathroom."],
    "involvement": ["{pa} passes. The team ran through you like a highway through a small town.",
                    "{pa} passes. You were more involved than a church bake-sale committee."],
    "tackle_timing": ["Won {tm} of {ta} tackles. Clean as a whistle and twice as loud.",
                      "Won {tm} of {ta} tackles. You picked your moment like a ripe peach."],
    "defensive_work_rate": ["{ta} tackles attempted. You did the dirty work nobody claps for. Well, I'm clapping.",
                            "{ta} tackles attempted. You chased like a golden retriever after a tennis ball. I mean that as a compliment."],
    "shot_volume": ["{shots} shots. Can't score 'em if you don't take 'em.",
                    "{shots} shots. You kept knocking on that door like a Girl Scout with a quota."],
    "shot_selection": ["{on} of {shots} shots on target. Smart picks beat big swings.",
                       "{on} of {shots} shots on target. You made that keeper earn his paycheck."],
    "finishing": ["{goals} from {on} shots on target. Clinical, like a dentist, but fun.",
                  "{goals} from {on} shots on target. When you hit it true, it went in."],
    "shot_stopping": ["{saves} saves. A brick wall with gloves on.",
                      "{saves} saves. You stopped the ones you should and a couple you shouldn't."],
    "busy_keeper": ["{saves} saves while they peppered you. You kept us in it, plain and simple.",
                    "{saves} saves. Busiest person on the pitch, and you didn't blink."],
    "clean_sheet": ["Clean sheet. Nobody got by, and you were a big part of that.",
                    "Clean sheet. Zero goals against. My favorite number after biscuits."],
    "leadership": ["Man of the Match. Frame it, then hang it where your mama can see it.",
                   "Man of the Match. The game noticed, and so did I."],
}
WORK_LINES = {
    "forcing_passes": ["{pp}% passing. Under ~72%, every extra pass costs rating. Simple and on the ground, partner.",
                       "{pp}% passing. Not every ball needs to be a love letter. Short and simple wins."],
    "passing_accuracy": ["{pp}% passing. Check your shoulder before it arrives so you already know the answer.",
                         "{pp}% passing. Open your hips, scan, then play the easy one."],
    "involvement": ["Only {pa} passes. Get in the passing lane and ask for it. Can't help us from the shadows.",
                    "Only {pa} passes. Show for the ball at an angle, not flat behind your marker."],
    "progression": ["No key passes from {pa} passes. Look forward first. Sideways is for crabs.",
                    "No key passes from {pa} passes. We had the ball; now let's hurt 'em with it."],
    "tackle_timing": ["Won {tm} of {ta} tackles. Jockey, stay goal-side, pounce on the heavy touch.",
                      "Won {tm} of {ta} tackles. Patience. Let 'em make the mistake, then pounce."],
    "defensive_work_rate": ["{TA}. A won tackle is worth about 0.2 rating. Get stuck in.",
                            "{TA}. Defending is everybody's job, like doing the dishes."],
    "shot_volume": ["{SH}. Get in the box: near post, far post, every cross.",
                    "{SH}. Time your run off the last defender and the chances will come."],
    "shot_selection": ["{on} of {shots} shots on target. Set your feet and shoot from central spots.",
                       "{on} of {shots} shots on target. If the angle's tight, cut it back to a friend."],
    "finishing": ["{goals} from {on} shots on target. Keepers love the middle. Go corners.",
                  "{goals} from {on} shots on target. Finesse to the far post, low and hard one-on-one."],
    "shot_stopping": ["{svp}% of shots stopped. Set your feet and hold your spot as they shoot.",
                      "{svp}% of shots stopped. Rushing out early opens the near post."],
    "positioning": ["Your rating came in {gap} below what your stats earned. That gap is off-ball shape. Hold the line.",
                    "Your rating came in {gap} below what your stats earned. Goal-side and central first, ball second."],
    "discipline": ["Red card. Stay on your feet; we need all eleven of us.",
                   "Red card. No slides from behind. Sprint the recovery run instead."],
    "idle": ["Idle {idle}% of the match. Check the connection, partner. We need you out there.",
             "Idle {idle}% of the match. A team's only as good as who's on the pitch."],
}
TOGETHER = {
    "forcing_passes": "give each other short options", "passing_accuracy": "give each other short options",
    "tackle_timing": "one presses, one covers", "defensive_work_rate": "pass runners off and track them into the box",
    "involvement": "make triangles, 1-2 touch", "shot_selection": "cut it back to each other",
    "finishing": "square it when the keeper commits", "progression": "make the run for each other",
}
SINGULAR = {"Goals": "goal", "Assists": "assist", "Key passes": "key pass", "Shots on target": "shot on target",
            "Shots off target": "shot off target", "Completed passes": "completed pass", "Misplaced passes": "misplaced pass",
            "Tackles won": "tackle won", "Missed tackles": "missed tackle", "Saves": "save", "Goals conceded": "goal conceded"}
# stats each tag already talks about, so filler bullets don't repeat them
TAG_KEYS = {
    "goal_threat": {"goals"}, "creativity": {"key_passes", "assists"}, "finishing": {"goals", "shots_on"},
    "passing_accuracy": {"passes_made", "passes_missed", "pass_pct"}, "forcing_passes": {"passes_made", "passes_missed", "pass_pct"},
    "involvement": {"passes_made", "passes_missed", "passes_att"}, "progression": {"key_passes"},
    "tackle_timing": {"tackles_made", "missed_tackles", "tackle_pct"}, "defensive_work_rate": {"tackles_made", "missed_tackles", "tackles_att"},
    "shot_volume": {"shots_on", "shots_off", "shots"}, "shot_selection": {"shots_on", "shots_off", "shot_accuracy"},
    "shot_stopping": {"saves", "conceded", "save_pct"}, "busy_keeper": {"saves", "conceded"},
}


def _driver_phrase(d):
    n = d["count"]
    noun = SINGULAR.get(d["label"], d["label"].lower()) if n == 1 else d["label"].lower()
    return f"{n} {noun}"


def _benchmark_lines(p, used):
    """Informative 'where you stand for your position' bullets for stats not already covered."""
    s, pos = p["stats"], p["pos"]
    role = pb.LABELS[pos].lower()
    good, work = [], []
    for metric, (top, poor, gate) in pb.BENCHMARKS[pos].items():
        val = s.get(metric)
        if val is None or metric in used or (gate and (s.get(gate[0]) or 0) < gate[1]):
            continue
        label = pb.METRIC_LABELS[metric].lower()
        shown = f"{val:.0f}%" if metric in pb.PERCENT_METRICS else f"{val:.0f}"
        target = f"{top}%" if metric in pb.PERCENT_METRICS else f"{top}"
        if val >= top:
            continue  # already a strength
        if poor is None or val > poor:
            work.append(f"{label.capitalize()}: {shown}. That's middle of the pack for a {role}; the top quarter hits {target}+. Room to climb.")
    return good, work


def push_message(m, p):
    """(title, body) for one player's push notification: 6-10 bullets."""
    s = p["stats"]
    v = _fmt_vals(s)
    v.update(G=_g(v), KP=_kp({**v, "assists": s["assists"]}), TA=v["ta_txt"].capitalize(), SH=v["shots_txt"].capitalize())
    mates = [q for q in m["players"] if q["name"] != p["name"]]
    rng = _rng(m["id"], p["name"], "push")
    gap = next((f"{abs(d['impact']):.1f}" for d in p["impact"]["drivers"] if d["key"] == "other"), "0")
    good, work, used = [], [], set()  # (priority, text)

    for x in p["strengths"]:
        if x["tag"] in GOOD_LINES:
            good.append((10, rng.choice(GOOD_LINES[x["tag"]]).format(**v)))
            used |= TAG_KEYS.get(x["tag"], set())
    weak = [w for w in p["weaknesses"] if w["tag"] in WORK_LINES]
    for w in weak:
        work.append((10, rng.choice(WORK_LINES[w["tag"]]).format(**v, gap=gap)))
        used |= TAG_KEYS.get(w["tag"], set())

    # Teammate lines
    scorer = max(mates, key=lambda q: q["stats"]["goals"], default=None)
    if scorer and scorer["stats"]["goals"] and ((s.get("key_passes") or 0) + s["assists"]):
        good.append((9, f"You & {scorer['name']} clicked. Keep feeding those runs, that partnership's got legs."))
    for w in weak:
        mate = next((q for q in mates if any(x["tag"] == w["tag"] for x in q["weaknesses"])), None)
        if mate and w["tag"] in TOGETHER:
            work.append((8, f"You and {mate['name']} both flagged for {pb.TAG_TITLES[w['tag']].lower()}. Work on it as a pair: {TOGETHER[w['tag']]}."))
            break

    # Form vs your own average
    va = p.get("vs_average")
    if va is not None and va >= 0.3:
        good.append((7, f"{va:.1f} above your usual rating. That's growth, and growth is the whole point."))
    elif va is not None and va <= -0.3:
        work.append((7, f"{abs(va):.1f} below your usual rating. One match doesn't define you. We go again."))

    # What actually moved the rating, for actions not mentioned yet
    drivers = [d for d in p["impact"]["drivers"] if d["key"] not in ("other", "result_val") and d.get("count") and d["key"] not in used]
    for d in drivers:
        if d["impact"] > 0:
            good.append((5, f"{_driver_phrase(d).capitalize()} added +{d['impact']:.1f} to your rating. Little things add up."))
    for d in reversed(drivers):
        if d["impact"] < 0:
            work.append((5, f"{_driver_phrase(d).capitalize()} cost you {abs(d['impact']):.1f} rating. Tidy those and the number climbs."))

    # Where you stand for your position
    _, bench = _benchmark_lines(p, used)
    work += [(4, b) for b in bench]

    # Team context (fillers)
    if m["result"] == "W":
        good.append((2, f"Team won {m['gf']}-{m['ga']}. Being part of a winning group is a habit worth keeping."))
    elif m["result"] == "L":
        work.append((2, f"Team lost {m['gf']}-{m['ga']}. Be a goldfish about the score, hang onto the lessons."))
    else:
        good.append((2, f"Team drew {m['gf']}-{m['ga']}. A point earned is a point we didn't have."))
    if p["band"].startswith("Top"):
        good.append((3, f"{s['rating']:.1f} puts you in the {p['band'].lower()} of {pb.LABELS[p['pos']].lower()}s league-wide."))
    good.append((1, f"Played {s['minutes']} minutes. Showing up is half of it, and you did."))
    work.append((1, f"Pick ONE of these to own next match. Just one. That's how habits stick."))

    # 6-10 bullets: up to 5 per side, then top up the shorter side
    good.sort(key=lambda x: -x[0])
    work.sort(key=lambda x: -x[0])
    g, w = good[:5], work[:5]
    if len(g) + len(w) < 6:  # one side is thin: let the other run longer
        g, w = good[:max(5, 6 - len(w))], work[:max(5, 6 - len(g))]

    def weakest():
        last = lambda side: side[-1][0] if side else 99
        return g if last(g) <= last(w) else w

    while len(g) + len(w) > 10:
        weakest().pop()
    # drop pure fillers once there's enough substance
    while len(g) + len(w) > 6 and min((x[-1][0] for x in (g, w) if x), default=99) <= 1:
        weakest().pop()

    lines = [p["coach"]["opener"], "", "DID WELL"] + [f"+ {t}" for _, t in g]
    lines += ["", "WORK ON"] + [f"- {t}" for _, t in w]
    if weak:
        drill = pb.tips_for(weak[0]["tag"], p["pos"], 1)
        if drill:
            lines += ["", f"Coach's drill: {drill[0]}"]
    lines += ["", f"{p['coach']['closer']} - {COACH_NAME}"]
    band = f"{p['band'].lower()} {pb.LABELS[p['pos']][:3].upper()}"
    title = f"{m['result']} {m['gf']}-{m['ga']} vs {m['opponent']['name']} | You: {s['rating']:.1f} ({band})"
    return title, "\n".join(lines)
