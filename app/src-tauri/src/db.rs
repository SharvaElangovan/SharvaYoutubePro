use sqlx::SqlitePool;

pub async fn run_migrations(pool: &SqlitePool) -> Result<(), sqlx::Error> {
    // Create topics table (hierarchical categories)
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            parent_id INTEGER,
            description TEXT,
            icon TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES topics(id) ON DELETE CASCADE
        )
        "#,
    )
    .execute(pool)
    .await?;

    // Create index for topic hierarchy
    sqlx::query("CREATE INDEX IF NOT EXISTS idx_topics_parent ON topics(parent_id)")
        .execute(pool)
        .await?;

    // Create massive question bank table
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS question_bank (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            question TEXT NOT NULL,
            option_a TEXT NOT NULL,
            option_b TEXT NOT NULL,
            option_c TEXT NOT NULL,
            option_d TEXT NOT NULL,
            correct_answer INTEGER NOT NULL CHECK (correct_answer BETWEEN 0 AND 3),
            difficulty INTEGER DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 5),
            explanation TEXT,
            source TEXT,
            times_used INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE CASCADE
        )
        "#,
    )
    .execute(pool)
    .await?;

    // Create indexes for fast queries
    sqlx::query("CREATE INDEX IF NOT EXISTS idx_questions_topic ON question_bank(topic_id)")
        .execute(pool)
        .await?;
    sqlx::query("CREATE INDEX IF NOT EXISTS idx_questions_difficulty ON question_bank(difficulty)")
        .execute(pool)
        .await?;
    sqlx::query("CREATE INDEX IF NOT EXISTS idx_questions_used ON question_bank(times_used)")
        .execute(pool)
        .await?;

    // Create projects table
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        "#,
    )
    .execute(pool)
    .await?;

    // Create videos table
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            title TEXT NOT NULL,
            file_path TEXT,
            youtube_id TEXT,
            status TEXT DEFAULT 'draft',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            uploaded_at DATETIME,
            FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
        )
        "#,
    )
    .execute(pool)
    .await?;

    // Create settings table
    sqlx::query(
        r#"
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        "#,
    )
    .execute(pool)
    .await?;

    // Insert comprehensive topics
    sqlx::query(
        r#"
        INSERT OR IGNORE INTO topics (id, name, parent_id, description, icon) VALUES
        -- Main Categories
        (1, 'Academic', NULL, 'Academic subjects and educational topics', '🎓'),
        (100, 'Entertainment', NULL, 'Movies, TV, music, games', '🎬'),
        (200, 'Technology', NULL, 'Computers, gadgets, internet', '💻'),
        (300, 'Sports', NULL, 'All sports and athletics', '⚽'),
        (400, 'Nature', NULL, 'Animals, plants, environment', '🌿'),
        (500, 'Transportation', NULL, 'Cars, planes, trains, ships', '🚗'),
        (600, 'Food & Cooking', NULL, 'Cuisine, recipes, nutrition', '🍳'),
        (700, 'World Culture', NULL, 'Countries, traditions, languages', '🌍'),
        (800, 'Health & Body', NULL, 'Medicine, fitness, wellness', '💪'),
        (900, 'Space & Astronomy', NULL, 'Planets, stars, space exploration', '🚀'),

        -- Academic Subtopics
        (2, 'Mathematics', 1, 'Math, algebra, geometry, calculus', '🔢'),
        (3, 'Science', 1, 'Physics, chemistry, biology', '🔬'),
        (4, 'History', 1, 'World history, civilizations, events', '📜'),
        (5, 'Geography', 1, 'Countries, capitals, landmarks', '🗺️'),
        (6, 'Literature', 1, 'Books, authors, poetry', '📚'),
        (7, 'Language', 1, 'Grammar, vocabulary, linguistics', '🗣️'),
        (8, 'Physics', 3, 'Mechanics, thermodynamics, quantum', '⚛️'),
        (9, 'Chemistry', 3, 'Elements, reactions, organic chemistry', '🧪'),
        (10, 'Biology', 3, 'Life sciences, anatomy, ecology', '🧬'),
        (11, 'Computer Science', 1, 'Programming, algorithms, technology', '💻'),
        (12, 'Economics', 1, 'Micro/macro economics, finance', '📈'),
        (13, 'Philosophy', 1, 'Logic, ethics, metaphysics', '🤔'),
        (14, 'Psychology', 1, 'Mind, behavior, cognitive science', '🧠'),
        (15, 'Art History', 1, 'Visual arts, artists, movements', '🎨'),
        (16, 'Music Theory', 1, 'Notes, scales, composers', '🎵'),

        -- Entertainment Subtopics
        (101, 'Movies', 100, 'Films, directors, actors', '🎬'),
        (102, 'Television', 100, 'TV shows, series, streaming', '📺'),
        (103, 'Music', 100, 'Artists, bands, genres, songs', '🎸'),
        (104, 'Video Games', 100, 'Gaming, consoles, characters', '🎮'),
        (105, 'Celebrities', 100, 'Famous people, pop culture', '⭐'),
        (106, 'Comics & Anime', 100, 'Superheroes, manga, animation', '🦸'),

        -- Technology Subtopics
        (201, 'Computers', 200, 'Hardware, software, operating systems', '🖥️'),
        (202, 'Internet', 200, 'Web, social media, online services', '🌐'),
        (203, 'Smartphones', 200, 'Mobile phones, apps, features', '📱'),
        (204, 'Programming', 200, 'Coding, languages, development', '👨‍💻'),
        (205, 'AI & Robotics', 200, 'Artificial intelligence, robots', '🤖'),
        (206, 'Gadgets', 200, 'Electronics, devices, inventions', '🔌'),

        -- Sports Subtopics
        (301, 'Football/Soccer', 300, 'FIFA, leagues, players', '⚽'),
        (302, 'Basketball', 300, 'NBA, teams, players', '🏀'),
        (303, 'American Football', 300, 'NFL, Super Bowl, teams', '🏈'),
        (304, 'Baseball', 300, 'MLB, World Series, players', '⚾'),
        (305, 'Tennis', 300, 'Grand Slams, players, rules', '🎾'),
        (306, 'Olympics', 300, 'Olympic games, records, athletes', '🏅'),
        (307, 'Cricket', 300, 'World Cup, players, rules', '🏏'),
        (308, 'Motor Sports', 300, 'F1, NASCAR, MotoGP', '🏎️'),

        -- Nature Subtopics
        (401, 'Animals', 400, 'Wildlife, pets, species', '🦁'),
        (402, 'Plants', 400, 'Flowers, trees, botany', '🌸'),
        (403, 'Oceans', 400, 'Marine life, seas, underwater', '🐋'),
        (404, 'Weather', 400, 'Climate, storms, meteorology', '🌤️'),
        (405, 'Environment', 400, 'Ecology, conservation, climate change', '♻️'),

        -- Transportation Subtopics
        (501, 'Cars', 500, 'Automobiles, brands, history', '🚗'),
        (502, 'Planes', 500, 'Aviation, airlines, aircraft', '✈️'),
        (503, 'Trains', 500, 'Railways, locomotives, metro', '🚂'),
        (504, 'Ships', 500, 'Naval, boats, maritime', '🚢'),
        (505, 'Motorcycles', 500, 'Bikes, brands, racing', '🏍️'),

        -- Food Subtopics
        (601, 'World Cuisine', 600, 'International dishes, recipes', '🍜'),
        (602, 'Nutrition', 600, 'Diet, vitamins, health food', '🥗'),
        (603, 'Beverages', 600, 'Drinks, coffee, tea, wine', '☕'),
        (604, 'Desserts', 600, 'Sweets, baking, pastries', '🍰'),

        -- World Culture Subtopics
        (701, 'Countries', 700, 'Nations, flags, governments', '🏳️'),
        (702, 'Languages', 700, 'World languages, linguistics', '🗣️'),
        (703, 'Religions', 700, 'World religions, beliefs', '🕯️'),
        (704, 'Holidays', 700, 'Celebrations, festivals', '🎉'),
        (705, 'Architecture', 700, 'Buildings, landmarks, styles', '🏛️'),

        -- Health Subtopics
        (801, 'Human Body', 800, 'Anatomy, organs, systems', '🫀'),
        (802, 'Medicine', 800, 'Diseases, treatments, drugs', '💊'),
        (803, 'Fitness', 800, 'Exercise, workouts, sports', '🏋️'),
        (804, 'Mental Health', 800, 'Psychology, wellness, mind', '🧘'),

        -- Space Subtopics
        (901, 'Solar System', 900, 'Planets, moons, sun', '🪐'),
        (902, 'Stars & Galaxies', 900, 'Astronomy, constellations', '⭐'),
        (903, 'Space Exploration', 900, 'NASA, missions, astronauts', '👨‍🚀'),
        (904, 'Universe', 900, 'Cosmology, black holes, big bang', '🌌')
        "#,
    )
    .execute(pool)
    .await?;

    Ok(())
}
