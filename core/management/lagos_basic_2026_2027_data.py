"""Seed data for the Lagos/NERDC-aligned 2026/2027 primary curriculum.

The topic banks are an editable school working scheme.  The subject offering follows
the Federal Ministry of Education's revised Basic Education Curriculum, while term
dates follow the Lagos State 2026/2027 Approved Harmonised Academic Calendar.
"""

from datetime import date


ACADEMIC_YEAR = "2026-2027"

CURRICULUM_SOURCE_URL = (
    "https://nerdc.gov.ng/content_manager/new_curriculum_home.html"
)
SUBJECT_OFFERING_SOURCE_URL = (
    "https://education.gov.ng/wp-content/uploads/2025/09/"
    "FG-OVERHAULS-CURRICULUM-1.pdf"
)
CALENDAR_SOURCE_URL = (
    "https://edunile.ng/school-calendar/lagos-2026-2027"
)


SUBJECTS = {
    "ENG": "English Studies",
    "MAT": "Mathematics",
    "YOR": "Yoruba Language",
    "BSC": "Basic Science",
    "BST": "Basic Science and Technology",
    "PHE": "Physical and Health Education",
    "CRS": "Christian Religious Studies",
    "IRS": "Islamic Religious Studies",
    "HIS": "Nigerian History",
    "SCS": "Social and Citizenship Studies",
    "CCA": "Cultural and Creative Arts",
    "BDL": "Basic Digital Literacy",
    "PVS": "Pre-Vocational Studies",
    "FRE": "French Language (Optional)",
    "ARA": "Arabic Language (Optional)",
}

GRADE_SUBJECTS = {
    1: ("ENG", "MAT", "YOR", "BSC", "PHE", "CRS", "IRS", "HIS", "SCS", "CCA", "ARA"),
    2: ("ENG", "MAT", "YOR", "BSC", "PHE", "CRS", "IRS", "HIS", "SCS", "CCA", "ARA"),
    3: ("ENG", "MAT", "YOR", "BSC", "PHE", "CRS", "IRS", "HIS", "SCS", "CCA", "ARA"),
    4: ("ENG", "MAT", "YOR", "BST", "PHE", "BDL", "CRS", "IRS", "HIS", "SCS", "CCA", "PVS", "FRE", "ARA"),
    5: ("ENG", "MAT", "YOR", "BST", "PHE", "BDL", "CRS", "IRS", "HIS", "SCS", "CCA", "PVS", "FRE", "ARA"),
}


# Twelve teachable units per subject and grade. The command divides each bank into
# four units per term and renders them as a week-by-week syllabus.
TOPIC_BANKS = {
    "ENG": {
        1: ("letter sounds", "simple greetings", "three-letter words", "picture reading", "handwriting strokes", "naming words", "short oral sentences", "rhymes", "action words", "simple punctuation", "guided composition", "story retelling"),
        2: ("sound blends", "everyday vocabulary", "reading short passages", "capital letters", "common nouns", "pronouns", "present-tense verbs", "sentence building", "question words", "descriptive words", "guided paragraphs", "listening comprehension"),
        3: ("vowels and consonants", "word families", "reading for main ideas", "dictionary order", "proper and common nouns", "verb tenses", "subject and predicate", "punctuation in dialogue", "adjectives and adverbs", "informal letters", "paragraph writing", "oral presentations"),
        4: ("reading fluency", "context clues", "main and supporting ideas", "parts of speech", "simple and compound sentences", "direct speech", "verb agreement", "comprehension inference", "formal and informal letters", "narrative writing", "descriptive writing", "debate and oral expression"),
        5: ("critical reading", "summarising passages", "figurative expressions", "advanced parts of speech", "sentence transformation", "reported speech", "concord", "vocabulary in context", "letter and email writing", "expository writing", "creative writing", "speech and debate"),
    },
    "MAT": {
        1: ("counting 0-20", "number recognition", "ordering numbers", "shapes", "addition within 10", "subtraction within 10", "length comparison", "money recognition", "numbers to 100", "simple fractions", "time to the hour", "picture graphs"),
        2: ("numbers to 1000", "place value", "addition with regrouping", "subtraction with regrouping", "multiplication as groups", "division as sharing", "halves and quarters", "measuring length", "Nigerian money", "time and calendar", "plane shapes", "simple data tables"),
        3: ("whole numbers to 10000", "place value and estimation", "four operations", "multiplication tables", "division with remainders", "equivalent fractions", "decimal tenths", "perimeter", "mass and capacity", "angles and shapes", "time intervals", "bar charts"),
        4: ("whole numbers to millions", "factors and multiples", "long multiplication", "long division", "fractions and mixed numbers", "decimals", "percentages", "area and perimeter", "metric measures", "angles and symmetry", "coordinates", "data and probability"),
        5: ("large numbers and approximation", "prime factors", "operations with fractions", "decimal operations", "ratio and proportion", "percentages in daily life", "algebraic expressions", "area and volume", "geometry constructions", "time and speed", "graphs and averages", "practical problem solving"),
    },
    "YOR": {
        1: ("alphabet and sounds", "greetings", "numbers 1-20", "family names", "simple words", "body parts", "home objects", "songs and rhymes", "colours", "market vocabulary", "short sentences", "folktale listening"),
        2: ("tone marks", "extended greetings", "numbers to 100", "days and months", "word formation", "school vocabulary", "food and farming words", "simple reading", "sentence construction", "proverbs", "guided writing", "oral storytelling"),
        3: ("vowel harmony", "tones in words", "reading short texts", "parts of speech", "Yoruba names and meanings", "occupations", "community vocabulary", "sentence patterns", "traditional greetings", "proverbs and riddles", "short composition", "folktales"),
        4: ("fluent reading", "tone and pronunciation", "grammar in sentences", "comprehension", "letter writing", "descriptive composition", "Yoruba customs", "festivals", "oral poetry", "proverbs", "translation of simple texts", "drama and storytelling"),
        5: ("advanced reading", "vocabulary development", "grammar and syntax", "summary", "formal letters", "narrative composition", "history of Yoruba people", "values and etiquette", "poetry appreciation", "idioms and proverbs", "translation", "debate and drama"),
    },
    "BSC": {
        1: ("living and non-living things", "parts of the body", "the five senses", "plants around us", "animals around us", "air", "water", "soil", "weather", "light and shadows", "simple machines at home", "personal safety"),
        2: ("characteristics of living things", "plant parts", "animal groups", "human growth", "sources and uses of water", "air in motion", "types of soil", "sun and weather", "sound", "heat", "simple tools", "care of the environment"),
        3: ("life cycles", "plant needs", "animal habitats", "human body systems", "water cycle", "air and combustion", "soil formation", "weather records", "light", "forces and motion", "energy sources", "environmental sanitation"),
    },
    "BST": {
        4: ("classification of living things", "adaptation", "human body and health", "matter and materials", "water purification", "air pressure", "soil conservation", "weather instruments", "energy forms", "forces and simple machines", "basic technology processes", "environmental responsibility"),
        5: ("ecosystems and food chains", "reproduction and growth", "nutrition and body systems", "states and changes of matter", "mixtures and separation", "electricity and circuits", "renewable energy", "earth and space", "measurement and design", "machines and maintenance", "technology and society", "climate and sustainability"),
    },
    "PHE": {
        1: ("body awareness", "walking and running", "jumping and hopping", "safe play", "personal hygiene", "healthy foods", "rest and sleep", "simple games", "rhythm and movement", "posture", "first-aid awareness", "home and road safety"),
        2: ("movement patterns", "balance", "throwing and catching", "playground rules", "cleanliness", "food groups", "disease prevention", "team games", "dance", "fitness exercises", "simple first aid", "road signs"),
        3: ("locomotor skills", "coordination", "athletics basics", "football basics", "personal and dental health", "balanced diet", "communicable diseases", "recreation", "traditional dance", "physical fitness", "first-aid box", "water and traffic safety"),
        4: ("fitness components", "track and field", "ball games", "gymnastics", "puberty and hygiene", "nutrition", "disease control", "drug-safety awareness", "dance and recreation", "teamwork and sportsmanship", "first-aid procedures", "community safety"),
        5: ("fitness assessment", "athletics techniques", "football and basketball", "gymnastics sequences", "adolescent health", "healthy lifestyle choices", "disease prevention", "substance-abuse prevention", "recreational planning", "leadership in sports", "emergency response", "environmental health"),
    },
    "CRS": {
        1: ("God as creator", "creation care", "God's love", "the family", "obedience", "kindness", "prayer", "Bible stories", "sharing", "forgiveness", "Christmas", "thankfulness"),
        2: ("creation and responsibility", "God's promises", "call of Abraham", "family values", "the birth of Jesus", "childhood of Jesus", "teachings of Jesus", "prayer", "honesty", "service", "Easter", "peaceful living"),
        3: ("God's covenant", "Moses and leadership", "the commandments", "David's courage", "prophets", "birth and ministry of Jesus", "parables", "miracles", "love of neighbour", "death and resurrection", "the early church", "Christian character"),
        4: ("creation stewardship", "faith of patriarchs", "leadership lessons", "law and justice", "prophetic messages", "life of Jesus", "kingdom parables", "discipleship", "compassion", "crucifixion and resurrection", "Holy Spirit", "responsible citizenship"),
        5: ("purpose and stewardship", "covenant and faith", "wise leadership", "justice and mercy", "messianic hope", "ministry of Jesus", "Christian service", "conflict resolution", "moral choices", "resurrection hope", "church and community", "integrity"),
    },
    "IRS": {
        1: ("Allah as creator", "care for creation", "Islamic greetings", "the family", "cleanliness", "kindness", "simple supplications", "short surahs", "sharing", "truthfulness", "Ramadan awareness", "gratitude"),
        2: ("oneness of Allah", "prophets", "Prophet Ibrahim", "family duties", "life of Prophet Muhammad", "cleanliness and wudu", "daily prayers", "short surahs", "honesty", "charity", "Ramadan", "peaceful living"),
        3: ("articles of faith", "selected prophets", "Qur'an revelation", "five pillars", "salah", "fasting", "selected surahs", "hadith on conduct", "respect for parents", "charity", "Islamic festivals", "good character"),
        4: ("tawhid", "prophethood", "Qur'an guidance", "pillars of Islam", "prayer practice", "fasting and discipline", "selected surahs", "hadith studies", "justice", "zakat and service", "hajj awareness", "responsible citizenship"),
        5: ("faith and accountability", "lives of prophets", "preservation of the Qur'an", "worship and intention", "congregational prayer", "Ramadan values", "selected surahs", "hadith and daily life", "rights and responsibilities", "charity", "Islamic history", "integrity and peace"),
    },
    "HIS": {
        1: ("meaning of history", "personal history", "family history", "community elders", "important family events", "local landmarks", "traditional occupations", "community leaders", "Lagos symbols", "national symbols", "past and present", "protecting heritage"),
        2: ("sources of history", "family trees", "oral tradition", "community origins", "local heroes", "old and new occupations", "traditional rulers", "Lagos communities", "Nigerian peoples", "national heroes", "independence", "heritage sites"),
        3: ("historical evidence", "migration stories", "early settlements", "traditional institutions", "trade in old communities", "Lagos history", "Nigerian kingdoms", "European contact", "amalgamation", "nationalism", "independence leaders", "preserving artefacts"),
        4: ("history and chronology", "archaeological and oral sources", "Nigerian ancient centres", "Yoruba city states", "Benin and Kanem-Borno", "trans-Saharan and coastal trade", "Lagos colony", "amalgamation of Nigeria", "colonial rule", "nationalist movements", "independence", "post-independence milestones"),
        5: ("historical inquiry", "Nok and early societies", "major Nigerian kingdoms", "inter-group relations", "slave trade", "legitimate trade", "missionaries and education", "colonial administration", "nationalism", "independence and republic", "civil rule and nation building", "heritage conservation"),
    },
    "SCS": {
        1: ("self and identity", "family members", "school community", "rules", "friendship", "respect", "helping others", "clean environment", "road safety", "community workers", "national symbols", "rights and duties"),
        2: ("personal identity", "family roles", "school responsibilities", "community groups", "good manners", "cooperation", "honesty", "environmental care", "traffic rules", "leadership", "Nigeria and its symbols", "child rights"),
        3: ("individual differences", "family values", "community services", "rules and laws", "culture", "teamwork", "integrity", "resources and conservation", "safety and security", "local government", "national unity", "rights and responsibilities"),
        4: ("identity and diversity", "social institutions", "community development", "law and order", "Nigerian cultures", "cooperation and conflict", "values and consequences", "environmental citizenship", "personal safety", "democratic leadership", "national identity", "human and child rights"),
        5: ("self-management", "family and society", "civic participation", "constitution and rule of law", "cultural diversity", "peace building", "corruption and integrity", "sustainable communities", "security awareness", "democratic institutions", "unity and patriotism", "rights with responsibilities"),
    },
    "CCA": {
        1: ("lines and shapes", "primary colours", "drawing familiar objects", "paper craft", "songs", "rhythm", "movement", "simple drama", "local patterns", "clay modelling", "festive art", "art appreciation"),
        2: ("shape composition", "colour mixing", "nature drawing", "collage", "folk songs", "beat and tempo", "creative movement", "role play", "textile patterns", "modelling", "puppetry", "display and appreciation"),
        3: ("elements of art", "colour values", "observational drawing", "printmaking", "melody", "musical notation basics", "dance patterns", "story dramatisation", "traditional crafts", "papier-mache", "costume and props", "art critique"),
        4: ("design principles", "painting techniques", "still-life drawing", "print and pattern", "voice and melody", "notation and instruments", "traditional and modern dance", "script and performance", "weaving and crafts", "sculpture", "costume design", "exhibition and critique"),
        5: ("creative design", "painting and mixed media", "perspective drawing", "graphic communication", "composition in music", "ensemble performance", "dance choreography", "play production", "Nigerian crafts", "sculpture and construction", "portfolio development", "arts enterprise"),
    },
    "BDL": {
        4: ("digital devices", "parts of a computer", "safe start-up and shutdown", "keyboard and mouse skills", "word processing", "file and folder management", "drawing applications", "internet basics", "online safety", "digital communication", "simple algorithms", "responsible technology use"),
        5: ("computer systems", "input and output devices", "operating-system navigation", "typing proficiency", "document formatting", "data organisation", "presentation tools", "search and information literacy", "privacy and cyber safety", "email etiquette", "block-based coding", "digital citizenship"),
    },
    "PVS": {
        4: ("meaning of work", "agricultural occupations", "soil and simple tools", "crop planting", "animal care", "home management", "food hygiene", "clothing care", "simple crafts", "measuring and making", "entrepreneurial habits", "workplace safety"),
        5: ("career awareness", "farm planning", "crop production", "livestock management", "food processing", "home resource management", "nutrition and meal planning", "textiles and repairs", "product design", "tools and maintenance", "saving and small enterprise", "safety and environmental care"),
    },
    "FRE": {
        4: ("French alphabet and sounds", "greetings", "numbers", "self-introduction", "family", "classroom objects", "days and months", "colours", "food", "simple questions", "short reading", "songs and culture"),
        5: ("pronunciation review", "extended greetings", "numbers and prices", "describing people", "home and family", "school routines", "time and calendar", "clothing and colours", "meals", "directions", "short messages", "Francophone culture"),
    },
    "ARA": {
        1: ("Arabic letter shapes", "letter sounds", "greetings", "numbers 1-10", "classroom words", "family words", "colours", "matching letters", "tracing", "simple oral phrases", "songs", "picture vocabulary"),
        2: ("joined letters", "short vowels", "greetings and responses", "numbers to 20", "school vocabulary", "home vocabulary", "colours and shapes", "simple words", "copy writing", "short phrases", "rhymes", "guided reading"),
        3: ("alphabet fluency", "long and short vowels", "everyday conversation", "numbers to 100", "people and places", "days and months", "adjectives", "sentence patterns", "handwriting", "short passages", "oral presentation", "cultural expressions"),
        4: ("reading fluency", "vowel marks", "introductions", "number and time expressions", "school and community", "family descriptions", "common verbs", "simple grammar", "paragraph copying", "comprehension", "dialogue", "Arabic-speaking cultures"),
        5: ("accurate recitation and reading", "vocabulary building", "daily conversation", "dates and prices", "descriptive language", "verb patterns", "question forms", "sentence agreement", "short composition", "reading comprehension", "speech practice", "culture and literature"),
    },
}


TERM_NAMES = ("First Term", "Second Term", "Third Term")

TERMS = (
    {
        "name": "First Term",
        "start_date": date(2026, 9, 14),
        "end_date": date(2026, 12, 18),
        "vacation_date": date(2026, 12, 21),
        "resumption_date": date(2027, 1, 11),
        "school_opened_days": 64,
    },
    {
        "name": "Second Term",
        "start_date": date(2027, 1, 11),
        "end_date": date(2027, 4, 16),
        "vacation_date": date(2027, 4, 19),
        "resumption_date": date(2027, 5, 3),
        "school_opened_days": 61,
    },
    {
        "name": "Third Term",
        "start_date": date(2027, 5, 3),
        "end_date": date(2027, 7, 30),
        "vacation_date": date(2027, 8, 2),
        "resumption_date": None,
        "school_opened_days": 57,
    },
)


# start and end dates are inclusive. A term name links the event to that term;
# events outside instructional dates intentionally have no term link.
EVENTS = (
    ("Staff Professional Development Window", "activity", date(2026, 9, 7), date(2026, 9, 11), None, "Schools select any two days in this window."),
    ("First Term Resumption", "activity", date(2026, 9, 14), date(2026, 9, 14), "First Term", "Learners resume for the 2026/2027 session."),
    ("First Term Primary Open Day", "meeting", date(2026, 10, 29), date(2026, 10, 29), "First Term", "Mandatory primary-school Open Day; timing is set by the school."),
    ("First Term Mid-Term Break", "holiday", date(2026, 11, 2), date(2026, 11, 6), "First Term", "Lagos State harmonised mid-term break."),
    ("First Term Vacation", "holiday", date(2026, 12, 21), date(2027, 1, 8), None, "Vacation before Second Term."),
    ("Second Term Resumption", "activity", date(2027, 1, 11), date(2027, 1, 11), "Second Term", "Learners resume for Second Term."),
    ("Second Term Primary Open Day", "meeting", date(2027, 2, 18), date(2027, 2, 18), "Second Term", "Mandatory primary-school Open Day; timing is set by the school."),
    ("Second Term Mid-Term Break", "holiday", date(2027, 2, 22), date(2027, 2, 26), "Second Term", "Lagos State harmonised mid-term break."),
    ("Second Term Vacation", "holiday", date(2027, 4, 19), date(2027, 4, 30), None, "Vacation before Third Term."),
    ("Third Term Resumption", "activity", date(2027, 5, 3), date(2027, 5, 3), "Third Term", "Learners resume for Third Term."),
    ("Third Term Primary Open Day", "meeting", date(2027, 6, 10), date(2027, 6, 10), "Third Term", "Mandatory primary-school Open Day; timing is set by the school."),
    ("Third Term Mid-Term Break", "holiday", date(2027, 6, 14), date(2027, 6, 18), "Third Term", "Lagos State harmonised mid-term break."),
    ("End of 2026/2027 Session", "activity", date(2027, 7, 30), date(2027, 7, 30), "Third Term", "Final instructional day of the academic session."),
    ("Long Vacation Begins", "holiday", date(2027, 8, 2), date(2027, 8, 2), None, "Long vacation begins."),
)


HOLIDAYS = (
    ("Independence Day", date(2026, 10, 1)),
    ("Eid-el-Fitr - Day 1", date(2027, 3, 10)),
    ("Eid-el-Fitr - Day 2", date(2027, 3, 11)),
    ("Good Friday", date(2027, 3, 26)),
    ("Easter Monday", date(2027, 3, 29)),
    ("Workers' Day", date(2027, 5, 1)),
    ("Eid-el-Kabir - Day 1", date(2027, 5, 17)),
    ("Eid-el-Kabir - Day 2", date(2027, 5, 18)),
    ("Children's Day", date(2027, 5, 27)),
    ("Democracy Day", date(2027, 6, 12)),
)


def validate_seed_data():
    """Fail fast if an edited topic bank no longer matches the seed contract."""
    for grade, subject_codes in GRADE_SUBJECTS.items():
        for code in subject_codes:
            topics = TOPIC_BANKS.get(code, {}).get(grade)
            if topics is None:
                raise ValueError(f"Missing topic bank for Basic {grade} {code}.")
            if len(topics) != 12:
                raise ValueError(
                    f"Basic {grade} {code} must define exactly 12 units; found {len(topics)}."
                )

