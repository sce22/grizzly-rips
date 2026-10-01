"""Position-specific benchmarks, rating weights and coaching tips.

Benchmarks are per-match percentiles from 4,764 live FC 27 player-matches
(60+ minutes) across the 40 top-ranked Pro Clubs, pulled 30 Sep 2026.
"good" is roughly the 75th percentile, "poor" roughly the 25th. Tips distill
common best-practice guidance from competitive Pro Clubs coaching.
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

TIPS = {
    "passing_accuracy": {
        "_": [
            "Default to the simple ground pass to the open, facing teammate; save driven and lobbed passes for clear lanes.",
            "Scan before receiving: know your next pass before the ball arrives so you are not passing under pressure.",
            "Avoid passing across your own box or into a teammate who has a marker tight on their back.",
        ],
        "defender": [
            "Play out through the pivot or full-back rather than long balls to a marked striker; a CB's job is to recycle, not to force.",
            "When pressed, a safe pass back to the keeper or a clearance beats a risky line-breaker.",
        ],
        "midfielder": [
            "Use one- and two-touch passing in triangles; hold the ball only when you have space to turn.",
        ],
        "forward": [
            "Hold-up play: shield with your back to goal and lay it off to the supporting midfielder instead of turning into traffic.",
        ],
        "goalkeeper": [
            "Distribute short to the free centre-back; avoid long kicks to contested headers.",
        ],
    },
    "forcing_passes": {
        "_": [
            "Below ~72% accuracy every extra pass costs rating. Take the simple option until the accuracy comes back.",
            "Through balls only when the runner is already moving and on the shoulder - otherwise recycle or switch play.",
            "If nothing is on, keep the ball: shield, turn back, and let the shape reset.",
        ],
    },
    "involvement": {
        "_": [
            "Show for the ball: move into passing lanes and call for it (pass request) instead of standing behind a marker.",
            "Stay within your role's zone so teammates always know where their outlet is.",
        ],
        "forward": [
            "Drop between the lines occasionally to link play, then spin in behind once the ball is played wide.",
        ],
        "defender": [
            "Offer width and angles for the keeper and pivot on build-up, especially when the opponent presses high.",
        ],
    },
    "progression": {
        "_": [
            "Look forward first: check the striker's run and the space between the lines before the safe sideways pass.",
            "Switch play to the far side when the opponent shifts across - it is the quickest way to create a chance.",
            "Arrive late at the edge of the box for cutbacks; that is where midfield key passes and goals come from.",
        ],
    },
    "tackle_timing": {
        "_": [
            "Jockey first and stay goal-side; only commit when the attacker's touch pushes the ball away from their body.",
            "Every missed tackle opens a gap behind you. If unsure, contain and let a covering teammate step in.",
            "Use standing tackles more than sliding ones; slide only when you are certain of the ball and there's cover.",
        ],
        "defender": [
            "Don't step out of the back line to chase; hold shape and let the ball come to you.",
        ],
        "midfielder": [
            "Press to cut the passing lane rather than lunging at the ball carrier from behind.",
        ],
    },
    "defensive_work_rate": {
        "_": [
            "Engage the ball carrier: a won tackle is worth ~0.2 rating and even a 12% success rate pays for the attempts.",
            "Track your runner all the way into the box; most goals against come from unmarked late runs.",
            "After losing the ball, counter-press for 3-5 seconds before recovering shape.",
        ],
        "midfielder": [
            "As a CDM/CM, screen the centre-backs: stay between the ball and your goal, and intercept rather than chase.",
        ],
    },
    "shot_volume": {
        "_": [
            "Attack the box: make near- and far-post runs on every cross and cutback.",
            "Take the shot when you have a clear sight of goal inside the box; hesitation lets defenders recover.",
        ],
        "forward": [
            "Play on the last defender's shoulder and time runs as the passer lifts their head.",
            "Ask for the ball early in the half-space where a first-time finish is possible.",
        ],
    },
    "shot_selection": {
        "_": [
            "Shoot from central areas inside the box; low-angle and long-range efforts are what miss the target.",
            "Take an extra touch to set your body if you have space - off-balance shots fly wide.",
            "If the angle is tight, cut it back to a teammate instead of shooting.",
        ],
    },
    "finishing": {
        "_": [
            "Your shots are on target but the keeper is getting to them: aim for the corners, not the middle.",
            "Use finesse shots to the far post from angles; use low driven shots one-on-one.",
            "Only use timed finishing when you're confident in the timing; a normal shot to the corner beats a mistimed one.",
        ],
    },
    "shot_stopping": {
        "_": [
            "Hold your position and let the keeper AI handle angles; rushing out early leaves the near post open.",
            "Come off your line only for through balls you are clearly first to.",
            "On crosses, stay central and only claim balls in the six-yard box.",
        ],
    },
    "positioning": {
        "_": [
            "Your rating is lower than your stats predict - the gap is off-ball: positioning, interceptions and blocks.",
            "Hold the defensive line with your partner and step up together; don't get pulled out by a dropping striker.",
            "Stay goal-side and central first, ball-side second. Cover the space behind the full-back when they press.",
        ],
        "midfielder": [
            "Keep your position in the shape when the ball is on the far side; drifting leaves the pivot exposed.",
        ],
    },
    "discipline": {
        "_": [
            "Avoid sliding tackles from behind and when you are the last defender - a red card usually costs the match.",
            "If beaten, recover the goal-side run rather than fouling.",
        ],
    },
    "idle": {
        "_": [
            "EA recorded a lot of idle time. Check your connection, and avoid stepping away mid-match - the team plays a man down.",
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
