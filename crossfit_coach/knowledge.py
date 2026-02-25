"""CrossFit L1/L2 knowledge base - movements, equipment, scaling, programming principles."""

from crossfit_coach.models import MovementCategory

# --- Equipment catalog with common aliases ---

EQUIPMENT_CATALOG = {
    "barbell": {"aliases": ["barra", "bar"], "description": "Olympic barbell (20kg men / 15kg women)"},
    "dumbbells": {"aliases": ["mancuernas", "db"], "description": "Pair of dumbbells"},
    "kettlebell": {"aliases": ["kb", "pesa rusa"], "description": "Kettlebell"},
    "pull_up_bar": {"aliases": ["barra dominadas", "rig"], "description": "Pull-up bar or rig"},
    "rings": {"aliases": ["anillas", "gymnastic rings"], "description": "Gymnastic rings"},
    "jump_rope": {"aliases": ["comba", "speed rope"], "description": "Jump rope / speed rope"},
    "box": {"aliases": ["cajón", "plyo box"], "description": "Plyo box (20\"/24\")"},
    "rower": {"aliases": ["remo", "concept2"], "description": "Rowing machine"},
    "bike": {"aliases": ["assault bike", "echo bike", "air bike"], "description": "Assault/Echo bike"},
    "wall_ball": {"aliases": ["balón medicinal", "med ball"], "description": "Wall ball (14/20 lbs)"},
    "rope": {"aliases": ["cuerda", "climbing rope"], "description": "Climbing rope"},
    "bands": {"aliases": ["gomas", "resistance bands"], "description": "Resistance bands"},
    "parallettes": {"aliases": ["paralelas"], "description": "Parallettes for gymnastics"},
    "plates": {"aliases": ["discos", "bumper plates"], "description": "Weight plates"},
    "squat_rack": {"aliases": ["rack", "jaula"], "description": "Squat rack or power cage"},
    "bench": {"aliases": ["banco"], "description": "Flat/incline bench"},
    "ab_mat": {"aliases": ["colchoneta"], "description": "AbMat for sit-ups"},
    "ghd": {"aliases": ["glute ham developer"], "description": "GHD machine"},
    "ski_erg": {"aliases": ["skierg"], "description": "SkiErg machine"},
    "sled": {"aliases": ["trineo"], "description": "Push/pull sled"},
    "sandbag": {"aliases": ["saco de arena"], "description": "Sandbag"},
    "none": {"aliases": ["nada", "bodyweight", "peso corporal"], "description": "No equipment needed"},
}

# --- Movement library based on CrossFit L1/L2 ---

MOVEMENTS = [
    # === MONOSTRUCTURAL (Cardio) ===
    {
        "name": "Run",
        "category": MovementCategory.MONOSTRUCTURAL,
        "equipment_needed": "none",
        "difficulty": 1,
        "points_of_performance": "Midfoot strike, upright torso, arm drive, consistent pace",
        "scaling_options": "Walk/run intervals; reduce distance",
    },
    {
        "name": "Row",
        "category": MovementCategory.MONOSTRUCTURAL,
        "equipment_needed": "rower",
        "difficulty": 2,
        "points_of_performance": "Drive with legs first, then hips, then arms. Reverse on recovery. Damper 3-6",
        "scaling_options": "Reduce distance/calories; lower stroke rate",
    },
    {
        "name": "Bike (Assault/Echo)",
        "category": MovementCategory.MONOSTRUCTURAL,
        "equipment_needed": "bike",
        "difficulty": 2,
        "points_of_performance": "Seated, steady RPM, push and pull with arms",
        "scaling_options": "Reduce calories; lower RPM",
    },
    {
        "name": "Single Unders",
        "category": MovementCategory.MONOSTRUCTURAL,
        "equipment_needed": "jump_rope",
        "difficulty": 1,
        "points_of_performance": "Wrists drive rotation, slight bounce, stay on balls of feet",
        "scaling_options": "Lateral hops without rope",
    },
    {
        "name": "Double Unders",
        "category": MovementCategory.MONOSTRUCTURAL,
        "equipment_needed": "jump_rope",
        "difficulty": 5,
        "points_of_performance": "Higher jump, faster wrist rotation (2 passes per jump), midline tight",
        "scaling_options": "3x single unders; attempts + single unders",
        "l2_progressions": "Triple unders; crossovers",
    },
    # === GYMNASTICS (Bodyweight) ===
    {
        "name": "Air Squat",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "none",
        "difficulty": 1,
        "points_of_performance": "Below parallel, weight in heels, chest up, knees track toes",
        "scaling_options": "Squat to box/target; hold onto rig",
    },
    {
        "name": "Push-Up",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "none",
        "difficulty": 2,
        "points_of_performance": "Full lockout at top, chest to deck, rigid midline, elbows at 45°",
        "scaling_options": "Knee push-ups; incline push-ups on box; hand-release push-ups",
    },
    {
        "name": "Pull-Up (Strict)",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "pull_up_bar",
        "difficulty": 4,
        "points_of_performance": "Dead hang start, chin over bar, full lockout at bottom",
        "scaling_options": "Banded pull-ups; ring rows; jumping pull-ups",
        "l2_progressions": "Weighted strict pull-ups",
    },
    {
        "name": "Kipping Pull-Up",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "pull_up_bar",
        "difficulty": 5,
        "points_of_performance": "Kip swing (arch/hollow), chin over bar, aggressive push-away",
        "scaling_options": "Banded kipping; jumping pull-ups; ring rows",
        "l2_progressions": "Butterfly pull-ups",
    },
    {
        "name": "Toes-to-Bar",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "pull_up_bar",
        "difficulty": 6,
        "points_of_performance": "Kip swing, toes touch bar simultaneously, controlled descent",
        "scaling_options": "Knees-to-elbows; hanging knee raises; V-ups on floor",
    },
    {
        "name": "Handstand Push-Up",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "none",
        "difficulty": 7,
        "points_of_performance": "Kicking up to wall, head touches ground, full lockout at top, tripod position",
        "scaling_options": "Pike push-ups on box; DB press; wall walks",
        "l2_progressions": "Strict HSPU; deficit HSPU; freestanding HSPU",
    },
    {
        "name": "Muscle-Up (Bar)",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "pull_up_bar",
        "difficulty": 9,
        "points_of_performance": "Aggressive kip, pull high, fast transition, lockout at top",
        "scaling_options": "Chest-to-bar pull-ups + dips; banded muscle-ups; jumping MU transitions",
        "l2_progressions": "Strict bar muscle-ups",
    },
    {
        "name": "Muscle-Up (Ring)",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "rings",
        "difficulty": 9,
        "points_of_performance": "False grip, kip, deep catch, turnout at top",
        "scaling_options": "Strict pull-ups + ring dips; banded ring MU; transitions on low rings",
        "l2_progressions": "Strict ring muscle-ups",
    },
    {
        "name": "Dip (Ring)",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "rings",
        "difficulty": 5,
        "points_of_performance": "Shoulder below elbow at bottom, full lockout, turnout at top",
        "scaling_options": "Box dips; banded ring dips; matador dips",
    },
    {
        "name": "Pistol (Single-Leg Squat)",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "none",
        "difficulty": 6,
        "points_of_performance": "Full depth on one leg, non-working leg extended, stand to full extension",
        "scaling_options": "Pistol to box; assisted with band/post; lunges",
    },
    {
        "name": "Burpee",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "none",
        "difficulty": 2,
        "points_of_performance": "Chest to deck, jump and clap overhead, full hip extension at top",
        "scaling_options": "Step-back burpees; no push-up burpees; elevated surface",
    },
    {
        "name": "Box Jump",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "box",
        "difficulty": 3,
        "points_of_performance": "Two-foot takeoff, land with full foot on box, stand to full extension",
        "scaling_options": "Step-ups; lower box height; box jump step-down",
    },
    {
        "name": "Sit-Up",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "ab_mat",
        "difficulty": 1,
        "points_of_performance": "Butterfly position, arms overhead at bottom, touch toes at top",
        "scaling_options": "Crunches; reduce range of motion",
    },
    {
        "name": "Wall Walk",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "none",
        "difficulty": 4,
        "points_of_performance": "Start in push-up, walk feet up wall and hands back, nose to wall, return controlled",
        "scaling_options": "Partial wall walks; inchworms; pike on box",
    },
    {
        "name": "Rope Climb",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "rope",
        "difficulty": 6,
        "points_of_performance": "Wrap and clamp foot lock, pull with arms, stand on rope, touch top",
        "scaling_options": "Rope pull from floor; strict pull-ups; lying rope climb",
    },
    {
        "name": "L-Sit",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "parallettes",
        "difficulty": 5,
        "points_of_performance": "Arms locked, legs parallel to floor, pointed toes",
        "scaling_options": "Tucked L-sit; one leg extended; L-hang from bar",
    },
    {
        "name": "Lunge",
        "category": MovementCategory.GYMNASTICS,
        "equipment_needed": "none",
        "difficulty": 2,
        "points_of_performance": "Knee touches ground, front shin vertical, torso upright, full hip extension at top",
        "scaling_options": "Reduce range of motion; hold support",
    },
    # === WEIGHTLIFTING (External load) ===
    {
        "name": "Back Squat",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell,squat_rack",
        "difficulty": 3,
        "points_of_performance": "Bar on traps, below parallel, knees track toes, chest up, drive through heels",
        "scaling_options": "Front squat; goblet squat; air squat",
        "l2_progressions": "Pause squat; tempo squat; box squat",
    },
    {
        "name": "Front Squat",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell,squat_rack",
        "difficulty": 4,
        "points_of_performance": "Elbows high, bar in front rack, below parallel, upright torso",
        "scaling_options": "Goblet squat; DB front squat",
        "l2_progressions": "Pause front squat; 1¼ front squat",
    },
    {
        "name": "Overhead Squat",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 6,
        "points_of_performance": "Wide grip, bar over mid-foot, active shoulders, below parallel",
        "scaling_options": "PVC/empty bar; DB overhead squat; front squat",
        "l2_progressions": "Snatch balance; pause OHS",
    },
    {
        "name": "Deadlift",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 3,
        "points_of_performance": "Flat back, bar close to body, drive through heels, hips and shoulders rise together",
        "scaling_options": "KB/DB deadlift; reduce weight; sumo deadlift",
        "l2_progressions": "Deficit deadlift; pause deadlift; Romanian deadlift",
    },
    {
        "name": "Press (Shoulder Press)",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 2,
        "points_of_performance": "Strict, no leg drive, bar from shoulders to overhead, full lockout, head through",
        "scaling_options": "DB press; reduce weight",
        "l2_progressions": "Z-press; tempo press",
    },
    {
        "name": "Push Press",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 3,
        "points_of_performance": "Dip-drive with legs, press bar overhead, full lockout",
        "scaling_options": "DB push press; reduce weight",
    },
    {
        "name": "Push Jerk",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 5,
        "points_of_performance": "Dip-drive, press under bar, catch with slightly bent knees, stand to full extension",
        "scaling_options": "Push press; DB push jerk",
        "l2_progressions": "Split jerk",
    },
    {
        "name": "Clean (Power)",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 5,
        "points_of_performance": "First pull (floor to knee), second pull (explosive hip extension), catch in front rack above parallel",
        "scaling_options": "Hang power clean; DB power clean; KB clean; muscle clean",
    },
    {
        "name": "Clean (Squat)",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 7,
        "points_of_performance": "Same as power clean but receive bar in full front squat, stand to full extension",
        "scaling_options": "Power clean; hang squat clean",
        "l2_progressions": "Clean complex; pause clean",
    },
    {
        "name": "Snatch (Power)",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 7,
        "points_of_performance": "Wide grip, first pull, explosive second pull, catch overhead above parallel",
        "scaling_options": "Hang power snatch; DB snatch; muscle snatch",
    },
    {
        "name": "Snatch (Squat)",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 9,
        "points_of_performance": "Wide grip, pull under bar, receive in overhead squat, stand to full extension",
        "scaling_options": "Power snatch; hang squat snatch; OHS as separate",
        "l2_progressions": "Snatch complex; pause snatch; snatch from blocks",
    },
    {
        "name": "Thruster",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 4,
        "points_of_performance": "Front squat + push press in one movement, full depth, full lockout overhead",
        "scaling_options": "DB thrusters; KB thrusters; wall ball (similar pattern); reduce weight",
    },
    {
        "name": "Sumo Deadlift High Pull",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 3,
        "points_of_performance": "Wide stance, narrow grip, explosive hip extension, elbows high and outside",
        "scaling_options": "KB SDHP; reduce weight",
    },
    {
        "name": "Wall Ball",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "wall_ball",
        "difficulty": 3,
        "points_of_performance": "Full depth squat, throw ball to 10/9ft target, catch and immediately descend",
        "scaling_options": "Lighter ball; lower target; air squat + press",
    },
    {
        "name": "Kettlebell Swing",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "kettlebell",
        "difficulty": 2,
        "points_of_performance": "Hip hinge, explosive hip extension, arms are pendulum, American = overhead",
        "scaling_options": "Russian swing (eye level); lighter KB",
    },
    {
        "name": "Turkish Get-Up",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "kettlebell",
        "difficulty": 5,
        "points_of_performance": "Floor to standing with KB/DB locked overhead, eye on weight throughout",
        "scaling_options": "No weight; shoe on fist for practice; partial TGU",
    },
    {
        "name": "Dumbbell Snatch",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "dumbbells",
        "difficulty": 4,
        "points_of_performance": "One arm, floor to overhead in one motion, full hip extension",
        "scaling_options": "Lighter weight; DB hang snatch; DB clean and press",
    },
    {
        "name": "Goblet Squat",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "kettlebell",
        "difficulty": 2,
        "points_of_performance": "Hold KB/DB at chest, below parallel, elbows inside knees, chest up",
        "scaling_options": "Air squat; reduce weight",
    },
    {
        "name": "Farmer Carry",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "kettlebell",
        "difficulty": 2,
        "points_of_performance": "Heavy load in each hand, upright posture, tight midline, controlled walk",
        "scaling_options": "Lighter weight; shorter distance",
    },
    {
        "name": "Clean & Jerk",
        "category": MovementCategory.WEIGHTLIFTING,
        "equipment_needed": "barbell",
        "difficulty": 8,
        "points_of_performance": "Full clean to front rack, then split/push jerk to overhead lockout",
        "scaling_options": "Power clean + push press; DB clean & jerk",
        "l2_progressions": "Clean & split jerk complex",
    },
]


# --- Benchmark WODs (Girls, Heroes, and common tests) ---

BENCHMARK_WODS = {
    # The Girls
    "Fran": {
        "type": "for_time",
        "description": "21-15-9: Thrusters (95/65 lb) + Pull-Ups",
        "modalities": ["weightlifting", "gymnastics"],
        "equipment": ["barbell", "pull_up_bar"],
        "target_time": {"beginner": "10-15min", "intermediate": "5-8min", "advanced": "3-5min", "elite": "<3min"},
    },
    "Grace": {
        "type": "for_time",
        "description": "30 Clean & Jerks (135/95 lb)",
        "modalities": ["weightlifting"],
        "equipment": ["barbell"],
        "target_time": {"beginner": "8-12min", "intermediate": "4-6min", "advanced": "2-3min", "elite": "<2min"},
    },
    "Helen": {
        "type": "for_time",
        "description": "3 rounds: 400m Run + 21 KB Swings (53/35 lb) + 12 Pull-Ups",
        "modalities": ["monostructural", "weightlifting", "gymnastics"],
        "equipment": ["kettlebell", "pull_up_bar"],
        "target_time": {"beginner": "15-20min", "intermediate": "10-14min", "advanced": "8-10min", "elite": "<8min"},
    },
    "Diane": {
        "type": "for_time",
        "description": "21-15-9: Deadlifts (225/155 lb) + Handstand Push-Ups",
        "modalities": ["weightlifting", "gymnastics"],
        "equipment": ["barbell"],
        "target_time": {"beginner": "12-18min", "intermediate": "6-10min", "advanced": "3-5min", "elite": "<3min"},
    },
    "Isabel": {
        "type": "for_time",
        "description": "30 Snatches (135/95 lb)",
        "modalities": ["weightlifting"],
        "equipment": ["barbell"],
        "target_time": {"beginner": "10-15min", "intermediate": "5-8min", "advanced": "2-4min", "elite": "<2min"},
    },
    "Cindy": {
        "type": "amrap",
        "description": "20 min AMRAP: 5 Pull-Ups + 10 Push-Ups + 15 Air Squats",
        "modalities": ["gymnastics"],
        "equipment": ["pull_up_bar"],
        "target_rounds": {"beginner": "8-12", "intermediate": "15-20", "advanced": "20-25", "elite": "25+"},
    },
    "Annie": {
        "type": "for_time",
        "description": "50-40-30-20-10: Double Unders + Sit-Ups",
        "modalities": ["monostructural", "gymnastics"],
        "equipment": ["jump_rope", "ab_mat"],
        "target_time": {"beginner": "12-18min", "intermediate": "8-12min", "advanced": "5-7min", "elite": "<5min"},
    },
    # Heroes
    "Murph": {
        "type": "for_time",
        "description": "1 mile Run + 100 Pull-Ups + 200 Push-Ups + 300 Air Squats + 1 mile Run (with vest 20/14 lb)",
        "modalities": ["monostructural", "gymnastics"],
        "equipment": ["pull_up_bar"],
        "target_time": {"beginner": "55-70min", "intermediate": "40-55min", "advanced": "30-40min", "elite": "<30min"},
    },
    # Strength benchmarks
    "Back Squat 1RM": {"type": "strength", "description": "Find 1-Rep Max Back Squat"},
    "Deadlift 1RM": {"type": "strength", "description": "Find 1-Rep Max Deadlift"},
    "Press 1RM": {"type": "strength", "description": "Find 1-Rep Max Shoulder Press"},
    "Clean & Jerk 1RM": {"type": "strength", "description": "Find 1-Rep Max Clean & Jerk"},
    "Snatch 1RM": {"type": "strength", "description": "Find 1-Rep Max Snatch"},
}


# --- Programming principles from L2 ---

PROGRAMMING_PRINCIPLES = {
    "variance": (
        "Constantly varied functional movements performed at high intensity. "
        "Vary time domains (short <7min, medium 7-15min, long 15+min), "
        "modalities (M/G/W and combinations), loads, and rep schemes."
    ),
    "modality_balance": (
        "L1 defines 3 modalities: Monostructural (M), Gymnastics (G), Weightlifting (W). "
        "Program all combinations: M, G, W, MG, MW, GW, MGW. "
        "Roughly equal exposure over a mesocycle."
    ),
    "time_domains": {
        "short": "< 7 minutes - High power output, heavy or sprint",
        "medium": "7-15 minutes - Moderate intensity, mixed modality",
        "long": "15+ minutes - Endurance, pacing, mental toughness",
    },
    "intensity_before_volume": (
        "L1 principle: increase intensity before volume. "
        "Mechanics -> Consistency -> Intensity progression."
    ),
    "scaling": (
        "Every workout should be scalable. Adjust load, volume, range of motion, "
        "or movement complexity to preserve the intended stimulus."
    ),
    "periodization": {
        "mesocycle_weeks": 4,  # 3 weeks building + 1 deload
        "macrocycle_mesocycles": 3,  # 3 mesocycles = ~12 weeks
        "phases": [
            "Foundation: Build movement quality and aerobic base (weeks 1-4)",
            "Accumulation: Increase volume, add complexity (weeks 5-8)",
            "Intensification: Increase load and intensity, reduce volume (weeks 9-11)",
            "Realization/Test: Benchmark testing week (week 12)",
        ],
    },
    "daily_structure": (
        "Typical class structure (L1): "
        "Warm-up (5-10min) -> Strength/Skill (10-20min) -> WOD (5-20min) -> Cool-down (5min)"
    ),
    "recovery": (
        "Program rest days. 3 on / 1 off or 5 on / 2 off depending on level. "
        "Monitor RPE, sleep, soreness for auto-regulation."
    ),
}


# --- Equipment-based movement substitutions ---

MOVEMENT_SUBSTITUTIONS = {
    "barbell": {
        "Back Squat": ["Goblet Squat", "DB Front Squat", "Air Squat"],
        "Front Squat": ["Goblet Squat", "DB Front Squat"],
        "Deadlift": ["KB Deadlift", "DB Deadlift"],
        "Press": ["DB Press", "KB Press", "Push-Up (pike)"],
        "Push Press": ["DB Push Press", "KB Push Press"],
        "Clean (Power)": ["DB Power Clean", "KB Clean"],
        "Clean (Squat)": ["DB Power Clean", "KB Clean"],
        "Snatch (Power)": ["DB Snatch", "KB Snatch"],
        "Snatch (Squat)": ["DB Snatch", "KB Snatch"],
        "Thruster": ["DB Thruster", "KB Thruster", "Wall Ball"],
        "Clean & Jerk": ["DB Clean & Press"],
    },
    "pull_up_bar": {
        "Pull-Up (Strict)": ["DB Bent-Over Row", "Band Pull-Apart", "Inverted Row (table)"],
        "Kipping Pull-Up": ["DB Bent-Over Row", "Band Pull-Apart"],
        "Toes-to-Bar": ["V-Ups", "Sit-Ups", "Lying Leg Raises"],
        "Muscle-Up (Bar)": ["Burpee Pull-Up (if bar available)", "Push-Up + DB Row combo"],
    },
    "rings": {
        "Dip (Ring)": ["Box Dips", "Push-Ups", "Bench Dips"],
        "Muscle-Up (Ring)": ["Pull-Up + Dip", "Burpee Pull-Up"],
    },
    "box": {
        "Box Jump": ["Broad Jump", "Tuck Jump", "Step-Ups (on sturdy surface)"],
    },
    "rope": {
        "Rope Climb": ["Towel Pull-Ups", "Strict Pull-Ups (extra reps)"],
    },
    "rower": {
        "Row": ["Run", "Bike", "High Knees", "Burpees"],
    },
    "bike": {
        "Bike (Assault/Echo)": ["Run", "Row", "High Knees + Burpees"],
    },
    "jump_rope": {
        "Double Unders": ["Lateral Hops", "Tuck Jumps", "High Knees"],
        "Single Unders": ["High Knees", "Jumping Jacks"],
    },
    "wall_ball": {
        "Wall Ball": ["Thruster (light)", "Goblet Squat + Press"],
    },
    "ghd": {
        "GHD Sit-Up": ["AbMat Sit-Up", "V-Up"],
        "Hip Extension": ["Superman", "Good Morning"],
    },
}
