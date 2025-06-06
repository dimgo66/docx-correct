"""
@file: structurize_html_prince.py
@description: Автоматическое семантическое структурирование HTML по правилам prince-rules с помощью LLM Cursor
@dependencies: docs/prince_rules.md, исходный HTML-файл, Cursor LLM
@created: 2024-07-27
"""

import argparse
import shutil
from pathlib import Path

# --- Константы ---
PRINCE_RULES_PATH = 'docs/prince_rules.md'

# --- Функции ---
def read_file_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def save_file_text(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

def make_backup(src_path):
    backup_path = src_path.with_suffix(src_path.suffix + '.bak')
    shutil.copy2(src_path, backup_path)
    print(f'[INFO] Резервная копия создана: {backup_path}')
    return backup_path

def build_prompt(html_text, rules_text):
    return f"""
Выполни семантическое структурирование HTML-документа по следующим правилам:
---
{rules_text}
---
Вот исходный HTML:
---
{html_text}
---
Верни только исправленный HTML, без пояснений и комментариев. Соблюдай все рекомендации и структуру из правил.
"""

def call_llm_structurize(prompt):
    """
    Вызывает LLM Cursor через functions.mcp_sequential-thinking_sequentialthinking.
    Работает только в среде Cursor! Возвращает исправленный HTML из ответа LLM.
    """
    response = functions.mcp_sequential-thinking_sequentialthinking({
        "thought": prompt,
        "nextThoughtNeeded": False,
        "thoughtNumber": 1,
        "totalThoughts": 1
    })
    # Ожидаем, что LLM вернёт только HTML (без пояснений)
    answer = response.get('answer') or response.get('thought') or ''
    return answer.strip()

# --- Основной скрипт ---
def main():
    parser = argparse.ArgumentParser(description='Семантическое структурирование HTML по правилам prince-rules с помощью LLM Cursor')
    parser.add_argument('html_path', type=str, help='Путь к исходному HTML-файлу')
    parser.add_argument('--out', type=str, default=None, help='Путь для сохранения структурированного HTML')
    args = parser.parse_args()

    html_path = Path(args.html_path)
    if not html_path.exists():
        print(f'[ERROR] Файл {html_path} не найден')
        return

    # Читаем правила и HTML
    rules_text = read_file_text(PRINCE_RULES_PATH)
    html_text = read_file_text(html_path)

    # Делаем резервную копию
    make_backup(html_path)

    # Формируем промпт
    prompt = build_prompt(html_text, rules_text)
    print('[INFO] Промпт для LLM сформирован.')
    print(f"\n--- Промпт для LLM: ---\n{prompt}\n---")
    return
    # --- Дальнейшие действия отключены для теста вне Cursor ---
    # result_html = call_llm_structurize(prompt)
    # print('[INFO] Ответ LLM получен.')
    # out_path = Path(args.out) if args.out else html_path.with_name(html_path.stem + '_sem.html')
    # save_file_text(out_path, result_html)
    # print(f'[INFO] Структурированный HTML сохранён: {out_path}')

if __name__ == '__main__':
    main() 