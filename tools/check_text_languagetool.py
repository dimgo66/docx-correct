"""
/**
 * @file: check_text_languagetool.py
 * @description: Скрипт для выполнения проверки текста в HTML-файле с помощью LanguageTool и сохранения отчета в JSON-формате.
 * @dependencies: LanguageTool-6.6 (внешний инструмент), Python 3
 * @created: 2024-07-26
 */
"""

import argparse
import subprocess
import json
import os
import sys
import re # Добавлено для работы с текстом и извлечения контекста
from openai import OpenAI # Библиотека OpenAI используется и для OpenRouter

# --- КОНФИГУРАЦИЯ OpenRouter --- 
# ЗАМЕНИТЕ "YOUR_OPENROUTER_API_KEY" НА ВАШ РЕАЛЬНЫЙ КЛЮЧ
# ЗАМЕНИТЕ "YOUR_SITE_URL" И "YOUR_APP_NAME" НА ВАШИ ДАННЫЕ
# Рекомендуется использовать переменные окружения для хранения ключа API
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
# Данные для заголовков OpenRouter, обязательны для некоторых моделей или для отслеживания
YOUR_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "http://localhost") # Для локальной разработки.
YOUR_APP_NAME = os.getenv("OPENROUTER_APP_NAME", "PiskulinTextProcessing") # Название вашего приложения.

if OPENROUTER_API_KEY == "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" and not os.getenv("OPENROUTER_API_KEY"):
    print("INFO: Используется API ключ OpenRouter, указанный в коде. Рекомендуется установить его через переменную окружения OPENROUTER_API_KEY для большей безопасности.")
elif OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY":
    print("ВНИМАНИЕ: Не указан реальный OpenRouter API ключ. Укажите его в переменной окружения OPENROUTER_API_KEY или напрямую в коде.", file=sys.stderr)

# Категории ошибок LanguageTool, которые будем пытаться исправить с помощью ИИ
# (можно расширить на основе ID правил: rule['ruleId'])
AI_CORRECTABLE_CATEGORIES = {
    "TYPOS",  # Опечатки
    "PUNCTUATION",  # Пунктуация
    "CASING",  # Регистр букв (например, начало предложения)
    "GRAMMAR", # Некоторые грамматические ошибки, связанные с пунктуацией или выбором слов
    "STYLE", # Некоторые стилистические (например, неправильные кавычки, дефисы)
    # Примеры ID правил, которые могут быть интересны:
    # MORFOLOGIK_RULE_RU_RU, RUSSIAN_WORD_REPEAT_RULE, NO_SPACE_AFTER_COMMA,
    # COMMA_BEFORE_AND_IN_LIST, DASH_RULE, EN_QUOTES_ON_RUSSIAN_TEXT
}
# Максимальная длина контекста вокруг ошибки для передачи ИИ
MAX_CONTEXT_LENGTH = 250


def get_original_text_segment(full_text_lines, offset, length):
    """
    Извлекает сегмент текста из списка строк по смещению и длине.
    Предполагается, что full_text_lines - это список строк, как они были в исходном файле.
    LanguageTool обычно дает смещения относительно всего текста как одной строки.
    Эта функция пытается восстановить оригинальный сегмент.
    """
    current_offset = 0
    segment = ""
    
    # Сначала найдем начальную позицию
    start_char_count = 0
    current_pos_in_text = 0
    
    # Объединим строки для простоты работы со смещениями, сохраняя оригинальные переносы для контекста
    # Однако, LanguageTool может считать смещения по-разному (с учетом \n или без).
    # Для простоты, здесь мы предполагаем, что смещения LanguageTool даны для текста,
    # где строки соединены через \n. Если это не так, логику нужно будет адаптировать.
    # Эта версия предполагает, что full_text_content - это ОДНА БОЛЬШАЯ СТРОКА, как ее видит LT
    
    # ВАЖНО: LanguageTool работает с текстом, извлеченным из HTML.
    # Смещения, которые он дает, относятся к этому извлеченному тексту, а не к исходному HTML с тегами.
    # Поэтому передавать сюда HTML строки напрямую неверно.
    # Эта функция должна получать на вход тот же текст, который "видел" LanguageTool.
    # На данном этапе мы не имеем прямого доступа к "чистому" тексту, который анализировал LanguageTool.
    # Поэтому, пока что, эта функция будет упрощенной и может не всегда корректно извлекать контекст
    # из HTML-содержимого.
    
    # Упрощенный вариант: full_text_lines - это одна строка, которую LT анализировал.
    if isinstance(full_text_lines, str):
        return full_text_lines[offset : offset + length]
    
    # Если это список строк (что менее вероятно для смещений LT)
    # Эта логика потребует доработки, если LT обрабатывает HTML построчно иначе.
    # Пока оставляем как есть, но с комментарием о необходимости уточнения.
    temp_text_for_offsets = "\n".join(full_text_lines) # Это может не совпадать с тем, как LT видит текст
    
    if offset + length <= len(temp_text_for_offsets):
        return temp_text_for_offsets[offset : offset + length]
    else:
        # Если выходит за пределы, вернем то, что есть, или пустую строку
        return temp_text_for_offsets[offset:] if offset < len(temp_text_for_offsets) else ""


def get_context_around_error(full_text_content_str, error_offset, error_length, context_window=MAX_CONTEXT_LENGTH):
    """
    Извлекает контекст (текст до и после) вокруг ошибки.
    full_text_content_str: Полный текст, который анализировал LanguageTool (одна строка).
    error_offset: Смещение ошибки в этом тексте.
    error_length: Длина ошибочного фрагмента.
    context_window: Количество символов контекста с каждой стороны.
    """
    start_context = max(0, error_offset - context_window)
    end_context = min(len(full_text_content_str), error_offset + error_length + context_window)
    
    context_before = full_text_content_str[start_context:error_offset]
    error_text = full_text_content_str[error_offset : error_offset + error_length]
    context_after = full_text_content_str[error_offset + error_length : end_context]
    
    return context_before, error_text, context_after


def get_ai_correction(error_message, rule_id, original_text_segment, context_before, context_after, replacements):
    """
    Обращается к OpenRouter для получения исправления ошибки.

    :param error_message: Сообщение об ошибке от LanguageTool.
    :param rule_id: ID правила LanguageTool.
    :param original_text_segment: Сегмент текста с ошибкой.
    :param context_before: Текст перед ошибкой.
    :param context_after: Текст после ошибки.
    :param replacements: Предлагаемые LanguageTool замены (если есть).
    :return: Строка с предложенным исправлением или None.
    """
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY":
        # print("Пропуск вызова OpenRouter API: не указан API ключ.", file=sys.stderr)
        lt_suggestions_list = [r['value'] for r in replacements if r['value']]
        lt_suggestions_str = ", ".join(lt_suggestions_list)
        if lt_suggestions_str:
            return f"[ЗАГЛУШКА ИИ: '{lt_suggestions_str}' для '{original_text_segment}']"
        else:
            return f"[ЗАГЛУШКА ИИ для '{original_text_segment}']"

    client = None # Инициализируем клиент как None
    try:
        # Инициализируем клиент здесь
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": YOUR_SITE_URL, 
                "X-Title": YOUR_APP_NAME,
            }
        )

        # Формируем промпт для ИИ
        # Этот промпт можно и нужно улучшать для более точных результатов
        prompt_lines = [
            "Ты — опытный редактор русского языка. Твоя задача — исправить только одну ошибку в предоставленном фрагменте текста.",
            "Оригинальный текст содержит ошибку, выделенную тройными кавычками. Контекст до и после ошибки также предоставлен.",
            "LanguageTool определил эту ошибку как:",
            f"- Сообщение: {error_message}",
            f"- ID правила: {rule_id}",
        ]
        if replacements:
            lt_suggestions = [r['value'] for r in replacements]
            prompt_lines.append(f"- LanguageTool предлагает следующие варианты: {', '.join(lt_suggestions)}")

        prompt_lines.extend([
            f'''Контекст до ошибки: """{context_before}"""''',
            f'''Ошибочный фрагмент: """{original_text_segment}"""''',
            f'''Контекст после ошибки: """{context_after}"""''',
            "Проанализируй ошибку и контекст. Исправь ТОЛЬКО ОШИБОЧНЫЙ ФРАГМЕНТ.",
            "Верни ТОЛЬКО ИСПРАВЛЕННЫЙ ФРАГМЕНТ ТЕКСТА, без каких-либо объяснений, кавычек или дополнительного текста.",
            "Если ты считаешь, что исправление не требуется или LanguageTool ошибся, верни оригинальный ошибочный фрагмент без изменений.",
            "Если LanguageTool предложил несколько вариантов, и один из них корректен, используй его.",
            "Сохраняй исходный стиль и форматирование текста насколько это возможно.",
            "Особое внимание удели правильной расстановке кавычек («ёлочки» для внешних, „лапки“ для внутренних, если применимо), дефисов (-) и тире (—).",
            "Твоя цель - исправить опечатки, пунктуационные ошибки, неправильное использование дефисов/тире и кавычек."
        ])
        prompt = "\n".join(prompt_lines)
        
        # print(f"\n--- Промпт для OpenRouter ---\n{prompt}\n--- Конец промпта ---", file=sys.stderr)


        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "Ты — высококвалифицированный ИИ-ассистент, специализирующийся на коррекции русского текста. Ты исправляешь только указанную ошибку, сохраняя остальной текст и его форматирование. Возвращаешь только исправленный фрагмент.",
                },
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            model="qwen/qwen3-235b-a22b:free", # Обновленный ID модели Qwen для OpenRouter
            temperature=0.2, # Низкая температура для более детерминированных и точных исправлений
            max_tokens=len(original_text_segment) + 50, # Ограничиваем длину ответа
            n=1,
            stop=None,
        )
        
        corrected_segment = chat_completion.choices[0].message.content.strip()
        
        # Дополнительная очистка ответа, если ИИ добавил лишние кавычки вокруг
        if corrected_segment.startswith('"""') and corrected_segment.endswith('"""'):
            corrected_segment = corrected_segment[3:-3]
        elif corrected_segment.startswith('"') and corrected_segment.endswith('"'):
            corrected_segment = corrected_segment[1:-1]
            
        # print(f"Оригинал: '{original_text_segment}', Предложение ИИ: '{corrected_segment}'", file=sys.stderr)
        return corrected_segment

    except Exception as e:
        print(f"Ошибка при обращении к OpenRouter API: {e}", file=sys.stderr)
        return None

def ensure_html_lang_ru(html_file_path):
    """
    Проверяет и при необходимости устанавливает lang="ru" в теге <html> HTML-файла.
    Если lang отсутствует или отличается от "ru", заменяет/добавляет его.
    Не создаёт дубликатов <html> и не нарушает структуру.
    """
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        # Ищем только первый тег <html ...>
        html_tag_match = re.search(r'<html(\s[^>]*)?>', content, re.IGNORECASE)
        if not html_tag_match:
            print(f"[WARN] Не найден тег <html> в файле {html_file_path}", file=sys.stderr)
            return False
        html_tag = html_tag_match.group(0)
        # Проверяем наличие lang
        if re.search(r'lang\s*=\s*"ru"', html_tag, re.IGNORECASE):
            return True  # Уже корректно
        # Если есть другой lang, заменяем только его
        if re.search(r'lang\s*=\s*"[^"]*"', html_tag, re.IGNORECASE):
            new_html_tag = re.sub(r'lang\s*=\s*"[^"]*"', 'lang="ru"', html_tag, flags=re.IGNORECASE)
        else:
            # lang отсутствует — добавляем
            new_html_tag = html_tag[:-1] + ' lang="ru">'
        # Заменяем только первый найденный тег <html ...>
        new_content = content[:html_tag_match.start()] + new_html_tag + content[html_tag_match.end():]
        with open(html_file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"[INFO] lang=\"ru\" установлен в <html> для файла {html_file_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Не удалось обработать lang в HTML: {e}", file=sys.stderr)
        return False

def run_languagetool(html_file_path, output_dir=None):
    """
    Запускает LanguageTool для проверки HTML-файла и сохраняет JSON-отчет.

    :param html_file_path: Путь к HTML-файлу для проверки.
    :param output_dir: Директория для сохранения отчета. Если None,
                       отчет сохраняется рядом с HTML-файлом.
    :return: True, если проверка прошла успешно и отчет сохранен, иначе False.
    """
    if not os.path.exists(html_file_path):
        print(f"Ошибка: HTML-файл не найден: {html_file_path}", file=sys.stderr)
        return False

    languagetool_jar_path = os.path.join("..", "LanguageTool-6.6", "languagetool-commandline.jar")
    if not os.path.exists(languagetool_jar_path):
        # Попытка найти относительно текущего скрипта, если запускается из tools/
        script_dir = os.path.dirname(os.path.abspath(__file__))
        languagetool_jar_path = os.path.join(script_dir, "..", "LanguageTool-6.6", "languagetool-commandline.jar")
        if not os.path.exists(languagetool_jar_path):
            print(f"Ошибка: languagetool-commandline.jar не найден. Ожидался путь: {languagetool_jar_path} или ../LanguageTool-6.6/languagetool-commandline.jar", file=sys.stderr)
            return False

    base_name = os.path.basename(html_file_path)
    file_name_without_ext = os.path.splitext(base_name)[0]

    if output_dir:
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except OSError as e:
                print(f"Ошибка при создании директории для отчета {output_dir}: {e}", file=sys.stderr)
                return False
        report_file_path = os.path.join(output_dir, f"{file_name_without_ext}_languagetool_report.json")
    else:
        report_file_path = os.path.join(os.path.dirname(html_file_path), f"{file_name_without_ext}_languagetool_report.json")

    # Перед запуском LanguageTool — гарантируем lang="ru" в <html>
    ensure_html_lang_ru(html_file_path)

    command = [
        "java",
        "-Xmx4G",  # Увеличиваем лимит памяти для Java
        "-jar",
        languagetool_jar_path,
        "-l", "ru",
        "-c", "utf-8",
        "--json",
        html_file_path
    ]

    process = None # Инициализируем process
    try:
        print(f"Запуск LanguageTool для файла: {html_file_path}")
        # Увеличиваем таймаут, так как LanguageTool может долго обрабатывать большие файлы
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        stdout, stderr = process.communicate(timeout=300) # 5 минут таймаут

        if process.returncode != 0:
            print(f"Ошибка при выполнении LanguageTool (код возврата: {process.returncode}):", file=sys.stderr)
            if stdout:
                print(f"Stdout: {stdout}", file=sys.stderr)
            if stderr:
                print(f"Stderr: {stderr}", file=sys.stderr)
            return False

        # LanguageTool выводит JSON в stdout, но иногда может предварять его другой информацией
        # Попробуем найти начало JSON
        # text_content_for_context = "" # Инициализируем переменные, чтобы они были доступны
        try:
            with open(html_file_path, 'r', encoding='utf-8') as f_html:
                # ВАЖНО: LanguageTool удаляет HTML теги перед анализом.
                # Мы должны попытаться получить "чистый" текст, как его видит LanguageTool.
                # Это сложная задача, так как разные парсеры HTML могут давать разный текстовый контент.
                # Для простоты, на данном этапе, мы будем использовать очень грубое извлечение текста,
                # что может привести к неточностям в смещениях и контексте.
                # В идеале, нужно использовать тот же механизм извлечения текста, что и LanguageTool,
                # или передавать HTML в LanguageTool таким образом, чтобы он возвращал смещения
                # относительно оригинального HTML, если это возможно.

                # Грубое извлечение текста: (ТРЕБУЕТ УЛУЧШЕНИЯ для точности)
                # html_content_for_context = f_html.read() # Весь HTML
                # from bs4 import BeautifulSoup # Импорт BeautifulSoup если используется
                # soup = BeautifulSoup(html_content_for_context, 'html.parser')
                # text_content_for_context = soup.get_text(separator='\n', strip=True)
                # На данный момент, для простоты, мы не будем извлекать контекст напрямую из HTML,
                # а будем работать с текстом ошибки, который LanguageTool возвращает.
                # Это ограничит качество контекста.
                pass # Заглушка для будущего извлечения текста из HTML для контекста
                
        except Exception as e:
            print(f"Предупреждение: Ошибка чтения HTML файла для извлечения полного контекста: {e}", file=sys.stderr)
            # Продолжаем без полного контекста, если не удалось прочитать файл
            # text_content_for_context = "" # Убедимся, что переменная существует
            
        json_output_start = stdout.find('{')
        if json_output_start == -1:
            json_output_start = stdout.find('[') # На случай если корневой элемент - массив

        if json_output_start != -1:
            json_data_str = stdout[json_output_start:]
            try:
                # Попытка загрузить JSON, чтобы убедиться, что он корректен
                report_data = json.loads(json_data_str)
                
                # --- Начало интеграции ИИ ---
                if 'matches' in report_data and OPENROUTER_API_KEY and OPENROUTER_API_KEY != "YOUR_OPENROUTER_API_KEY":
                    # Попытка получить "сырой" текст, который анализировал LanguageTool.
                    # LanguageTool CLI не предоставляет эту возможность напрямую.
                    # В качестве грубого приближения, можно попробовать собрать все "sentence" по ошибкам,
                    # но это не будет полным текстом.
                    # Для более точного извлечения контекста, нужен доступ к тексту,
                    # который LanguageTool получил ПОСЛЕ удаления HTML-тегов.
                    # Это одна из сложностей данной задачи.
                    
                    # Пока будем использовать "sentence" из ошибки как основной текст для ИИ.
                    
                    print(f"Начинаем обработку ошибок с помощью ИИ ({len(report_data['matches'])} ошибок).") # Убрал file=sys.stderr
                    ai_corrected_count = 0
                    for match in report_data['matches']:
                        rule_category = match.get('rule', {}).get('category', {}).get('id', '')
                        rule_id = match.get('rule', {}).get('id', '')
                        
                        # Проверяем, подходит ли категория или ID правила для ИИ-исправления
                        if rule_category in AI_CORRECTABLE_CATEGORIES or rule_id in AI_CORRECTABLE_CATEGORIES:
                            error_text_segment = match.get('context', {}).get('text', '')
                            error_offset_in_context = match.get('context', {}).get('offset', 0)
                            error_length_in_context = match.get('context', {}).get('length', 0)
                            
                            # Извлекаем ошибочный фрагмент из контекста, предоставленного LT
                            # Этот контекст уже является "чистым" текстом
                            actual_error_snippet = error_text_segment[error_offset_in_context : error_offset_in_context + error_length_in_context]
                            
                            context_before_snippet = error_text_segment[:error_offset_in_context]
                            context_after_snippet = error_text_segment[error_offset_in_context + error_length_in_context:]

                            if not actual_error_snippet: # Если не удалось извлечь фрагмент
                                # print(f"Пропуск ИИ: не удалось извлечь текст ошибки для: {match.get('message')}", file=sys.stderr)
                                continue

                            # print(f"\nОшибка: {match.get('message')}")
                            # print(f"Контекст LT: '{error_text_segment}'")
                            # print(f"  - До: '{context_before_snippet}'")
                            # print(f"  - Ошибка: '{actual_error_snippet}'")
                            # print(f"  - После: '{context_after_snippet}'")

                            suggested_correction = get_ai_correction(
                                error_message=match.get('message', ''),
                                rule_id=rule_id,
                                original_text_segment=actual_error_snippet,
                                context_before=context_before_snippet,
                                context_after=context_after_snippet,
                                replacements=match.get('replacements', [])
                            )
                            
                            if suggested_correction:
                                match['ai_suggestion'] = suggested_correction
                                # Сравниваем, чтобы не засчитывать, если ИИ вернул то же самое
                                if suggested_correction != actual_error_snippet:
                                    ai_corrected_count += 1
                                    # print(f"  AI Suggestion: '{suggested_correction}'")
                        else: # Для отладки, если категория или ID не подошли
                            # print(f"Пропуск ИИ для правила: {rule_id}, категория: {rule_category}, сообщение: {match.get('message')}")
                            pass 

                    if ai_corrected_count > 0:
                        print(f"ИИ ({YOUR_APP_NAME} через OpenRouter) предложил исправления для {ai_corrected_count} ошибок.")
                elif 'matches' in report_data and (not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "YOUR_OPENROUTER_API_KEY"):
                    print("Обработка ИИ пропущена: API ключ для OpenRouter не настроен.")
                # --- Конец интеграции ИИ ---

                # Сохраняем обновленный JSON (с ai_suggestion, если есть)
                with open(report_file_path, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, ensure_ascii=False, indent=4)
                print(f"Отчет LanguageTool успешно сохранен в: {report_file_path}")
                return True
            except json.JSONDecodeError as e:
                print(f"Ошибка декодирования JSON из вывода LanguageTool: {e}", file=sys.stderr)
                print(f"Полный вывод stdout:\n{stdout}", file=sys.stderr)
                # Сохраняем "сырой" вывод для анализа, если он не является валидным JSON
                raw_report_path = report_file_path.replace(".json", ".raw_output.txt")
                with open(raw_report_path, "w", encoding="utf-8") as f:
                    f.write(stdout)
                print(f"Невалидный вывод LanguageTool сохранен в: {raw_report_path}", file=sys.stderr)
                return False
        else:
            print(f"Не удалось найти JSON в выводе LanguageTool.", file=sys.stderr)
            if stdout:
                 print(f"Stdout: {stdout}", file=sys.stderr)
            if stderr:
                print(f"Stderr: {stderr}", file=sys.stderr) # Stderr может содержать полезную информацию
            return False

    except subprocess.TimeoutExpired:
        print(f"Ошибка: LanguageTool превысил лимит времени выполнения (300 секунд) для файла {html_file_path}", file=sys.stderr)
        if process: # Убедимся что process был инициализирован
            process.kill()
            # Собираем остатки вывода после kill. Popen.communicate() уже был вызван.
            # Если хотим еще раз, то это новый вызов communicate(), но процесс уже завершен или убит.
            # stdout_after_kill, stderr_after_kill = process.communicate() # Это может зависнуть или дать ошибку
            # Лучше просто получить то, что уже было собрано, если оно не было None
            # Однако, stdout и stderr уже определены выше.
            # Если процесс был убит из-за таймаута, его stdout/stderr могут быть неполными.
            # Просто выведем то, что успели получить до таймаута (уже сделано в основном блоке try)
            # или то, что получили после kill, если это имеет смысл.
            # Повторный вызов communicate() на убитом процессе не рекомендуется.
            pass # stdout и stderr уже содержат вывод до таймаута
        return False
    except Exception as e: # Общий обработчик ошибок для subprocess.Popen и communicate
        print(f"Непредвиденная ошибка при запуске LanguageTool или коммуникации с процессом: {e}", file=sys.stderr)
        if process and process.poll() is None: # Если процесс еще жив, пытаемся его убить
            process.kill()
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Проверяет HTML-файл с помощью LanguageTool и сохраняет JSON-отчет.")
    parser.add_argument("html_file", help="Путь к HTML-файлу для проверки.")
    parser.add_argument("-o", "--output-dir", help="Директория для сохранения JSON-отчета (по умолчанию: рядом с HTML-файлом).", default=None)

    args = parser.parse_args()

    if run_languagetool(args.html_file, args.output_dir):
        print("Проверка LanguageTool завершена успешно.")
    else:
        print("Проверка LanguageTool завершилась с ошибками.", file=sys.stderr)
        sys.exit(1) 