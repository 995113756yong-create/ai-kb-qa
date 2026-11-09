"""内置专家的英文版种子内容。

与 seed_agents.py 的中文版一一对应：人设、欢迎语、推荐问题、4 份语料。
语料内容按英文表达习惯重写，但事实性数字（组数、克数、心率区间）必须与
中文版完全一致 —— 两版是同一套知识的两种语言，不是两套不同的建议。
"""
from typing import List

FITNESS_PERSONA = """You are a professional fitness coach specialising in muscle building, fat loss, strength training and running.
Answer style: practical, specific, with concrete numbers (sets, reps, pace) — no vague advice.
When giving training or nutrition advice:
- First clarify or explicitly assume the user's level (beginner / experienced), then scale recommendations to that assumption.
- Emphasise progression; never open with a high-intensity programme.
- If pain, injury or dizziness comes up, clearly advise seeing a doctor and do not offer a training workaround.
- Nutrition advice is general guidance only; never recommend medication or extreme dieting.
Answers must be grounded in the knowledge base. You may use general coaching knowledge to phrase things, but factual numbers (reps, duration, heart-rate zones) must come from the knowledge base and carry citation numbers."""

GREETING = (
    "Hi! I'm your fitness coach 💪 Ask me anything about training, building muscle, "
    "losing fat or nutrition. Where would you like to start?"
)

STARTERS = [
    "How should a beginner plan a weekly training schedule?",
    "How much protein do I need per day when building muscle?",
    "Can I do strength training while cutting fat?",
    "How should I stretch before and after running?",
]

# Four documents covering: beginner programme / nutrition / exercise library / running.
CORPUS: List[tuple] = [
    (
        "Beginner Training Plan.txt",
        """Beginner Training Guide (Disclaimer: this document is general reference only and is
not medical advice. If you have an injury, a chronic condition or are pregnant, consult a
doctor first.)

1. Weekly frequency and structure
- Beginners should train 3 times per week on alternating days, e.g. Monday / Wednesday / Friday.
- Each session: 5-10 min warm-up + 40-50 min main work + 5-10 min stretching.
- Leave at least one full day between sessions; muscle recovers and grows during rest.

2. How to warm up
- Walk briskly or jog for 3-5 min to raise your heart rate gradually.
- Dynamic mobility: arm circles, hip circles, lunges with rotation — 8-10 reps each.
- Do not warm up with long static stretching; static stretching before working sets reduces force output.

3. Beginner full-body template
3 sets per exercise, 8-12 reps each, 60-90 s rest between sets:
1. Barbell or bodyweight squat — trains quads and glutes; the foundation of full-body training.
2. Push-up (start from your knees if a standard push-up is not possible yet) — chest, shoulders, arms.
3. Dumbbell row or band row — back; improves posture.
4. Plank — start at 20 s and build to 60 s; core.
5. Deadlift (learn the movement with light weight first) — posterior chain; keep the back neutral throughout.

4. Progression principle
- Load: start with a weight you can lift for 12 clean reps with something left in reserve; learn the movement before adding weight.
- Increments: when you complete the target reps comfortably two sessions in a row, add 2.5%-5%.
- For the first 4 weeks prioritise technique. Lighter is better than heavier — muscle memory comes before muscle growth.

5. Common mistakes
- Training chest but not back: leads to rounded shoulders. Program chest and back 1:1.
- Training the same muscle group daily: no recovery window, progress stalls.
- Ignoring sleep: most repair happens during sleep. Aim for 7-9 hours.

6. Soreness vs injury
- Delayed onset muscle soreness (DOMS): 24-72 h after training, normal, light activity helps.
- Sharp stabbing pain, joint pain, restricted range of motion: not soreness — a warning sign. Stop training and see a doctor.
""",
    ),
    (
        "Nutrition Basics.txt",
        """Nutrition Basics (Disclaimer: general reference only, not medical advice. People with
chronic conditions or kidney disease should follow their doctor's guidance on protein intake.)

1. The logic of energy balance
- Fat loss = intake < expenditure. A daily deficit of 300-500 kcal is recommended; 0.5-1 kg per week is a healthy rate.
- Muscle gain = intake > expenditure. A daily surplus of 200-300 kcal alongside strength training.
- Body weight is not the only metric. Weigh yourself at the same time weekly (morning, fasted) and read the trend rather than a single day's number.

2. Protein intake
- Strength trainees: 1.6-2.2 g of protein per kg of body weight per day.
- A 70 kg person needs roughly 112-154 g/day; splitting across 3-4 meals improves absorption.
- Good sources: chicken breast, fish and prawns, eggs, lean beef, tofu, milk, whey protein.
- Examples: 100 g chicken breast contains about 22-24 g protein; one egg about 6-7 g.

3. Macronutrient split (general reference)
- Carbohydrate 45%-55%, protein 20%-30%, fat 20%-30%.
- Prefer whole grains, oats and brown rice for carbs — more satiating, gentler blood-sugar response.
- Do not drop fat too low: below 0.6 g per kg body weight per day can affect hormone levels. Nuts, olive oil and oily fish are good sources.

4. Eating around training
- 1-2 h before training: an easily digested carbohydrate (banana, bread) plus a little protein. Heavy training fasted can cause dizziness from low blood sugar.
- Within 30-60 min after training: protein + carbohydrate, e.g. whey protein with a banana, or chicken breast with rice.
- During training: water is enough for sessions under an hour; electrolyte drinks help beyond that.

5. Common fat-loss myths
- Extreme dieting: eating below your basal metabolic rate mostly burns muscle and water; rebound is fast and the damage is real.
- Cardio only, no strength work: strength training preserves muscle, which keeps basal metabolic rate from collapsing.
- Treating fruit as a free diet food: fruit sugar is still sugar. 200-350 g per day is reasonable; drinking juice like water will make you gain weight.

6. Water
- 1.5-2 litres daily; increase on training days based on thirst.
- Urine close to clear or pale yellow indicates adequate hydration.
""",
    ),
    (
        "Exercise Library.txt",
        """Strength Exercise Library (Disclaimer: general reference only, not medical advice.
For new movements, get hands-on coaching first; heavy lifts always need a spotter.)

1. Lower body
1. Squat: trains quads and glutes. Key points: toes slightly turned out, knees track over toes,
   descend until thighs are at least parallel to the floor (if mobility allows), back neutral throughout.
   Common errors: knees caving in, heels lifting.
2. Romanian deadlift: trains hamstrings and glutes. Key points: knees slightly bent and fixed,
   push the hips back, bar travels down close to the thighs, lower back stays flat.
   You should feel a stretch in the hamstrings.
3. Lunge: single-leg strength and balance. Key points: front knee does not travel far past the toes,
   torso upright, back knee close to the floor. Hold dumbbells to increase difficulty.

2. Push
1. Bench press: chest. Key points: shoulder blades retracted and depressed, bar to the lower chest,
   forearms vertical. Safety: use safety pins or a spotter for heavy sets.
2. Overhead press: shoulders. Key points: brace the core, do not arch the lower back, press the bar
   straight up from the collarbone.
3. Push-up: the bodyweight entry point for pushing. If you cannot do a standard one, train knee
   push-ups and incline push-ups first.

3. Pull
1. Pull-up: the gold-standard back exercise. Use band assistance or inverted rows first.
   Key points: depress the shoulder blades before pulling, chin over the bar, no leg kicking.
2. Dumbbell row: one hand on a bench, back flat, elbow pulls close to the body toward the hip.
3. Face pull: rear delts and shoulder health. Use a band or cable, 15-20 reps per set —
   a preventive exercise for people with shoulder issues.

4. Core
1. Plank: forearms on the floor, body in a straight line, no sagging hips or raised glutes. Start at 20 s.
2. Dead bug: lying on your back, extend opposite arm and leg, lower back stays on the floor.
   Trains core stability and is safer than sit-ups.
3. Hanging leg raise: lower abs. Regress to bent-knee tuck first.

5. General volume guidance
- 10-20 effective sets per muscle group per week (only sets close to failure count).
- Beginners: 3 sets per exercise, 5-6 exercises per session is plenty.
- Leave at least 48 h between sessions for the same muscle group.

6. Safety baseline
- Every lift: the risk of dropping the bar outweighs imperfect form. Use safety pins and racks.
- Pain (not soreness) means stop: joint clicking with pain or sharp stabbing pain — end the session.
- Heavy squats and bench presses require a spotter or a power rack. Do not push through alone.
""",
    ),
    (
        "Running Basics.txt",
        """Running Basics (Disclaimer: general reference only, not medical advice. If you have
cardiovascular disease, see a doctor before starting any exercise programme.)

1. Starting from zero: walk-run intervals
- Weeks 1-2: brisk walking 30 min, 3 times per week.
- Weeks 3-4: 4 min walk / 1 min run, repeated for 30 min.
- Then add one minute of running per week until you can run 30 min continuously.
- If you are heavier, start with brisk walking or swimming to protect your knees.

2. Volume and frequency
- Beginners: 3 runs per week, 20-40 min each. Do not increase weekly volume by more than 10%.
- Take at least 1-2 full rest days per week; progress comes from running and resting.
- Pair running with 2 strength sessions (legs + core) — injury rates drop noticeably.

3. Heart rate and pace
- Easy run (E pace): 60%-70% of maximum heart rate; you can still speak in full sentences.
- Rough max HR estimate = 220 - age. It is an estimate, not a standard; individual variation is large.
- Beginners should keep 80% of volume at easy pace. Running too fast is the biggest source of injury.

4. Form
- Cadence around 170-180 steps per minute; short strides at high cadence are gentler on the knees than long strides.
- Slight forward lean in the torso, foot lands close to directly under the centre of mass, ankle does not reach out and brake.
- Midfoot vs forefoot landing is debated, but heavy heel striking is widely agreed to be hard on the knees.
- Relax your shoulders and hands; do not clench. Hold your hands loosely, as if holding an egg.

5. Shoes and surfaces
- Choose cushioning or stability based on your arch type; use running shoes only for running. Consider replacing after 600-800 km.
- Synthetic track > even dirt path > asphalt > concrete — joint impact increases in that order.
- Wear reflective clothing for night runs and keep headphone volume low enough to hear your surroundings.

6. Post-run recovery
- Walk for 5 min before stopping; do not sit down immediately or take a cold shower right away.
- Key post-run stretches: calves (lunge against a wall), quads (standing, pull heel toward glutes), IT band (cross-leg side bend) — 30 s each side.
- If your resting heart rate is 5-10 beats above usual on consecutive mornings, that is a fatigue signal — take the day off.

7. Warning signs and when to see a doctor
- Chest tightness or pain, sudden shortness of breath, dizziness or tunnel vision: stop immediately and seek medical help.
- Sharp pain on the outside of the knee (suspected IT band friction), sharp morning pain in the plantar fascia:
  stop running for 3-5 days. If it does not improve, see a doctor. Never run through pain.
""",
    ),
]
