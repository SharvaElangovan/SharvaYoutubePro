#!/usr/bin/env python3
"""
Question Generator for SharvaYoutubePro
Uses local Mistral via Ollama + built-in question bank
"""

import json
import sqlite3
import os
import sys
import requests
import re
from pathlib import Path

# Database path (Tauri uses the app identifier)
DB_PATH = os.path.expanduser("~/.local/share/com.sharva.youtube-pro/sharva_youtube_pro.db")

OLLAMA_URL = "http://localhost:11434/api/generate"

def get_db_connection():
    """Connect to the SQLite database."""
    db_dir = os.path.dirname(DB_PATH)
    os.makedirs(db_dir, exist_ok=True)
    return sqlite3.connect(DB_PATH)

def generate_with_mistral(topic: str, subtopic: str, count: int = 10, difficulty: int = 2) -> list:
    """Generate questions using local Mistral via Ollama."""

    difficulty_desc = {
        1: "very easy, suitable for beginners",
        2: "easy to moderate",
        3: "moderate difficulty",
        4: "challenging",
        5: "very difficult, expert level"
    }

    prompt = f"""Generate exactly {count} multiple choice quiz questions about {topic} - {subtopic}.
Difficulty level: {difficulty_desc.get(difficulty, 'moderate')}

IMPORTANT: Return ONLY a valid JSON array, no other text. Each question must have this exact format:
[
  {{
    "question": "The question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": 0,
    "explanation": "Brief explanation why this is correct"
  }}
]

The "answer" field must be 0, 1, 2, or 3 (index of correct option).
Make questions factually accurate and educational.
Generate exactly {count} questions about {subtopic}."""

    try:
        response = requests.post(OLLAMA_URL, json={
            "model": "mistral",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 4000
            }
        }, timeout=120)

        if response.status_code == 200:
            result = response.json()
            text = result.get("response", "")

            # Try to extract JSON from the response
            # Look for JSON array pattern
            json_match = re.search(r'\[[\s\S]*\]', text)
            if json_match:
                try:
                    questions = json.loads(json_match.group())
                    return questions
                except json.JSONDecodeError:
                    pass

            print(f"Failed to parse Mistral response for {subtopic}", file=sys.stderr)
            return []
    except Exception as e:
        print(f"Mistral error: {e}", file=sys.stderr)
        return []

    return []

def insert_questions(conn, topic_id: int, questions: list, source: str = "generated"):
    """Insert questions into the database."""
    cursor = conn.cursor()
    count = 0

    for q in questions:
        try:
            options = q.get("options", [])
            if len(options) < 4:
                continue

            cursor.execute("""
                INSERT INTO question_bank
                (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, explanation, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                topic_id,
                q.get("question", ""),
                options[0],
                options[1],
                options[2],
                options[3],
                q.get("answer", 0),
                q.get("difficulty", 2),
                q.get("explanation", ""),
                source
            ))
            count += 1
        except Exception as e:
            print(f"Insert error: {e}", file=sys.stderr)
            continue

    conn.commit()
    return count

def get_builtin_questions():
    """Return a large set of pre-made academic questions."""
    return {
        # Mathematics (topic_id: 2)
        2: [
            {"question": "What is the value of pi (π) to two decimal places?", "options": ["3.14", "3.41", "2.14", "3.12"], "answer": 0, "difficulty": 1, "explanation": "Pi is approximately 3.14159..."},
            {"question": "What is 15% of 200?", "options": ["30", "25", "35", "20"], "answer": 0, "difficulty": 1, "explanation": "15% × 200 = 0.15 × 200 = 30"},
            {"question": "What is the square root of 144?", "options": ["12", "14", "11", "13"], "answer": 0, "difficulty": 1, "explanation": "12 × 12 = 144"},
            {"question": "What is the next prime number after 7?", "options": ["11", "9", "10", "13"], "answer": 0, "difficulty": 1, "explanation": "11 is the next prime after 7 (9 and 10 are not prime)"},
            {"question": "What is 2³ (2 to the power of 3)?", "options": ["8", "6", "9", "4"], "answer": 0, "difficulty": 1, "explanation": "2³ = 2 × 2 × 2 = 8"},
            {"question": "What is the formula for the area of a circle?", "options": ["πr²", "2πr", "πd", "r²"], "answer": 0, "difficulty": 2, "explanation": "Area = π times radius squared"},
            {"question": "What is the sum of angles in a triangle?", "options": ["180°", "360°", "90°", "270°"], "answer": 0, "difficulty": 1, "explanation": "All triangles have interior angles summing to 180°"},
            {"question": "What is the Pythagorean theorem?", "options": ["a² + b² = c²", "a + b = c", "a² × b² = c²", "a² - b² = c²"], "answer": 0, "difficulty": 2, "explanation": "In a right triangle, the sum of squares of legs equals the square of hypotenuse"},
            {"question": "What is 7 factorial (7!)?", "options": ["5040", "720", "40320", "120"], "answer": 0, "difficulty": 3, "explanation": "7! = 7×6×5×4×3×2×1 = 5040"},
            {"question": "What is the derivative of x²?", "options": ["2x", "x", "2x²", "x²"], "answer": 0, "difficulty": 3, "explanation": "Using the power rule: d/dx(x²) = 2x"},
            {"question": "What is log₁₀(1000)?", "options": ["3", "2", "4", "10"], "answer": 0, "difficulty": 2, "explanation": "10³ = 1000, so log₁₀(1000) = 3"},
            {"question": "How many sides does a hexagon have?", "options": ["6", "5", "7", "8"], "answer": 0, "difficulty": 1, "explanation": "Hexa- means six"},
            {"question": "What is the value of e (Euler's number) approximately?", "options": ["2.718", "3.141", "1.414", "2.236"], "answer": 0, "difficulty": 3, "explanation": "e ≈ 2.71828..."},
            {"question": "What is 0.25 as a fraction?", "options": ["1/4", "1/3", "1/5", "1/2"], "answer": 0, "difficulty": 1, "explanation": "0.25 = 25/100 = 1/4"},
            {"question": "What is the least common multiple (LCM) of 4 and 6?", "options": ["12", "24", "6", "2"], "answer": 0, "difficulty": 2, "explanation": "12 is the smallest number divisible by both 4 and 6"},
            {"question": "What is the quadratic formula?", "options": ["x = (-b ± √(b²-4ac))/2a", "x = -b/2a", "x = b² - 4ac", "x = a + b + c"], "answer": 0, "difficulty": 3, "explanation": "Used to solve ax² + bx + c = 0"},
            {"question": "What is the integral of 1/x?", "options": ["ln|x| + C", "x + C", "1/x² + C", "e^x + C"], "answer": 0, "difficulty": 4, "explanation": "The integral of 1/x is the natural logarithm"},
            {"question": "What is 5! (5 factorial)?", "options": ["120", "60", "24", "720"], "answer": 0, "difficulty": 2, "explanation": "5! = 5×4×3×2×1 = 120"},
            {"question": "What is the value of sin(90°)?", "options": ["1", "0", "-1", "0.5"], "answer": 0, "difficulty": 2, "explanation": "Sine of 90 degrees equals 1"},
            {"question": "What is the golden ratio approximately?", "options": ["1.618", "2.718", "3.141", "1.414"], "answer": 0, "difficulty": 3, "explanation": "φ ≈ 1.618033..."},
        ],

        # Physics (topic_id: 8)
        8: [
            {"question": "What is the speed of light in vacuum?", "options": ["3 × 10⁸ m/s", "3 × 10⁶ m/s", "3 × 10¹⁰ m/s", "3 × 10⁵ m/s"], "answer": 0, "difficulty": 2, "explanation": "Light travels at approximately 299,792,458 m/s"},
            {"question": "What is Newton's First Law also known as?", "options": ["Law of Inertia", "Law of Acceleration", "Law of Reaction", "Law of Gravity"], "answer": 0, "difficulty": 1, "explanation": "Objects at rest stay at rest, objects in motion stay in motion"},
            {"question": "What is the SI unit of force?", "options": ["Newton", "Joule", "Watt", "Pascal"], "answer": 0, "difficulty": 1, "explanation": "Force is measured in Newtons (N)"},
            {"question": "What is the formula for kinetic energy?", "options": ["½mv²", "mgh", "mv", "ma"], "answer": 0, "difficulty": 2, "explanation": "Kinetic energy = half × mass × velocity squared"},
            {"question": "What is the acceleration due to gravity on Earth?", "options": ["9.8 m/s²", "10.8 m/s²", "8.8 m/s²", "11.8 m/s²"], "answer": 0, "difficulty": 1, "explanation": "g ≈ 9.8 m/s² on Earth's surface"},
            {"question": "What is Einstein's famous equation?", "options": ["E = mc²", "F = ma", "E = hf", "PV = nRT"], "answer": 0, "difficulty": 1, "explanation": "Energy equals mass times speed of light squared"},
            {"question": "What type of wave is sound?", "options": ["Longitudinal", "Transverse", "Electromagnetic", "Surface"], "answer": 0, "difficulty": 2, "explanation": "Sound waves are compression waves (longitudinal)"},
            {"question": "What is the SI unit of electric current?", "options": ["Ampere", "Volt", "Ohm", "Watt"], "answer": 0, "difficulty": 1, "explanation": "Current is measured in Amperes (A)"},
            {"question": "What is Ohm's Law?", "options": ["V = IR", "P = IV", "F = ma", "E = mc²"], "answer": 0, "difficulty": 2, "explanation": "Voltage = Current × Resistance"},
            {"question": "What particle has a negative charge?", "options": ["Electron", "Proton", "Neutron", "Photon"], "answer": 0, "difficulty": 1, "explanation": "Electrons carry negative charge"},
            {"question": "What is the SI unit of energy?", "options": ["Joule", "Watt", "Newton", "Pascal"], "answer": 0, "difficulty": 1, "explanation": "Energy is measured in Joules (J)"},
            {"question": "What is the frequency of visible light approximately?", "options": ["10¹⁴ Hz", "10⁶ Hz", "10⁹ Hz", "10²⁰ Hz"], "answer": 0, "difficulty": 3, "explanation": "Visible light has frequency around 4-8 × 10¹⁴ Hz"},
            {"question": "What is absolute zero in Celsius?", "options": ["-273.15°C", "-100°C", "0°C", "-459.67°C"], "answer": 0, "difficulty": 2, "explanation": "Absolute zero is 0 Kelvin = -273.15°C"},
            {"question": "What force keeps planets in orbit around the Sun?", "options": ["Gravity", "Electromagnetic", "Strong nuclear", "Weak nuclear"], "answer": 0, "difficulty": 1, "explanation": "Gravitational force from the Sun"},
            {"question": "What is the SI unit of power?", "options": ["Watt", "Joule", "Newton", "Ampere"], "answer": 0, "difficulty": 1, "explanation": "Power is measured in Watts (W)"},
            {"question": "What is Planck's constant approximately?", "options": ["6.63 × 10⁻³⁴ J·s", "6.63 × 10⁻²⁴ J·s", "3.00 × 10⁸ J·s", "1.38 × 10⁻²³ J·s"], "answer": 0, "difficulty": 4, "explanation": "h ≈ 6.626 × 10⁻³⁴ J·s"},
            {"question": "What is the formula for momentum?", "options": ["p = mv", "F = ma", "E = mc²", "W = Fd"], "answer": 0, "difficulty": 2, "explanation": "Momentum = mass × velocity"},
            {"question": "What type of radiation has the shortest wavelength?", "options": ["Gamma rays", "X-rays", "Ultraviolet", "Radio waves"], "answer": 0, "difficulty": 2, "explanation": "Gamma rays have the shortest wavelength in the EM spectrum"},
            {"question": "What is the principle of conservation of energy?", "options": ["Energy cannot be created or destroyed", "Energy always increases", "Energy always decreases", "Energy can be created"], "answer": 0, "difficulty": 2, "explanation": "Energy can only be transformed, not created or destroyed"},
            {"question": "What is the unit of electric resistance?", "options": ["Ohm", "Ampere", "Volt", "Farad"], "answer": 0, "difficulty": 1, "explanation": "Resistance is measured in Ohms (Ω)"},
        ],

        # Chemistry (topic_id: 9)
        9: [
            {"question": "What is the chemical symbol for gold?", "options": ["Au", "Ag", "Fe", "Cu"], "answer": 0, "difficulty": 1, "explanation": "Au comes from Latin 'aurum'"},
            {"question": "What is the atomic number of carbon?", "options": ["6", "12", "8", "14"], "answer": 0, "difficulty": 1, "explanation": "Carbon has 6 protons"},
            {"question": "What is H₂O commonly known as?", "options": ["Water", "Hydrogen peroxide", "Heavy water", "Oxygen"], "answer": 0, "difficulty": 1, "explanation": "H₂O is the chemical formula for water"},
            {"question": "What is the pH of pure water?", "options": ["7", "0", "14", "1"], "answer": 0, "difficulty": 1, "explanation": "Pure water is neutral with pH 7"},
            {"question": "What is the most abundant gas in Earth's atmosphere?", "options": ["Nitrogen", "Oxygen", "Carbon dioxide", "Argon"], "answer": 0, "difficulty": 1, "explanation": "Nitrogen makes up about 78% of the atmosphere"},
            {"question": "What is the chemical formula for table salt?", "options": ["NaCl", "KCl", "CaCl₂", "NaOH"], "answer": 0, "difficulty": 1, "explanation": "Sodium chloride is NaCl"},
            {"question": "How many elements are in the periodic table (as of 2023)?", "options": ["118", "109", "92", "100"], "answer": 0, "difficulty": 2, "explanation": "There are 118 confirmed elements"},
            {"question": "What is the chemical symbol for silver?", "options": ["Ag", "Au", "Si", "Sr"], "answer": 0, "difficulty": 1, "explanation": "Ag comes from Latin 'argentum'"},
            {"question": "What type of bond forms between sodium and chlorine?", "options": ["Ionic", "Covalent", "Metallic", "Hydrogen"], "answer": 0, "difficulty": 2, "explanation": "Electrons are transferred, forming an ionic bond"},
            {"question": "What is the molecular formula for glucose?", "options": ["C₆H₁₂O₆", "C₁₂H₂₂O₁₁", "CH₄", "CO₂"], "answer": 0, "difficulty": 2, "explanation": "Glucose has 6 carbons, 12 hydrogens, and 6 oxygens"},
            {"question": "What is Avogadro's number approximately?", "options": ["6.02 × 10²³", "3.14 × 10²³", "6.02 × 10²⁰", "1.38 × 10²³"], "answer": 0, "difficulty": 3, "explanation": "One mole contains 6.022 × 10²³ particles"},
            {"question": "What is the lightest element?", "options": ["Hydrogen", "Helium", "Lithium", "Carbon"], "answer": 0, "difficulty": 1, "explanation": "Hydrogen has atomic mass of ~1"},
            {"question": "What is the chemical formula for carbon dioxide?", "options": ["CO₂", "CO", "C₂O", "O₂C"], "answer": 0, "difficulty": 1, "explanation": "One carbon, two oxygen atoms"},
            {"question": "What group do noble gases belong to?", "options": ["Group 18", "Group 1", "Group 17", "Group 2"], "answer": 0, "difficulty": 2, "explanation": "Noble gases are in the rightmost column"},
            {"question": "What is the chemical symbol for iron?", "options": ["Fe", "Ir", "In", "I"], "answer": 0, "difficulty": 1, "explanation": "Fe comes from Latin 'ferrum'"},
            {"question": "What is an isotope?", "options": ["Atoms with same protons but different neutrons", "Atoms with different protons", "Molecules with same atoms", "Ions with same charge"], "answer": 0, "difficulty": 2, "explanation": "Isotopes have the same atomic number but different mass numbers"},
            {"question": "What is the chemical formula for ammonia?", "options": ["NH₃", "NO₂", "N₂O", "HNO₃"], "answer": 0, "difficulty": 2, "explanation": "One nitrogen and three hydrogen atoms"},
            {"question": "What is oxidation?", "options": ["Loss of electrons", "Gain of electrons", "Loss of protons", "Gain of neutrons"], "answer": 0, "difficulty": 2, "explanation": "OIL RIG: Oxidation Is Loss of electrons"},
            {"question": "What is the most electronegative element?", "options": ["Fluorine", "Oxygen", "Chlorine", "Nitrogen"], "answer": 0, "difficulty": 3, "explanation": "Fluorine has the highest electronegativity (3.98)"},
            {"question": "What is the chemical symbol for potassium?", "options": ["K", "P", "Po", "Pt"], "answer": 0, "difficulty": 1, "explanation": "K comes from Latin 'kalium'"},
        ],

        # Biology (topic_id: 10)
        10: [
            {"question": "What is the powerhouse of the cell?", "options": ["Mitochondria", "Nucleus", "Ribosome", "Golgi apparatus"], "answer": 0, "difficulty": 1, "explanation": "Mitochondria produce ATP, the cell's energy currency"},
            {"question": "What is DNA's full name?", "options": ["Deoxyribonucleic acid", "Dioxynucleic acid", "Diribonucleic acid", "Deoxyribo acid"], "answer": 0, "difficulty": 2, "explanation": "DNA stands for Deoxyribonucleic acid"},
            {"question": "How many chromosomes do humans have?", "options": ["46", "23", "48", "44"], "answer": 0, "difficulty": 1, "explanation": "Humans have 23 pairs = 46 chromosomes"},
            {"question": "What is the process by which plants make food?", "options": ["Photosynthesis", "Respiration", "Fermentation", "Digestion"], "answer": 0, "difficulty": 1, "explanation": "Plants convert light energy to chemical energy"},
            {"question": "What is the largest organ in the human body?", "options": ["Skin", "Liver", "Brain", "Heart"], "answer": 0, "difficulty": 1, "explanation": "Skin covers about 2 square meters"},
            {"question": "What carries oxygen in blood?", "options": ["Hemoglobin", "Plasma", "White blood cells", "Platelets"], "answer": 0, "difficulty": 2, "explanation": "Hemoglobin in red blood cells binds oxygen"},
            {"question": "What is the basic unit of life?", "options": ["Cell", "Atom", "Molecule", "Organ"], "answer": 0, "difficulty": 1, "explanation": "Cells are the smallest unit of life"},
            {"question": "What type of cell division produces gametes?", "options": ["Meiosis", "Mitosis", "Binary fission", "Budding"], "answer": 0, "difficulty": 2, "explanation": "Meiosis produces sex cells with half the chromosomes"},
            {"question": "What is the function of ribosomes?", "options": ["Protein synthesis", "Energy production", "Cell division", "Storage"], "answer": 0, "difficulty": 2, "explanation": "Ribosomes translate mRNA into proteins"},
            {"question": "What base pairs with adenine in DNA?", "options": ["Thymine", "Guanine", "Cytosine", "Uracil"], "answer": 0, "difficulty": 2, "explanation": "A-T and G-C are the base pairs in DNA"},
            {"question": "What is the study of heredity called?", "options": ["Genetics", "Ecology", "Anatomy", "Physiology"], "answer": 0, "difficulty": 1, "explanation": "Genetics studies how traits are inherited"},
            {"question": "What organelle contains the cell's genetic material?", "options": ["Nucleus", "Mitochondria", "Chloroplast", "Vacuole"], "answer": 0, "difficulty": 1, "explanation": "The nucleus houses DNA"},
            {"question": "What is the process of cell division in body cells?", "options": ["Mitosis", "Meiosis", "Binary fission", "Fragmentation"], "answer": 0, "difficulty": 2, "explanation": "Mitosis produces two identical daughter cells"},
            {"question": "What is taxonomy?", "options": ["Classification of organisms", "Study of cells", "Study of ecosystems", "Study of evolution"], "answer": 0, "difficulty": 2, "explanation": "Taxonomy is the science of naming and classifying organisms"},
            {"question": "What is the human body's largest internal organ?", "options": ["Liver", "Brain", "Heart", "Lungs"], "answer": 0, "difficulty": 2, "explanation": "The liver weighs about 1.5 kg"},
            {"question": "What is an enzyme?", "options": ["A biological catalyst", "A type of cell", "A hormone", "A vitamin"], "answer": 0, "difficulty": 2, "explanation": "Enzymes speed up biochemical reactions"},
            {"question": "What is the term for an organism that makes its own food?", "options": ["Autotroph", "Heterotroph", "Decomposer", "Consumer"], "answer": 0, "difficulty": 2, "explanation": "Plants and some bacteria are autotrophs"},
            {"question": "What structure controls what enters and exits a cell?", "options": ["Cell membrane", "Cell wall", "Nucleus", "Cytoplasm"], "answer": 0, "difficulty": 1, "explanation": "The cell membrane is selectively permeable"},
            {"question": "What is Darwin's theory called?", "options": ["Natural selection", "Spontaneous generation", "Lamarckism", "Creationism"], "answer": 0, "difficulty": 2, "explanation": "Natural selection explains evolution through survival of the fittest"},
            {"question": "What is the green pigment in plants?", "options": ["Chlorophyll", "Melanin", "Carotene", "Hemoglobin"], "answer": 0, "difficulty": 1, "explanation": "Chlorophyll absorbs light for photosynthesis"},
        ],

        # History (topic_id: 4)
        4: [
            {"question": "In what year did World War II end?", "options": ["1945", "1944", "1946", "1943"], "answer": 0, "difficulty": 1, "explanation": "WWII ended in September 1945"},
            {"question": "Who was the first President of the United States?", "options": ["George Washington", "Thomas Jefferson", "John Adams", "Benjamin Franklin"], "answer": 0, "difficulty": 1, "explanation": "Washington served from 1789-1797"},
            {"question": "In what year did the French Revolution begin?", "options": ["1789", "1776", "1799", "1804"], "answer": 0, "difficulty": 2, "explanation": "The storming of the Bastille was July 14, 1789"},
            {"question": "Who built the Great Wall of China?", "options": ["Qin Shi Huang", "Genghis Khan", "Kublai Khan", "Sun Tzu"], "answer": 0, "difficulty": 2, "explanation": "The first emperor of unified China began construction"},
            {"question": "What ancient wonder was located in Egypt?", "options": ["Great Pyramid of Giza", "Hanging Gardens", "Colossus of Rhodes", "Lighthouse of Alexandria"], "answer": 0, "difficulty": 1, "explanation": "The Great Pyramid is the only surviving ancient wonder"},
            {"question": "Who discovered America in 1492?", "options": ["Christopher Columbus", "Amerigo Vespucci", "Leif Erikson", "Ferdinand Magellan"], "answer": 0, "difficulty": 1, "explanation": "Columbus reached the Americas in 1492"},
            {"question": "What empire was ruled by Caesars?", "options": ["Roman Empire", "Greek Empire", "Persian Empire", "Ottoman Empire"], "answer": 0, "difficulty": 1, "explanation": "Roman emperors used the title Caesar"},
            {"question": "When did the Berlin Wall fall?", "options": ["1989", "1991", "1985", "1987"], "answer": 0, "difficulty": 2, "explanation": "The wall fell on November 9, 1989"},
            {"question": "Who was the first man to walk on the moon?", "options": ["Neil Armstrong", "Buzz Aldrin", "Yuri Gagarin", "John Glenn"], "answer": 0, "difficulty": 1, "explanation": "Armstrong walked on the moon July 20, 1969"},
            {"question": "What was the Renaissance?", "options": ["Cultural rebirth in Europe", "A war", "A plague", "A religious movement"], "answer": 0, "difficulty": 2, "explanation": "The Renaissance was a cultural movement from the 14th-17th century"},
            {"question": "Who painted the Mona Lisa?", "options": ["Leonardo da Vinci", "Michelangelo", "Raphael", "Donatello"], "answer": 0, "difficulty": 1, "explanation": "Da Vinci painted it in the early 1500s"},
            {"question": "What year did World War I begin?", "options": ["1914", "1918", "1912", "1916"], "answer": 0, "difficulty": 1, "explanation": "WWI began in July 1914"},
            {"question": "Who was the first female Prime Minister of the UK?", "options": ["Margaret Thatcher", "Theresa May", "Queen Victoria", "Queen Elizabeth II"], "answer": 0, "difficulty": 2, "explanation": "Thatcher served from 1979-1990"},
            {"question": "What ancient civilization built the Parthenon?", "options": ["Greeks", "Romans", "Egyptians", "Persians"], "answer": 0, "difficulty": 1, "explanation": "The Parthenon was built in Athens, Greece"},
            {"question": "Who wrote the Declaration of Independence?", "options": ["Thomas Jefferson", "George Washington", "Benjamin Franklin", "John Adams"], "answer": 0, "difficulty": 2, "explanation": "Jefferson was the primary author in 1776"},
            {"question": "What was the Cold War?", "options": ["Tension between USA and USSR", "A war in Antarctica", "A winter war", "A trade war"], "answer": 0, "difficulty": 1, "explanation": "The Cold War was a geopolitical tension from 1947-1991"},
            {"question": "Who was Cleopatra?", "options": ["Queen of Egypt", "Queen of Rome", "Queen of Greece", "Queen of Persia"], "answer": 0, "difficulty": 1, "explanation": "Cleopatra VII was the last pharaoh of Egypt"},
            {"question": "What treaty ended World War I?", "options": ["Treaty of Versailles", "Treaty of Paris", "Treaty of Vienna", "Treaty of Rome"], "answer": 0, "difficulty": 2, "explanation": "Signed on June 28, 1919"},
            {"question": "Who was the leader of Nazi Germany?", "options": ["Adolf Hitler", "Joseph Stalin", "Benito Mussolini", "Winston Churchill"], "answer": 0, "difficulty": 1, "explanation": "Hitler led Germany from 1933-1945"},
            {"question": "When was the United Nations founded?", "options": ["1945", "1919", "1950", "1939"], "answer": 0, "difficulty": 2, "explanation": "The UN was established October 24, 1945"},
        ],

        # Geography (topic_id: 5)
        5: [
            {"question": "What is the largest country by area?", "options": ["Russia", "Canada", "China", "United States"], "answer": 0, "difficulty": 1, "explanation": "Russia spans 17.1 million km²"},
            {"question": "What is the longest river in the world?", "options": ["Nile", "Amazon", "Yangtze", "Mississippi"], "answer": 0, "difficulty": 1, "explanation": "The Nile is approximately 6,650 km long"},
            {"question": "What is the capital of Japan?", "options": ["Tokyo", "Osaka", "Kyoto", "Hiroshima"], "answer": 0, "difficulty": 1, "explanation": "Tokyo has been Japan's capital since 1868"},
            {"question": "What is the smallest country in the world?", "options": ["Vatican City", "Monaco", "San Marino", "Liechtenstein"], "answer": 0, "difficulty": 1, "explanation": "Vatican City is only 0.44 km²"},
            {"question": "What is the largest ocean?", "options": ["Pacific Ocean", "Atlantic Ocean", "Indian Ocean", "Arctic Ocean"], "answer": 0, "difficulty": 1, "explanation": "The Pacific covers about 165 million km²"},
            {"question": "What is the highest mountain in the world?", "options": ["Mount Everest", "K2", "Kangchenjunga", "Lhotse"], "answer": 0, "difficulty": 1, "explanation": "Everest is 8,849 meters tall"},
            {"question": "What continent is Egypt in?", "options": ["Africa", "Asia", "Europe", "Middle East"], "answer": 0, "difficulty": 1, "explanation": "Egypt is in northeastern Africa"},
            {"question": "What is the capital of Australia?", "options": ["Canberra", "Sydney", "Melbourne", "Brisbane"], "answer": 0, "difficulty": 2, "explanation": "Canberra, not Sydney, is the capital"},
            {"question": "How many continents are there?", "options": ["7", "6", "5", "8"], "answer": 0, "difficulty": 1, "explanation": "Africa, Antarctica, Asia, Australia, Europe, North America, South America"},
            {"question": "What is the largest desert in the world?", "options": ["Antarctic Desert", "Sahara", "Arabian", "Gobi"], "answer": 0, "difficulty": 2, "explanation": "Antarctica is technically the largest desert"},
            {"question": "What country has the most people?", "options": ["India", "China", "United States", "Indonesia"], "answer": 0, "difficulty": 2, "explanation": "India surpassed China in 2023"},
            {"question": "What is the capital of Brazil?", "options": ["Brasília", "Rio de Janeiro", "São Paulo", "Salvador"], "answer": 0, "difficulty": 2, "explanation": "Brasília became the capital in 1960"},
            {"question": "What is the deepest ocean trench?", "options": ["Mariana Trench", "Puerto Rico Trench", "Java Trench", "Philippine Trench"], "answer": 0, "difficulty": 2, "explanation": "The Mariana Trench is about 11,034 meters deep"},
            {"question": "What country is known as the Land of the Rising Sun?", "options": ["Japan", "China", "Korea", "Thailand"], "answer": 0, "difficulty": 1, "explanation": "Japan's name in Japanese means 'origin of the sun'"},
            {"question": "What is the largest lake in the world?", "options": ["Caspian Sea", "Lake Superior", "Lake Victoria", "Lake Baikal"], "answer": 0, "difficulty": 2, "explanation": "The Caspian Sea is technically a lake (371,000 km²)"},
            {"question": "What strait separates Europe from Africa?", "options": ["Strait of Gibraltar", "Bosphorus", "English Channel", "Dardanelles"], "answer": 0, "difficulty": 2, "explanation": "Gibraltar connects Mediterranean to Atlantic"},
            {"question": "What is the capital of Canada?", "options": ["Ottawa", "Toronto", "Vancouver", "Montreal"], "answer": 0, "difficulty": 2, "explanation": "Ottawa, not Toronto, is the capital"},
            {"question": "What is the largest island in the world?", "options": ["Greenland", "New Guinea", "Borneo", "Madagascar"], "answer": 0, "difficulty": 2, "explanation": "Greenland is about 2.2 million km²"},
            {"question": "How many time zones does Russia have?", "options": ["11", "9", "7", "5"], "answer": 0, "difficulty": 3, "explanation": "Russia spans 11 time zones"},
            {"question": "What is the capital of South Africa?", "options": ["Pretoria (executive)", "Cape Town", "Johannesburg", "Durban"], "answer": 0, "difficulty": 3, "explanation": "South Africa has three capitals; Pretoria is the executive capital"},
        ],

        # Literature (topic_id: 6)
        6: [
            {"question": "Who wrote 'Romeo and Juliet'?", "options": ["William Shakespeare", "Charles Dickens", "Jane Austen", "Mark Twain"], "answer": 0, "difficulty": 1, "explanation": "Shakespeare wrote it around 1594-1596"},
            {"question": "Who wrote '1984'?", "options": ["George Orwell", "Aldous Huxley", "Ray Bradbury", "H.G. Wells"], "answer": 0, "difficulty": 1, "explanation": "Orwell published 1984 in 1949"},
            {"question": "Who wrote 'Pride and Prejudice'?", "options": ["Jane Austen", "Charlotte Brontë", "Emily Brontë", "Mary Shelley"], "answer": 0, "difficulty": 1, "explanation": "Austen published it in 1813"},
            {"question": "What is the first book of the Bible?", "options": ["Genesis", "Exodus", "Leviticus", "Matthew"], "answer": 0, "difficulty": 1, "explanation": "Genesis tells of creation"},
            {"question": "Who wrote 'The Great Gatsby'?", "options": ["F. Scott Fitzgerald", "Ernest Hemingway", "John Steinbeck", "William Faulkner"], "answer": 0, "difficulty": 2, "explanation": "Fitzgerald published it in 1925"},
            {"question": "Who wrote 'Harry Potter'?", "options": ["J.K. Rowling", "J.R.R. Tolkien", "C.S. Lewis", "Stephen King"], "answer": 0, "difficulty": 1, "explanation": "Rowling published the first book in 1997"},
            {"question": "Who wrote 'The Odyssey'?", "options": ["Homer", "Virgil", "Sophocles", "Plato"], "answer": 0, "difficulty": 2, "explanation": "Homer wrote this ancient Greek epic"},
            {"question": "What is the longest novel ever written?", "options": ["In Search of Lost Time", "War and Peace", "Les Misérables", "Don Quixote"], "answer": 0, "difficulty": 3, "explanation": "Proust's novel has about 1.2 million words"},
            {"question": "Who wrote 'To Kill a Mockingbird'?", "options": ["Harper Lee", "Truman Capote", "John Grisham", "Ernest Hemingway"], "answer": 0, "difficulty": 1, "explanation": "Lee published it in 1960"},
            {"question": "What is a haiku?", "options": ["A Japanese poem with 5-7-5 syllables", "A Greek tragedy", "An English sonnet", "A French ballad"], "answer": 0, "difficulty": 2, "explanation": "Haiku have 17 syllables in 3 lines"},
            {"question": "Who wrote 'The Divine Comedy'?", "options": ["Dante Alighieri", "Giovanni Boccaccio", "Francesco Petrarch", "Niccolò Machiavelli"], "answer": 0, "difficulty": 2, "explanation": "Dante wrote it in the early 14th century"},
            {"question": "Who wrote 'Don Quixote'?", "options": ["Miguel de Cervantes", "Federico García Lorca", "Gabriel García Márquez", "Pablo Neruda"], "answer": 0, "difficulty": 2, "explanation": "Cervantes published it in 1605-1615"},
            {"question": "What is the name of Sherlock Holmes' assistant?", "options": ["Dr. Watson", "Inspector Lestrade", "Mycroft", "Moriarty"], "answer": 0, "difficulty": 1, "explanation": "Dr. John Watson narrates most Holmes stories"},
            {"question": "Who wrote 'The Catcher in the Rye'?", "options": ["J.D. Salinger", "John Updike", "Philip Roth", "Kurt Vonnegut"], "answer": 0, "difficulty": 2, "explanation": "Salinger published it in 1951"},
            {"question": "Who created the character Frankenstein's monster?", "options": ["Mary Shelley", "Bram Stoker", "Edgar Allan Poe", "H.P. Lovecraft"], "answer": 0, "difficulty": 2, "explanation": "Shelley wrote 'Frankenstein' in 1818"},
            {"question": "What is an iambic pentameter?", "options": ["A line with 10 syllables in 5 feet", "A 14-line poem", "A Greek tragedy", "A type of rhyme"], "answer": 0, "difficulty": 3, "explanation": "Common in Shakespeare's works"},
            {"question": "Who wrote 'Crime and Punishment'?", "options": ["Fyodor Dostoevsky", "Leo Tolstoy", "Anton Chekhov", "Ivan Turgenev"], "answer": 0, "difficulty": 2, "explanation": "Dostoevsky published it in 1866"},
            {"question": "What is the Iliad about?", "options": ["The Trojan War", "Odysseus' journey", "Roman history", "Greek gods"], "answer": 0, "difficulty": 2, "explanation": "Homer's epic about the Trojan War"},
            {"question": "Who wrote 'A Tale of Two Cities'?", "options": ["Charles Dickens", "Thomas Hardy", "George Eliot", "William Thackeray"], "answer": 0, "difficulty": 2, "explanation": "Dickens published it in 1859"},
            {"question": "What is a sonnet?", "options": ["A 14-line poem", "A 3-line poem", "A play", "A novel"], "answer": 0, "difficulty": 2, "explanation": "Sonnets have 14 lines with specific rhyme schemes"},
        ],

        # Computer Science (topic_id: 11)
        11: [
            {"question": "What does CPU stand for?", "options": ["Central Processing Unit", "Computer Personal Unit", "Central Program Utility", "Core Processing Unit"], "answer": 0, "difficulty": 1, "explanation": "The CPU is the brain of the computer"},
            {"question": "What does HTML stand for?", "options": ["HyperText Markup Language", "High Tech Modern Language", "Hyper Transfer Markup Language", "Home Tool Markup Language"], "answer": 0, "difficulty": 1, "explanation": "HTML is the standard language for web pages"},
            {"question": "What is an algorithm?", "options": ["A step-by-step procedure", "A programming language", "A computer virus", "A type of hardware"], "answer": 0, "difficulty": 1, "explanation": "Algorithms are instructions to solve problems"},
            {"question": "What is binary code made of?", "options": ["0s and 1s", "Letters and numbers", "Symbols", "All characters"], "answer": 0, "difficulty": 1, "explanation": "Binary uses only two digits: 0 and 1"},
            {"question": "What does RAM stand for?", "options": ["Random Access Memory", "Read Access Memory", "Run Application Memory", "Rapid Access Module"], "answer": 0, "difficulty": 1, "explanation": "RAM is temporary working memory"},
            {"question": "Who is considered the father of computer science?", "options": ["Alan Turing", "Bill Gates", "Steve Jobs", "Charles Babbage"], "answer": 0, "difficulty": 2, "explanation": "Turing laid the foundations of theoretical computer science"},
            {"question": "What is an operating system?", "options": ["Software that manages hardware", "A programming language", "An application", "A computer virus"], "answer": 0, "difficulty": 1, "explanation": "Examples: Windows, macOS, Linux"},
            {"question": "What does SQL stand for?", "options": ["Structured Query Language", "Simple Question Language", "System Query Logic", "Standard Query List"], "answer": 0, "difficulty": 2, "explanation": "SQL is used to manage databases"},
            {"question": "What is a compiler?", "options": ["Translates code to machine language", "A type of CPU", "A programming language", "A text editor"], "answer": 0, "difficulty": 2, "explanation": "Compilers convert source code to executable programs"},
            {"question": "What is the time complexity of binary search?", "options": ["O(log n)", "O(n)", "O(n²)", "O(1)"], "answer": 0, "difficulty": 3, "explanation": "Binary search halves the search space each iteration"},
            {"question": "What is a variable in programming?", "options": ["A named storage location", "A function", "A loop", "A class"], "answer": 0, "difficulty": 1, "explanation": "Variables store data values"},
            {"question": "What does HTTP stand for?", "options": ["HyperText Transfer Protocol", "High Tech Transfer Protocol", "Hyper Transfer Text Protocol", "Home Transfer Text Protocol"], "answer": 0, "difficulty": 1, "explanation": "HTTP is the protocol for web communication"},
            {"question": "What is recursion?", "options": ["A function calling itself", "A loop", "A variable", "A data type"], "answer": 0, "difficulty": 2, "explanation": "Recursive functions solve problems by self-reference"},
            {"question": "What is a data structure?", "options": ["A way to organize data", "A programming language", "A hardware component", "An algorithm"], "answer": 0, "difficulty": 2, "explanation": "Examples: arrays, linked lists, trees"},
            {"question": "What is the difference between '=' and '==' in programming?", "options": ["Assignment vs comparison", "Both are the same", "Both are comparisons", "Both are assignments"], "answer": 0, "difficulty": 2, "explanation": "'=' assigns, '==' compares for equality"},
            {"question": "What is a database?", "options": ["Organized collection of data", "A programming language", "A type of CPU", "A network protocol"], "answer": 0, "difficulty": 1, "explanation": "Databases store and manage structured data"},
            {"question": "What is an API?", "options": ["Application Programming Interface", "Advanced Program Integration", "Automatic Process Interface", "Application Process Integration"], "answer": 0, "difficulty": 2, "explanation": "APIs allow software to communicate"},
            {"question": "What is machine learning?", "options": ["Computers learning from data", "Manual programming", "Hardware maintenance", "Network security"], "answer": 0, "difficulty": 2, "explanation": "ML enables systems to learn without explicit programming"},
            {"question": "What is object-oriented programming?", "options": ["Programming with objects and classes", "Programming with functions only", "Assembly programming", "Machine code"], "answer": 0, "difficulty": 2, "explanation": "OOP uses objects to model real-world entities"},
            {"question": "What is Big O notation used for?", "options": ["Describing algorithm efficiency", "Writing code", "Debugging", "Documentation"], "answer": 0, "difficulty": 3, "explanation": "Big O describes time/space complexity"},
        ],

        # Economics (topic_id: 12)
        12: [
            {"question": "What is inflation?", "options": ["Rising prices over time", "Falling prices", "Stable prices", "Currency exchange"], "answer": 0, "difficulty": 1, "explanation": "Inflation reduces purchasing power"},
            {"question": "What is GDP?", "options": ["Gross Domestic Product", "General Development Plan", "Global Distribution Protocol", "Government Domestic Policy"], "answer": 0, "difficulty": 1, "explanation": "GDP measures a country's economic output"},
            {"question": "What is supply and demand?", "options": ["Economic model of price determination", "Government policy", "Trade agreement", "Banking system"], "answer": 0, "difficulty": 1, "explanation": "Prices are set where supply meets demand"},
            {"question": "What is a monopoly?", "options": ["Single seller in a market", "Many sellers", "Government control", "Trade union"], "answer": 0, "difficulty": 2, "explanation": "Monopolies have no competition"},
            {"question": "What is a recession?", "options": ["Economic decline", "Economic growth", "Stable economy", "Trade surplus"], "answer": 0, "difficulty": 1, "explanation": "Two consecutive quarters of GDP decline"},
            {"question": "What does the Federal Reserve do?", "options": ["Controls US monetary policy", "Makes laws", "Collects taxes", "Prints money only"], "answer": 0, "difficulty": 2, "explanation": "The Fed manages interest rates and money supply"},
            {"question": "What is opportunity cost?", "options": ["Value of next best alternative", "Actual cost", "Total cost", "Fixed cost"], "answer": 0, "difficulty": 2, "explanation": "What you give up when making a choice"},
            {"question": "What is a stock?", "options": ["Share of company ownership", "Government bond", "Bank loan", "Currency"], "answer": 0, "difficulty": 1, "explanation": "Stocks represent equity in a company"},
            {"question": "What is a trade deficit?", "options": ["Imports exceed exports", "Exports exceed imports", "Balanced trade", "No trade"], "answer": 0, "difficulty": 2, "explanation": "A country buys more than it sells"},
            {"question": "What is capitalism?", "options": ["Private ownership of production", "Government ownership", "Collective ownership", "No ownership"], "answer": 0, "difficulty": 1, "explanation": "Capitalism is based on private property and free markets"},
            {"question": "What is unemployment rate?", "options": ["Percentage of workforce without jobs", "Number of jobs", "Total population", "Working population"], "answer": 0, "difficulty": 1, "explanation": "Measures jobless people actively seeking work"},
            {"question": "What is a bond?", "options": ["A debt security", "Company stock", "Currency", "Commodity"], "answer": 0, "difficulty": 2, "explanation": "Bonds are loans to governments or corporations"},
            {"question": "What is fiscal policy?", "options": ["Government spending and taxation", "Central bank policy", "Trade policy", "Banking regulation"], "answer": 0, "difficulty": 2, "explanation": "Fiscal policy uses budget to influence economy"},
            {"question": "What is interest rate?", "options": ["Cost of borrowing money", "Exchange rate", "Tax rate", "Growth rate"], "answer": 0, "difficulty": 1, "explanation": "Interest is the price of borrowing"},
            {"question": "What is microeconomics?", "options": ["Study of individual economic units", "Study of national economy", "Study of international trade", "Study of money"], "answer": 0, "difficulty": 2, "explanation": "Micro focuses on firms and consumers"},
            {"question": "What is a tariff?", "options": ["Tax on imports", "Export subsidy", "Trade agreement", "Currency control"], "answer": 0, "difficulty": 2, "explanation": "Tariffs protect domestic industries"},
            {"question": "What causes inflation?", "options": ["Too much money, few goods", "Too little money", "Balanced economy", "Trade surplus"], "answer": 0, "difficulty": 2, "explanation": "Inflation occurs when demand exceeds supply"},
            {"question": "What is elasticity in economics?", "options": ["Responsiveness to price changes", "Market size", "Production cost", "Trade volume"], "answer": 0, "difficulty": 3, "explanation": "Elastic goods see big demand changes with price"},
            {"question": "What is the law of diminishing returns?", "options": ["Additional inputs yield less output", "More inputs, more output always", "Constant returns", "No returns"], "answer": 0, "difficulty": 3, "explanation": "After a point, each unit adds less"},
            {"question": "What is a central bank?", "options": ["Institution managing monetary policy", "Commercial bank", "Investment bank", "Retail bank"], "answer": 0, "difficulty": 2, "explanation": "Examples: Federal Reserve, European Central Bank"},
        ],
    }

def main():
    """Main function to generate and insert questions."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate questions for SharvaYoutubePro')
    parser.add_argument('--topic', type=int, help='Topic ID to generate for')
    parser.add_argument('--count', type=int, default=20, help='Number of questions to generate')
    parser.add_argument('--difficulty', type=int, default=2, help='Difficulty level (1-5)')
    parser.add_argument('--builtin', action='store_true', help='Insert built-in questions')
    parser.add_argument('--mistral', action='store_true', help='Generate with Mistral')
    parser.add_argument('--subtopic', type=str, help='Subtopic for Mistral generation')

    args = parser.parse_args()

    conn = get_db_connection()

    if args.builtin:
        # Insert all built-in questions
        total = 0
        builtin = get_builtin_questions()
        for topic_id, questions in builtin.items():
            count = insert_questions(conn, topic_id, questions, "built-in")
            total += count
            print(f"Inserted {count} questions for topic {topic_id}")
        print(f"Total: {total} built-in questions inserted")

    elif args.mistral and args.topic and args.subtopic:
        # Generate with Mistral
        print(f"Generating {args.count} questions about {args.subtopic}...")
        questions = generate_with_mistral(
            "Academic",
            args.subtopic,
            args.count,
            args.difficulty
        )
        if questions:
            for q in questions:
                q['difficulty'] = args.difficulty
            count = insert_questions(conn, args.topic, questions, "mistral")
            print(f"Inserted {count} questions")
        else:
            print("Failed to generate questions")

    else:
        print("Usage:")
        print("  --builtin           Insert all built-in questions")
        print("  --mistral --topic 8 --subtopic 'Quantum Physics' --count 20")

    conn.close()

if __name__ == "__main__":
    main()
