"""
@file: split_and_prompt_html.py
@description: Делит большой HTML-файл на части, формирует промпт для каждой части, сохраняет промпты в отдельные файлы, собирает итоговый HTML из обработанных частей.
@dependencies: docs/prince_rules.md, исходный HTML-файл, обработанные части HTML
@created: 2024-07-29

Использование:
1. Разбить HTML и сгенерировать промпты:
   python3 tools/split_and_prompt_html.py split <html_path> [lines_per_chunk]
2. Собрать итоговый HTML из обработанных частей:
   python3 tools/split_and_prompt_html.py merge <output_prefix> <num_parts> <merged_output>

Пример:
  python3 tools/split_and_prompt_html.py split reports/pisk/pisk.html 500
  # После обработки частей в LLM:
  python3 tools/split_and_prompt_html.py merge output_part 5 output_merged.html
"""
import sys
import os

def read_file_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file_text(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

def split_html_and_generate_prompts(html_path, rules_path, lines_per_chunk=500):
    html_lines = read_file_text(html_path).splitlines(keepends=True)
    rules_text = read_file_text(rules_path)
    total = len(html_lines)
    num_parts = (total + lines_per_chunk - 1) // lines_per_chunk
    part = 1
    prompts = []
    for i in range(0, total, lines_per_chunk):
        chunk = ''.join(html_lines[i:i+lines_per_chunk])
        prompt = f"""
Часть {part} из {num_parts}
Выполни семантическое структурирование HTML-документа по следующим правилам:
---
{rules_text}
---
Вот исходный HTML:
---
{chunk}
---
Верни только исправленный HTML, без пояснений и комментариев. Соблюдай все рекомендации и структуру из правил.
"""
        prompt_file = f"prompt_part{part}.txt"
        write_file_text(prompt_file, prompt)
        print(f"Сохранён промпт: {prompt_file}")
        prompts.append(prompt_file)
        part += 1
    print(f"Всего частей: {num_parts}")
    return prompts

def merge_processed_parts(output_prefix, num_parts, merged_output):
    merged = ''
    for i in range(1, num_parts+1):
        part_file = f"{output_prefix}{i}.html"
        if not os.path.exists(part_file):
            print(f"[WARN] Не найден файл: {part_file}")
            continue
        merged += read_file_text(part_file)
        merged += '\n'  # Разделитель между частями
    write_file_text(merged_output, merged)
    print(f"Итоговый HTML сохранён: {merged_output}")

def main():
    if len(sys.argv) < 3:
        print("Использование:\n  split <html_path> [lines_per_chunk]\n  merge <output_prefix> <num_parts> <merged_output>")
        return
    mode = sys.argv[1]
    if mode == 'split':
        html_path = sys.argv[2]
        lines_per_chunk = int(sys.argv[3]) if len(sys.argv) > 3 else 500
        rules_path = 'docs/prince_rules.md'
        split_html_and_generate_prompts(html_path, rules_path, lines_per_chunk)
    elif mode == 'merge':
        if len(sys.argv) < 5:
            print("Использование: merge <output_prefix> <num_parts> <merged_output>")
            return
        output_prefix = sys.argv[2]
        num_parts = int(sys.argv[3])
        merged_output = sys.argv[4]
        merge_processed_parts(output_prefix, num_parts, merged_output)
    else:
        print("Неизвестный режим. Используйте split или merge.")

if __name__ == "__main__":
    main() 