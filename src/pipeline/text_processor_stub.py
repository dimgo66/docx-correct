# /**
#  * @file: text_processor_stub.py
#  * @description: Заглушка для модуля обработки текста.
#  * @dependencies: os, json, shutil, datetime, src.utils.logger_setup, src.utils.exceptions
#  * @created: 2024-07-30
#  */

import os
import json
import shutil
import datetime
import traceback
from ..utils.logger_setup import setup_logger
from ..utils.exceptions import InputFileNotFoundError, FileOperationError # Можем использовать общие ошибки

PIPELINE_STAGE_NAME = "TextProcessingStub"

def process_text_stub(input_html_path, output_html_path, processing_dir, correlation_id):
    logger = setup_logger(__name__, correlation_id=correlation_id, pipeline_stage=PIPELINE_STAGE_NAME, file_path=input_html_path)
    logger.info(f"Начало имитации обработки текста: {input_html_path}")

    status_file_path = os.path.join(processing_dir, f"{correlation_id}_{PIPELINE_STAGE_NAME}.status.json")
    status_data = {
        "module": __name__,
        "pipeline_stage": PIPELINE_STAGE_NAME,
        "correlation_id": correlation_id,
        "input_file": input_html_path,
        "output_file": None,
        "status": "error",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "error_details": None
    }

    try:
        if not os.path.exists(input_html_path):
            raise InputFileNotFoundError(f"Входной HTML файл не найден: {input_html_path}")

        os.makedirs(os.path.dirname(output_html_path), exist_ok=True)

        # Имитация обработки: просто копируем файл
        shutil.copyfile(input_html_path, output_html_path)
        logger.debug(f"Файл скопирован из {input_html_path} в {output_html_path}")

        if not os.path.exists(output_html_path) or os.path.getsize(output_html_path) == 0:
            error_msg = f"Выходной HTML файл (копия) не создан или пуст: {output_html_path}"
            logger.error(error_msg)
            raise FileOperationError(error_msg, target_file=output_html_path)

        logger.info(f"Имитация обработки текста успешно завершена. Результат: {output_html_path}")
        status_data["status"] = "success"
        status_data["output_file"] = output_html_path

    except InputFileNotFoundError as e:
        logger.error(f"Ошибка: {str(e)}", exc_info=True)
        status_data["error_details"] = {"type": e.__class__.__name__, "message": str(e), "traceback": traceback.format_exc()}
        raise
    except FileOperationError as e:
        logger.error(f"Ошибка операции с файлом: {str(e)}", exc_info=True)
        status_data["error_details"] = {"type": e.__class__.__name__, "message": str(e), "details": e.details, "traceback": traceback.format_exc()}
        raise
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при имитации обработки текста: {str(e)}", exc_info=True)
        status_data["error_details"] = {"type": e.__class__.__name__, "message": str(e), "traceback": traceback.format_exc()}
        raise FileOperationError(f"Непредвиденная ошибка в заглушке: {str(e)}", original_exception=e)
    finally:
        status_data["timestamp_end"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        try:
            with open(status_file_path, 'w', encoding='utf-8') as f:
                json.dump(status_data, f, ensure_ascii=False, indent=4)
            logger.debug(f"Статус-файл сохранен: {status_file_path}")
        except Exception as e_stat:
            logger.error(f"Не удалось сохранить статус-файл {status_file_path}: {str(e_stat)}", exc_info=True)

    return status_data["status"] == "success"

if __name__ == '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_root = os.path.join(current_dir, '..', '..', 'workspace')
    # Предполагаем, что предыдущий этап (DocxToHtmlConversion) уже создал файл
    # в своей директории обработки
    prev_stage_processing_dir = os.path.join(workspace_root, 'processing', 'DocxToHtmlConversion') 
    input_file_from_prev_stage = os.path.join(prev_stage_processing_dir, 'test_output.html') # Имя файла из примера docx_to_html_converter

    processing_dir_for_module = os.path.join(workspace_root, 'processing', PIPELINE_STAGE_NAME)
    os.makedirs(processing_dir_for_module, exist_ok=True)

    # Для теста создадим входной файл, если его нет
    if not os.path.exists(input_file_from_prev_stage):
        os.makedirs(os.path.dirname(input_file_from_prev_stage), exist_ok=True)
        with open(input_file_from_prev_stage, 'w', encoding='utf-8') as f:
            f.write("<html><body><h1>Тестовый HTML для заглушки</h1><p>Какой-то текст.</p></body></html>")
        print(f"Создан заглушка для входного HTML: {input_file_from_prev_stage}")

    test_output_file = os.path.join(processing_dir_for_module, 'stub_processed_output.html')
    test_correlation_id = "test-corr-002"

    print(f"Тестовый запуск {PIPELINE_STAGE_NAME}...")
    main_logger_for_example = setup_logger('main_test_script_stub', correlation_id=test_correlation_id)
    main_logger_for_example.info(f"Начало тестового запуска заглушки обработчика текста.")

    try:
        success = process_text_stub(input_file_from_prev_stage, test_output_file, processing_dir_for_module, test_correlation_id)
        if success:
            main_logger_for_example.info(f"Обработка-заглушка завершилась успешно. Результат: {test_output_file}")
        else:
            main_logger_for_example.error(f"Обработка-заглушка не удалась. Смотрите логи и статус-файл в {processing_dir_for_module}")
    except Exception as e:
        main_logger_for_example.error(f"Во время тестового запуска заглушки произошла ошибка: {str(e)}", exc_info=True)
    
    print(f"Проверьте логи в {os.path.join(workspace_root, 'logs')} и статус-файл в {processing_dir_for_module}") 