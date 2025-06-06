# /**
#  * @file: orchestrator.py
#  * @description: Оркестратор для запуска модулей конвейера обработки текста.
#  * @dependencies: os, uuid, json, src.utils.logger_setup, src.utils.exceptions,
#  *                src.pipeline.docx_to_html_converter, src.pipeline.languagetool_processor_module,
#  *                src.pipeline.autocorrect_processor_module, src.pipeline.typograf_processor_module
#  * @created: 2024-07-30
#  * @updated: 2024-07-31
#  */

import os
import uuid
import json
import logging # Для основного логгера оркестратора
import argparse # Добавляем для обработки аргументов командной строки
import sys
from ..utils.logger_setup import setup_logging # Исправлен импорт logger_setup
from ..utils.exceptions import TextProcessingError # Общий класс ошибок для перехвата
from .docx_to_html_converter import convert_docx_to_html, PIPELINE_STAGE_NAME as DOCX_TO_HTML_STAGE
# Удаляем импорт заглушки
# from .text_processor_stub import process_text_stub, PIPELINE_STAGE_NAME as TEXT_PROCESSOR_STUB_STAGE
# Добавляем импорты новых модулей
from .typograf_processor_module import TypografProcessorModule
from .languagetool_processor_module import LanguageToolProcessorModule
from .autocorrect_processor_module import AutocorrectProcessorModule
from .html_to_docx_processor_module import HtmlToDocxProcessorModule
import shutil
import unicodedata
import string

# Карта транслитерации для русских букв
RUSSIAN_TO_LATIN = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
    'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
    'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
    'я': 'ya',
    'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'Yo', 'Ж': 'Zh',
    'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M', 'Н': 'N', 'О': 'O',
    'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U', 'Ф': 'F', 'Х': 'Kh', 'Ц': 'Ts',
    'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch', 'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu',
    'Я': 'Ya',
}

def safe_ascii_filename(name):
    """
    Транслитерирует русские символы и оставляет только безопасные ASCII-символы для имен файлов.
    Небезопасные символы удаляются.
    """
    # Нормализация Unicode
    name = unicodedata.normalize('NFKD', name)
    
    transliterated_name = ''.join(RUSSIAN_TO_LATIN.get(c, c) for c in name)
    
    # Оставляем только ASCII-буквы, цифры, пробелы, подчеркивания, дефисы и точки
    # Удаляем остальные символы
    safe_name = ''.join(c for c in transliterated_name if c in string.ascii_letters + string.digits + ' _-.')
    
    return safe_name

logging.warning("=== PIPELINE VERSION: DIAGNOSTIC DEBUG 2024-06-03 ===")

# Определяем имена этапов для новых модулей
LANGUAGETOOL_STAGE = "LanguageToolProcessorModule"
AUTOCORRECT_STAGE = "AutocorrectProcessorModule"
TYPOGRAF_STAGE = "TypografProcessorModule"


# Определяем корневую директорию проекта относительно текущего файла
# Предполагается, что orchestrator.py находится в src/pipeline/
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKSPACE_ROOT = os.path.join(PROJECT_ROOT, 'workspace')
TEXTINPUT_DIR = os.path.join(PROJECT_ROOT, 'textinput') # Новая директория для входных файлов
PROCESSING_DIR_BASE = os.path.join(WORKSPACE_ROOT, 'processing') # Общая папка для всех этапов
OUTPUT_DIR = os.path.join(WORKSPACE_ROOT, 'output') # Директория для итоговых файлов

# Создаем директории, если их нет
os.makedirs(TEXTINPUT_DIR, exist_ok=True)
os.makedirs(PROCESSING_DIR_BASE, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_pipeline(input_file_name, basename=None):
    correlation_id = str(uuid.uuid4())
    meta_path = f"/tmp/pipeline_{correlation_id}.meta"

    original_input_path = os.path.join(TEXTINPUT_DIR, input_file_name) # Формируем путь

    # Передаем correlation_id в setup_logging для всего пайплайна
    # Устанавливаем уровень логирования DEBUG для детальной отладки
    main_logger = setup_logging(correlation_id=correlation_id, logger_name='orchestrator', level=logging.DEBUG)

    main_logger.info(f"Начало нового сеанса обработки конвейера. Correlation ID: {correlation_id}")
    main_logger.info(f"Входной файл: {original_input_path}")

    if not os.path.exists(original_input_path):
        main_logger.error(f"Исходный файл не найден: {original_input_path}")
        return False

    # Создаём meta-файл с исходным путём
    with open(meta_path, "w") as f:
        f.write(original_input_path)

    try:
        # Переменная для хранения выходного файла текущего этапа
        # Перед каждым этапом читаем путь из meta-файла
        with open(meta_path, "r") as f:
            current_input_path = f.read().strip()

        # ----- Этап 1: DOCX в HTML (DocxToHtmlConverter) -----
        stage1_module_name = DOCX_TO_HTML_STAGE
        stage1_processing_dir = os.path.join(PROCESSING_DIR_BASE, correlation_id, stage1_module_name)
        if basename is None:
            basename_local = os.path.splitext(input_file_name)[0]
        else:
            basename_local = basename
        stage1_output_html_temp = os.path.join(stage1_processing_dir, f"output_temp.html")
        main_logger.info(f"Запуск этапа: {stage1_module_name}")
        os.makedirs(stage1_processing_dir, exist_ok=True)
        try:
            output_from_stage1 = convert_docx_to_html(current_input_path, stage1_output_html_temp, stage1_processing_dir, correlation_id, basename=basename_local)
            status_file_path = os.path.join(stage1_processing_dir, f"{stage1_module_name}_SUCCESS.json")
            if os.path.exists(status_file_path):
                 with open(status_file_path, 'r', encoding='utf-8') as f_stat:
                     status_content = json.load(f_stat)
                     output_from_stage1 = status_content.get('output_file')
            if not output_from_stage1 or not os.path.exists(output_from_stage1):
                main_logger.error(f"Этап {stage1_module_name} завершился ошибкой. Выходной файл не создан или не найден: {output_from_stage1}")
                # return False  # Не прерываем пайплайн для диагностики
            # После этапа записываем новый путь в meta-файл
            with open(meta_path, "w") as f:
                f.write(output_from_stage1)
            # Логируем содержимое meta-файла и список файлов в директории
            main_logger.info(f"[DEBUG] После этапа {stage1_module_name}: output_from_stage1={output_from_stage1}")
            main_logger.info(f"[DEBUG] Содержимое директории {stage1_processing_dir}: {os.listdir(stage1_processing_dir)}")
        except TextProcessingError as e:
            main_logger.error(f"Ошибка на этапе {stage1_module_name}: {str(e)}", exc_info=True, extra=getattr(e, 'details', {}))
            main_logger.error(f"Остановка конвейера после ошибки на этапе: {stage1_module_name}")
            # return False  # Временно не прерываем пайплайн для диагностики
        except Exception as e:
            main_logger.error(f"Непредвиденная системная ошибка на этапе {stage1_module_name}: {str(e)}", exc_info=True)
            main_logger.error(f"Остановка конвейера после системной ошибки на этапе: {stage1_module_name}")
            # return False  # Временно не прерываем пайплайн для диагностики

        # Перед следующим этапом читаем путь из meta-файла
        with open(meta_path, "r") as f:
            current_input_path = f.read().strip()

        # ----- Этап 2: Типографика HTML (TypografProcessorModule) -----
        stage2_module_name = TYPOGRAF_STAGE
        stage2_processing_dir = os.path.join(PROCESSING_DIR_BASE, correlation_id, stage2_module_name)
        main_logger.info(f"Запуск этапа: {stage2_module_name}")
        os.makedirs(stage2_processing_dir, exist_ok=True)
        try:
            typograf_module = TypografProcessorModule(correlation_id)
            output_from_stage2_html = typograf_module.run(current_input_path, stage2_processing_dir)
            status_file_path = os.path.join(stage2_processing_dir, f"{stage2_module_name}_SUCCESS.json")
            if os.path.exists(status_file_path):
                with open(status_file_path, 'r', encoding='utf-8') as f_stat:
                    status_content = json.load(f_stat)
                    output_from_stage2_html = status_content.get('output_file', output_from_stage2_html)
            if not output_from_stage2_html or not os.path.exists(output_from_stage2_html):
                main_logger.error(f"Этап {stage2_module_name} завершился ошибкой. Выходной файл HTML не создан или не найден: {output_from_stage2_html}")
                return False
            main_logger.info(f"Этап {stage2_module_name} успешно завершен. Результат: {output_from_stage2_html}")
            with open(meta_path, "w") as f:
                f.write(output_from_stage2_html)
            main_logger.info(f"[DEBUG] После этапа {stage2_module_name}: output_from_stage2_html={output_from_stage2_html}")
            main_logger.info(f"[DEBUG] Содержимое директории {stage2_processing_dir}: {os.listdir(stage2_processing_dir)}")
        except TextProcessingError as e:
            main_logger.error(f"Ошибка на этапе {stage2_module_name}: {str(e)}", exc_info=True, extra=getattr(e, 'details', {}))
            main_logger.error(f"Остановка конвейера после ошибки на этапе: {stage2_module_name}")
            return False
        except Exception as e:
            main_logger.error(f"Непредвиденная системная ошибка на этапе {stage2_module_name}: {str(e)}", exc_info=True)
            main_logger.error(f"Остановка конвейера после системной ошибки на этапе: {stage2_module_name}")
            return False

        with open(meta_path, "r") as f:
            current_input_path = f.read().strip()

        # ----- Этап 3: Проверка LanguageTool (LanguageToolProcessorModule) -----
        stage3_module_name = LANGUAGETOOL_STAGE
        stage3_processing_dir = os.path.join(PROCESSING_DIR_BASE, correlation_id, stage3_module_name)
        stage3_output_report_expected = os.path.join(stage3_processing_dir, os.path.splitext(os.path.basename(current_input_path))[0] + "_languagetool_report.json")
        main_logger.info(f"Запуск этапа: {stage3_module_name}")
        os.makedirs(stage3_processing_dir, exist_ok=True)
        try:
            languagetool_module = LanguageToolProcessorModule(correlation_id)
            output_from_stage3_report = languagetool_module.run(current_input_path, stage3_processing_dir)
            status_file_path = os.path.join(stage3_processing_dir, f"{stage3_module_name}_SUCCESS.json")
            if os.path.exists(status_file_path):
                with open(status_file_path, 'r', encoding='utf-8') as f_stat:
                    status_content = json.load(f_stat)
                    output_from_stage3_report = status_content.get('output_report_path', output_from_stage3_report)
            if not output_from_stage3_report or not os.path.exists(output_from_stage3_report):
                main_logger.error(f"Этап {stage3_module_name} завершился ошибкой. Выходной файл отчета не создан или не найден: {output_from_stage3_report}")
                return False
            main_logger.info(f"Этап {stage3_module_name} успешно завершен. Отчет: {output_from_stage3_report}")
            # current_input_path не меняется, нужен HTML для автокоррекции
            # Но если нужно передать путь отчёта — можно записать его в meta-файл
            main_logger.info(f"[DEBUG] После этапа {stage3_module_name}: output_from_stage3_report={output_from_stage3_report}")
            main_logger.info(f"[DEBUG] Содержимое директории {stage3_processing_dir}: {os.listdir(stage3_processing_dir)}")
        except TextProcessingError as e:
            main_logger.error(f"Ошибка на этапе {stage3_module_name}: {str(e)}", exc_info=True, extra=getattr(e, 'details', {}))
            main_logger.error(f"Остановка конвейера после ошибки на этапе: {stage3_module_name}")
            # return False  # Временно не прерываем пайплайн для диагностики
        except Exception as e:
            main_logger.error(f"Непредвиденная системная ошибка на этапе {stage3_module_name}: {str(e)}", exc_info=True)
            main_logger.error(f"Остановка конвейера после системной ошибки на этапе: {stage3_module_name}")
            # return False  # Временно не прерываем пайплайн для диагностики

        # Для автокоррекции нужен и HTML, и отчёт, поэтому current_input_path не меняем
        # Но если нужно, можно записать оба пути в meta-файл в формате JSON

        # ----- Этап 4: Автокоррекция HTML с LLM (AutocorrectProcessorModule) -----
        stage4_module_name = AUTOCORRECT_STAGE
        stage4_processing_dir = os.path.join(PROCESSING_DIR_BASE, correlation_id, stage4_module_name)
        main_logger.info(f"Запуск этапа: {stage4_module_name}")
        os.makedirs(stage4_processing_dir, exist_ok=True)
        try:
            autocorrect_module = AutocorrectProcessorModule(correlation_id)
            output_from_stage4_html = autocorrect_module.run(current_input_path, output_from_stage3_report, stage4_processing_dir)
            status_file_path = os.path.join(stage4_processing_dir, f"{stage4_module_name}_SUCCESS.json")
            if os.path.exists(status_file_path):
                with open(status_file_path, 'r', encoding='utf-8') as f_stat:
                    status_content = json.load(f_stat)
                    output_from_stage4_html = status_content.get('output_file', output_from_stage4_html)
            if not output_from_stage4_html or not os.path.exists(output_from_stage4_html):
                main_logger.error(f"Этап {stage4_module_name} завершился ошибкой. Выходной файл HTML не создан или не найден: {output_from_stage4_html}")
                rejected_log_path = os.path.join(stage4_processing_dir, os.path.basename(current_input_path).replace(".html", ".rejected_fixes.log"))
                if os.path.exists(rejected_log_path):
                    main_logger.info(f"Лог отклоненных исправлений: {rejected_log_path}")
                return False
            main_logger.info(f"Этап {stage4_module_name} успешно завершен. Результат: {output_from_stage4_html}")
            with open(meta_path, "w") as f:
                f.write(output_from_stage4_html)
            main_logger.info(f"[DEBUG] После этапа {stage4_module_name}: output_from_stage4_html={output_from_stage4_html}")
            main_logger.info(f"[DEBUG] Содержимое директории {stage4_processing_dir}: {os.listdir(stage4_processing_dir)}")
        except TextProcessingError as e:
            main_logger.error(f"Ошибка на этапе {stage4_module_name}: {str(e)}", exc_info=True, extra=getattr(e, 'details', {}))
            main_logger.error(f"Остановка конвейера после ошибки на этапе: {stage4_module_name}")
            return False
        except Exception as e:
            main_logger.error(f"Непредвиденная системная ошибка на этапе {stage4_module_name}: {str(e)}", exc_info=True)
            main_logger.error(f"Остановка конвейера после системной ошибки на этапе: {stage4_module_name}")
            return False

        with open(meta_path, "r") as f:
            current_input_path = f.read().strip()

        # Проверка и создание output-папки с логированием
        try:
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            main_logger.info(f"[DEBUG] OUTPUT_DIR создан или уже существует: {OUTPUT_DIR}")
            main_logger.info(f"[DEBUG] Права на OUTPUT_DIR: {oct(os.stat(OUTPUT_DIR).st_mode)}")
        except Exception as e:
            main_logger.error(f"[DEBUG] Ошибка при создании OUTPUT_DIR: {e}")

        # Тестовое создание файла для проверки прав
        test_file_path = os.path.join(OUTPUT_DIR, "test_output_file.txt")
        try:
            with open(test_file_path, "w") as tf:
                tf.write("test")
            main_logger.info(f"[DEBUG] Тестовый файл успешно создан: {test_file_path}")
        except Exception as e:
            main_logger.error(f"[DEBUG] Ошибка при создании тестового файла: {e}")

        # Транслитерация имени итогового файла для диагностики
        output_html_name = f"{basename}_final.html"
        output_docx_name = f"{basename}_final.docx"
        # Транслитерируем только базовое имя
        ascii_basename = safe_ascii_filename(basename)
        # Формируем полные ожидаемые имена с транслитерированным базовым именем
        ascii_html_name = f"{ascii_basename}_final.html"
        ascii_docx_name = f"{ascii_basename}_final.docx"

        output_html_path = os.path.join(OUTPUT_DIR, ascii_html_name)
        output_docx_path = os.path.join(OUTPUT_DIR, ascii_docx_name)
        main_logger.info(f"[DEBUG] Исходное базовое имя: {basename} | Транслитерированное: {ascii_basename}")
        main_logger.info(f"[DEBUG] Ожидаемое итоговое имя HTML: {ascii_html_name}")
        main_logger.info(f"[DEBUG] Ожидаемое итоговое имя DOCX: {ascii_docx_name}")

        # Копирование HTML
        try:
            # Копируем автокорректированный HTML в output с правильным именем
            # current_input_path на этом этапе указывает на автокорректированный HTML
            shutil.copy2(current_input_path, output_html_path)
            main_logger.info(f"Итоговый HTML файл сохранен в: {output_html_path}")
        except Exception as e:
            main_logger.error(f"Ошибка при сохранении итогового HTML файла: {e}", exc_info=True)

        # Проверка содержимого output-папки
        try:
            main_logger.info(f"[DEBUG] Содержимое OUTPUT_DIR после копирования HTML: {os.listdir(OUTPUT_DIR)}")
        except Exception as e:
            main_logger.error(f"[DEBUG] Ошибка при просмотре содержимого OUTPUT_DIR: {e}")

        # === Новый этап: HTML → DOCX ===
        try:
            html2docx = HtmlToDocxProcessorModule(correlation_id)
            # Передаем транслитерированное базовое имя в модуль
            temp_docx_path = html2docx.run(output_html_path, OUTPUT_DIR, basename=ascii_basename)

            if not temp_docx_path or not os.path.exists(temp_docx_path):
                main_logger.error(f"Ошибка на этапе конвертации HTML → DOCX. DOCX не создан: {temp_docx_path}")
                return False
            main_logger.info(f"Итоговый DOCX файл сохранен в: {temp_docx_path}")
        except Exception as e:
            main_logger.error(f"Ошибка при экспорте DOCX: {e}", exc_info=True)
            return False

        # Проверка содержимого output-папки после DOCX
        try:
            main_logger.info(f"[DEBUG] Содержимое OUTPUT_DIR после DOCX: {os.listdir(OUTPUT_DIR)}")
        except Exception as e:
            main_logger.error(f"[DEBUG] Ошибка при просмотре содержимого OUTPUT_DIR после DOCX: {e}")

        orchestrator_status = {
            "status": "success", 
            "correlation_id": correlation_id, 
            "final_output_html": output_html_path,
            "final_output_docx": temp_docx_path
        }
        orchestrator_status_path = os.path.join(PROCESSING_DIR_BASE, correlation_id, "pipeline_status.json")
        with open(orchestrator_status_path, 'w', encoding='utf-8') as f:
            json.dump(orchestrator_status, f, ensure_ascii=False, indent=4)
        main_logger.info(f"Pipeline завершён успешно. Статус сохранён: {orchestrator_status_path}")
        return True
    except Exception as e:
        main_logger.error(f"Непредвиденная ошибка во время выполнения конвейера: {str(e)}", exc_info=True)
        return False
    finally:
        try:
            main_logger.info(f"[DEBUG] Содержимое OUTPUT_DIR в finally: {os.listdir(OUTPUT_DIR)}")
        except Exception as e:
            main_logger.error(f"[DEBUG] Ошибка при просмотре OUTPUT_DIR в finally: {e}")
        main_logger.info("[DEBUG] Пайплайн завершён (finally)")
        if os.path.exists(meta_path):
            os.remove(meta_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Запускает конвейер обработки текстового файла.")
    parser.add_argument("input_filename", help="Имя входного файла (например, 'mydoc.docx'), который должен находиться в директории 'textinput'.")
    parser.add_argument("--basename", help="Оригинальное имя файла без расширения для итоговых файлов.", default=None)

    args = parser.parse_args()

    input_file_to_process = args.input_filename
    basename_arg = args.basename

    # Формируем полный путь для проверки существования, но в run_pipeline передаем только имя
    full_path_to_check = os.path.join(TEXTINPUT_DIR, input_file_to_process)

    if not os.path.exists(full_path_to_check):
        print(f"ОШИБКА: Входной файл не найден в директории '{TEXTINPUT_DIR}': {input_file_to_process}")
        print("Пожалуйста, поместите файл в эту директорию и убедитесь, что имя указано верно.")
        sys.exit(1) # Выходим с ошибкой
    else:
        print(f"Запуск конвейера для файла: {full_path_to_check}")
        if run_pipeline(input_file_to_process, basename_arg): # Передаем имя файла и basename
            print("Обработка конвейера завершена успешно.")
            sys.exit(0) # Выходим без ошибки
        else:
            print("Обработка конвейера завершилась с ошибкой. Проверьте логи.")
            sys.exit(1) # Выходим с ошибкой

    # Директории для информации пользователя после запуска
    print(f"\nДиректория с логами: {os.path.join(WORKSPACE_ROOT, 'logs')}")
    print(f"Директория для входных файлов: {TEXTINPUT_DIR}")
    print(f"Директория с результатами обработки: {PROCESSING_DIR_BASE}")
    print("Внутри processing/[correlation_id]/[имя_этапа]/ будут промежуточные файлы и статус-файлы.")

    print(f"[DEBUG] Рабочая директория: {os.getcwd()}")
    print(f"[DEBUG] Содержимое workspace/output: {os.listdir('workspace/output') if os.path.exists('workspace/output') else 'нет папки'}")
    print(f"[DEBUG] Содержимое workspace/processing: {os.listdir('workspace/processing') if os.path.exists('workspace/processing') else 'нет папки'}")
    print(f"[DEBUG] Входной файл: {full_path_to_check}")
    print(f"[DEBUG] Выходной файл: {os.path.join(PROCESSING_DIR_BASE, correlation_id, 'AutocorrectProcessorModule', 'output_file') if os.path.exists(os.path.join(PROCESSING_DIR_BASE, correlation_id, 'AutocorrectProcessorModule', 'output_file')) else 'нет файла'}") 