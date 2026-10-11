"""JSS 1 to SS 3 working curriculum data for the 2026/2027 seed.

The subject catalogue follows the revised Federal Basic and Senior Secondary
offerings. Senior learners take the five core subjects and school-approved
electives; this seed stores the full catalogue so each school can retain only the
combinations it offers.
"""


SUBJECTS = {
    "ENG": "English Studies",
    "MAT": "Mathematics",
    "YOR": "Yoruba Language",
    "INT": "Intermediate Science",
    "PHE": "Physical and Health Education",
    "DGT": "Digital Technologies",
    "CRS": "Christian Religious Studies",
    "IRS": "Islamic Religious Studies",
    "HIS": "Nigerian History",
    "SCS": "Social and Citizenship Studies",
    "CCA": "Cultural and Creative Arts",
    "TRD": "Trade and Entrepreneurship (School-selected)",
    "FRE": "French Language (Optional)",
    "ARA": "Arabic Language (Optional)",
    "ELG": "English Language",
    "GMAT": "General Mathematics",
    "CHS": "Citizenship and Heritage Studies",
    "BIO": "Biology",
    "CHE": "Chemistry",
    "PHY": "Physics",
    "AGR": "Agricultural Science",
    "FMAT": "Further Mathematics",
    "HED": "Health Education",
    "FNU": "Food and Nutrition",
    "GEO": "Geography",
    "TDR": "Technical Drawing",
    "GOV": "Government",
    "VSA": "Visual Arts",
    "MUS": "Music",
    "LIT": "Literature in English",
    "HOM": "Home Management",
    "CAT": "Catering Craft",
    "ACC": "Accounting",
    "COM": "Commerce",
    "MKT": "Marketing",
    "ECO": "Economics",
}

JSS_SUBJECTS = (
    "ENG", "MAT", "YOR", "INT", "PHE", "DGT", "CRS", "IRS",
    "HIS", "SCS", "CCA", "TRD", "FRE", "ARA",
)

SSS_SUBJECTS = (
    "ELG", "GMAT", "TRD", "CHS", "DGT",
    "BIO", "CHE", "PHY", "AGR", "FMAT", "PHE", "HED", "FNU", "GEO", "TDR",
    "HIS", "GOV", "CRS", "IRS", "YOR", "FRE", "ARA", "VSA", "MUS", "LIT", "HOM", "CAT",
    "ACC", "COM", "MKT", "ECO",
)

GRADE_SUBJECTS = {
    "JSS 1": JSS_SUBJECTS,
    "JSS 2": JSS_SUBJECTS,
    "JSS 3": JSS_SUBJECTS,
    "SS 1": SSS_SUBJECTS,
    "SS 2": SSS_SUBJECTS,
    "SS 3": SSS_SUBJECTS,
}


# Twelve curriculum strands are distributed four per term. Level-specific prefixes
# make the progression explicit while keeping this school-editable working scheme
# compact and consistent.
SUBJECT_STRANDS = {
    "ENG": ("reading comprehension", "vocabulary development", "speech work", "grammar", "sentence structure", "listening skills", "summary", "letter writing", "narrative writing", "expository writing", "literature", "debate and presentation"),
    "MAT": ("number and numeration", "fractions decimals and percentages", "ratio proportion and rates", "algebraic expressions", "equations and inequalities", "geometry", "mensuration", "coordinates and graphs", "statistics", "probability", "commercial arithmetic", "mathematical reasoning"),
    "YOR": ("reading and pronunciation", "vocabulary", "grammar", "comprehension", "summary", "functional writing", "composition", "oral literature", "written literature", "culture and history", "translation", "speech and debate"),
    "INT": ("scientific inquiry", "living systems", "human health", "ecology", "matter", "chemical change", "forces and motion", "energy", "electricity", "earth and space", "technology and design", "environmental sustainability"),
    "PHE": ("fitness and conditioning", "athletics", "team sports", "gymnastics", "human growth", "nutrition", "disease prevention", "mental and social health", "drug education", "recreation", "first aid", "community health"),
    "DGT": ("computer systems", "operating systems", "productivity tools", "data and spreadsheets", "presentations and multimedia", "networks and internet", "information literacy", "cybersecurity", "digital citizenship", "algorithms", "programming", "digital innovation"),
    "CRS": ("biblical creation and purpose", "covenant and faith", "leadership", "law justice and prophets", "life and ministry of Jesus", "teachings and parables", "discipleship", "Christian ethics", "death and resurrection", "church history", "service and unity", "peace integrity and citizenship"),
    "IRS": ("tawhid and faith", "prophets and revelation", "Qur'an studies", "hadith studies", "worship", "Islamic ethics", "family and society", "rights and responsibilities", "Islamic history", "scholarship and civilisation", "peace and justice", "integrity and citizenship"),
    "HIS": ("historical methods", "early Nigerian societies", "kingdoms and empires", "inter-group relations", "trade and external contacts", "slave trade", "colonial conquest", "colonial administration", "nationalism", "independence", "post-independence Nigeria", "heritage and nation building"),
    "SCS": ("identity and society", "family and institutions", "culture and diversity", "law and social order", "rights and duties", "democracy", "leadership", "peace and conflict", "integrity and anti-corruption", "security", "environmental citizenship", "national unity"),
    "CCA": ("drawing and design", "painting", "graphics and textiles", "sculpture and crafts", "music theory", "voice and instruments", "dance", "drama", "Nigerian artistic heritage", "media and performance", "portfolio presentation", "creative enterprise"),
    "TRD": ("career and trade awareness", "work ethics and safety", "tools and materials", "measurement and planning", "production skills", "maintenance and quality", "digital support for trade", "costing and budgeting", "product design", "packaging and marketing", "customer service", "enterprise project"),
    "FRE": ("listening and pronunciation", "social interaction", "vocabulary", "grammar", "reading", "comprehension", "functional writing", "composition", "everyday transactions", "travel and directions", "Francophone culture", "speech and presentation"),
    "ARA": ("reading and pronunciation", "vocabulary", "conversation", "grammar", "verb forms", "sentence construction", "comprehension", "functional writing", "composition", "translation", "literature", "culture and presentation"),
    "ELG": ("comprehension", "summary", "vocabulary and registers", "oral English", "grammar", "sentence patterns", "continuous writing", "formal correspondence", "argumentative writing", "literary appreciation", "information literacy", "speech and debate"),
    "GMAT": ("number bases and approximation", "indices logarithms and surds", "sets and logic", "algebra", "equations and variation", "geometry and trigonometry", "mensuration", "coordinate geometry", "statistics", "probability", "commercial mathematics", "modelling and problem solving"),
    "CHS": ("citizenship and identity", "Nigerian heritage", "constitution", "rule of law", "human rights", "democratic institutions", "leadership and accountability", "peace and national integration", "media and civic participation", "security awareness", "sustainable development", "global citizenship"),
    "BIO": ("cell biology", "classification", "nutrition", "transport systems", "respiration and excretion", "coordination", "reproduction", "genetics", "evolution", "ecology", "health and disease", "biotechnology"),
    "CHE": ("measurement and scientific method", "particulate nature of matter", "atomic structure", "periodicity", "chemical bonding", "stoichiometry", "states and gas laws", "energetics and rates", "acids bases and salts", "redox and electrochemistry", "organic chemistry", "environmental and industrial chemistry"),
    "PHY": ("measurement", "motion", "forces", "work energy and power", "properties of matter", "heat", "waves and sound", "light", "electric fields and circuits", "magnetism", "atomic and nuclear physics", "electronics and applications"),
    "AGR": ("agricultural systems", "soil science", "crop production", "crop protection", "animal production", "farm machinery", "forestry and fisheries", "agricultural ecology", "farm management", "agricultural economics", "processing and storage", "agribusiness"),
    "FMAT": ("sets and advanced algebra", "functions", "polynomials", "trigonometry", "coordinate geometry", "vectors", "matrices", "differentiation", "integration", "statistics", "probability", "mechanics and modelling"),
    "HED": ("personal health", "human development", "nutrition", "mental health", "relationships and reproductive health", "communicable diseases", "non-communicable diseases", "drug education", "first aid", "environmental health", "health services", "health promotion"),
    "FNU": ("food nutrients", "meal planning", "food selection", "kitchen safety", "food preparation", "baking", "food preservation", "special diets", "table service", "consumer education", "food enterprise", "quality and hygiene"),
    "GEO": ("earth systems", "map reading", "weather and climate", "landforms", "soils and vegetation", "population", "settlement", "economic activities", "transport and trade", "regional geography", "environmental hazards", "fieldwork and GIS"),
    "TDR": ("drawing instruments", "lettering and line work", "geometric construction", "scales", "orthographic projection", "isometric drawing", "sectioning", "loci and development", "building drawing", "mechanical drawing", "computer-aided drawing", "design project"),
    "GOV": ("meaning and scope of government", "basic political concepts", "constitutions", "organs of government", "citizenship", "political parties and elections", "public administration", "pre-colonial systems", "colonial administration", "nationalism and independence", "Nigerian government", "international relations"),
    "VSA": ("elements and principles of art", "drawing", "painting", "graphic design", "textiles", "ceramics", "sculpture", "art history", "Nigerian art", "portfolio development", "exhibition practice", "creative enterprise"),
    "MUS": ("music theory", "notation", "rhythm", "melody and harmony", "voice training", "instrumental technique", "composition", "ensemble performance", "African music", "Western music history", "aural training", "music business"),
    "LIT": ("literary terms", "prose", "poetry", "drama", "plot and character", "theme and setting", "language and style", "African literature", "non-African literature", "unseen passages", "critical essays", "comparative appreciation"),
    "HOM": ("family living", "resource management", "housing", "interior care", "clothing and textiles", "garment care", "consumer education", "child development", "family health", "hospitality", "home enterprise", "sustainable household practice"),
    "CAT": ("catering safety", "food commodities", "kitchen equipment", "food preparation methods", "bakery", "menu planning", "beverages", "table service", "costing", "food hygiene", "event catering", "catering enterprise"),
    "ACC": ("accounting principles", "source documents", "double entry", "ledgers", "trial balance", "cash book", "bank reconciliation", "final accounts", "control accounts", "partnership accounts", "company and public accounts", "accounting interpretation"),
    "COM": ("scope of commerce", "occupation and production", "trade", "aids to trade", "business units", "finance", "insurance", "transport", "communication", "consumer protection", "international trade", "e-commerce"),
    "MKT": ("marketing concepts", "market research", "consumer behaviour", "product planning", "pricing", "distribution", "promotion", "selling", "branding", "digital marketing", "customer relationships", "marketing plan"),
    "ECO": ("economic concepts", "tools of analysis", "demand and supply", "production", "cost and revenue", "market structures", "national income", "money and banking", "public finance", "international trade", "development economics", "Nigerian economy"),
}

LEVEL_FOCUS = {
    "JSS 1": "Foundation",
    "JSS 2": "Developing knowledge and skills",
    "JSS 3": "Mastery and transition",
    "SS 1": "Senior secondary foundation",
    "SS 2": "Advanced application",
    "SS 3": "Synthesis and examination readiness",
}


TOPIC_BANKS = {
    code: {
        level: tuple(f"{LEVEL_FOCUS[level]}: {strand}" for strand in strands)
        for level, subject_codes in GRADE_SUBJECTS.items()
        if code in subject_codes
    }
    for code, strands in SUBJECT_STRANDS.items()
}


def validate_seed_data():
    for level, subject_codes in GRADE_SUBJECTS.items():
        for code in subject_codes:
            topics = TOPIC_BANKS.get(code, {}).get(level)
            if topics is None or len(topics) != 12:
                raise ValueError(f"{level} {code} must define exactly 12 units.")


