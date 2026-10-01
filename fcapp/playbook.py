"""Position-specific benchmarks, rating weights and coaching tips.

Benchmarks are per-match percentiles from 4,764 live FC 27 player-matches
(60+ minutes) across the 40 top-ranked Pro Clubs, pulled 30 Sep 2026.
"good" is roughly the 75th percentile, "poor" roughly the 25th. Tips distill
standard soccer coaching principles, in the coach's voice.
Edit freely - the analysis reads everything from here.
"""

POSITIONS = ("goalkeeper", "defender", "midfielder", "forward")

LABELS = {
    "goalkeeper": "Goalkeeper",
    "defender": "Defender",
    "midfielder": "Midfielder",
    "forward": "Forward",
}

# Match-rating percentiles (P25, P50, P75, P90) by position. Ratings are only
# comparable within a position - keepers sit ~1.3 points below outfielders.
RATING_PERCENTILES = {
    "forward": (6.3, 7.0, 7.9, 9.3),
    "midfielder": (6.9, 7.3, 7.9, 8.6),
    "defender": (6.9, 7.2, 7.7, 8.2),
    "goalkeeper": (5.3, 6.0, 6.6, 7.1),
}

# metric: (good, poor, gate) where gate = (metric, minimum) needed before judging.
# poor=None means the metric can earn a strength but is never flagged as a weakness.
BENCHMARKS = {
    "goalkeeper": {
        "save_pct": (83, 60, ("shots_faced", 3)),
    },
    "defender": {
        "pass_pct": (89, 71, ("passes_att", 8)),
        "passes_att": (15, 9, None),
        "tackle_pct": (60, 25, ("tackles_att", 3)),
        "tackles_att": (4, 1, None),
    },
    "midfielder": {
        "pass_pct": (87, 71, ("passes_att", 10)),
        "passes_att": (25, 15, None),
        "tackle_pct": (50, 18, ("tackles_att", 3)),
        "tackles_att": (6, 2, None),
        "key_passes": (2, None, None),
    },
    "forward": {
        "pass_pct": (88, 73, ("passes_att", 8)),
        "shots": (3, 0, None),
        "shot_accuracy": (90, 60, ("shots", 2)),
        "finishing": (60, 30, ("shots_on", 2)),
        "key_passes": (2, None, None),
    },
}

LOWER_IS_BETTER = set()

# Interaction rules (see the Stat Atlas, section 6)
PASS_BREAK_EVEN = 72          # below this, each extra pass costs rating
DIVING_IN_SUCCESS = 30        # tackle success below this with high volume
POSITIONING_GAP = -0.5        # rating below what the stats predict, per match
IDLE_SHARE = 0.15             # share of real match time idle

METRIC_LABELS = {
    "pass_pct": "Pass accuracy",
    "passes_att": "Passes attempted",
    "tackle_pct": "Tackle success",
    "tackles_att": "Tackles attempted",
    "shots": "Shots",
    "shot_accuracy": "Shots on target",
    "finishing": "Goals per shot on target",
    "key_passes": "Key passes",
    "save_pct": "Save percentage",
}

PERCENT_METRICS = {"pass_pct", "tackle_pct", "shot_accuracy", "finishing", "save_pct", "conversion"}

WEAKNESS_FROM_METRIC = {
    "pass_pct": "passing_accuracy",
    "passes_att": "involvement",
    "tackle_pct": "tackle_timing",
    "tackles_att": "defensive_work_rate",
    "shots": "shot_volume",
    "shot_accuracy": "shot_selection",
    "finishing": "finishing",
    "save_pct": "shot_stopping",
}

STRENGTH_FROM_METRIC = {
    "pass_pct": "passing_accuracy",
    "passes_att": "involvement",
    "tackle_pct": "tackle_timing",
    "tackles_att": "defensive_work_rate",
    "shots": "shot_volume",
    "shot_accuracy": "shot_selection",
    "finishing": "finishing",
    "key_passes": "creativity",
    "save_pct": "shot_stopping",
}

TAG_TITLES = {
    "passing_accuracy": "Passing accuracy",
    "forcing_passes": "Forcing passes",
    "involvement": "On-ball involvement",
    "progression": "Playing forward",
    "tackle_timing": "Tackle timing",
    "defensive_work_rate": "Defensive work rate",
    "shot_volume": "Getting shots off",
    "shot_selection": "Shot selection",
    "finishing": "Finishing",
    "shot_stopping": "Shot stopping",
    "positioning": "Off-ball positioning",
    "discipline": "Discipline",
    "idle": "Staying in the game",
    "goal_threat": "Goal threat",
    "creativity": "Chance creation",
    "clean_sheet": "Keeping it tight",
    "leadership": "Match-winning impact",
    "busy_keeper": "Kept us in it",
}

# Coaching points grounded in standard soccer coaching principles (scanning,
# body shape, support angles, delay-deny-dictate defending, finishing technique),
# written in the coach's voice and translated to how they show up on the pitch in FC.
TIPS = {
    "passing_accuracy": {
        "_": [
            "Scan before the ball gets to you - a quick shoulder check means you already know the pass before you need it.",
            "Open your hips to the field when you receive. Side-on body shape turns a back pass into a forward one.",
            "Simple and on the ground to the open, facing teammate. Driven and lofted balls are for clear lanes only.",
            "Pass to the far foot of a teammate who's facing play; it lets them take it forward in one touch.",
            "Weight matters as much as direction. Firm along the ground beats soft and loopy.",
            "If you're pressed from behind, play it back the way you're facing. Don't turn into trouble.",
            "Count your touches. Two-touch is a habit that keeps your head up and the ball moving.",
        ],
        "defender": [
            "From the back, your job is to recycle, not to force. The pivot or full-back is almost always on.",
            "Under pressure, the keeper or a clearance is a perfectly good pass. Nobody ever lost a match to a smart clearance.",
        ],
        "midfielder": [
            "Play in triangles - one or two touches, then move. The ball should do the running, not you.",
        ],
        "forward": [
            "With your back to goal, shield it and set it back to the runner facing play. Turning into traffic is a coin flip.",
        ],
        "goalkeeper": [
            "Distribute short to the free centre-back. Long kicks into a crowd are a 50/50 we don't need to take.",
        ],
    },
    "forcing_passes": {
        "_": [
            "Below about 72% the extra passes start costing us. Pick the simple option until the touch comes back.",
            "Through balls only when the runner is already moving and on the last defender's shoulder.",
            "If nothing's on, keep it: shield, turn back, let the shape reset. Patience is a pass too.",
            "A sideways pass that keeps the ball is worth more than a forward one that loses it.",
            "Before the killer ball, check: is my runner onside, moving, and unmarked? Two out of three isn't enough.",
            "When the lane closes, switch the point of attack instead of threading the needle.",
            "Use the keeper and center-backs to reset. Recycling is how good teams find the gap.",
        ],
    },
    "involvement": {
        "_": [
            "Show for it. Move into the passing lane and ask for the ball instead of hiding behind your marker.",
            "Give the passer an angle - diagonal to the ball, not flat in a line where it can't reach you.",
            "Move after you pass. A pass-and-move player is always an option.",
            "Check away, then check back. A two-yard feint buys you the space to receive.",
            "Talk. Call for it early so the passer knows where you'll be.",
        ],
        "forward": [
            "Drop between the lines to link play, then spin in behind once it goes wide.",
        ],
        "defender": [
            "Split wide when the keeper has it. Offer an angle so we can build from the back.",
        ],
    },
    "progression": {
        "_": [
            "Look forward first. Check the striker's run and the gap between the lines before the sideways pass.",
            "Switch play when they shift across. Quickest way to find space is usually on the far side.",
            "Arrive late at the edge of the box for cutbacks. That's where midfield chances come from.",
            "Receive on the half-turn so your first touch can go forward.",
            "Look for the third man: pass to the feet of the player who can find the runner.",
            "Carry it into space when nobody steps to you. Dribbling into a gap pulls defenders out of shape.",
        ],
    },
    "tackle_timing": {
        "_": [
            "Delay, deny, then dictate. Jockey goal-side and only commit when their touch gets heavy.",
            "Every missed tackle leaves a runner free behind you. If you're not sure, contain and let cover arrive.",
            "Stay on your feet. Slide only when you're certain of the ball and there's somebody behind you.",
            "Show them down the line, toward the touchline and away from goal, then strike.",
            "Get low and side-on. Square-on defenders get nutmegged.",
            "Win it with your body before your foot: shoulder to shoulder, then poke it away.",
        ],
        "defender": [
            "Don't get pulled out of the line to chase. Hold your spot and let the ball come to you.",
        ],
        "midfielder": [
            "Press to cut the passing lane, not to lunge at the ball carrier from behind.",
        ],
    },
    "defensive_work_rate": {
        "_": [
            "Get stuck in. A won tackle is worth about 0.2 rating, and even 1 in 8 pays for the attempts.",
            "Track your runner all the way into the box. Most goals against come from late, unmarked runs.",
            "When we lose it, press for 3-5 seconds right away. That's when they're most disorganized.",
            "When the ball is lost, the nearest player presses and everyone else closes the passing lanes.",
            "Know your runner before the cross comes in. A quick look over the shoulder saves a goal.",
            "Sprint back the first five yards. That's the moment counter-attacks are won or lost.",
        ],
        "midfielder": [
            "As a CDM/CM, screen the back line: stay between the ball and our goal and pick off passes.",
        ],
    },
    "shot_volume": {
        "_": [
            "Attack the box. Near post and far post on every cross and every cutback.",
            "When you've got a clear look inside the box, pull the trigger. Hesitation lets defenders recover.",
            "Get across your defender at the near post. Most close-range goals come from that first-post run.",
            "Follow every shot in. Rebounds are free goals for people who keep running.",
        ],
        "forward": [
            "Live on the last defender's shoulder and time the run as the passer lifts their head.",
            "Ask for it early in the half-space, where a first-time finish is on.",
        ],
    },
    "shot_selection": {
        "_": [
            "Shoot from central, inside the box. Tight angles and long range are where shots go wide.",
            "Set your feet first if you've got a half second. Off-balance shots fly into the stands.",
            "Tight angle? Cut it back to a teammate. A better shot beats a first shot.",
            "The best shots come from the middle of the box. Work it there before you pull the trigger.",
            "Hit the target first, beat the keeper second. A shot on target can still be saved into a rebound.",
            "Look up before you shoot. Half a second tells you where the keeper's weight is.",
        ],
    },
    "finishing": {
        "_": [
            "We're hitting the target, so now aim for the corners. Keepers love a shot down the middle.",
            "Finesse it to the far post from an angle. One-on-one, go low and hard.",
            "Timed finishing only when you trust it. A clean shot to the corner beats a mistimed rocket.",
            "Low shots across the keeper are the hardest to save and the easiest to tap in on the rebound.",
            "Pick your spot before the ball arrives, then commit. Changing your mind mid-swing is how shots go wide.",
            "Side-foot for accuracy inside the box; power is for outside it.",
        ],
    },
    "shot_stopping": {
        "_": [
            "Set your feet and hold your position as the shot comes. Rushing out early opens up the near post.",
            "Only come off your line for through balls you're clearly winning.",
            "On crosses, stay central and claim only what's in the six-yard box.",
        ],
    },
    "positioning": {
        "_": [
            "Your rating came in lower than your stats say, and that gap is off-ball: positioning, interceptions, blocks.",
            "Hold the line with your partner and step up together. Don't let a dropping striker drag you out.",
            "Goal-side and central first, ball-side second. Cover the space behind the full-back when they press.",
        ],
        "midfielder": [
            "Hold your spot in the shape when the ball's on the far side. Drifting leaves the back line naked.",
        ],
    },
    "discipline": {
        "_": [
            "No slide tackles from behind or as the last defender. A red card costs us the whole match.",
            "If you're beaten, sprint the recovery run goal-side instead of reaching in.",
        ],
    },
    "idle": {
        "_": [
            "The data shows a lot of idle time. Check the connection. We need all hands on deck.",
        ],
    },
}

STRENGTH_NOTES = {
    "passing_accuracy": "Keeps possession reliably - teammates can trust the ball with them.",
    "involvement": "Heavily involved; the team plays through them.",
    "tackle_timing": "Wins the ball cleanly and rarely gets beaten in the duel.",
    "defensive_work_rate": "Puts in the defensive work and engages the ball carrier.",
    "shot_volume": "Consistently finds shooting opportunities.",
    "shot_selection": "Picks good shooting moments and hits the target.",
    "finishing": "Clinical - beats the keeper once on target.",
    "shot_stopping": "Stops the shots they should and more.",
    "goal_threat": "Scored - direct goal contribution.",
    "creativity": "Creates chances for teammates.",
    "clean_sheet": "Part of a clean-sheet performance.",
    "leadership": "Named Man of the Match.",
    "busy_keeper": "Faced a lot of shots - goals against reflect the defence as much as the keeper.",
}


def tips_for(tag, position, limit=3):
    pool = TIPS.get(tag, {})
    tips = list(pool.get(position, [])) + list(pool.get("_", []))
    return tips[:limit]
