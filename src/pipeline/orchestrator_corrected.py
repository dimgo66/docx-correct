import os
import shutil
import json
import sys
import argparse
import uuid
from datetime import datetime
import logging

from .processors.docx_to_html_converter import convert_docx_to_html
from .processors.typograf_processor import TypografProcessorModule
from .processors.languagetool_processor import LanguageToolProcessorModule
from .processors.autocorrect_processor import AutocorrectProcessorModule
from .processors.html_to_docx_processor import HtmlToDocxProcessorModule
from .utils import setup_logging, TextProcessingError, safe_ascii_filename

# Настройка логирования
main_logger = setup_logging("main_orchestrator")

# Определение директорий (предполагается, что они определены где-то выше или в другом конфиге)
# В рамках данного примера, определим их здесь
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEXTINPUT_DIR = os.path.join(WORKSPACE_ROOT, "textinput")
PROCESSING_DIR_BASE = os.path.join(WORKSPACE_ROOT, "workspace", "processing")
OUTPUT_DIR = os.path.join(WORKSPACE_ROOT, "workspace", "output")

# Имена этапов для логирования и создания поддиректорий
DOCX_TO_HTML_STAGE = "DocxToHtmlConversion"
TYPOGRAF_STAGE = "TypografProcessorModule"
LANGUAGETOOL_STAGE = "LanguageToolProcessorModule"
AUTOCORRECT_STAGE = "AutocorrectProcessorModule"
HTML_TO_DOCX_STAGE = "HtmlToDocxProcessorModule"


def run_pipeline(input_file_name: str, basename: str = None) -> bool:
    """
    Запускает конвейер обработки текстового файла.

    Args:
        input_file_name: Имя входного файла (предполагается, что он находится в TEXTINPUT_DIR).
        basename: Оригинальное имя файла без расширения для итоговых файлов. Если None, определяется из input_file_name.

    Returns:
        True, если конвейер завершился успешно, False иначе.
    """
    main_logger.info(f"Запуск конвейера для файла: {input_file_name}")

    # Генерация correlation_id для отслеживания конкретного запуска
    # Используем имя файла и временную метку для уникальности
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    file_basename = os.path.splitext(input_file_name)[0]
    correlation_id = f"{file_basename}_{timestamp}_{uuid.uuid4().hex[:8]}" # Добавляем часть UUID для гарантии уникальности

    original_input_path = os.path.join(TEXTINPUT_DIR, input_file_name)
    meta_path = os.path.join(PROCESSING_DIR_BASE, f"pipeline_{correlation_id}.meta")

    main_logger.info(f"Сгенерирован correlation_id: {correlation_id}")
    main_logger.info(f"Путь к мета-файлу: {meta_path}")

    # Проверка существования входного файла
    if not os.path.exists(original_input_path):
        main_logger.error(f"Входной файл не найден: {original_input_path}")
        return False

    # Создаём meta-файл с исходным путём
    try:
        os.makedirs(PROCESSING_DIR_BASE, exist_ok=True)
        with open(meta_path, "w") as f:
            f.write(original_input_path)
        main_logger.info(f"Создан мета-файл с исходным путём: {meta_path}")
        main_logger.info(f"[DEBUG] Содержимое мета-файла после записи: {original_input_path}")

    except Exception as e:
        main_logger.error(f"Ошибка при создании или записи мета-файла {meta_path}: {e}", exc_info=True)
        return False

    try:
        # Переменная для хранения выходного файла текущего этапа
        current_input_path = original_input_path # Начинаем с исходного файла

        # Перед каждым этапом читаем путь из meta-файла (эта логика уже внутри этапов или должна быть там)
        # Чтение из мета-файл будет делать перед каждым этапом, чтобы убедиться в актуальности пути
        # Но для первого этапа input_path - это original_input_path

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
                # Решаем не прерывать пайплайн, а продолжить с последним известным хорошим файлом или отметить ошибку и пропустить этап?
                # Пока просто логируем и продолжаем. Если return False - пайплайн прервется.
                # return False

            # После этапа записываем новый путь в meta-файл
            # Здесь логика должна быть такой: если этап успешен, записываем ЕГО выходной файл.
            # Если нет, оставляем путь предыдущего успешного этапа или исходного файла.
            # Для простоты сейчас всегда записываем то, что вернул convert_docx_to_html (даже если его нет)
            # В реальной системе тут нужна проверка output_from_stage1 и запись только при успехе.
            with open(meta_path, "w") as f:
                f.write(output_from_stage1 if output_from_stage1 and os.path.exists(output_from_stage1) else current_input_path)

            main_logger.info(f"Этап {stage1_module_name} успешно завершен. Результат: {output_from_stage1}")
            # Логируем содержимое meta-файла и список файлов в директории
            main_logger.info(f"[DEBUG] После этапа {stage1_module_name}: output_from_stage1={output_from_stage1}")
            main_logger.info(f"[DEBUG] Содержимое директории {stage1_processing_dir}: {os.listdir(stage1_processing_dir)}")

        except TextProcessingError as e:
            main_logger.error(f"Ошибка на этапе {stage1_module_name}: {str(e)}", exc_info=True, extra=getattr(e, 'details', {}))
            main_logger.error(f"Остановка конвейера после ошибки на этапе: {stage1_module_name}")
            # return False # Временно не прерываем пайплайн для диагностики
        except Exception as e:
            main_logger.error(f"Непредвиденная системная ошибка на этапе {stage1_module_name}: {str(e)}", exc_info=True)
            main_logger.error(f"Остановка конвейера после системной ошибки на этапе: {stage1_module_name}")
            # return False # Временно не прерываем пайплайн для диагностики


        # Перед следующим этапом читаем путь из meta-файла
        with open(meta_path, "r") as f:
            current_input_path = f.read().strip()
        main_logger.info(f"[DEBUG] Прочитан путь из мета-файла перед этапом 2: {current_input_path}")


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
                return False # Этот этап критичен, останавливаем пайплайн при ошибке

            main_logger.info(f"Этап {stage2_module_name} успешно завершен. Результат: {output_from_stage2_html}")
            # После этапа записываем новый путь в meta-файл
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


        # Перед следующим этапом читаем путь из meta-файла
        with open(meta_path, "r") as f:
            current_input_path = f.read().strip()
        main_logger.info(f"[DEBUG] Прочитан путь из мета-файла перед этапом 3: {current_input_path}")


        # ----- Этап 3: Проверка LanguageTool (LanguageToolProcessorModule) -----

        stage3_module_name = LANGUAGETOOL_STAGE
        stage3_processing_dir = os.path.join(PROCESSING_DIR_BASE, correlation_id, stage3_module_name)
        # stage3_output_report_expected = os.path.join(stage3_processing_dir, os.path.splitext(os.path.basename(current_input_path))[0] + "_languagetool_report.json")
        main_logger.info(f"Запуск этапа: {stage3_module_name}")
        os.makedirs(stage3_processing_dir, exist_ok=True)
        try:
            languagetool_module = LanguageToolProcessorModule(correlation_id)
            # LanguageTool run должен принять путь к HTML (current_input_path) и вернуть путь к отчету JSON
            output_from_stage3_report = languagetool_module.run(current_input_path, stage3_processing_dir)

            status_file_path = os.path.join(stage3_processing_dir, f"{stage3_module_name}_SUCCESS.json")
            if os.path.exists(status_file_path):
                with open(status_file_path, 'r', encoding='utf-8') as f_stat:
                    status_content = json.load(f_stat)
                output_from_stage3_report = status_content.get('output_report_path', output_from_stage3_report)


            if not output_from_stage3_report or not os.path.exists(output_from_stage3_report):
                main_logger.error(f"Этап {stage3_module_name} завершился ошибкой. Выходной файл отчета не создан или не найден: {output_from_stage3_report}")
                # Решаем не прерывать пайплайн, а продолжить? Или отчет критичен?
                # Пока просто логируем и продолжаем. Если return False - пайплайн прервется.
                # return False

            main_logger.info(f"Этап {stage3_module_name} успешно завершен. Отчет: {output_from_stage3_report}")
            # current_input_path не меняется после этого этапа, т.к. следующий этап AutocorrectModule работает с HTML
            # Но если нужно передать путь отчёта для следующего этапа — можно записать его в meta-файл вместе с путём HTML (например, в JSON формате)
            # Для текущей логики AutocorrectProcessorModule, который принимает HTML и отчет, meta-файл не обновляется.
            # Это нужно пересмотреть, если AutocorrectProcessorModule будет читать входной HTML из meta-файла.
            # А пока, для консистентности, запишем путь HTML обратно, если этап успешен
            # Но в AutocorrectModule нужно будет читать и путь HTML, и путь отчета.
            # В мета-файле лучше хранить JSON со всеми путями, нужными следующему этапу.
            # Например: {"html_path": "...", "report_path": "..."}
            # Для простоты пока ничего не записываем в meta_path после этого этапа, т.к. AutocorrectModule берет HTML из прошлого этапа и отчет из этого.
            # Это потенциальная точка ошибки при чтении из мета-файла перед 4-м этапом.

            main_logger.info(f"[DEBUG] После этапа {stage3_module_name}: output_from_stage3_report={output_from_stage3_report}")
            main_logger.info(f"[DEBUG] Содержимое директории {stage3_processing_dir}: {os.listdir(stage3_processing_dir)}")

        except TextProcessingError as e:
            main_logger.error(f"Ошибка на этапе {stage3_module_name}: {str(e)}", exc_info=True, extra=getattr(e, 'details', {}))
            main_logger.error(f"Остановка конвейера после ошибки на этапе: {stage3_module_name}")
            # return False # Временно не прерываем пайплайн для диагностики
        except Exception as e:
            main_logger.error(f"Непредвиденная системная ошибка на этапе {stage3_module_name}: {str(e)}", exc_info=True)
            main_logger.error(f"Остановка конвейера после системной ошибки на этапе: {stage3_module_name}")
            # return False # Временно не прерываем пайплайн для диагностики

        # Для автокоррекции нужен и HTML (current_input_path), и отчёт (output_from_stage3_report)
        # Мета-файл сейчас хранит только один путь. Это нужно изменить, чтобы хранить JSON.
        # Чтение перед этапом 4 должно быть адаптировано для чтения JSON с двумя путями.
        # Пока что, AutocorrectProcessorModule принимает оба пути как аргументы функции.


        # ----- Этап 4: Автокоррекция HTML с LLM (AutocorrectProcessorModule) -----

        stage4_module_name = AUTOCORRECT_STAGE
        stage4_processing_dir = os.path.join(PROCESSING_DIR_BASE, correlation_id, stage4_module_name)
        main_logger.info(f"Запуск этапа: {stage4_module_name}")
        os.makedirs(stage4_processing_dir, exist_ok=True)
        try:
            autocorrect_module = AutocorrectProcessorModule(correlation_id)
            # AutocorrectModule принимает путь к HTML (который должен быть из этапа 2 или 1)
            # и путь к отчету (из этапа 3).
            # current_input_path после этапа 3 всё еще содержит путь к HTML из этапа 2.
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
                return False # Этот этап критичен, останавливаем пайплайн при ошибке

            main_logger.info(f"Этап {stage4_module_name} успешно завершен. Результат: {output_from_stage4_html}")
            # После этапа записываем новый путь (к автокорректированному HTML) в meta-файл
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


        # Перед следующим этапом читаем путь из мета-файл (это будет путь к автокорректированному HTML)
        with open(meta_path, "r") as f:
            current_input_path = f.read().strip()
        main_logger.info(f"[DEBUG] Прочитан путь из мета-файла перед этапом 5 (HTML→DOCX): {current_input_path}")


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
        if basename is None:
             base_name_for_output = os.path.splitext(input_file_name)[0]
        else:
             base_name_for_output = basename

        output_html_name = f"{base_name_for_output}_final.html"
        output_docx_name = f"{base_name_for_output}_final.docx"

        ascii_html_name = safe_ascii_filename(output_html_name)
        ascii_docx_name = safe_ascii_filename(output_docx_name)

        output_html_path = os.path.join(OUTPUT_DIR, ascii_html_name)
        output_docx_path = os.path.join(OUTPUT_DIR, ascii_docx_name)

        main_logger.info(f"[DEBUG] Итоговое имя HTML: {output_html_name} | ASCII: {ascii_html_name}")
        main_logger.info(f"[DEBUG] Итоговое имя DOCX: {output_docx_name} | ASCII: {ascii_docx_name}")


        # Копирование итогового HTML из processing в output
        # Путь к итоговому HTML сейчас в current_input_path (из мета-файла после этапа 4)
        try:
            if os.path.exists(current_input_path):
                 shutil.copy2(current_input_path, output_html_path)
                 main_logger.info(f"Итоговый HTML файл сохранен в: {output_html_path}")
            else:
                 main_logger.error(f"Исходный HTML файл для сохранения не найден: {current_input_path}")
                 # Решить, нужно ли прерывать пайплайн или просто не сохранять HTML?
                 # Пока просто логируем и идем дальше к DOCX
        except Exception as e:
            main_logger.error(f"Ошибка при сохранении итогового HTML файла: {e}", exc_info=True)


        # Проверка содержимого output-папки
        try:
            main_logger.info(f"[DEBUG] Содержимое OUTPUT_DIR после копирования HTML: {os.listdir(OUTPUT_DIR)}")
        except Exception as e:
            main_logger.error(f"[DEBUG] Ошибка при просмотре содержимого OUTPUT_DIR: {e}")


        # === Этап 5: HTML → DOCX ===
        stage5_module_name = HTML_TO_DOCX_STAGE
        main_logger.info(f"Запуск этапа: {stage5_module_name}")
        # Этот этап должен принять путь к итоговому HTML (current_input_path)
        try:
            html2docx = HtmlToDocxProcessorModule(correlation_id)
            # output_html_path - это куда был скопирован HTML в output директорию
            temp_docx_path = html2docx.run(output_html_path, OUTPUT_DIR, basename=ascii_docx_name)

            if not temp_docx_path or not os.path.exists(temp_docx_path):
                main_logger.error(f"Ошибка на этапе конвертации HTML → DOCX. DOCX не создан: {temp_docx_path}")
                return False # Этот этап критичен, останавливаем пайплайн

            main_logger.info(f"Итоговый DOCX файл сохранен в: {temp_docx_path}")

        except Exception as e:
            main_logger.error(f"Ошибка при экспорте DOCX: {e}", exc_info=True)
            return False


        # Проверка содержимого output-папки после DOCX
        try:
            main_logger.info(f"[DEBUG] Содержимое OUTPUT_DIR после DOCX: {os.listdir(OUTPUT_DIR)}")
        except Exception as e:
            main_logger.error(f"[DEBUG] Ошибка при просмотре содержимого OUTPUT_DIR после DOCX: {e}")


        # Формирование и сохранение итогового статуса пайплайна
        orchestrator_status = {
            "status": "success",
            "correlation_id": correlation_id,
            "final_output_html": output_html_path,
            "final_output_docx": temp_docx_path
        }
        orchestrator_status_path = os.path.join(PROCESSING_DIR_BASE, correlation_id, "pipeline_status.json")
        try:
            # Убедимся, что директория для статус файла существует
            os.makedirs(os.path.dirname(orchestrator_status_path), exist_ok=True)
            with open(orchestrator_status_path, 'w', encoding='utf-8') as f:
                json.dump(orchestrator_status, f, ensure_ascii=False, indent=4)
            main_logger.info(f"Pipeline завершён успешно. Статус сохранён: {orchestrator_status_path}")
        except Exception as e:
             main_logger.error(f"Ошибка при сохранении статус файла {orchestrator_status_path}: {e}")


        return True # Пайплайн успешно завершен

    except Exception as e:
        main_logger.error(f"Непредвиденная ошибка во время выполнения конвейера: {str(e)}", exc_info=True)
        # В случае общей ошибки конвейера, также можно сохранить статус "failed"
        orchestrator_status = {
            "status": "failed",
            "correlation_id": correlation_id,
            "error": str(e)
        }
        orchestrator_status_path = os.path.join(PROCESSING_DIR_BASE, correlation_id, "pipeline_status.json")
        try:
            os.makedirs(os.path.dirname(orchestrator_status_path), exist_ok=True)
            with open(orchestrator_status_path, 'w', encoding='utf-8') as f:
                json.dump(orchestrator_status, f, ensure_ascii=False, indent=4)
            main_logger.info(f"Pipeline завершён с ошибкой. Статус сохранён: {orchestrator_status_path}")
        except Exception as status_e:
             main_logger.error(f"Критическая ошибка: не удалось сохранить статус 'failed' {orchestrator_status_path}: {status_e}")


        return False # Пайплайн завершен с ошибкой
    finally:
        # Этот блок выполняется всегда, независимо от того, было ли исключение или нет
        main_logger.info(f"[DEBUG] Пайплайн завершён (finally). Проверка и удаление мета-файла: {meta_path}")
        # Добавим логирование содержимого OUTPUT_DIR и PROCESSING_DIR_BASE в finally для диагностики
        try:
            main_logger.info(f"[DEBUG] Содержимое OUTPUT_DIR в finally: {os.listdir(OUTPUT_DIR) if os.path.exists(OUTPUT_DIR) else 'Папка не существует'}")
        except Exception as e:
            main_logger.error(f"[DEBUG] Ошибка при просмотре OUTPUT_DIR в finally: {e}")
        try:
            # Логируем только директорию correlation_id в PROCESSING_DIR_BASE
            correlation_processing_dir = os.path.join(PROCESSING_DIR_BASE, correlation_id)
            main_logger.info(f"[DEBUG] Содержимое {correlation_processing_dir} в finally: {os.listdir(correlation_processing_dir) if os.path.exists(correlation_processing_dir) else 'Папка не существует'}")
        except Exception as e:
            main_logger.error(f"[DEBUG] Ошибка при просмотре {correlation_processing_dir} в finally: {e}")

        if os.path.exists(meta_path):
            try:
                os.remove(meta_path)
                main_logger.info(f"Мета-файл удален: {meta_path}")
            except Exception as e:
                main_logger.error(f"Ошибка при удалении мета-файла {meta_path}: {e}", exc_info=True)
        else:
             main_logger.info(f"Мета-файл не найден для удаления: {meta_path}")


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
        sys.exit(1)
    else:
        print(f"Запуск конвейера для файла: {full_path_to_check}")
        # Передаем только имя файла в run_pipeline, чтобы там формировались полные пути на основе TEXTINPUT_DIR
        if run_pipeline(input_file_to_process, basename_arg):
            print("Обработка конвейера завершена успешно.")
            sys.exit(0)
        else:
            print("Обработка конвейера завершилась с ошибкой. Проверьте логи.")
            sys.exit(1)

    # Директории для информации пользователя после запуска (эти строки не будут выполнены после sys.exit)
    # print(f"\nДиректория с логами: {os.path.join(WORKSPACE_ROOT, 'logs')}")
    # print(f"Директория для входных файлов: {TEXTINPUT_DIR}")
    # print(f"Директория с результатами обработки: {PROCESSING_DIR_BASE}")
    # print("Внутри processing/[correlation_id]/[имя_этапа]/ будут промежуточные файлы и статус-файлы.")

    # print(f"[DEBUG] Рабочая директория: {os.getcwd()}")
    # print(f"[DEBUG] Содержимое workspace/output: {os.listdir('workspace/output') if os.path.exists('workspace/output') else 'нет папки'}")
    # print(f"[DEBUG] Содержимое workspace/processing: {os.listdir('workspace/processing') if os.path.exists('workspace/processing') else 'нет папка'}")
    # print(f"[DEBUG] Входной файл: {full_path_to_check}")
    # # Эта строка может вызвать ошибку, если файл не создан. Лучше проверять его существование.
    # # print(f"[DEBUG] Выходной файл: {os.path.join(PROCESSING_DIR_BASE, correlation_id, 'AutocorrectProcessorModule', 'output_file') if os.path.exists(os.path.join(PROCESSING_DIR_BASE, correlation_id, 'AutocorrectProcessorModule', 'output_file')) else 'нет файла')}")
