"""Basic 6 extension for the Lagos/NERDC-aligned 2026/2027 seed."""

from core.management.lagos_basic_2026_2027_data import SUBJECTS as PRIMARY_SUBJECTS


GRADE_SUBJECTS = {
    6: (
        "ENG", "MAT", "YOR", "BST", "PHE", "BDL", "CRS", "IRS",
        "HIS", "SCS", "CCA", "PVS", "FRE", "ARA",
    ),
}

SUBJECTS = {
    code: PRIMARY_SUBJECTS[code]
    for code in GRADE_SUBJECTS[6]
}

TOPIC_BANKS = {
    "ENG": {6: ("advanced comprehension", "summary writing", "vocabulary and registers", "parts of speech review", "complex sentences", "direct and reported speech", "concord and tense consistency", "figurative language", "formal correspondence", "argumentative writing", "literature appreciation", "public speaking and debate")},
    "MAT": {6: ("whole numbers and approximation", "factors and indices", "fractions and decimals", "ratio and proportion", "percentages and commercial arithmetic", "algebraic sentences", "plane shapes and constructions", "area volume and capacity", "coordinates and scale drawing", "speed distance and time", "statistics and probability", "multi-step problem solving")},
    "YOR": {6: ("advanced reading and pronunciation", "vocabulary and idioms", "grammar and sentence analysis", "comprehension and summary", "formal and informal letters", "argumentative composition", "Yoruba history and identity", "customs and civic values", "oral and written poetry", "proverbs and figurative language", "translation", "debate drama and literature")},
    "BST": {6: ("cells and living systems", "ecosystems and adaptation", "human development and health", "matter and chemical change", "water air and pollution", "electricity and magnetism", "energy transformation", "earth resources and space", "technical drawing and measurement", "machines structures and design", "ICT-supported investigations", "climate action and sustainability")},
    "PHE": {6: ("personal fitness planning", "athletics rules and performance", "team-sport tactics", "gymnastics and movement sequences", "adolescent reproductive health", "nutrition and lifestyle diseases", "communicable-disease control", "drug education", "recreation and leisure", "leadership and officiating", "first aid and emergency response", "community and environmental health")},
    "BDL": {6: ("computer architecture", "operating systems", "efficient keyboarding", "advanced document production", "spreadsheets and data", "multimedia presentations", "internet research", "cybersecurity and privacy", "digital collaboration", "algorithms and flowcharts", "block-based programming projects", "digital ethics and entrepreneurship")},
    "CRS": {6: ("creation purpose and stewardship", "covenant and faith", "leadership in the Old Testament", "prophets justice and hope", "birth and mission of Jesus", "teachings and parables", "discipleship and service", "moral decision making", "death and resurrection", "Holy Spirit and the church", "Christian unity and community", "integrity peace and citizenship")},
    "IRS": {6: ("tawhid and accountability", "prophets and revelation", "Qur'an preservation and guidance", "worship and intention", "salah and community", "fasting self-control and charity", "selected surahs and meaning", "hadith in daily conduct", "Islamic law rights and duties", "hajj and Muslim unity", "Islamic history and scholarship", "integrity peace and citizenship")},
    "HIS": {6: ("methods of historical inquiry", "early Nigerian societies", "kingdoms and empires", "inter-group relations and trade", "Atlantic slave trade", "legitimate trade and missions", "colonial conquest", "colonial administration", "nationalist movements", "independence and republican government", "military and civil eras", "nation building and heritage conservation")},
    "SCS": {6: ("identity goals and self-management", "family and social responsibility", "community participation", "constitution and rule of law", "culture diversity and inclusion", "peace building and mediation", "integrity and anti-corruption", "sustainable development", "personal and national security", "democratic institutions and elections", "patriotism and national unity", "human rights and civic duties")},
    "CCA": {6: ("design process", "painting and mixed media", "perspective and technical drawing", "graphics and visual communication", "music theory and composition", "ensemble and instrument performance", "dance choreography", "script writing and stage production", "Nigerian traditional crafts", "sculpture and construction", "portfolio exhibition", "creative enterprise and copyright")},
    "PVS": {6: ("career interests and work ethics", "farm budgeting and records", "crop production systems", "livestock and fisheries", "food preservation and processing", "home and resource management", "nutrition meal planning and service", "textile construction and repairs", "product design and packaging", "tools maintenance and quality control", "enterprise finance and marketing", "workplace safety and sustainable production")},
    "FRE": {6: ("pronunciation and listening", "social conversation", "numbers prices and transactions", "describing people and places", "daily routines", "school and future plans", "time travel and directions", "clothing health and weather", "food and hospitality", "letters and short messages", "comprehension and composition", "Francophone culture and presentations")},
    "ARA": {6: ("fluent reading and pronunciation", "vocabulary and expressions", "extended conversation", "numbers dates and transactions", "descriptive language", "verb forms and tense", "questions and sentence agreement", "functional writing", "short composition", "reading comprehension", "speech and recitation", "Arabic literature and culture")},
}


def validate_seed_data():
    for code in GRADE_SUBJECTS[6]:
        topics = TOPIC_BANKS.get(code, {}).get(6)
        if topics is None or len(topics) != 12:
            raise ValueError(f"Basic 6 {code} must define exactly 12 units.")

