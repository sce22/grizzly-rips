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


# ------------------------------------------------------------------ helpers

def _plural(n, word, plural=None):
    return f"{n} {word if n == 1 else (plural or word + 's')}"


class Rotation:
    """Club-wide memory of when each phrase was last used, across every
    player note, team talk and profile, in match order."""

    def __init__(self):
        self.seq = 0
        self.last = {}


class Picker:
    """Chooses phrase variants: never twice in one note, and otherwise the
    variant used longest ago anywhere in the club (ties broken at random,
    seeded so rebuilding the site never reshuffles past notes)."""

    def __init__(self, seed, rotation):
        self.rng = random.Random(zlib.crc32(seed.encode()))
        self.rot = rotation
        self.used = set()

    def __call__(self, key, options):
        ids = [i for i in range(len(options)) if f"{key}:{i}" not in self.used] or list(range(len(options)))
        oldest = min(self.rot.last.get(f"{key}:{i}", -1) for i in ids)
        i = self.rng.choice([i for i in ids if self.rot.last.get(f"{key}:{i}", -1) == oldest])
        self.rot.seq += 1
        self.rot.last[f"{key}:{i}"] = self.rot.seq
        self.used.add(f"{key}:{i}")
        return options[i]


class Context:
    """What makes this performance different from the player's others."""

    def __init__(self, m, p, history):
        self.s = p["stats"]
        self.all = [h["stats"] for h in history]          # every match they've played for us
        self.prev = self.all[-10:]                        # "your usual" = recent form
        self.history = history
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
        """All-time best for us (needs a few matches to mean anything)."""
        vals = [h[key] for h in self.all if h.get(key) is not None]
        return max(vals) if len(vals) >= 3 else None

    def last_scored(self):
        """Date of their previous goal if it was 3+ matches ago, e.g. 'Sep 29'."""
        for i, h in enumerate(reversed(self.history)):
            if h["stats"]["goals"]:
                return h["date_label"] if i >= 3 else None
        return None

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
                    "Scoring's a lot like karaoke: confidence is half of it.",
                    "Goals are like biscuits: always better shared, but I'll take this one.",
                    "That ball had your name on it from the moment you set your feet.",
                    "Cool as the other side of the pillow."],
    "creativity": ["Making your teammates look good is the most generous thing in football.", "You were handing out chances like Halloween candy.",
                   "That's what I call neighborly football.", "Selfless as a church potluck, and twice as filling.",
                   "Chances like that are gifts. You were Santa out there.",
                    "You saw passes other folks didn't even know existed.",
                    "That's the kind of vision you can't teach. Well, I can try, but you already have it.",
                    "A good pass is a love note. You wrote a few."],
    "passing_accuracy": ["You kept that ball like it owed you money.", "Tidier than my mama's guest bathroom.",
                         "Every pass had a return address on it.", "Smooth as a fresh jar of peanut butter.",
                         "Possession is nine-tenths of the law, and you were the sheriff.",
                    "Every ball arrived like it had a GPS.",
                    "Neat, tidy, and not a wasted touch."],
    "involvement": ["The team ran through you like a highway through a small town.", "You were more involved than a church bake-sale committee.",
                    "Everybody wanted the ball at your feet, and for good reason.", "You were the busiest person on the pitch. I'm tired just watching.",
                    "You were the hub, and hubs keep wheels turning.",
                    "You touched the ball more than a nervous waiter touches a menu.",
                    "Always available, always an option."],
    "tackle_timing": ["Clean as a whistle and twice as loud.", "You picked your moment like a ripe peach.",
                      "Patient, then pounced. That's textbook.", "You read it like a bedtime story.",
                      "Their attackers are gonna have nightmares about you, and I mean that kindly.",
                    "Timing like a grandfather clock.",
                    "You won it clean and gave it back to us with a bow on top."],
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
               "Little homework:", "Next match:", "Here's a thought:",
    "Simple fix:",
    "Quick one:",
    "Real talk:",
    "Homework:",
]

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
    "You and {mate} share this one: {issue}. Tandem fix: {fix}.",

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
           "{x} better than usual. That's a staircase, and you're climbing it.",
    "{x} above your usual. Somebody's been eating their Wheaties.",
]
FORM_DOWN = ["{x} below your usual rating. One match doesn't define you. We go again.",
             "{x} under your average. Every player has those. The great ones answer back.",
             "{x} off your norm. Let it go like a bad haircut. It'll grow back.",
             "{x} below your average. Even the sun takes a cloudy day off.",
             "{x} under your usual. That's a dip, not a trend. Promise.",
    "{x} below your usual. Shake it off like a wet dog.",
]
DRIVER_GOOD = ["{what} added +{x} to your rating. Little things add up.",
               "{what} chipped in +{x}. Pennies make dollars.",
               "{what} was worth +{x} on its own. That's the quiet stuff that wins.",
               "{what} nudged you up +{x}. Every bit counts.",
               "{what}: +{x}. Like finding a twenty in last winter's coat.",
               "{what} bought you +{x}. Sprinkles on the sundae.",
               "{what} kicked in +{x}. Small hinges swing big doors.",
    "{what} earned +{x}. That's interest on hard work.",
    "{what} gave you a +{x} lift. Nice little tailwind.",
    "{what}: +{x}. The kind of thing nobody notices except me and the rating.",
]
DRIVER_WORK = ["{what} cost you {x}. Tidy those and the number climbs.",
               "{what} took {x} off your rating. Easy points to win back.",
               "{what} shaved {x} off. Clean that up and you're flying.",
               "{what} pulled you down {x}. That's the low-hanging fruit.",
               "{what}: -{x}. Leaky faucet stuff. Small drips, big bill.",
               "{what} docked you {x}. Nothing a little focus can't fix.",
               "{what} cost {x}. Think of it as a pebble in your boot. Shake it out.",
    "{what} cost {x}. Squeaky wheel; let's oil it.",
    "{what} dinged you {x}. Fixable by Thursday.",
    "{what}: -{x}. Like leaving the porch light on all day. Small, but it adds up.",
]
BENCHMARK = ["{label}: {val}. Middle of the pack for a {role}; the top quarter hits {target}+. Room to climb.",
             "{label}: {val}. Decent, but top-quarter {role}s get to {target}+. That's the next rung.",
             "{label}: {val}. Solid ground. The best {role}s push it to {target}+.",
    "{label}: {val}. Good, not great yet; top-quarter {role}s sit at {target}+.",
    "{label}: {val}. You're in the neighborhood. The fancy houses start at {target}+.",
    "{label}: {val}. That's a B. The A-students among {role}s are at {target}+.",
    "{label}: {val}. Halfway up the mountain. The view from {target}+ is something else.",
    "{label}: {val}. Respectable. Top-quarter {role}s get to {target}+, and you've got it in you.",
]
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
          "Fell {score} to {opp}. The scoreboard keeps score; I keep track of growth.",
    "Fell to {opp}, {score}. Tomorrow's a clean slate and we've got chalk.",
    "{score} to {opp}. Even oak trees lose a few leaves.",
]
CAREER_HIGH = ["Your highest rating yet for us, across all {n} matches. Mark the calendar.",
               "{r} is a new personal best for us. Somebody call the local paper.",
               "Best rating of your {n} matches with us. That's not luck, that's reps."]
BAND_LINE = ["{r} puts you in the {band} of {role}s league-wide.", "League-wide, a {r} is {band} territory for a {role}.",
             "Stack that {r} against every {role} out there: {band}.",
    "A {r} is {band} stuff for a {role} anywhere you look.",
    "{band} of {role}s, league-wide. Not bad for a weeknight.",
]
MINUTES = ["Played all {mins} minutes. Showing up is half of it, and you did.",
           "{mins} minutes on the pitch. Availability is an ability.",
           "You gave us {mins} minutes. That's a full tank, and I noticed.",
    "{mins} minutes, full shift. Your lungs earned a nap.",
    "Went the distance: {mins} minutes.",
]
ONE_THING = ["Pick ONE of these to own next match. Just one. That's how habits stick.",
             "Don't fix it all at once. Choose one, nail it, then come back for the next.",
             "One thing at a time. Rome wasn't built in a day, and neither was a midfield.",
    "Choose your favorite problem from that list and make it your project.",
    "Circle one. Just one. Then come tell me how it went.",
]
DRILL_LEAD = ["Coach's drill:", "This week's homework:", "Practice this:", "Training-ground special:",
    "Back-garden drill:",
    "Before next match:",
    "Five minutes of this:",
]
CLOSERS_GOOD = [
    "Keep that up and I'll have to start buying bigger biscuit tins.", "Proud of you. Now go drink some water.",
    "That's the stuff. Same time next match?", "You make this job too easy. Don't tell the gaffer.",
    "Believe. And maybe stretch.", "Go tell somebody you love about that one.",
    "If I had a gold star sticker, you'd get the whole sheet.",
    "That's the kind of night that makes me glad I took this job.",
    "Keep doing you. You're doing great at it.",
    "I'm gonna go tell my plant about you.",

]
CLOSERS_MIXED = [
    "Pick one thing from that list and own it next match. Just one.",
    "Growth isn't a straight line. It's more like a squiggle. We're squiggling in the right direction.",
    "I believe in you. More importantly, I need you to believe in you.",
    "Go easy on yourself tonight. Go hard at it tomorrow.",
    "Tomorrow's a fresh pitch. Let's go make some divots.",
    "Every great player has nights like this. Most of 'em just don't get a note from me.",
    "Rome wasn't built in a day, but they were laying bricks every hour.",
    "You're closer than you think. Trust the process, and trust your teammates.",
    "Ups and downs make a roller coaster, and roller coasters are fun.",
    "Write one of these on your hand next match. I'm serious.",

]


# ------------------------------------------------------------- the facts

def _good_fact(tag, s, c):
    g, kp = s["goals"], s.get("key_passes") or 0
    if tag == "goal_threat":
        base = {1: "A goal", 2: "A brace", 3: "A hat trick"}.get(g, f"{g} goals") + f" against {c.opp}"
        drought = c.last_scored()
        if c.goal_streak >= 2:
            base += f", your {_ordinal(c.goal_streak)} straight match scoring"
        elif drought:
            base += f", your first since {drought}"
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

FAMILY = {}
for _fam, _keys in {
    "passing": ("passes_att", "passes_made", "passes_missed", "pass_pct", "errors", "actions"),
    "tackling": ("tackles_att", "tackles_made", "missed_tackles", "tackle_pct"),
    "shooting": ("shots", "shots_on", "shots_off", "shot_accuracy", "conversion", "finishing", "goals", "goal_involvements"),
    "creating": ("key_passes", "assists"),
    "keeping": ("saves", "conceded", "save_pct", "shots_faced"),
    "rating": ("rating", "positioning"),
}.items():
    for _k in _keys:
        FAMILY[_k] = _fam


def _fams(keys):
    return {FAMILY.get(k, k) for k in keys}


def build(m, p, history, rotation):
    """Returns (title, body, used_phrase_ids, note) for one player's note:
    The Good, The Bad and (when earned) The Ugly, 6-10 bullets in all, chosen
    from every signal Coach weighed (fcapp/signals.py)."""
    s = p["stats"]
    c = Context(m, p, history)
    pick = Picker(f"{m['id']}|{p['name']}|lasso", rotation)
    mates = [q for q in m["players"] if q["name"] != p["name"]]
    role = pb.LABELS[p["pos"]].lower()
    gap = next((f"{abs(d['impact']):.1f}" for d in p["impact"]["drivers"] if d["key"] == "other"), "0")
    blank = s.get("raw_rating", s["rating"]) <= 3.0 or s.get("stats_missing")
    good, work, ugly = [], [], []  # (priority, text, families)
    used = set()

    for x in p["strengths"]:
        fact = _good_fact(x["tag"], s, c)
        if fact and x["tag"] in GOOD:
            good.append((8.5, f"{fact}. {pick('g_' + x['tag'], GOOD[x['tag']])}", _fams(TAG_KEYS.get(x["tag"], {x["tag"]}))))
            used |= TAG_KEYS.get(x["tag"], set())
    weak = [w for w in p["weaknesses"] if _work_fact(w["tag"], s, c, gap)]
    for w in weak:
        tips = pb.tips_for(w["tag"], p["pos"], limit=12)
        tip = pick("t_" + w["tag"], tips) if tips else ""
        lead = pick("lead", WORK_LEADIN) + " "
        tail = " " + pick("tail", WORK_TAIL) if pick.rng.random() < 0.7 else ""
        keys = TAG_KEYS.get(w["tag"], {"rating"} if w["tag"] == "positioning" else {w["tag"]})
        work.append((8.5, f"{_work_fact(w['tag'], s, c, gap)}. {lead}{tip}{tail}".strip(), _fams(keys)))
        used |= TAG_KEYS.get(w["tag"], set())

    scorer = max(mates, key=lambda q: q["stats"]["goals"], default=None)
    if scorer and scorer["stats"]["goals"] and ((s.get("key_passes") or 0) + s["assists"]):
        good.append((6, pick("mate_g", TEAMMATE_GOOD).format(mate=scorer["name"]), {"mate"}))
    for w in weak:
        mate = next((q for q in mates if any(x["tag"] == w["tag"] for x in q["weaknesses"])), None)
        if mate and w["tag"] in TOGETHER:
            work.append((5.5, pick("mate_w", TEAMMATE_WORK).format(mate=mate["name"], issue=pb.TAG_TITLES[w["tag"]].lower(), fix=TOGETHER[w["tag"]]), {"mate"}))
            break

    # Everything else Coach weighed: vs your usual, all-time, teammates, the
    # opponent's humans, the session, the season, the ladder...
    for x in p.get("signals", []):
        fam = _fams([x["metric"]])
        if x["side"] == "ugly":
            if x["metric"] == "rage_quit":
                ugly.append((20, f"{x['text']}. {pick('rage', RAGE)}", fam))
                continue
            tips = pb.tips_for(x["tip"], p["pos"], limit=12) if x.get("tip") else []
            fix = f" {pick('lead', WORK_LEADIN)} {pick('t_' + x['tip'], tips)}" if tips else ""
            ugly.append((x["w"] + 5, f"{x['text']}. {pick('ugly', UGLY)}{fix}", fam))
        elif x["metric"] == "stats_missing":
            work.append((x["w"], x["text"] + ".", fam))  # EA's blank, not the player's fault: no framing
        elif x["metric"] in TEAM_METRICS:
            side, pool = (good, TEAM_GOOD) if x["side"] == "good" else (work, TEAM_BAD)
            side.append((x["w"], f"{x['text']}. {pick('sig_team_' + x['side'], pool)}", fam))
        elif x["side"] == "good":
            good.append((x["w"], f"{x['text']}. {pick('sig_g', SIG_GOOD)}", fam))
        else:
            tips = pb.tips_for(x["tip"], p["pos"], limit=12) if x.get("tip") else []
            if tips and pick.rng.random() < 0.5:
                frame = f"{pick('lead', WORK_LEADIN)} {pick('t_' + x['tip'], tips)}"
            else:
                frame = pick("sig_b", SIG_BAD)
            work.append((x["w"], f"{x['text']}. {frame}", fam))

    va = p.get("vs_average")
    if va is not None and va >= 0.3 and not blank:
        good.append((5, pick("form_up", FORM_UP).format(x=f"{va:.1f}"), {"rating"}))
    elif va is not None and va <= -0.3 and not blank:
        work.append((5, pick("form_down", FORM_DOWN).format(x=f"{abs(va):.1f}"), {"rating"}))

    drivers = [] if blank else [d for d in p["impact"]["drivers"] if d["key"] not in ("other", "result_val") and d.get("count") and d["key"] not in used]
    for d in drivers:
        if d["impact"] > 0:
            good.append((3.5, pick("drv_g", DRIVER_GOOD).format(what=_driver_what(d), x=f"{d['impact']:.1f}"), _fams([d["key"]])))
    for d in reversed(drivers):
        if d["impact"] < 0:
            work.append((3.5, pick("drv_w", DRIVER_WORK).format(what=_driver_what(d), x=f"{abs(d['impact']):.1f}"), _fams([d["key"]])))

    for metric, (top, poor, gate) in ({} if blank else pb.BENCHMARKS[p["pos"]]).items():
        val = s.get(metric)
        if val is None or metric in used or (gate and (s.get(gate[0]) or 0) < gate[1]) or val >= top or (poor is not None and val <= poor):
            continue
        pct = metric in pb.PERCENT_METRICS
        work.append((3, pick("bench", BENCHMARK).format(label=pb.METRIC_LABELS[metric], role=role,
                                                        val=f"{val:.0f}%" if pct else f"{val:.0f}", target=f"{top}%" if pct else top), _fams([metric])))

    if c.season_high("rating") and not blank:
        good.append((8, pick("career_high", CAREER_HIGH).format(r=f"{s['rating']:.1f}", n=len(c.all) + 1), {"rating"}))
    rk = p.get("rank")
    if rk and rk["of"] >= 3 and rk.get("show") and not rk.get("perfect") and not blank:
        line_args = dict(r=f"{s['rating']:.1f}", rank=rk["text"])
        if rk["dir"] == "best" and rk["best"] <= max(3, rk["of"] // 4):
            good.append((6, pick("rank_g", RANK_GOOD).format(**line_args), {"rating"}))
        elif rk["dir"] == "worst" and rk["worst"] <= max(3, rk["of"] // 4):
            work.append((6, pick("rank_w", RANK_WORK).format(**line_args), {"rating"}))
    team = {"W": ("team_w", TEAM_W, good), "D": ("team_d", TEAM_D, good), "L": ("team_l", TEAM_L, work)}[m["result"]]
    team[2].append((2, pick(team[0], team[1]).format(score=c.score, opp=c.opp), {"scoreline"}))
    if not blank:
        good.append((1, pick("mins", MINUTES).format(mins=s["minutes"]), {"minutes"}))
    work.append((1, pick("one", ONE_THING), {"one"}))

    def choose(items, limit, taken=()):
        """Strongest first, one bullet per stat family, nothing already said in The Ugly."""
        out, fams = [], set(taken)
        for x in sorted(items, key=lambda x: -x[0]):
            if x[2] & fams:
                continue
            out.append(x)
            fams |= x[2]
            if len(out) == limit:
                break
        return out

    u = choose(ugly, 3)
    ugly_fams = {f for x in u for f in x[2]} - {"scoreline", "ladder"}
    g, w = choose(good, 5), choose(work, 5, ugly_fams)
    if len(g) + len(w) + len(u) < 6:
        g, w = choose(good, max(5, 6 - len(w) - len(u))), choose(work, max(5, 6 - len(g) - len(u)), ugly_fams)

    def weakest():
        last = lambda side: side[-1][0] if side else 99
        return g if last(g) <= last(w) else w

    while len(g) + len(w) + len(u) > 10:
        weakest().pop()
    while len(g) + len(w) + len(u) > 6 and min((x[-1][0] for x in (g, w) if x), default=99) <= 1:
        weakest().pop()

    tone = p.get("rank", {}).get("tone", p["band"])
    shown = p.get("rank", {}).get("show")
    rank = p.get("rank", {}).get("text", "") if shown else ""
    # only a season top-5 / bottom-5 (or a Perfect Game) gets its ranking said out loud
    openers = OPENERS[tone] if shown else [x for x in OPENERS[tone] if "{rank}" not in x]
    opener = pick(f"open_{tone}", openers).format(name=p["name"], r=f"{s['rating']:.1f}", pos=role, opp=c.opp, rank=rank)
    if s.get("perfect"):
        opener = pick("perfect_open", PERFECT_OPEN).format(name=p["name"], opp=c.opp, rank=rank)
    if s.get("rage_quit"):
        opener = pick("rage_open", RAGE_OPEN).format(name=p["name"], score=c.score)
    drill_tag = next((x["tag"] for x in weak), None) or next((x["tip"] for x in p.get("signals", []) if x["side"] != "good" and x.get("tip")), None)
    drill = None
    if drill_tag:
        bullet_text = "\n".join(x[1] for x in w + u)
        drills = [t for t in pb.tips_for(drill_tag, p["pos"], limit=12) if t not in bullet_text]
        if drills:
            drill = f"{pick('drill', DRILL_LEAD)} {pick('t_' + drill_tag, drills)}"
    closer = pick("close_good", CLOSERS_GOOD) if (not w and not u) or tone.startswith("Top") else pick("close_mixed", CLOSERS_MIXED)
    lassoism = pick("closing_frame", CLOSING_FRAMES).format(name=p["name"], line=pick("lassoism", LASSOISMS))
    note = {"opener": _an(opener), "good": [_an(x[1]) for x in g], "work": [_an(x[1]) for x in w], "ugly": [_an(x[1]) for x in u],
            "drill": drill, "lassoism": lassoism, "closer": closer, "coach": COACH, "weighed": p.get("signals_checked", 0)}
    lines = [note["opener"]]
    for head, mark, items in ((GOOD_HEAD, "+", note["good"]), (BAD_HEAD, "-", note["work"]), (UGLY_HEAD, "!", note["ugly"])):
        if items:
            lines += ["", head] + [f"{mark} {t}" for t in items]
    if drill:
        lines += ["", drill]
    lines += ["", lassoism, "", f"{closer} - {COACH}"]
    title = f"{m['result']} {c.score} vs {c.opp} | You: {s['rating']:.1f}" + (f" ({rank})" if rank else "")
    if s.get("rage_quit"):
        title = f"{m['result']} {c.score} vs {c.opp} | You: rage quit"
    return title, "\n".join(lines), pick.used, note


def _an(text):
    """'a 8.4' -> 'an 8.4'."""
    return re.sub(r"\b([Aa]) (?=(8|11|18)(\.\d)?\b)", lambda mm: mm.group(1) + "n ", text)


def _date_label(ts):
    from datetime import datetime
    d = datetime.fromtimestamp(ts)
    return f"{d:%b} {d.day}"


def annotate(matches, players):
    """Write every player note, team talk and profile note in match order,
    sharing one club-wide phrase rotation so nothing reads like a rerun."""
    rotation, history = Rotation(), {}
    for m in sorted(matches, key=lambda x: x["ts"]):
        for p in m["players"]:
            hist = history.setdefault(p["name"], [])
            title, body, _, note = build(m, p, hist, rotation)
            p["push"] = {"title": title, "body": body}
            p["note"] = note  # same words on the website player card
        m["talk"], _ = build_talk(m, history, rotation)
        for p in m["players"]:
            history[p["name"]].append({**p, "date_label": _date_label(m["ts"])})
    for p in players.values():
        build_profile(p, rotation)


# ================================================================ team talk
# Match-page team talk: 3 things we did well, 3 to work on. Phrasing rotates
# so consecutive match pages don't read alike.

TALK_OPEN = {
    "W": ["Three points, y'all. {gf}-{ga} over {opp}.",
          "That's a W. {gf}-{ga} against {opp}, and I'm smiling so big my cheeks hurt.",
          "{gf}-{ga} over {opp}. Somebody put the kettle on, we're celebrating.",
          "We beat {opp} {gf}-{ga}. That's what happens when a team trusts each other.",
          "Win number one-more-than-before: {gf}-{ga} against {opp}.",
          "{opp} came, {opp} saw, {opp} lost {ga}-{gf}. Let's talk about why."],
    "D": ["{gf}-{ga} with {opp}. A draw is a win that hasn't figured itself out yet.",
          "We shared the points with {opp}, {gf}-{ga}. Plenty to learn from.",
          "{gf}-{ga}. Not a loss, not a win, but a whole lotta lessons.",
          "Even-steven with {opp} at {gf}-{ga}. Let's find the extra gear."],
    "L": ["{ga}-{gf} to {opp}. Be a goldfish about the result, keep the lessons.",
          "Lost {gf}-{ga} to {opp}. Chins up. One match doesn't define a team.",
          "{opp} got us {ga}-{gf}. Losses are tuition, and we're getting smarter.",
          "Tough night against {opp}, {gf}-{ga}. Let's turn it into fuel.",
          "{gf}-{ga} loss. The scoreboard keeps score; I keep track of growth."],
}
TALK_SIGNOFF = ["Believe.", "Proud of y'all.", "Onward.", "Biscuits on me.", "Hydrate, then celebrate.",
                "Same time next match.", "Go hug your mama.", "Stay curious."]

TALK_GOOD = {
    "clean_sheet": ["Clean sheet against {opp}. Nobody got past us, and that's all of us defending, not just the back line.",
                    "Zero conceded to {opp}. We defended like the last slice of pie was on the line.",
                    "{opp} didn't score. Shutouts are built by everybody."],
    "scoring": ["{gf} goals from {shots} shots. When we flood the box, good things happen.",
                "Put {gf} past {opp}. Our runners made their back line dizzy.",
                "{gf} goals. That attack was humming like a pickup on a cold morning."],
    "shot_acc": ["{on} of {shots} shots on target ({acc}%). We picked our moments instead of swinging at everything.",
                 "{acc}% of our shots hit the target. Patience in front of goal pays off.",
                 "{on}/{shots} on target. Their keeper's gloves are still smoking."],
    "passing": ["Passing at {pp}%. We kept that ball like it owed us money.",
                "{pp}% team passing. Smooth as Sunday morning.",
                "{pp}% of our passes found a teammate. That's how you tire a team out."],
    "duels": ["Won {tm} of {ta} tackles ({tp}%). First to the ball, and we meant it.",
              "{tp}% of our tackles won. We were hungrier than them.",
              "{tm}/{ta} tackles won. Every loose ball looked like ours."],
    "chances": ["{kp} key passes. We made chances for each other.",
                "{kp} chances created. Unselfish football is beautiful football.",
                "{kp} key passes. Assist-minded team, and I love it."],
    "star": ["{name} led the way with {art} {r}: {bits}.", "Tip of the cap to {name}, {art} {r}: {bits}.",
             "{name} was the engine ({r}): {bits}."],
}
TALK_WORK = {
    "conceded": ["Conceded {ga}. When we lose it, get compact and goal-side: shape before chase.",
                 "{ga} goals against. We left the back door open; let's lock it.",
                 "Let in {ga}. Recovery runs and tracking runners into the box fix most of that."],
    "passing": ["Passing at {pp}%, under the ~72% line where extra passes start costing us.",
                "{pp}% passing. We gave it away too cheap.",
                "Only {pp}% of passes found a teammate. Shorter, safer, then go."],
    "shot_sel": ["Only {on} of {shots} shots on target.", "{on}/{shots} on target. Too many hopeful ones.",
                 "{acc}% shot accuracy. Better looks, not more looks."],
    "tackling": ["Won just {tm} of {ta} tackles.", "{tm}/{ta} tackles won. We dove in.", "{tp}% tackle success. Patience in the duel."],
    "few_shots": ["Only {shots} shots all match.", "{shots} shots. We need to arrive in the box, not admire it.",
                  "Just {shots} attempts at goal."],
    "progression": ["{kp} key passes from {pa} passes.", "Lots of ball ({pa} passes), {kp} key passes.",
                    "{pa} passes, {kp} key passes. We weren't hurting them."],
    "red": ["{name} saw red.", "Red card for {name}.", "We played a man down after {name}'s red."],
}
TALK_TIP_TAG = {"conceded": "defensive_work_rate", "passing": "passing_accuracy", "shot_sel": "shot_selection",
                "tackling": "tackle_timing", "few_shots": "shot_volume", "progression": "progression", "red": "discipline"}
TALK_TITLES = {"clean_sheet": "Clean sheet", "scoring": "Scoring", "shot_acc": "Shot accuracy", "passing": "Passing",
               "duels": "Winning duels", "chances": "Creating chances", "conceded": "Defending as a unit",
               "shot_sel": "Shot selection", "tackling": "Tackling", "few_shots": "Getting shots off",
               "progression": "Playing forward", "red": "Discipline"}


def _star_bits(p):
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
    return ", ".join(bits[:3]) or "all-round work"


def build_talk(m, histories, rotation):
    t, ps = m["team"], m["players"]
    pick = Picker(f"{m['id']}|talk", rotation)
    f = dict(opp=m["opponent"]["name"], gf=m["gf"], ga=m["ga"], shots=t.get("shots", 0), on=t.get("shots_on") or 0,
             acc=f"{t['shot_accuracy']:.0f}" if t.get("shot_accuracy") is not None else "-",
             pp=f"{t['pass_pct']:.0f}" if t.get("pass_pct") is not None else "-",
             tm=t.get("tackles_made", 0), ta=t.get("tackles_att", 0),
             tp=f"{t['tackle_pct']:.0f}" if t.get("tackle_pct") is not None else "-",
             kp=t.get("key_passes") or 0, pa=t.get("passes_att", 0))
    good, work = [], []  # (score, title, line, tip)

    def g(score, key):
        good.append((score, TALK_TITLES[key], pick("tg_" + key, TALK_GOOD[key]).format(**f), None))

    def w(score, key, **extra):
        tip_tag = TALK_TIP_TAG[key]
        tips = pb.tips_for(tip_tag, "_", limit=12)
        work.append((score, TALK_TITLES[key], pick("tw_" + key, TALK_WORK[key]).format(**f, **extra),
                     pick("t_" + tip_tag, tips) if tips else None))

    acc, pp, tp = t.get("shot_accuracy"), t.get("pass_pct"), t.get("tackle_pct")
    if m["ga"] == 0:
        g(3.0, "clean_sheet")
    if m["gf"] >= 3:
        g(2 + (m["gf"] - 3) * 0.5, "scoring")
    if acc is not None and f["shots"] >= 4 and acc >= 65:
        g(1.5 + (acc - 65) / 20, "shot_acc")
    if pp is not None and pp >= 82:
        g(1.5 + (pp - 82) / 5, "passing")
    if tp is not None and f["ta"] >= 6 and tp >= 45:
        g(1.5 + (tp - 45) / 15, "duels")
    if f["kp"] >= 4:
        g(1.4 + (f["kp"] - 4) * 0.2, "chances")
    star = ps[0] if ps else None
    if star and star["band"] in ("Top 10%", "Top 25%"):
        r = f"{star['stats']['rating']:.1f}"
        good.append((2.6 if star["band"] == "Top 10%" else 2.0, star["name"],
                     pick("tg_star", TALK_GOOD["star"]).format(name=star["name"], r=r, bits=_star_bits(star),
                                                               art="an" if r.startswith(("8", "11", "18")) else "a"), None))

    if m["ga"] >= 3:
        w(2 + (m["ga"] - 3) * 0.5, "conceded")
    if pp is not None and pp < pb.PASS_BREAK_EVEN:
        w(2 + (pb.PASS_BREAK_EVEN - pp) / 5, "passing")
    if acc is not None and f["shots"] >= 4 and acc < 45:
        w(1.8 + (45 - acc) / 20, "shot_sel")
    if tp is not None and f["ta"] >= 6 and tp < 30:
        w(1.8 + (30 - tp) / 15, "tackling")
    if f["shots"] <= 3:
        w(1.6, "few_shots")
    if f["kp"] <= 1 and f["pa"] >= 40:
        w(1.4, "progression")
    for p in ps:
        if p["stats"]["red_cards"]:
            w(3.0, "red", name=p["name"])

    # Individual moments, in the same varied voice as the player notes
    covered = {"passing_accuracy", "forcing_passes", "shot_selection", "tackle_timing", "shot_volume", "discipline", "progression"}
    for p in ps[1:] if star and star["band"] in ("Top 10%", "Top 25%") else ps:
        c = Context(m, p, histories.get(p["name"], []))
        x = next((x for x in p["strengths"] if x["tag"] in GOOD and _good_fact(x["tag"], p["stats"], c)), None)
        if x:
            good.append((0.6, f"{p['name']} · {pb.TAG_TITLES[x['tag']]}",
                         f"{p['name']}: {_good_fact(x['tag'], p['stats'], c)}. {pick('g_' + x['tag'], GOOD[x['tag']])}", None))
    for p in ps:
        c = Context(m, p, histories.get(p["name"], []))
        gap = next((f"{abs(d['impact']):.1f}" for d in p["impact"]["drivers"] if d["key"] == "other"), "0")
        x = next((x for x in p["weaknesses"] if x["tag"] not in covered and _work_fact(x["tag"], p["stats"], c, gap)), None)
        if x:
            tips = pb.tips_for(x["tag"], p["pos"], limit=12)
            work.append((0.9, f"{p['name']} · {pb.TAG_TITLES[x['tag']]}",
                         f"{p['name']}: {_work_fact(x['tag'], p['stats'], c, gap)}.", pick("t_" + x["tag"], tips) if tips else None))
    # Fallbacks so there are always three of each
    for p in ps:
        drivers = [d for d in p["impact"]["drivers"] if d["key"] not in ("other", "result_val") and d.get("count")]
        if drivers and drivers[0]["impact"] > 0:
            d = drivers[0]
            good.append((0.3, f"{p['name']} · {d['label']}", f"{p['name']}: " + pick("drv_g", DRIVER_GOOD).format(what=_driver_what(d), x=f"{d['impact']:.1f}"), None))
        if drivers and drivers[-1]["impact"] < 0:
            d = drivers[-1]
            work.append((0.3, f"{p['name']} · {d['label']}", f"{p['name']}: " + pick("drv_w", DRIVER_WORK).format(what=_driver_what(d), x=f"{abs(d['impact']):.1f}"), None))

    def top3(items):
        seen, out = set(), []
        for score, title, line, tip in sorted(items, key=lambda i: -i[0]):
            if title in seen:
                continue
            seen.add(title)
            item = {"title": title, "line": _an(line)}
            if tip:
                item["tip"] = tip
            out.append(item)
            if len(out) == 3:
                break
        return out

    well, improve = top3(good), top3(work)
    if not improve:
        improve = [{"title": "Keep it rolling", "line": "Honestly? Not much. Bottle whatever that was and bring it next match."}]
    talk = {"opener": pick("talk_open_" + m["result"], TALK_OPEN[m["result"]]).format(**f),
            "well": well, "work_on": improve, "signoff": pick("talk_sign", TALK_SIGNOFF), "coach": COACH}
    return talk, pick.used


# ================================================================= profiles

PROFILE_INTRO = [
    "{name}, I've watched all {n} of your matches. Here's what the tape and the numbers are telling me.",
    "Alright {name}, {n} matches in. Let's talk patterns, the good and the growing.",
    "{name}, {n} matches is enough to see who you are as a player. I like what I see, and I see where we can go.",
    "{n} matches, {name}. Patterns don't lie, but they do change. Here's where yours are headed.",
    "Pull up a chair, {name}. {n} matches of evidence, and I've got thoughts.",
]
THEME_LINES = {
    "improving": ["It's come up in {rate}% of your matches, but only {recent}% lately. You're winning this one.",
                  "Flagged {rate}% of the time overall, {recent}% in your last five. That's a trend I like.",
                  "{rate}% of matches overall, down to {recent}% recently. Keep chipping away."],
    "worsening": ["It's crept up to {recent}% of your recent matches ({rate}% overall). Let's make it the focus.",
                  "{recent}% of your last five, up from {rate}% overall. Time to put this one front and center.",
                  "This one's been sneaking up: {recent}% lately vs {rate}% overall."],
    "steady": ["It's shown up in {rate}% of your matches and it's holding steady. Let's crack it.",
               "Steady at about {rate}% of matches. Steady means fixable; it's a habit, not a fluke.",
               "{rate}% of matches, right in line with your recent form. A good one to drill."],
}
THEME_STRENGTH = ["Shows up in {rate}% of your matches. That's a calling card.",
                  "{rate}% of the time. Teammates can count on it.",
                  "There in {rate}% of your matches. Build your game around it.",
                  "{rate}% of matches. That's not luck; that's who you are."]


def build_profile(p, rotation):
    pick = Picker(f"profile|{p['name']}|{p['matches']}", rotation)
    p["coach"] = {"intro": pick("p_intro", PROFILE_INTRO).format(name=p["name"], n=p["matches"]), "name": COACH}
    if not p.get("themes"):
        return
    for t in p["themes"]["improve"]:
        t["coach"] = pick("p_theme_" + t["direction"], THEME_LINES[t["direction"]]).format(rate=t["rate"], recent=t["recent_rate"])
        tips = pb.tips_for(t["tag"], p["main_pos"], limit=12)
        t["tips"] = [pick("t_" + t["tag"], tips) for _ in range(min(3, len(tips)))]
    for x in p["themes"]["strengths"]:
        frame = pick("g_" + x["tag"], GOOD[x["tag"]]) if x["tag"] in GOOD else ""
        x["coach"] = f"{frame} {pick('p_str', THEME_STRENGTH).format(rate=x['rate'])}".strip()


# Extra phrasing (about 5x the pools above), merged append-only
import sys as _sys  # noqa: E402
from . import lasso_more as _lasso_more  # noqa: E402
_lasso_more.merge(_sys.modules[__name__])

# Ratings are framed against each player's own games, not league percentages:
# drop opener lines that talk in percentages, add the personal-ranking ones.
_PCT = re.compile(r"%|percent|quarter|top 10|top 25|average for|par for|league-wide|anywhere in this league|for a \{pos\} out there", re.I)
for _tone, _lines in OPENERS.items():
    OPENERS[_tone] = [x for x in _lines if not _PCT.search(x)] + _lasso_more.RANK_OPENERS[_tone]
RANK_GOOD, RANK_WORK = _lasso_more.RANK_GOOD, _lasso_more.RANK_WORK
WORK_TAIL, LASSOISMS, CLOSING_FRAMES = _lasso_more.WORK_TAIL, _lasso_more.LASSOISMS, _lasso_more.CLOSING_FRAMES
from .lasso_ugly import (BAD_HEAD, GOOD_HEAD, PERFECT_OPEN, RAGE, RAGE_OPEN, SIG_BAD, SIG_GOOD, TEAM_BAD, TEAM_GOOD,  # noqa: E402
                         TEAM_METRICS, UGLY, UGLY_HEAD)
