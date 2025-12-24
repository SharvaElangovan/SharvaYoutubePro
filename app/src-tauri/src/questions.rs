use serde::{Deserialize, Serialize};
use sqlx::SqlitePool;
use tauri::State;

#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct Topic {
    pub id: i64,
    pub name: String,
    pub parent_id: Option<i64>,
    pub description: Option<String>,
    pub icon: Option<String>,
}

#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct TopicWithCount {
    pub id: i64,
    pub name: String,
    pub parent_id: Option<i64>,
    pub description: Option<String>,
    pub icon: Option<String>,
    pub question_count: i64,
}

#[derive(Debug, Serialize, Deserialize, sqlx::FromRow)]
pub struct Question {
    pub id: i64,
    pub topic_id: i64,
    pub question: String,
    pub option_a: String,
    pub option_b: String,
    pub option_c: String,
    pub option_d: String,
    pub correct_answer: i32,
    pub difficulty: i32,
    pub explanation: Option<String>,
    pub source: Option<String>,
    pub times_used: i32,
}

#[derive(Debug, Deserialize)]
pub struct NewQuestion {
    pub topic_id: i64,
    pub question: String,
    pub option_a: String,
    pub option_b: String,
    pub option_c: String,
    pub option_d: String,
    pub correct_answer: i32,
    pub difficulty: Option<i32>,
    pub explanation: Option<String>,
    pub source: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct QuestionStats {
    pub total_questions: i64,
    pub by_topic: Vec<TopicWithCount>,
    pub by_difficulty: Vec<DifficultyCount>,
}

#[derive(Debug, Serialize, sqlx::FromRow)]
pub struct DifficultyCount {
    pub difficulty: i32,
    pub count: i64,
}

#[tauri::command]
pub async fn get_topics(pool: State<'_, SqlitePool>) -> Result<Vec<TopicWithCount>, String> {
    let topics = sqlx::query_as::<_, TopicWithCount>(
        r#"
        SELECT
            t.id, t.name, t.parent_id, t.description, t.icon,
            COUNT(q.id) as question_count
        FROM topics t
        LEFT JOIN question_bank q ON t.id = q.topic_id
        GROUP BY t.id
        ORDER BY t.parent_id NULLS FIRST, t.name
        "#,
    )
    .fetch_all(pool.inner())
    .await
    .map_err(|e| e.to_string())?;

    Ok(topics)
}

#[tauri::command]
pub async fn get_question_stats(pool: State<'_, SqlitePool>) -> Result<QuestionStats, String> {
    let total: (i64,) = sqlx::query_as("SELECT COUNT(*) FROM question_bank")
        .fetch_one(pool.inner())
        .await
        .map_err(|e| e.to_string())?;

    let by_topic = sqlx::query_as::<_, TopicWithCount>(
        r#"
        SELECT
            t.id, t.name, t.parent_id, t.description, t.icon,
            COUNT(q.id) as question_count
        FROM topics t
        LEFT JOIN question_bank q ON t.id = q.topic_id
        GROUP BY t.id
        HAVING question_count > 0
        ORDER BY question_count DESC
        "#,
    )
    .fetch_all(pool.inner())
    .await
    .map_err(|e| e.to_string())?;

    let by_difficulty = sqlx::query_as::<_, DifficultyCount>(
        "SELECT difficulty, COUNT(*) as count FROM question_bank GROUP BY difficulty ORDER BY difficulty"
    )
    .fetch_all(pool.inner())
    .await
    .map_err(|e| e.to_string())?;

    Ok(QuestionStats {
        total_questions: total.0,
        by_topic,
        by_difficulty,
    })
}

#[tauri::command]
pub async fn get_questions(
    pool: State<'_, SqlitePool>,
    topic_id: Option<i64>,
    difficulty: Option<i32>,
    limit: Option<i64>,
    offset: Option<i64>,
) -> Result<Vec<Question>, String> {
    let limit = limit.unwrap_or(50);
    let offset = offset.unwrap_or(0);

    let questions = match (topic_id, difficulty) {
        (Some(tid), Some(diff)) => {
            sqlx::query_as::<_, Question>(
                "SELECT * FROM question_bank WHERE topic_id = ? AND difficulty = ? LIMIT ? OFFSET ?"
            )
            .bind(tid)
            .bind(diff)
            .bind(limit)
            .bind(offset)
            .fetch_all(pool.inner())
            .await
        }
        (Some(tid), None) => {
            sqlx::query_as::<_, Question>(
                "SELECT * FROM question_bank WHERE topic_id = ? LIMIT ? OFFSET ?"
            )
            .bind(tid)
            .bind(limit)
            .bind(offset)
            .fetch_all(pool.inner())
            .await
        }
        (None, Some(diff)) => {
            sqlx::query_as::<_, Question>(
                "SELECT * FROM question_bank WHERE difficulty = ? LIMIT ? OFFSET ?"
            )
            .bind(diff)
            .bind(limit)
            .bind(offset)
            .fetch_all(pool.inner())
            .await
        }
        (None, None) => {
            sqlx::query_as::<_, Question>(
                "SELECT * FROM question_bank LIMIT ? OFFSET ?"
            )
            .bind(limit)
            .bind(offset)
            .fetch_all(pool.inner())
            .await
        }
    }
    .map_err(|e| e.to_string())?;

    Ok(questions)
}

#[tauri::command]
pub async fn get_random_questions(
    pool: State<'_, SqlitePool>,
    topic_id: Option<i64>,
    count: i64,
    difficulty: Option<i32>,
) -> Result<Vec<Question>, String> {
    let questions = match (topic_id, difficulty) {
        (Some(tid), Some(diff)) => {
            sqlx::query_as::<_, Question>(
                "SELECT * FROM question_bank WHERE topic_id = ? AND difficulty = ? ORDER BY RANDOM() LIMIT ?"
            )
            .bind(tid)
            .bind(diff)
            .bind(count)
            .fetch_all(pool.inner())
            .await
        }
        (Some(tid), None) => {
            sqlx::query_as::<_, Question>(
                "SELECT * FROM question_bank WHERE topic_id = ? ORDER BY RANDOM() LIMIT ?"
            )
            .bind(tid)
            .bind(count)
            .fetch_all(pool.inner())
            .await
        }
        (None, Some(diff)) => {
            sqlx::query_as::<_, Question>(
                "SELECT * FROM question_bank WHERE difficulty = ? ORDER BY RANDOM() LIMIT ?"
            )
            .bind(diff)
            .bind(count)
            .fetch_all(pool.inner())
            .await
        }
        (None, None) => {
            sqlx::query_as::<_, Question>(
                "SELECT * FROM question_bank ORDER BY RANDOM() LIMIT ?"
            )
            .bind(count)
            .fetch_all(pool.inner())
            .await
        }
    }
    .map_err(|e| e.to_string())?;

    Ok(questions)
}

#[tauri::command]
pub async fn add_question(
    pool: State<'_, SqlitePool>,
    question: NewQuestion,
) -> Result<i64, String> {
    let result = sqlx::query(
        r#"
        INSERT INTO question_bank (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, explanation, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        "#,
    )
    .bind(question.topic_id)
    .bind(&question.question)
    .bind(&question.option_a)
    .bind(&question.option_b)
    .bind(&question.option_c)
    .bind(&question.option_d)
    .bind(question.correct_answer)
    .bind(question.difficulty.unwrap_or(1))
    .bind(&question.explanation)
    .bind(&question.source)
    .execute(pool.inner())
    .await
    .map_err(|e| e.to_string())?;

    Ok(result.last_insert_rowid())
}

#[tauri::command]
pub async fn add_questions_bulk(
    pool: State<'_, SqlitePool>,
    questions: Vec<NewQuestion>,
) -> Result<i64, String> {
    let mut count = 0i64;

    for question in questions {
        sqlx::query(
            r#"
            INSERT INTO question_bank (topic_id, question, option_a, option_b, option_c, option_d, correct_answer, difficulty, explanation, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            "#,
        )
        .bind(question.topic_id)
        .bind(&question.question)
        .bind(&question.option_a)
        .bind(&question.option_b)
        .bind(&question.option_c)
        .bind(&question.option_d)
        .bind(question.correct_answer)
        .bind(question.difficulty.unwrap_or(1))
        .bind(&question.explanation)
        .bind(&question.source)
        .execute(pool.inner())
        .await
        .map_err(|e| e.to_string())?;

        count += 1;
    }

    Ok(count)
}

#[tauri::command]
pub async fn delete_question(pool: State<'_, SqlitePool>, id: i64) -> Result<(), String> {
    sqlx::query("DELETE FROM question_bank WHERE id = ?")
        .bind(id)
        .execute(pool.inner())
        .await
        .map_err(|e| e.to_string())?;

    Ok(())
}

#[tauri::command]
pub async fn add_topic(
    pool: State<'_, SqlitePool>,
    name: String,
    parent_id: Option<i64>,
    description: Option<String>,
    icon: Option<String>,
) -> Result<i64, String> {
    let result = sqlx::query(
        "INSERT INTO topics (name, parent_id, description, icon) VALUES (?, ?, ?, ?)",
    )
    .bind(&name)
    .bind(parent_id)
    .bind(&description)
    .bind(&icon)
    .execute(pool.inner())
    .await
    .map_err(|e| e.to_string())?;

    Ok(result.last_insert_rowid())
}

#[tauri::command]
pub async fn increment_question_usage(pool: State<'_, SqlitePool>, id: i64) -> Result<(), String> {
    sqlx::query("UPDATE question_bank SET times_used = times_used + 1 WHERE id = ?")
        .bind(id)
        .execute(pool.inner())
        .await
        .map_err(|e| e.to_string())?;

    Ok(())
}
