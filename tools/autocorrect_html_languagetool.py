"""
/**
 * @file: autocorrect_html_languagetool.py
 * @description: Скрипт для попытки автоматического исправления "очевидных" ошибок в HTML-файле на основе JSON-отчета LanguageTool, с привлечением LLM для подтверждения.
 * @dependencies: Python 3, openai
 * @created: 2024-07-26
 * @updated: 2024-07-29
 */
"""

import argparse
import json
import sys
import shutil
from pathlib import Path
import re
import os
from openai import OpenAI

# Настройка OpenRouter API клиента
# ВАЖНО: Рекомендуется переместить API ключ в переменную окружения!
# OPENROUTER_API_KEY = "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" # Закомментировано
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") # Предпочтительный способ

MODEL_NAME = "google/gemini-flash-1.5" # Gemini 1.5 Flash Preview 05-20 (идентификатор может немного отличаться)

open_router_client = None
if OPENROUTER_API_KEY:
    try:
        open_router_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
    except Exception as e:
        print(f"Ошибка инициализации клиента OpenRouter: {e}", file=sys.stderr)
else:
    print("Ошибка: API ключ для OpenRouter не найден. Установите OPENROUTER_API_KEY.", file=sys.stderr)

# Правила, которые мы пока считаем кандидатами на автозамену (если 1 вариант)
# В основном орфография, но можно расширить
AUTOFIX_CANDIDATE_RULE_IDS = {
    "MORFOLOGIK_RULE_RU_RU",
    "COMMA_DEFIS",      # Добавлено: Замена дефиса на тире после запятой
    "NO_KAK_POPALO",    # Добавлено: Удаление лишней запятой перед "где попало"
    # Можно добавить другие ID правил, например, для простых пунктуационных ошибок,
    # если будем уверены в их "очевидности" и безопасности автозамены.
}

# Категории слов, которые часто не следует исправлять
EXCLUDE_WORD_CATEGORIES = {
    "имена_собственные": [r"[А-Я][а-я]+"],  # Имена собственные обычно с большой буквы
    "термины_хутор": [r"хут\.", r"хутор\s+[А-Я][а-я]+"],
    "диалектизмы": [r"угорь", r"трошки", r"гутарил"],
    "специфические_слова": [r"сказилось", r"бушковать", r"чиниться"]
    # Этот список можно расширять на основе анализа текстов
}

def extract_extended_context(html_content, match_offset, context_size=500):
    """
    Извлекает расширенный контекст вокруг ошибки для лучшего понимания LLM.
    """
    start = max(0, match_offset - context_size)
    end = min(len(html_content), match_offset + context_size)
    
    extended_context = html_content[start:end]
    
    # Находим ближайшие целые предложения
    if start > 0:
        # Ищем начало предложения (после точки и пробела или новой строки)
        sentence_start = re.search(r'[.!?]\s+[А-Я]', extended_context[:context_size//2])
        if sentence_start:
            extended_context = extended_context[sentence_start.end()-1:]
    
    if end < len(html_content):
        # Ищем конец предложения (точка, восклицательный или вопросительный знак)
        sentence_end = re.search(r'[.!?]\s+', extended_context[context_size//2:])
        if sentence_end:
            end_pos = context_size//2 + sentence_end.start() + 1
            extended_context = extended_context[:end_pos]
    
    return extended_context, match_offset - start

def should_exclude_match(error_segment, context):
    """
    Проверяет, следует ли исключить данное слово из автоисправления.
    """
    # Проверка по категориям слов, которые не следует исправлять
    for category, patterns in EXCLUDE_WORD_CATEGORIES.items():
        for pattern in patterns:
            if re.search(pattern, error_segment) or re.search(pattern, context, re.IGNORECASE):
                return True, category
    return False, None

def get_html_tag_context(html_content, match_offset):
    """
    Определяет, находится ли ошибка внутри HTML-тега и какого именно.
    Это важно для понимания роли текста (заголовок, параграф и т.д.)
    """
    # Ищем ближайший открывающий тег до ошибки
    tag_pattern = r"<([a-zA-Z0-9]+)[^>]*>"
    opening_tags = list(re.finditer(tag_pattern, html_content[:match_offset]))
    
    if not opening_tags:
        return None
    
    last_tag = opening_tags[-1]
    tag_name = last_tag.group(1)
    
    # Проверяем, что ошибка не внутри атрибута тега
    if "<" in html_content[last_tag.end():match_offset] and ">" in html_content[last_tag.end():match_offset]:
        return None
    
    # Проверяем, есть ли закрывающий тег после ошибки
    closing_tag_pattern = f"</{tag_name}>"
    closing_tag = re.search(closing_tag_pattern, html_content[match_offset:])
    
    if not closing_tag:
        return None
    
    return {
        "tag": tag_name,
        "semantic_role": get_semantic_role(tag_name, html_content, last_tag.start())
    }

def get_semantic_role(tag_name, html_content, tag_start):
    """
    Определяет семантическую роль тега на основе его атрибутов (class, id и т.д.)
    """
    # Получаем весь тег с атрибутами
    tag_end = html_content.find(">", tag_start)
    if tag_end == -1:
        return "неизвестно"
    
    full_tag = html_content[tag_start:tag_end+1]
    
    semantic_roles = {
        "h1": "заголовок первого уровня",
        "h2": "заголовок второго уровня",
        "h3": "заголовок третьего уровня",
        "h4": "заголовок четвертого уровня",
        "p": "параграф",
        "blockquote": "цитата",
        "code": "программный код",
        "pre": "форматированный текст",
        "em": "выделенный текст",
        "strong": "важный текст",
        "table": "таблица",
        "figure": "рисунок или иллюстрация",
        "figcaption": "подпись к рисунку",
        "ul": "маркированный список",
        "ol": "нумерованный список",
        "li": "элемент списка",
        "a": "ссылка",
    }
    
    # Проверяем атрибуты class и id для дополнительного контекста
    class_match = re.search(r'class=["\'](.*?)["\']', full_tag)
    id_match = re.search(r'id=["\'](.*?)["\']', full_tag)
    
    role = semantic_roles.get(tag_name.lower(), "стандартный элемент")
    
    if class_match:
        class_value = class_match.group(1)
        if "chapter" in class_value:
            role = "глава"
        elif "section" in class_value:
            role = "раздел"
        elif "title" in class_value or "heading" in class_value:
            role = "заголовок"
        elif "quote" in class_value:
            role = "цитата"
        elif "example" in class_value:
            role = "пример"
        elif "note" in class_value:
            role = "примечание"
    
    return role

def generate_llm_prompt(match_info, html_content):
    """
    Генерирует улучшенный промпт для LLM с расширенным контекстом.
    """
    original_text = match_info.get('context', {}).get('text', '')
    global_offset = match_info.get('offset', 0)
    context_offset = match_info.get('context', {}).get('offset', 0)
    length = match_info.get('context', {}).get('length', 0)
    
    error_segment = original_text[context_offset:context_offset + length]
    
    # Получаем расширенный контекст
    extended_context, adjusted_offset = extract_extended_context(html_content, global_offset)
    
    # Определяем HTML-контекст (в каком теге находится ошибка)
    html_context_info_obj = get_html_tag_context(html_content, global_offset)
    
    # Проверяем, следует ли исключить данное слово из автоисправления
    exclude_match, exclude_category = should_exclude_match(error_segment, extended_context)
    
    # Добавляем информацию об исключении в промпт
    exclusion_info = ""
    if exclude_match:
        exclusion_info = f"\nВНИМАНИЕ: Данное слово \"{error_segment}\" похоже на {exclude_category}. Особенно внимательно проверьте уместность исправления."
    
    # Информация о HTML-контексте
    html_context_info_str = ""
    if html_context_info_obj:
        html_context_info_str = f"\nHTML-контекст: Ошибка находится внутри тега <{html_context_info_obj['tag']}>, который представляет '{html_context_info_obj['semantic_role']}'."
    
    prompt = (
        f"Обнаружена следующая потенциальная ошибка в русскоязычном тексте:\n\n"
        f"Расширенный контекст (часть документа, где найдена ошибка):\n\"\"\"{extended_context}\"\"\"\n\n"
        f"Непосредственный контекст (фрагмент, возвращенный LanguageTool):\n\"\"\"{original_text}\"\"\"\n\n"
        f"Ошибка (выделенный текст): \"{error_segment}\"\n"
        f"Сообщение LanguageTool: {match_info.get('message', 'N/A')}\n"
        f"Правило LanguageTool ID: {match_info.get('rule', {}).get('id', 'N/A')}\n"
        # f"Описание правила: {match_info.get('rule', {}).get('description', 'N/A')}\n" # Часто слишком длинное
        f"{html_context_info_str}\n"
        f"Предлагаемая LanguageTool замена: \"{match_info.get('replacements', [{}])[0].get('value', 'N/A')}\"{exclusion_info}\n\n"
        f"ЗАДАЧА: Оцените, является ли предлагаемое исправление корректным и уместным в данном контексте. "
        f"Учитывайте грамматику, пунктуацию, стиль и общий смысл текста. "
        f"Особое внимание уделите:\n"
        f"1. Специальной терминологии, жаргонизмам и диалектизмам (они могут быть корректны в определенном контексте).\n"
        f"2. Именам собственным, названиям и аббревиатурам.\n"
        f"3. Цитатам и прямой речи, где ошибки могут быть намеренными или частью авторского стиля.\n"
        f"4. Художественным приемам и стилистическим особенностям текста.\n\n"
        f"ОТВЕТ: Ответьте ОДНИМ СЛОВОМ: \"ДА\" (если исправление корректно) или \"НЕТ\" (если исправление некорректно или сомнительно). "
        f"После слова ДА/НЕТ, если хотите, можете дать КРАТКОЕ пояснение (не более одного предложения)."
    )
    return prompt

def ask_llm_if_fix_is_correct(prompt):
    """
    Отправляет промпт в LLM через OpenRouter и анализирует ответ.
    Возвращает True, если LLM подтверждает исправление, иначе False.
    """
    if not open_router_client:
        print("Клиент OpenRouter не инициализирован. Пропускаем проверку LLM, исправление НЕ будет применено.", file=sys.stderr)
        return False # Не применять исправления, если LLM недоступен

    try:
        print(f"\n--- Запрос к LLM ({MODEL_NAME}) ---")
        # print(f"Промпт: {prompt}") # Раскомментировать для детального логгирования
        
        chat_completion = open_router_client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": "Выступай в роли опытного редактора русского языка. Твоя задача - оценить корректность предложенного исправления ошибки в тексте."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2, # Более детерминированный ответ
            max_tokens=50   # Ожидаем короткий ответ ДА/НЕТ + пояснение
        )
        
        response_text = chat_completion.choices[0].message.content.strip().upper()
        print(f"Ответ LLM: {chat_completion.choices[0].message.content.strip()}")
        print("---------------------------")

        if response_text.startswith("ДА"):
            return True
        elif response_text.startswith("НЕТ"):
            return False
        else:
            print(f"Неоднозначный ответ от LLM: \"{response_text}\". Исправление будет отклонено.", file=sys.stderr)
            return False # В случае неоднозначного ответа, лучше отклонить
            
    except Exception as e:
        print(f"Ошибка при обращении к LLM через OpenRouter: {e}", file=sys.stderr)
        # print(f"Промпт, вызвавший ошибку: {prompt}", file=sys.stderr) # Логирование промпта при ошибке
        return False # В случае ошибки считаем, что исправление не подтверждено

def analyze_and_correct_with_llm_auto(html_file_path, json_report_path):
    """
    Анализирует JSON-отчет LanguageTool, отправляет промпты в LLM Курсора и автоматически вносит исправления в HTML-файл.
    Создает резервную копию исходного файла.
    """
    try:
        with open(json_report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
    except Exception as e:
        print(f"Ошибка при чтении отчета: {e}", file=sys.stderr)
        return False
    
    if 'matches' not in report_data or not report_data['matches']:
        print(f"В отчете {json_report_path} не найдено ошибок для анализа.")
        return True
    
    # Читаем содержимое HTML-файла
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        print(f"Ошибка при чтении HTML-файла: {e}", file=sys.stderr)
        return False

    # Делаем резервную копию
    backup_path = html_file_path + ".bak"
    shutil.copy2(html_file_path, backup_path)
    print(f"Резервная копия исходного файла: {backup_path}")

    # Создаем лог-файл для отклоненных исправлений
    log_dir = os.path.dirname(html_file_path)
    log_path = os.path.join(log_dir, os.path.basename(html_file_path) + ".rejected_fixes.log")
    
    approved_corrections = []
    rejected_corrections = []
    
    sorted_matches = sorted(report_data['matches'], key=lambda m: m.get('offset', 0), reverse=True)
    print(f"\n[ОТЛАДКА] Всего найдено LanguageTool ошибок: {len(sorted_matches)}")
    
    for i, match in enumerate(sorted_matches):
        rule_id = match.get('rule', {}).get('id')
        replacements = match.get('replacements', [])
        original_text_segment = html_content[match.get('offset', 0):match.get('offset', 0)+match.get('length', 0)]
        
        print(f"\n[ОТЛАДКА] Ошибка #{i+1}: Rule ID: {rule_id}, Original: '{original_text_segment}', Replacements: {len(replacements)}")

        if rule_id in AUTOFIX_CANDIDATE_RULE_IDS and len(replacements) == 1:
            print(f"[ОТЛАДКА] Ошибка #{i+1} является кандидатом на автозамену и имеет 1 вариант.")
            # Глобальное смещение относительно всего текста
            global_offset = match.get('offset', 0)
            length = match.get('length', 0)
            original = html_content[global_offset:global_offset+length]
            replacement = replacements[0].get('value', '')
            
            # Проверяем, следует ли исключить это слово на основе предопределенных категорий
            exclude_match, exclude_category = should_exclude_match(original, html_content[max(0, global_offset-50):global_offset+length+50])
            print(f"[ОТЛАДКА] Ошибка #{i+1} - Проверка на исключение: exclude_match={exclude_match}, exclude_category={exclude_category}")
            
            if exclude_match:
                print(f"[АвтоОтклонено] Исправление отклонено: '{original}' -> '{replacement}' (категория: {exclude_category})")
                rejected_corrections.append({
                    'offset': global_offset,
                    'length': length,
                    'replacement': replacement,
                    'original': original,
                    'reason': f"Автоматически отклонено (категория: {exclude_category})"
                })
                continue
            
            # Не исправлять, если замена делит одно слово на два (например, "теперича" -> "теперь ча")
            if ' ' in replacement and ' ' not in original:
                print(f"[АвтоОтклонено] Исправление отклонено: '{original}' -> '{replacement}' (разделение одного слова на два)")
                rejected_corrections.append({
                    'offset': global_offset,
                    'length': length,
                    'replacement': replacement,
                    'original': original,
                    'reason': "Автоматически отклонено (разделение одного слова на два)"
                })
                continue
            
            print(f"[ОТЛАДКА] Ошибка #{i+1} - Генерирую промпт для LLM.")
            # Генерируем промпт для LLM
            llm_prompt = generate_llm_prompt(match, html_content)
            
            # Проверяем с помощью LLM
            if ask_llm_if_fix_is_correct(llm_prompt):
                approved_corrections.append({
                    'offset': global_offset,
                    'length': length,
                    'replacement': replacement,
                    'original': original
                })
                print(f"[LLM] Исправление одобрено: '{original}' -> '{replacement}' (смещение {global_offset})")
            else:
                rejected_corrections.append({
                    'offset': global_offset,
                    'length': length,
                    'replacement': replacement,
                    'original': original,
                    'reason': "Отклонено LLM"
                })
                print(f"[LLM] Исправление отклонено: '{original}' -> '{replacement}'")

    # Применяем исправления в обратном порядке смещений
    content = html_content
    for fix in approved_corrections:
        offset = fix['offset']
        length = fix['length']
        replacement = fix['replacement']
        content = content[:offset] + replacement + content[offset+length:]
    
    # Записываем обновленный HTML
    with open(html_file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Все исправления ({len(approved_corrections)}) внесены в файл: {html_file_path}")
    
    # Записываем отклоненные исправления в лог
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"Отклоненные исправления для {html_file_path}:\n")
        f.write(f"Всего отклонено: {len(rejected_corrections)}\n\n")
        for i, fix in enumerate(rejected_corrections):
            f.write(f"{i+1}. Оригинал: '{fix['original']}' -> Предложено: '{fix['replacement']}'\n")
            f.write(f"   Причина: {fix.get('reason', 'Не указана')}\n")
            f.write(f"   Смещение: {fix['offset']}, Длина: {fix['length']}\n\n")
    
    print(f"Отклоненные исправления ({len(rejected_corrections)}) записаны в лог: {log_path}")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="""Анализирует отчет LanguageTool, отправляет промпты в LLM Курсора и автоматически исправляет HTML-файл.""")
    parser.add_argument("html_file", help="Путь к исходному HTML-файлу.")
    parser.add_argument("json_report_file", help="Путь к JSON-файлу отчета LanguageTool для данного HTML-файла.")
    args = parser.parse_args()
    if not analyze_and_correct_with_llm_auto(args.html_file, args.json_report_file):
        print("Анализ и автокоррекция завершились с ошибками.", file=sys.stderr)
        sys.exit(1)
    else:
        print("Анализ и автокоррекция завершены успешно.") 