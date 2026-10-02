"""Extra Coach Lasso phrasing (part 2: the nightly Daily Summary speech).
Merged into fcapp/daily.py at import time (append-only)."""

OPEN = {
    "low": [
        "Alright, everybody sit. No phones, no excuses, just us.",
        "I'm not gonna sugarcoat it, and I love sugar.",
        "Gather up. This one's gonna be honest, because honest is how we get better.",
        "Okay. I've had a minute to cool off, and I'm still a little warm.",
        "Team, today we didn't look like us. Let's talk about why.",
        "Folks, I've seen better days, and so have you.",
        "Sit down, take a breath. We're gonna have a real conversation.",
        "Well. That was a day I'd like to put in the shed and lock the door on.",
        "Look at me, everybody. Eyes up. We're not hiding from this one.",
        "I'm gonna say some tough stuff, and then I'm gonna say some hopeful stuff. Stick with me.",
        "We stunk it up today, y'all. I say that with love, but I say it.",
        "Today the wheels came off the wagon, and the horse wandered off too.",
    ],
    "mid": [
        "Alright, huddle up. Mixed bag today, like a box of assorted chocolates.",
        "Team, today was a little bit of everything.",
        "Bring it in. We had some highs, some lows, and some 'what was that?'s.",
        "Okay, family meeting. Today had peaks and valleys.",
        "Well, today was like weather in Kansas: a little of everything by dinner.",
        "Gather round the campfire. Let's talk about a perfectly middling day.",
        "Today was a rough draft. Good bones, needs editing.",
        "Team, I've got good news and I've got homework.",
        "Huddle up. Today we were almost there, and almost is a starting point.",
        "Pull up a seat. We're gonna celebrate a little and fix a little.",
        "Alright, today we were the definition of 'it's complicated.'",
        "Gather 'round. Some of today was art, and some of it was finger-painting.",
    ],
    "high": [
        "Somebody get me a microphone, because this deserves an announcement.",
        "Y'all! Bring it in! I've got the biggest smile in the county!",
        "Gather round, champs. Tonight we talk about how good you were.",
        "Oh, team. Oh, team. What a day.",
        "I'd do a cartwheel if my knees would let me.",
        "Grab a seat and get comfortable, because I've got a lot of nice things to say.",
        "That was the most fun I've had since the county fair had a pie-eating contest.",
        "Bring it in tight. I want to hug every one of you, but let's start with words.",
        "Today you made an old coach feel young.",
        "Somebody check the record books, because something special happened today.",
        "Gather up, superstars. And yes, I mean all of you.",
        "Today was a masterpiece, and I'm just here to hang it on the wall.",
    ],
}

RECAP = [
    "Here's the scorecard: {games} games, {W} {W_w}, {D} {D_w}, {L} {L_w}. Goals: {gf} for, {ga} against.",
    "By the numbers, {games} matches, {W} {W_w}, {D} {D_w}, {L} {L_w}, {gf} scored, {ga} conceded.",
    "We played {games} today and came away with {W} {W_w}, {D} {D_w} and {L} {L_w}. {gf} goals for, {ga} against.",
    "Tale of the tape: {games} games, {gf} goals scored, {ga} let in. {W} {W_w}, {D} {D_w}, {L} {L_w}.",
    "{games} games. {W} {W_w}. {D} {D_w}. {L} {L_w}. {gf} goals in their net, {ga} in ours.",
    "The ledger says {games} played, {W} {W_w}, {D} {D_w}, {L} {L_w}, with {gf} scored and {ga} conceded.",
    "Today's box score: {W} {W_w}, {D} {D_w}, {L} {L_w} over {games} games. {gf} for and {ga} against.",
    "We went {W}-{D}-{L} across {games} games, scoring {gf} and giving up {ga}.",
    "Numbers first, feelings second: {games} games, {gf} scored, {ga} allowed, {W} {W_w}, {D} {D_w}, {L} {L_w}.",
    "{games} matches in the books. {W} {W_w}, {D} {D_w}, {L} {L_w}. {gf} goals for, {ga} against.",
    "Final tally: {W} {W_w}, {D} {D_w} and {L} {L_w} from {games} games, {gf} goals to {ga}.",
    "Let's read the receipt: {games} games, {gf} for, {ga} against, {W} {W_w}, {D} {D_w}, {L} {L_w}.",
]

BEST = [
    "The highlight was that {score} against {opp}. That's the template.",
    "Let's talk about the {score} over {opp}. That's who we are when we're humming.",
    "Remember the {score} against {opp}? Bottle that and drink it daily.",
    "The {score} win over {opp} was football the way it's supposed to look.",
    "That {score} against {opp}? I'd frame it if they sold frames that big.",
    "Our best moment: {score} over {opp}. Pure joy.",
    "The {score} versus {opp} showed what we look like when everybody's tuned in.",
    "When we beat {opp} {score}, I felt like a proud papa at a recital.",
    "That {score} over {opp} was a clinic. Let's teach it to ourselves again.",
    "The {score} against {opp} is the game I'll show the next new player.",
    "Our {score} win over {opp} was a thing of beauty.",
    "Look at the {score} over {opp}. That's the blueprint.",
]

WORST = [
    "The {score} against {opp} is the one we learn from. Bring a notebook.",
    "{opp} got us {score}, and I want us to remember how that felt.",
    "That {score} to {opp}? We'll study it like a pop quiz.",
    "The {score} against {opp} was a gut punch. We'll get our breath back.",
    "Let's be honest about the {score} to {opp}. We beat ourselves a little.",
    "The {score} loss to {opp} showed us exactly what to fix.",
    "That {score} against {opp} stung. Stings are reminders, not definitions.",
    "We'll file the {score} against {opp} under 'lessons, expensive.'",
    "The {score} to {opp} is the game we'll be thinking about at practice.",
    "{opp} beat us {score}. Credit them, then correct us.",
    "That {score} to {opp} was the low point, and low points are launch points.",
    "The {score} against {opp}? Learn it, then let it go like a balloon.",
]

CORE = {
    "low": [
        "We got outworked in spots today, and that's the one thing I won't accept from a team this good.",
        "When things went sideways, we went quiet. Quiet teams lose. Loud teams find a way.",
        "We kept trying the hero pass when the simple one was sitting right there.",
        "Our shape went walkabout. When we lose the ball, we sprint back together or we don't sprint at all.",
        "Too many of us were playing our own game instead of our team's game.",
        "We let one bad goal turn into two, and two turn into a mood. That's the habit to break.",
        "I saw heads drop after mistakes. Heads up is free, and it's the cheapest fix in football.",
        "We didn't win our duels. When the ball's fifty-fifty, it's gotta be ours sixty percent of the time.",
        "We were sloppy with the ball and soft without it. That's a rough combination.",
        "The effort was there in flashes. Flashes don't win days; full-time effort does.",
        "We stopped trusting each other a little. Trust is a muscle; we're gonna work it.",
        "Today we forgot the basics: talk, move, support. Basics win.",
    ],
    "mid": [
        "We were good enough to win more and sloppy enough to not. That's the gap to close.",
        "The talent's there. The consistency is the next brick in the wall.",
        "We had moments where we looked unbeatable and moments where we looked lost. Let's keep the first kind.",
        "Some games we controlled, some games controlled us. We want to be the steering wheel, not the passenger.",
        "We played well in patches, like a quilt with a few squares missing.",
        "We're right on the edge of something good. Just need to stop tripping on the doorstep.",
        "When we kept it simple, we cooked. When we got fancy, we burned the toast.",
        "Effort was solid. Execution needs a polish.",
        "The difference between our wins and our losses today was focus, plain and simple.",
        "We showed fight. Now let's add a little finesse.",
        "Middling days are where good teams quietly become great ones. This is that day.",
        "Some of our best football and some of our worst football came on the same day. Let's pick one.",
    ],
    "high": [
        "Everybody did their job, and then a little extra. That's the secret sauce.",
        "We moved the ball like it was on a string. Beautiful.",
        "We defended as a unit and attacked as a unit. That's a team.",
        "The talking was great today. I heard you all the way from the sideline, and I loved it.",
        "You played fearless. Fearless and smart is a dangerous combination for the other team.",
        "Every time somebody made a mistake, somebody else had their back. That's family.",
        "We were sharper than a brand-new pencil.",
        "Today we played the way I dream about on Sunday nights.",
        "You made the hard things look easy and the easy things look automatic.",
        "We controlled games instead of chasing them. That's maturity.",
        "We were relentless, and relentless wins.",
        "You played for each other, and it showed in every touch.",
    ],
}

STORY = {
    "low": [
        "My granddaddy planted a peach tree that didn't fruit for three years. Year four, we had peaches till Christmas. Patience.",
        "You ever watch a baby learn to walk? Falls down a hundred times and never once thinks about quitting. Be the baby.",
        "Back home the creek floods every spring, and every spring the town cleans up and has a picnic. Tomorrow's the picnic.",
        "My old truck stalled every winter morning. I never sold it. I just learned how to warm it up. We'll warm up.",
        "Somebody once told me the darkest part of the night is right before the bakery opens. Smell that? Bread's coming.",
        "My mama burned the Thanksgiving turkey one year. We had pancakes instead, and it's still the best Thanksgiving I remember.",
        "Ever notice a kite flies against the wind, not with it? We're flying tonight.",
        "A farmer doesn't quit after one bad harvest. He checks the soil and plants again.",
        "I once got lost driving to a game and found the best barbecue joint in three counties. Wrong turns lead somewhere.",
    ],
    "mid": [
        "There's a fella back home who fixes clocks. Says most of 'em aren't broken, just need a little oil. We need a little oil.",
        "My aunt makes a chili that's good on day one and great on day two. We're a day-one chili right now.",
        "A sculptor once said the statue's already in the rock; you just chip away the extra. We're chipping.",
        "Rain makes the corn grow. Today was a little rain.",
        "Ever do a puzzle and have the edges done but the middle's a mess? That's us. The edges are done.",
        "My dog learned to fetch on his fortieth try. Now he won't stop. Repetition, y'all.",
        "A good pie needs time in the oven. Pull it too early and it's soup. We're still baking.",
        "My first bike had training wheels for a month longer than I'd like to admit. Then one day, off they came.",
        "The town choir sounds rough at first rehearsal and beautiful by Christmas. We're in October.",
    ],
    "high": [
        "When I was a kid, the whole town would come out when the high school won. Tonight, I'm the whole town.",
        "You know that feeling when the fireworks finish and everybody just goes 'wow'? That.",
        "My mama used to say some days you just leave the porch light on because something good's coming home. You came home.",
        "There's a song I play when I'm happy, and I'm gonna play it the whole drive home.",
        "If today were a pie, I'd enter it at the state fair and win the blue ribbon and the red one too.",
        "I once saw a double rainbow over a cornfield and thought I'd never see anything prettier. I was wrong. I saw today.",
        "Ever catch a fish so big you don't even care about the picture? I care about the picture. Smile, everybody.",
        "My granddaddy said you'll know your team's special when they make the hard stuff look like recess. Recess today, y'all.",
        "There's a saying back home: when the cornbread rises, don't open the oven. I'm not opening the oven.",
    ],
}

FOCUS = [
    "Our one fix for next time: {issue}. {tip}",
    "If we take one thing to practice, it's {issue}. {tip}",
    "Top of the to-do list: {issue}. {tip}",
    "The thing that'll move the needle most is {issue}. {tip}",
    "Let's attack {issue} next. {tip}",
    "Coach's homework is {issue}. {tip}",
    "We'll sharpen {issue} first. {tip}",
    "Priority number one: {issue}. {tip}",
    "Here's our project: {issue}. {tip}",
    "The quickest path to better is {issue}. {tip}",
    "Next match, all eyes on {issue}. {tip}",
    "Let's make {issue} a strength. {tip}",
]

TABLE = [
    "On the ladder: {spoken}. Every match is a step.",
    "Ladder check: {spoken}. Keep climbing.",
    "Here's where we stand: {spoken}.",
    "League update: {spoken}. I like where we're pointed.",
    "As for the ladder, {spoken}. One game at a time.",
    "Big picture: {spoken}. Eyes up, feet moving.",
    "The ladder tells it plain: {spoken}.",
    "Where are we? {spoken}. Let's keep going.",
    "Standing check: {spoken}. Good things ahead.",
    "On the climb: {spoken}. We're built for this.",
    "Our spot on the ladder: {spoken}.",
    "The league table says {spoken}. Here we go.",
]

TEAMWORK = {
    "low": [
        "Credit where it's due: {a} and {b} still combined for {n} goals. That's our foundation.",
        "{a} and {b} found each other {n} times. When the rest of us join in, look out.",
        "Even today, {a} and {b} made {n} goals happen together. Build around that.",
        "{n} goals between {a} and {b}. The spark's there; we need the whole fire.",
        "{a} and {b} were a bright spot with {n} goals. Let's add more lights.",
        "Bright side: {a} and {b}, {n} goals. Partnerships like that turn days around.",
        "{a} and {b} kept us in it with {n} goals. More of that, from all of us.",
        "{n} goals from {a} and {b}. The bones are good.",
    ],
    "mid": [
        "{a} and {b}, {n} goals between you. Keep finding each other.",
        "{n} goals came from {a} and {b} working together. That's the model.",
        "{a} and {b} were the engine with {n} goals.",
        "Loved the {a}-{b} connection: {n} goals.",
        "{a} and {b} put {n} past the opposition. Feed that partnership.",
        "{n} goals for the {a} and {b} show. Great chemistry.",
        "{a} and {b}, {n} goals. That's a duo I want to see more of.",
        "The {a} and {b} combo was worth {n} goals today.",
    ],
    "high": [
        "{a} and {b}, {n} goals. Y'all were like two hands clapping.",
        "{n} goals from {a} and {b}. If chemistry were a class, you'd ace it.",
        "{a} and {b} combined for {n}. That partnership is a five-star restaurant.",
        "{a} and {b}: {n} goals. Somebody write a country song about it.",
        "{n} goals between {a} and {b}. Batman and Robin, but both are Batman.",
        "{a} and {b} put up {n}. That's a highlight reel all by itself.",
        "{a} and {b}, {n} goals. You two were peaches and cream.",
        "{n} goals for {a} and {b}. Telepathy, I swear.",
    ],
}

RALLY = {
    "low": [
        "We're gonna come back from this, and the comeback is gonna be fun.",
        "Remember: the scoreboard resets tomorrow. Our character doesn't need to.",
        "This team has more heart than a valentine shop. Use it.",
        "Bad days are where good teams decide who they are. Decide with me.",
        "I'm not worried. I'm excited to see the response.",
        "Tomorrow we go back to basics and back to believing.",
        "You're too good to stay down. I know it, and soon the league will too.",
        "One day doesn't write the season. We hold the pen.",
    ],
    "mid": [
        "We're a couple of good habits away from a great run.",
        "Keep the effort, sharpen the details, and watch what happens.",
        "Good teams get better on days like this.",
        "We're building something, and buildings take time.",
        "I like this group. I like our chances.",
        "Let's turn 'almost' into 'absolutely.'",
        "Tomorrow, let's be a little braver and a little smarter.",
        "We're right there. Let's go take it.",
    ],
    "high": [
        "Remember this feeling. It's the fuel for the next one.",
        "You earned every bit of tonight's joy.",
        "This is what happens when a team believes.",
        "Let's not get comfortable; let's get consistent.",
        "Celebrate tonight, sharpen tomorrow.",
        "The sky's the limit, and I'm not sure there is one.",
        "Stay humble, stay hungry, stay together.",
        "That's the standard now. Let's keep it.",
    ],
}

CLOSE = {
    "low": [
        "Go home, rest, and come back ready. I'll be here, and so will the belief.",
        "Tomorrow's a fresh page. Bring your best pencil.",
        "I love this team. That's not changing, win or lose.",
        "Rest up, reset, return. We go again.",
        "Be a goldfish about the scoreline and an elephant about the lessons.",
        "Tonight we rest. Tomorrow we rise.",
        "Keep your chin up. I'm keeping mine up for you.",
        "We'll get it right. I promise you that.",
    ],
    "mid": [
        "Good work, honest work. Let's sharpen it up and go again.",
        "Proud of the effort. Hungry for the results.",
        "Rest those legs and those heads. Big things ahead.",
        "Tomorrow, let's finish what we started.",
        "Keep believing, keep working, keep smiling.",
        "One step at a time, and we're stepping forward.",
        "Love the fight. Let's add the finish.",
        "Rest up. We've got more to give.",
    ],
    "high": [
        "Go celebrate, you earned it. Then get some sleep, champions.",
        "I'm the proudest coach in the world tonight.",
        "What a day. Thank you for letting me watch it.",
        "That's championship football. Let's make it a habit.",
        "Go home happy. You made a lot of people proud.",
        "Enjoy it. Days like this are why we play.",
        "Biscuits for everyone, and a good night's sleep.",
        "Believe it, because I sure do.",
    ],
}


def merge(daily):
    """Extend the pools in fcapp.daily in place (append-only)."""
    for name, extra in globals().items():
        if not name.isupper() or not hasattr(daily, name):
            continue
        pool = getattr(daily, name)
        if isinstance(pool, list):
            pool.extend(x for x in extra if x not in pool)
        elif isinstance(pool, dict):
            for key, lines in extra.items():
                if key in pool:
                    pool[key].extend(x for x in lines if x not in pool[key])
