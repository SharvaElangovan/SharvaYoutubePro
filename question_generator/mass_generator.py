#!/usr/bin/env python3
"""
Mass Question Generator for SharvaYoutubePro
Generates millions of questions using local Mistral via Ollama
"""

import json
import sqlite3
import os
import sys
import requests
import re
import time
import random
from pathlib import Path
import threading

# Database path (Tauri uses the app identifier)
DB_PATH = os.path.expanduser("~/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db")
OLLAMA_URL = "http://localhost:11434/api/generate"

db_lock = threading.Lock()

# MASSIVE topic database with hundreds of subtopics
ALL_TOPICS = {
    # ============ ACADEMIC ============
    2: {
        "name": "Mathematics",
        "subtopics": [
            # Basic Math
            "addition facts", "subtraction facts", "multiplication tables", "division facts",
            "place value", "rounding numbers", "comparing numbers", "number patterns",
            "even and odd numbers", "prime numbers", "composite numbers", "factors",
            "multiples", "greatest common factor", "least common multiple", "divisibility rules",
            # Fractions & Decimals
            "fractions basics", "equivalent fractions", "comparing fractions", "adding fractions",
            "subtracting fractions", "multiplying fractions", "dividing fractions", "mixed numbers",
            "improper fractions", "decimals basics", "decimal operations", "converting fractions to decimals",
            "percentages", "percent of a number", "percent increase decrease", "ratios",
            "proportions", "unit rates", "scale factors",
            # Algebra
            "variables and expressions", "evaluating expressions", "simplifying expressions",
            "solving one-step equations", "solving two-step equations", "multi-step equations",
            "inequalities", "graphing inequalities", "systems of equations", "linear equations",
            "slope and y-intercept", "graphing linear equations", "quadratic equations",
            "factoring polynomials", "FOIL method", "quadratic formula", "completing the square",
            "exponent rules", "scientific notation", "radical expressions", "rational expressions",
            # Geometry
            "points lines planes", "angles types", "angle relationships", "parallel lines",
            "perpendicular lines", "triangles classification", "triangle properties", "quadrilaterals",
            "polygons", "circles", "circumference", "area of rectangles", "area of triangles",
            "area of circles", "area of parallelograms", "area of trapezoids", "surface area",
            "volume of prisms", "volume of cylinders", "volume of cones", "volume of spheres",
            "Pythagorean theorem", "distance formula", "midpoint formula", "coordinate geometry",
            "transformations", "reflections", "rotations", "translations", "dilations",
            "similarity", "congruence", "geometric proofs",
            # Trigonometry
            "sine cosine tangent", "trigonometric ratios", "unit circle", "radians and degrees",
            "law of sines", "law of cosines", "trigonometric identities", "inverse trig functions",
            # Statistics & Probability
            "mean median mode", "range", "standard deviation", "variance", "box plots",
            "histograms", "scatter plots", "line of best fit", "correlation", "probability basics",
            "compound probability", "independent events", "dependent events", "combinations",
            "permutations", "expected value", "normal distribution",
            # Advanced
            "limits", "derivatives basics", "derivative rules", "chain rule", "integrals basics",
            "integration techniques", "sequences", "arithmetic sequences", "geometric sequences",
            "series", "matrices", "matrix operations", "determinants", "vectors",
            "complex numbers", "logarithms", "exponential functions", "number theory",
        ]
    },

    3: {
        "name": "Science",
        "subtopics": [
            # Physics
            "motion and speed", "velocity and acceleration", "Newton's first law", "Newton's second law",
            "Newton's third law", "gravity", "weight vs mass", "friction", "air resistance",
            "momentum", "impulse", "work and energy", "kinetic energy", "potential energy",
            "conservation of energy", "power", "simple machines", "mechanical advantage",
            "levers", "pulleys", "inclined planes", "wheels and axles", "wedges", "screws",
            "pressure", "density", "buoyancy", "Archimedes principle", "fluid dynamics",
            "waves properties", "wave types", "sound waves", "sound frequency", "pitch and volume",
            "Doppler effect", "light properties", "reflection", "refraction", "lenses",
            "mirrors", "color and light", "electromagnetic spectrum", "electricity basics",
            "static electricity", "current electricity", "circuits", "series circuits",
            "parallel circuits", "Ohm's law", "voltage", "resistance", "power in circuits",
            "magnetism", "electromagnets", "motors and generators", "heat transfer",
            "conduction", "convection", "radiation", "temperature scales", "thermodynamics",
            # Chemistry
            "matter properties", "states of matter", "phase changes", "atoms structure",
            "protons neutrons electrons", "atomic number", "mass number", "isotopes",
            "electron configuration", "periodic table organization", "periodic table groups",
            "periodic table periods", "metals", "nonmetals", "metalloids", "alkali metals",
            "halogens", "noble gases", "transition metals", "chemical symbols",
            "chemical formulas", "molecules", "compounds", "mixtures", "solutions",
            "suspensions", "colloids", "concentration", "solubility", "saturation",
            "chemical bonds", "ionic bonds", "covalent bonds", "metallic bonds",
            "chemical reactions", "balancing equations", "types of reactions",
            "synthesis reactions", "decomposition reactions", "single replacement",
            "double replacement", "combustion reactions", "acids", "bases", "pH scale",
            "neutralization", "oxidation", "reduction", "redox reactions",
            "organic chemistry basics", "hydrocarbons", "polymers",
            # Biology
            "cell structure", "cell organelles", "cell membrane", "nucleus", "mitochondria",
            "chloroplasts", "ribosomes", "endoplasmic reticulum", "Golgi apparatus", "vacuoles",
            "prokaryotes vs eukaryotes", "plant vs animal cells", "cell division", "mitosis",
            "meiosis", "DNA structure", "DNA replication", "RNA", "protein synthesis",
            "genes", "chromosomes", "genetics basics", "Punnett squares", "dominant traits",
            "recessive traits", "genotype vs phenotype", "heredity", "mutations",
            "evolution basics", "natural selection", "adaptation", "speciation",
            "classification of organisms", "kingdoms of life", "taxonomy", "binomial nomenclature",
            "bacteria", "viruses", "fungi", "protists", "plants structure",
            "photosynthesis", "plant reproduction", "animal systems", "digestive system",
            "respiratory system", "circulatory system", "nervous system", "skeletal system",
            "muscular system", "immune system", "endocrine system", "reproductive system",
            "ecosystems", "food chains", "food webs", "energy pyramid", "producers",
            "consumers", "decomposers", "biomes", "biodiversity",
            # Earth Science
            "Earth layers", "plate tectonics", "continental drift", "earthquakes",
            "volcanoes", "mountains formation", "rock cycle", "igneous rocks",
            "sedimentary rocks", "metamorphic rocks", "minerals", "fossils",
            "geologic time scale", "erosion", "weathering", "soil formation",
            "water cycle", "groundwater", "rivers and streams", "oceans",
            "ocean currents", "tides", "atmosphere layers", "air pressure",
            "wind", "clouds", "precipitation", "weather fronts", "hurricanes",
            "tornadoes", "climate zones", "climate change", "greenhouse effect",
            "ozone layer", "natural resources", "renewable resources", "nonrenewable resources",
        ]
    },

    4: {
        "name": "History",
        "subtopics": [
            # Ancient History
            "ancient Mesopotamia", "Sumerians", "Babylonians", "ancient Egypt pharaohs",
            "Egyptian pyramids", "Egyptian gods", "ancient Greece", "Greek city-states",
            "Athens", "Sparta", "Greek mythology", "Greek philosophers", "Alexander the Great",
            "ancient Rome", "Roman Republic", "Roman Empire", "Julius Caesar", "Roman emperors",
            "Roman architecture", "fall of Rome", "ancient China", "Chinese dynasties",
            "Great Wall of China", "ancient India", "Indus Valley", "Maurya Empire",
            "Persian Empire", "Phoenicians", "ancient Hebrews", "ancient Africa civilizations",
            # Medieval History
            "Middle Ages", "feudalism", "knights and castles", "Crusades", "Black Death",
            "Byzantine Empire", "Islamic Golden Age", "Vikings", "Charlemagne",
            "Magna Carta", "Hundred Years War", "medieval church", "monasteries",
            # Renaissance & Early Modern
            "Renaissance", "Renaissance art", "Leonardo da Vinci", "Michelangelo",
            "Protestant Reformation", "Martin Luther", "Age of Exploration", "Columbus",
            "Magellan", "conquistadors", "colonization", "slave trade", "Scientific Revolution",
            "Galileo", "Newton", "Enlightenment", "French Revolution", "Napoleon",
            # American History
            "Native Americans", "colonial America", "thirteen colonies", "Jamestown",
            "Plymouth", "American Revolution causes", "Declaration of Independence",
            "Revolutionary War battles", "George Washington", "Constitution", "Bill of Rights",
            "early republic", "westward expansion", "Louisiana Purchase", "Lewis and Clark",
            "War of 1812", "manifest destiny", "Mexican-American War", "slavery in America",
            "abolitionist movement", "Civil War causes", "Civil War battles", "Abraham Lincoln",
            "Emancipation Proclamation", "Reconstruction", "Gilded Age", "Industrial Revolution America",
            "immigration waves", "Progressive Era", "World War I America", "Roaring Twenties",
            "Great Depression", "New Deal", "World War II America", "Pearl Harbor",
            "D-Day", "atomic bomb", "Cold War", "Korean War", "Vietnam War",
            "Civil Rights Movement", "Martin Luther King Jr", "JFK", "Moon landing",
            "Watergate", "Reagan era", "fall of Soviet Union", "9/11", "recent history",
            # World History
            "World War I causes", "World War I battles", "Treaty of Versailles",
            "Russian Revolution", "rise of fascism", "Nazi Germany", "Holocaust",
            "World War II Europe", "World War II Pacific", "United Nations",
            "decolonization", "Indian independence", "Chinese Revolution", "Mao Zedong",
            "apartheid", "Middle East conflicts", "European Union", "globalization",
        ]
    },

    5: {
        "name": "Geography",
        "subtopics": [
            # Physical Geography
            "continents", "oceans", "major seas", "mountain ranges", "highest mountains",
            "major rivers", "longest rivers", "lakes", "great lakes", "deserts",
            "largest deserts", "rainforests", "islands", "largest islands", "peninsulas",
            "archipelagos", "volcanoes", "famous volcanoes", "waterfalls", "canyons",
            "plains", "plateaus", "valleys", "glaciers", "tundra", "coral reefs",
            # Countries & Capitals
            "European countries", "European capitals", "Asian countries", "Asian capitals",
            "African countries", "African capitals", "North American countries",
            "South American countries", "South American capitals", "Oceania countries",
            "Middle Eastern countries", "Caribbean nations", "Central American countries",
            # US Geography
            "US states", "US state capitals", "US regions", "US landmarks",
            "US national parks", "US rivers", "US mountains", "US cities",
            # World Landmarks
            "world wonders", "famous buildings", "famous bridges", "UNESCO sites",
            "natural wonders", "famous monuments", "ancient ruins",
            # Maps & Skills
            "latitude and longitude", "map reading", "time zones", "hemispheres",
            "equator", "prime meridian", "compass directions", "map scales",
            "topographic maps", "political maps", "physical maps",
            # Human Geography
            "population", "most populous countries", "most populous cities",
            "population density", "urbanization", "migration", "cultures",
            "world religions distribution", "languages distribution", "economies",
            "natural resources by country", "trade routes", "borders",
        ]
    },

    6: {
        "name": "Literature",
        "subtopics": [
            # Literary Elements
            "plot structure", "exposition", "rising action", "climax", "falling action",
            "resolution", "conflict types", "character types", "protagonist", "antagonist",
            "character development", "setting", "theme", "mood", "tone",
            "point of view", "first person", "third person", "narrator", "foreshadowing",
            "flashback", "symbolism", "imagery", "metaphor", "simile",
            "personification", "alliteration", "onomatopoeia", "hyperbole", "irony",
            "dramatic irony", "situational irony", "verbal irony", "satire", "allegory",
            # Poetry
            "poetry elements", "rhyme scheme", "meter", "stanza", "verse",
            "free verse", "sonnet", "haiku", "limerick", "epic poetry",
            "ballad", "ode", "elegy", "lyric poetry", "narrative poetry",
            "famous poets", "Shakespeare sonnets", "Emily Dickinson", "Robert Frost",
            # Prose & Drama
            "short story elements", "novel structure", "drama elements", "tragedy",
            "comedy", "acts and scenes", "stage directions", "monologue", "dialogue",
            # Famous Works
            "Shakespeare plays", "Romeo and Juliet", "Hamlet", "Macbeth", "Othello",
            "Greek tragedies", "American literature", "British literature", "world literature",
            "classic novels", "modern literature", "young adult literature",
            "Dickens works", "Jane Austen works", "Mark Twain works",
            # Reading Skills
            "main idea", "supporting details", "inference", "context clues",
            "summarizing", "paraphrasing", "comparing texts", "analyzing texts",
            "author's purpose", "author's perspective", "text structure",
            "cause and effect text", "compare contrast text", "sequence text",
            "problem solution text", "descriptive text",
        ]
    },

    7: {
        "name": "Language",
        "subtopics": [
            # Parts of Speech
            "nouns", "common nouns", "proper nouns", "collective nouns", "abstract nouns",
            "pronouns", "personal pronouns", "possessive pronouns", "reflexive pronouns",
            "verbs", "action verbs", "linking verbs", "helping verbs", "verb tenses",
            "present tense", "past tense", "future tense", "perfect tenses",
            "adjectives", "comparative adjectives", "superlative adjectives",
            "adverbs", "prepositions", "conjunctions", "coordinating conjunctions",
            "subordinating conjunctions", "interjections", "articles",
            # Sentence Structure
            "subjects and predicates", "simple sentences", "compound sentences",
            "complex sentences", "compound-complex sentences", "independent clauses",
            "dependent clauses", "phrases", "prepositional phrases", "participial phrases",
            "sentence fragments", "run-on sentences", "sentence combining",
            # Punctuation
            "periods", "question marks", "exclamation points", "commas", "comma rules",
            "semicolons", "colons", "apostrophes", "quotation marks", "hyphens",
            "parentheses", "ellipses",
            # Capitalization & Spelling
            "capitalization rules", "spelling rules", "commonly misspelled words",
            "homophones", "homographs", "homonyms", "prefixes", "suffixes",
            "root words", "Greek roots", "Latin roots", "word families",
            # Writing
            "paragraph writing", "topic sentences", "supporting sentences",
            "concluding sentences", "transitions", "essay structure", "introductions",
            "body paragraphs", "conclusions", "thesis statements",
            "narrative writing", "descriptive writing", "expository writing",
            "persuasive writing", "argumentative writing", "compare contrast writing",
            "cause effect writing", "research writing", "citations",
            # Vocabulary
            "synonyms", "antonyms", "analogies", "context clues vocabulary",
            "word meanings", "multiple meaning words", "figurative language",
            "idioms", "proverbs", "academic vocabulary",
        ]
    },

    # ============ ENTERTAINMENT ============
    101: {
        "name": "Movies",
        "subtopics": [
            "Oscar winners", "Oscar best picture", "movie directors", "Steven Spielberg films",
            "Christopher Nolan films", "Martin Scorsese films", "Quentin Tarantino films",
            "Disney movies", "Pixar movies", "Marvel movies", "DC movies", "superhero films",
            "Star Wars", "Harry Potter films", "Lord of the Rings", "James Bond films",
            "horror movies", "comedy movies", "action movies", "romantic movies",
            "animated movies", "classic Hollywood", "silent films", "movie quotes",
            "movie actors", "movie actresses", "movie villains", "movie soundtracks",
            "box office records", "film festivals", "Cannes Film Festival",
            "movie genres", "sci-fi movies", "fantasy movies", "war movies",
            "biographical films", "documentary films", "foreign films", "movie trivia",
        ]
    },

    102: {
        "name": "Television",
        "subtopics": [
            "TV show trivia", "sitcoms", "drama series", "reality TV", "game shows",
            "talk shows", "news programs", "TV characters", "Friends TV show",
            "The Office", "Breaking Bad", "Game of Thrones", "Stranger Things",
            "The Simpsons", "animated TV shows", "Netflix originals", "HBO shows",
            "TV awards", "Emmy winners", "TV history", "classic TV shows",
            "TV catchphrases", "TV theme songs", "TV spin-offs", "TV finales",
            "streaming services", "British TV shows", "Korean dramas", "anime series",
        ]
    },

    103: {
        "name": "Music",
        "subtopics": [
            "music genres", "rock music", "pop music", "hip hop", "country music",
            "jazz", "classical music", "R&B", "electronic music", "reggae",
            "famous musicians", "The Beatles", "Elvis Presley", "Michael Jackson",
            "Madonna", "Queen band", "Led Zeppelin", "Rolling Stones",
            "modern pop artists", "Taylor Swift", "Ed Sheeran", "Beyonce",
            "rap artists", "music awards", "Grammy winners", "Billboard charts",
            "music history", "musical instruments", "guitar", "piano", "drums",
            "famous songs", "song lyrics", "album covers", "music festivals",
            "concert venues", "music producers", "record labels", "one-hit wonders",
        ]
    },

    104: {
        "name": "Video Games",
        "subtopics": [
            "video game history", "Nintendo games", "Mario games", "Zelda games",
            "Pokemon", "PlayStation games", "Xbox games", "PC gaming",
            "Minecraft", "Fortnite", "Call of Duty", "Grand Theft Auto",
            "RPG games", "sports video games", "FIFA games", "racing games",
            "fighting games", "puzzle games", "indie games", "mobile games",
            "game consoles", "game characters", "game developers", "esports",
            "gaming terminology", "retro games", "arcade games", "VR gaming",
        ]
    },

    # ============ TECHNOLOGY ============
    201: {
        "name": "Computers",
        "subtopics": [
            "computer history", "computer components", "CPU", "RAM", "hard drives",
            "SSD", "graphics cards", "motherboards", "computer memory", "storage devices",
            "operating systems", "Windows", "macOS", "Linux", "computer networks",
            "internet basics", "WiFi", "Bluetooth", "USB", "computer security",
            "viruses and malware", "antivirus software", "firewalls", "encryption",
            "cloud computing", "data centers", "servers", "computer pioneers",
            "Bill Gates", "Steve Jobs", "computer brands", "laptops vs desktops",
        ]
    },

    202: {
        "name": "Internet",
        "subtopics": [
            "internet history", "World Wide Web", "web browsers", "search engines",
            "Google", "social media", "Facebook", "Twitter", "Instagram", "TikTok",
            "YouTube", "Wikipedia", "email", "websites", "domains", "URLs",
            "HTTP and HTTPS", "internet safety", "online privacy", "cookies",
            "streaming services", "e-commerce", "Amazon", "online banking",
            "cybersecurity", "hackers", "phishing", "internet memes", "viral content",
        ]
    },

    204: {
        "name": "Programming",
        "subtopics": [
            "programming basics", "programming languages", "Python", "JavaScript",
            "Java", "C++", "HTML", "CSS", "SQL", "algorithms", "data structures",
            "variables", "functions", "loops", "conditionals", "arrays",
            "object-oriented programming", "debugging", "software development",
            "web development", "mobile app development", "databases", "APIs",
            "version control", "Git", "GitHub", "coding careers", "tech companies",
        ]
    },

    # ============ SPORTS ============
    301: {
        "name": "Football Soccer",
        "subtopics": [
            "FIFA World Cup", "World Cup winners", "World Cup history", "UEFA Champions League",
            "Premier League", "La Liga", "Serie A", "Bundesliga", "Ligue 1",
            "famous soccer players", "Pele", "Maradona", "Messi", "Ronaldo",
            "soccer rules", "soccer positions", "goalkeepers", "defenders",
            "midfielders", "strikers", "soccer tactics", "soccer clubs",
            "Manchester United", "Real Madrid", "Barcelona", "Bayern Munich",
            "soccer records", "golden boot", "Ballon d'Or", "soccer stadiums",
        ]
    },

    302: {
        "name": "Basketball",
        "subtopics": [
            "NBA history", "NBA champions", "NBA teams", "Lakers", "Celtics",
            "Bulls", "Warriors", "famous basketball players", "Michael Jordan",
            "LeBron James", "Kobe Bryant", "Magic Johnson", "Larry Bird",
            "basketball rules", "basketball positions", "point guard", "shooting guard",
            "small forward", "power forward", "center", "basketball courts",
            "NBA playoffs", "NBA Finals", "NBA All-Star", "basketball records",
            "college basketball", "March Madness", "WNBA", "international basketball",
        ]
    },

    306: {
        "name": "Olympics",
        "subtopics": [
            "Olympic history", "ancient Olympics", "modern Olympics", "Summer Olympics",
            "Winter Olympics", "Olympic sports", "Olympic records", "Olympic hosts",
            "famous Olympians", "Michael Phelps", "Usain Bolt", "Simone Biles",
            "Olympic medals", "gold medals", "Olympic ceremonies", "Olympic torch",
            "track and field", "swimming Olympics", "gymnastics Olympics",
            "figure skating", "skiing", "Olympic controversies", "Paralympic Games",
        ]
    },

    # ============ NATURE ============
    401: {
        "name": "Animals",
        "subtopics": [
            "mammals", "birds", "reptiles", "amphibians", "fish", "insects",
            "arachnids", "marine animals", "whales", "dolphins", "sharks",
            "big cats", "lions", "tigers", "elephants", "giraffes", "bears",
            "wolves", "dogs breeds", "cats breeds", "horses", "primates",
            "gorillas", "chimpanzees", "endangered animals", "extinct animals",
            "dinosaurs", "animal habitats", "animal behaviors", "migration",
            "hibernation", "animal communication", "animal facts", "fastest animals",
            "largest animals", "smallest animals", "venomous animals", "pet care",
        ]
    },

    402: {
        "name": "Plants",
        "subtopics": [
            "plant parts", "roots", "stems", "leaves", "flowers", "seeds",
            "photosynthesis", "plant reproduction", "trees", "types of trees",
            "deciduous trees", "evergreen trees", "rainforest plants", "desert plants",
            "aquatic plants", "flowering plants", "roses", "tulips", "orchids",
            "fruits", "vegetables", "herbs", "medicinal plants", "poisonous plants",
            "plant adaptations", "plant life cycle", "gardening", "agriculture",
            "crops", "forests", "deforestation", "plant conservation",
        ]
    },

    # ============ TRANSPORTATION ============
    501: {
        "name": "Cars",
        "subtopics": [
            "car history", "car brands", "Ford", "Toyota", "Honda", "BMW",
            "Mercedes-Benz", "Ferrari", "Lamborghini", "Porsche", "Tesla",
            "car parts", "engines", "transmissions", "car types", "sedans",
            "SUVs", "trucks", "sports cars", "electric cars", "hybrid cars",
            "classic cars", "car racing", "Formula 1", "NASCAR", "rally racing",
            "car safety", "car technology", "self-driving cars", "car records",
            "fastest cars", "most expensive cars", "car manufacturers",
        ]
    },

    502: {
        "name": "Planes",
        "subtopics": [
            "aviation history", "Wright brothers", "first flights", "airplane parts",
            "how planes fly", "commercial aviation", "airlines", "airports",
            "famous airports", "Boeing", "Airbus", "passenger planes", "cargo planes",
            "military aircraft", "fighter jets", "helicopters", "private jets",
            "aviation records", "longest flights", "air travel", "pilots",
            "flight attendants", "air traffic control", "aviation safety",
            "famous aviators", "Amelia Earhart", "Charles Lindbergh", "space planes",
        ]
    },

    # ============ SPACE ============
    901: {
        "name": "Solar System",
        "subtopics": [
            "the Sun", "Mercury", "Venus", "Earth", "Mars", "Jupiter",
            "Saturn", "Uranus", "Neptune", "Pluto", "dwarf planets", "moons",
            "Earth's moon", "Jupiter's moons", "Saturn's moons", "asteroids",
            "asteroid belt", "comets", "meteor showers", "solar eclipses",
            "lunar eclipses", "planet facts", "planet sizes", "planet distances",
            "planet temperatures", "planet atmospheres", "rings of Saturn",
            "Great Red Spot", "Mars rovers", "planet formation",
        ]
    },

    903: {
        "name": "Space Exploration",
        "subtopics": [
            "NASA", "SpaceX", "space race", "Apollo missions", "Moon landing",
            "Neil Armstrong", "Buzz Aldrin", "astronauts", "cosmonauts",
            "Yuri Gagarin", "International Space Station", "space shuttles",
            "rockets", "satellites", "Hubble telescope", "James Webb telescope",
            "Mars missions", "Mars rovers", "Curiosity", "Perseverance",
            "Voyager missions", "space probes", "space stations", "spacewalks",
            "future of space travel", "Mars colonization", "space tourism",
        ]
    },
}

def get_db_connection():
    """Connect to the SQLite database."""
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def generate_with_mistral(topic_name: str, subtopic: str, count: int = 5, difficulty: int = 2) -> list:
    """Generate questions using local Mistral via Ollama."""

    prompt = f"""Generate exactly {count} trivia quiz questions about {subtopic}.
JSON format: [{{"question":"Question?","options":["A","B","C","D"],"answer":0,"explanation":"brief"}}]
Output:"""

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.7, "num_predict": 2000}
        }, timeout=180)

        if response.status_code == 200:
            text = response.json().get("response", "")
            match = re.search(r'\[[\s\S]*\]', text)
            if match:
                try:
                    questions = json.loads(match.group())
                    valid = []
                    for q in questions:
                        if (q.get("question") and
                            len(q.get("options", [])) == 4 and
                            isinstance(q.get("answer"), int) and
                            0 <= q.get("answer") <= 3):
                            valid.append(q)
                    return valid
                except:
                    pass
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
    return []

def insert_questions(questions: list, topic_id: int, source: str) -> int:
    """Insert questions into database."""
    with db_lock:
        conn = get_db_connection()
        cursor = conn.cursor()
        count = 0
        for q in questions:
            try:
                opts = q.get("options", [])
                if len(opts) < 4:
                    continue
                cursor.execute(
                    "SELECT 1 FROM question_bank WHERE question = ?",
                    (q.get("question", ""),)
                )
                if cursor.fetchone():
                    continue
                cursor.execute("""
                    INSERT INTO question_bank
                    (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, explanation, source)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (topic_id, q["question"], opts[0], opts[1], opts[2], opts[3],
                      q.get("answer", 0), q.get("difficulty", 2), q.get("explanation", ""), source))
                count += 1
            except:
                continue
        conn.commit()
        conn.close()
        return count

def get_counts():
    """Get question counts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT topic_id, COUNT(*) FROM question_bank GROUP BY topic_id")
    counts = {r[0]: r[1] for r in cursor.fetchall()}
    cursor.execute("SELECT COUNT(*) FROM question_bank")
    counts['total'] = cursor.fetchone()[0]
    conn.close()
    return counts

def generate_for_topic(topic_id: int, target: int = 100000):
    """Generate questions for a topic."""
    info = ALL_TOPICS.get(topic_id)
    if not info:
        print(f"Unknown topic: {topic_id}")
        return

    name = info["name"]
    subtopics = info["subtopics"]
    current = get_counts().get(topic_id, 0)

    print(f"\n{'='*50}")
    print(f"{name}: {current:,} / {target:,}")
    print(f"{'='*50}")

    batch = 0
    while current < target:
        subtopic = subtopics[batch % len(subtopics)]
        diff = random.choice([1, 2, 2, 3, 3, 3, 4])

        print(f"[{batch+1}] {subtopic} (d{diff})...", end=" ", flush=True)

        qs = generate_with_mistral(name, subtopic, 5, diff)
        if qs:
            for q in qs:
                q['difficulty'] = diff
            added = insert_questions(qs, topic_id, f"mistral")
            current += added
            print(f"+{added} = {current:,}")
        else:
            print("retry")
            time.sleep(1)

        batch += 1
        time.sleep(0.3)

        if batch % 50 == 0:
            print(f"--- {current:,}/{target:,} ({100*current/target:.1f}%) ---")

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', type=int)
    parser.add_argument('--target', type=int, default=100000)
    parser.add_argument('--all', action='store_true')
    parser.add_argument('--status', action='store_true')
    args = parser.parse_args()

    if args.status:
        counts = get_counts()
        print("\nQuestion Counts:")
        print("-" * 40)
        for tid, info in sorted(ALL_TOPICS.items()):
            c = counts.get(tid, 0)
            print(f"  [{tid}] {info['name']}: {c:,}")
        print("-" * 40)
        print(f"  TOTAL: {counts.get('total', 0):,}")
        return

    if args.all:
        for tid in ALL_TOPICS:
            generate_for_topic(tid, args.target)
    elif args.topic:
        generate_for_topic(args.topic, args.target)
    else:
        print("Usage:")
        print("  --status         Show counts")
        print("  --topic ID       Generate for specific topic")
        print("  --all            Generate for all topics")
        print("  --target N       Target count (default 100000)")
        print("\nTopics:")
        for tid, info in sorted(ALL_TOPICS.items()):
            print(f"  {tid}: {info['name']}")

if __name__ == "__main__":
    main()
