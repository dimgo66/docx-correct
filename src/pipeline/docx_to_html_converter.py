# /**
#  * @file: docx_to_html_converter.py
#  * @description: Модуль для конвертации DOCX в HTML с использованием Pandoc.
#  * @dependencies: subprocess, os, json, datetime, src.utils.logger_setup, src.utils.exceptions
#  * @created: 2024-07-30
#  */

import subprocess
import os
import json
import datetime
import traceback
from ..utils.logger_setup import setup_logging # Исправляем на setup_logging
from ..utils.exceptions import PandocConversionError, InputFileNotFoundError, FileOperationError, TextProcessingError

PIPELINE_STAGE_NAME = "DocxToHtmlConversion"

def convert_docx_to_html(input_docx_path, output_html_path, processing_dir, correlation_id, basename=None):
    logger = setup_logging(logger_name=__name__, correlation_id=correlation_id)
    logger.info(f"Начало конвертации DOCX в HTML: {input_docx_path}")

    status_file_path = os.path.join(processing_dir, f"{correlation_id}_DocxToHtmlConverter.status.json")
    status_data = {
        "module": __name__,
        "pipeline_stage": PIPELINE_STAGE_NAME,
        "correlation_id": correlation_id,
        "input_file": input_docx_path,
        "output_file": None,
        "status": "error",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "error_details": None
    }

    try:
        if not os.path.exists(input_docx_path):
            raise InputFileNotFoundError(f"Входной DOCX файл не найден: {input_docx_path}")

        # Убедимся, что директория для выходного файла существует
        os.makedirs(os.path.dirname(output_html_path), exist_ok=True)

        # Формируем имя выходного файла
        if basename is not None:
            output_html_path = os.path.join(os.path.dirname(output_html_path), f"{basename}_final.html")

        # Команда Pandoc
        # Используем --embed-resources для включения изображений и других ресурсов прямо в HTML
        # --standalone для создания полного HTML документа
        # --to html5 для современного HTML
        # --extract-media="куда_извлекать_медиа" - если не хотим встраивать, а извлекать в папку
        command = [
            'pandoc',
            '--from', 'docx',
            '--to', 'html5',
            '--output', output_html_path,
            '--standalone',
            '--metadata', 'title=',
            input_docx_path
        ]

        logger.debug(f"Выполнение команды: {' '.join(command)}")
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            error_message = f"Ошибка Pandoc при конвертации {input_docx_path} в HTML. stderr: {stderr.decode('utf-8', errors='ignore')}"
            logger.error(error_message, extra={'pandoc_stdout': stdout.decode('utf-8', errors='ignore'), 'pandoc_stderr': stderr.decode('utf-8', errors='ignore')}) # Добавил stderr в extra
            raise PandocConversionError(error_message, pandoc_stderr=stderr.decode('utf-8', errors='ignore'), pandoc_stdout=stdout.decode('utf-8', errors='ignore'))

        # Базовая валидация HTML (просто проверяем, что файл не пустой и создан)
        if not os.path.exists(output_html_path) or os.path.getsize(output_html_path) == 0:
            error_msg = f"Выходной HTML файл не создан или пуст: {output_html_path}"
            logger.error(error_msg)
            raise FileOperationError(error_msg, target_file=output_html_path)

        logger.info(f"Файл успешно сконвертирован в HTML: {output_html_path}")
        status_data["status"] = "success"
        status_data["output_file"] = output_html_path

    except InputFileNotFoundError as e:
        logger.error(f"Ошибка: {str(e)}", exc_info=True)
        status_data["error_details"] = {"type": e.__class__.__name__, "message": str(e), "traceback": traceback.format_exc()}
        # Перебрасываем исключение, чтобы оркестратор мог его поймать
        raise
    except PandocConversionError as e:
        # Уже залогировано выше, здесь только обновляем статус
        status_data["error_details"] = {"type": e.__class__.__name__, "message": str(e), "details": e.details, "traceback": traceback.format_exc()}
        raise
    except FileOperationError as e:
        logger.error(f"Ошибка операции с файлом: {str(e)}", exc_info=True)
        status_data["error_details"] = {"type": e.__class__.__name__, "message": str(e), "details": e.details, "traceback": traceback.format_exc()}
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при конвертации DOCX в HTML: {str(e)}", exc_info=True)
        status_data["error_details"] = {"type": e.__class__.__name__, "message": str(e), "traceback": traceback.format_exc()}
        # Оборачиваем в наше общее исключение для консистентности, если нужно
        # raise FileOperationError(f"Непредвиденная ошибка: {str(e)}", original_exception=e) # Лучше перебросить оригинальное исключение или наше кастомное
        raise TextProcessingError(f"Непредвиденная ошибка на этапе {PIPELINE_STAGE_NAME}: {str(e)}", details={'original_exception': str(e)}) # Оборачиваем в TextProcessingError
    finally:
        status_data["timestamp_end"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            # Используем f-строку для имени статус-файла
            success_status_file = os.path.join(processing_dir, f"{PIPELINE_STAGE_NAME}_SUCCESS.json")
            error_status_file = os.path.join(processing_dir, f"{PIPELINE_STAGE_NAME}_ERROR.json")

            # Определяем, какой файл сохранить, в зависимости от статуса
            final_status_file_path = success_status_file if status_data["status"] == "success" else error_status_file

            with open(final_status_file_path, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=4)
            logger.debug(f"Статус-файл сохранен: {final_status_file_path}")
        except Exception as e_stat:
            # Здесь уже нельзя использовать основной логгер, т.к. может быть проблема с ним
            print(f"КРИТИЧЕСКАЯ ОШИБКА: Не удалось сохранить статус-файл {final_status_file_path}: {str(e_stat)}", file=sys.stderr)

    return status_data.get("output_file") # Возвращаем путь к выходному файлу при успехе, иначе None

if __name__ == '__main__':
    # Пример использования (требует создания тестовых файлов и папок)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.join(current_dir, '..', '..', 'workspace')
    input_dir = os.path.join(workspace_root, 'input')
    # Используем уникальную подпапку для тестового запуска
    test_correlation_id = "test-corr-" + datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    processing_dir_for_module = os.path.join(workspace_root, 'processing', test_correlation_id, PIPELINE_STAGE_NAME)

    os.makedirs(input_dir, exist_ok=True)
    os.makedirs(processing_dir_for_module, exist_ok=True)

    # Создайте тестовый .docx файл тут: test_input.docx
    test_docx_file = os.path.join(input_dir, 'test_input.docx')
    # Для теста, если нет pandoc или файла, можно создать пустой файл
    # ВНИМАНИЕ: Создание пустого файла DOCX без использования библиотеки приведет к ошибке Pandoc!
    # Лучше убедиться, что Pandoc установлен и создать настоящий тестовый DOCX файл или использовать существующий.
    if not os.path.exists(test_docx_file):
        print(f"ВНИМАНИЕ: Тестовый DOCX файл не найден: {test_docx_file}")
        print("Пожалуйста, создайте его или укажите существующий для корректного теста.")
        # Если файла нет, можно просто выйти или создать заглушку, но Pandoc все равно выдаст ошибку
        # Создадим пустой файл как заглушку, но ожидаем ошибку Pandoc
        try:
            with open(test_docx_file, 'w') as f: pass # Создаем пустой файл
            print(f"Создан пустой файл-заглушка: {test_docx_file}. Pandoc, скорее всего, выдаст ошибку.")
        except Exception as e:
             print(f"Ошибка при создании файла-заглушки {test_docx_file}: {e}")
             sys.exit(1) # Выходим, если не удалось даже создать файл


    test_html_file = os.path.join(processing_dir_for_module, 'test_output.html') # Теперь путь к выходному файлу внутри папки обработки этапа
    

    print(f"Тестовый запуск {PIPELINE_STAGE_NAME}...")
    print(f"Входной файл: {test_docx_file}")
    print(f"Выходной файл будет: {test_html_file}")
    print(f"Директория обработки: {processing_dir_for_module}")
    print(f"Correlation ID: {test_correlation_id}")

    # Настройка основного логгера для примера
    # В реальном оркестраторе логгер будет настроен один раз
    # Используем setup_logging и передаем correlation_id
    main_logger_for_example = setup_logging(logger_name='main_test_script_converter', correlation_id=test_correlation_id)
    main_logger_for_example.info("Начало тестового запуска конвертера.")

    try:
        # Передаем test_html_file как output_html_path
        output_file = convert_docx_to_html(test_docx_file, test_html_file, processing_dir_for_module, test_correlation_id)
        if output_file:
            main_logger_for_example.info(f"Конвертация завершилась успешно. HTML файл: {output_file}")
        else:
            main_logger_for_example.error(f"Конвертация не удалась. Смотрите логи и статус-файл в {processing_dir_for_module}")
    except Exception as e:
        main_logger_for_example.error(f"Во время тестового запуска произошла ошибка: {str(e)}", exc_info=True)
        sys.exit(1) # Выходим с ошибкой при тестовом запуске

    print(f"Проверьте логи в {os.path.join(workspace_root, 'logs', test_correlation_id)} и статус-файл в {processing_dir_for_module}") # Указываем путь до логов с correlation_id
    sys.exit(0) # Выходим без ошибки при успешном тестовом запуске 