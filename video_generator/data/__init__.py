# Data banks for JSON generation
from .question_bank import QUESTIONS, get_random_questions, get_questions_count
from .emoji_bank import EMOJI_PUZZLES, get_random_puzzles, get_puzzles_by_category, get_all_categories, get_puzzles_count

__all__ = [
    'QUESTIONS', 'get_random_questions', 'get_questions_count',
    'EMOJI_PUZZLES', 'get_random_puzzles', 'get_puzzles_by_category',
    'get_all_categories', 'get_puzzles_count'
]
