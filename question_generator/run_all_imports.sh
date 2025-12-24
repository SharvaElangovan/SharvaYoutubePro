#!/bin/bash
cd /home/sharva/projects/SharvaYoutubePro/question_generator

echo "Starting sequential imports at $(date)"

echo "=== NarrativeQA ===" && python3 bulk_import.py --narrativeqa
echo "=== CMU QA ===" && python3 bulk_import.py --cmuqa
echo "=== el-cms ===" && python3 bulk_import.py --elcms
echo "=== DuoRC ===" && python3 bulk_import.py --duorc
echo "=== RACE ===" && python3 bulk_import.py --race
echo "=== BoolQ ===" && python3 bulk_import.py --boolq
echo "=== DROP ===" && python3 bulk_import.py --drop
echo "=== WinoGrande ===" && python3 bulk_import.py --winogrande
echo "=== HellaSwag ===" && python3 bulk_import.py --hellaswag
echo "=== TriviaQA ===" && python3 bulk_import.py --triviaqa
echo "=== QuAC ===" && python3 bulk_import.py --quac
echo "=== CoQA ===" && python3 bulk_import.py --coqa

echo "All imports completed at $(date)"
python3 bulk_import.py --stats
