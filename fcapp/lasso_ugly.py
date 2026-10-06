"""Coach Lasso's framing for the extra signals and for "The Ugly".

The Good / The Bad / The Ugly: signals (fcapp/signals.py) arrive as plain
facts; these lines put Coach's voice on them. Ugly lines are blunt - Coach is
honest about the worst of it - but never cruel, and every note still ends warm.
"""

SIG_GOOD = [
    "That's the stuff I want framed.",
    "Write that one down and stick it on the fridge.",
    "Quietly brilliant, and I noticed.",
    "That's the version of you I'm building the team around.",
    "Bottle that and bring it next match.",
    "Nobody hands out trophies for that, so here's my handshake.",
    "That's a habit, and habits win leagues.",
    "Proof you've got another gear.",
    "Little things like that are big things in disguise.",
    "That right there is what good teammates do.",
    "Keep stacking those bricks.",
    "That's growth you can count.",
    "I'd put that on a billboard if I could afford one.",
    "That's the good stuff, like the corner piece of the brownie.",
    "Your teammates felt that, even if the scoreboard didn't.",
    "That doesn't happen by accident.",
    "I see you, and I like what I see.",
    "Remember that the next time you doubt yourself.",
    "Gold star, no notes.",
    "Pure hustle, and hustle is free.",
    "That's the reliable kind of good.",
    "That's the bit I'll replay in my head on the drive home.",
    "If the rest of the night was a storm, that was the lighthouse.",
    "You can build a whole match on that.",
    "Keep that in your back pocket.",
    "That's what showing up looks like.",
    "More of that, please and thank you.",
    "You earned that one the honest way.",
    "Small wins add up to big ones.",
    "That's a keeper. The habit, not the position.",
]

SIG_BAD = [
    "We can fix that.",
    "That's on the to-do list now.",
    "Not who you are, but it was who showed up.",
    "Let's not make that a pattern.",
    "Fixable, but only if we fix it.",
    "That's the leak in the boat.",
    "Honest truth: that cost us.",
    "That's the one I'd circle in red.",
    "We need more from you there, and I know you've got it.",
    "That's a habit trying to sneak in. Don't let it.",
    "That's the part of the tape we'll rewind.",
    "Numbers don't lie, even when we wish they would.",
    "Let's call that a lesson and not a trend.",
    "That's the gap between a good night and a great one.",
    "That's where the match slipped.",
    "I'm not mad, I'm just writing it down.",
    "That's not you at your best, and we both know it.",
    "That needs to look different next time out.",
    "That's the stone in your boot. Take it out.",
    "It's a small thing until it's the whole thing.",
    "We don't hide from that one; we fix it.",
    "That's not a crisis, but it's a warning light.",
    "That's the kind of number that loses matches.",
    "Let's turn that around by next session.",
    "Note to self, from me to you.",
    "That's the bit that kept us from winning.",
    "One honest look at that and we move forward.",
    "That has to tighten up.",
    "It happens. It can't keep happening.",
    "We'll drill that till it's boring.",
]

UGLY = [
    "I'm gonna be straight with you: that's not good enough, and you know it.",
    "That one's ugly, friend. No sugar on it.",
    "I love you, but that wasn't football. That was a fire drill.",
    "That's the kind of thing that loses a team its spot in a division.",
    "No silver lining on this one. Let's just make sure it never happens again.",
    "That's a red-ink, see-me-after-class kind of number.",
    "I've seen tidier yard sales.",
    "That's not a bad day, that's a warning siren.",
    "We don't sweep that under the rug. We look at it, then we fix it.",
    "That's the stuff that keeps me up at night, and I sleep like a baby.",
    "Ugly is the right word. Not the only word, but the right one.",
    "That's below the line we drew together, and the line is the line.",
    "If the tape had a smell, that part would stink.",
    "Plain as a tractor: unacceptable.",
    "That's the first thing we fix, before anything else.",
    "I'm not gonna pretty that up for you.",
    "That's not who we are, and it can't be who we become.",
    "That one hurt the team, and the team deserves better.",
    "A low point, and a clear one. Clear is good: it means we know where to start.",
    "That's the part of tonight I'd burn if it were on paper.",
    "We owe the team better than that. All of us.",
    "That has to be the floor, and we never visit the floor again.",
    "Rough? That's sandpaper with an attitude.",
]

RAGE = [
    "Walking off leaves your teammates playing short-handed, and that's the one thing I can't coach around. Frustration's allowed; quitting on each other isn't.",
    "I get it, the night was going sideways. But when one of us leaves, everybody left behind pays for it. Next time, stay, even if all you do is chase.",
    "Losing is part of the game. Leaving isn't. Stick it out, even when it's ugly, because that's when your teammates need you most.",
    "A rage quit hurts the team more than any bad pass ever could. Breathe, finish the match, and save the fury for the next kickoff.",
    "The team needs you on the pitch more on the bad nights than the good ones. Stay with 'em. That's what makes a team.",
    "I'd rather have you play badly for 90 minutes than walk off for one. Stay in it. You never know when the comeback starts.",
    "Quitting a match is a habit, and I want this to be the last time we see it. Count to ten, then go win the next ball.",
    "Frustration is fuel. Walking off is pouring it on the ground. Use it next time.",
]

UGLY_HEAD = "THE UGLY"
GOOD_HEAD = "THE GOOD"
BAD_HEAD = "THE BAD"

# Team-level facts (scoreline, ladder, opponent strength, losing runs) get
# team-level framing, so nobody is blamed alone for a team result.
TEAM_GOOD = [
    "That one belongs to all of us, and you were in it.",
    "Team wins are the best kind.",
    "Everybody gets a slice of that pie.",
    "That's what happens when we pull the same rope.",
    "Moments like that are why we keep showing up.",
    "Enjoy it. Then go get the next one.",
    "Put that in the team scrapbook.",
    "That's a team that believes in itself.",
]
TEAM_BAD = [
    "That's on all of us, not just you, and all of us fix it.",
    "We win together and we wear this together.",
    "Nobody carries that alone. We carry it as a team.",
    "That's the scoreboard being honest with us.",
    "A team result, and it needs a team answer.",
    "We dug that hole together; we'll climb out together.",
    "I'm not pointing fingers. I'm pointing at the mirror, mine included.",
    "That stings the whole locker room, and it should.",
    "We'll talk about it as a group, then leave it behind us.",
    "That's the bill for the little mistakes, and we all chipped in.",
    "Ain't no hiding from that one. Good. Now we learn from it.",
    "That's where we are. It's not where we're staying.",
]
RAGE_OPEN = [
    "{name}, we need to talk about how this one ended, because you weren't there for the end of it.",
    "{name}, the scoreboard says {score}, but the part I care about is that you walked off.",
    "{name}, I'm not grading football tonight. I'm talking about leaving your teammates.",
    "Alright, {name}. EA marked this one a rage quit, and I'm not gonna pretend I didn't see it.",
    "{name}, everybody has a breaking point. Tonight we found yours, and we're gonna move it.",
    "{name}, you left this one early. Let's talk about that before anything else.",
]
TEAM_METRICS = {"scoreline", "ladder", "opp_strength", "results"}

PERFECT_OPEN = [
    "{name}, a perfect 10.0 against {opp}. {rank}. I don't have a speech for this. I'm just gonna stand here and clap.",
    "Ten. Point. Zero. {name}, that's a {rank} and I'd like it laminated, please.",
    "{name}, they don't make the rating any higher than that. {rank} against {opp}. Somebody ring a bell.",
    "{rank}, {name}. A 10.0 against {opp}. If football had a dictionary, your picture would be next to 'flawless'.",
    "{name}, a 10.0. {rank}. I've been coaching a long time and I still got goosebumps.",
]
