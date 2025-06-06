"""
Модуль для настройки и конфигурации логгеров.

@file: logger_setup.py
@description: Настройка логирования для проекта.
@dependencies: logging
@created: 2024-07-31
"""

import logging
import os
import sys
from datetime import datetime

# Определяем базовую директорию для логов относительно корня проекта
# Предполагаем, что этот файл находится в src/utils/, значит корень проекта - это ../../
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
LOGS_DIR = os.path.join(PROJECT_ROOT, "workspace", "logs")

if not os.path.exists(LOGS_DIR):
    try:
        os.makedirs(LOGS_DIR)
    except OSError as e:
        # Если не удалось создать директорию, будем выводить в stderr
        sys.stderr.write(f"Warning: Could not create log directory {LOGS_DIR}. Error: {e}. Logs will go to stderr.\n")
        LOGS_DIR = None # Сбрасываем, чтобы логи шли в консоль

# Уровень логирования по умолчанию
DEFAULT_LOG_LEVEL = logging.INFO

# Флаг, чтобы базовая конфигурация применялась только один раз
_base_config_applied = False

def setup_logging(correlation_id="global", logger_name="default_logger", level=DEFAULT_LOG_LEVEL, log_to_file=True):
    """
    Настраивает и возвращает логгер с заданным именем и уровнем.
    Логи будут сохраняться в файл и выводиться в консоль.
    Файл логов будет именоваться с использованием correlation_id и текущей даты.

    :param correlation_id: Идентификатор текущего запуска/сессии для группировки логов.
    :param logger_name: Имя логгера (обычно __name__ вызывающего модуля).
    :param level: Уровень логирования (например, logging.INFO, logging.DEBUG).
    :param log_to_file: Булево значение, сохранять ли логи в файл.
    :return: Сконфигурированный объект логгера.
    """
    global _base_config_applied

    logger = logging.getLogger(logger_name)
    
    # Чтобы избежать многократного добавления обработчиков к одному и тому же логгеру
    # при повторных вызовах setup_logging для того же logger_name.
    if logger.hasHandlers() and not getattr(logger, '_configured_by_setup_logging', False):
        # Если есть обработчики, но не наши, это может быть проблемой. 
        # Если это наши (например, root logger уже настроен), то не будем добавлять еще раз.
        pass
    elif logger.hasHandlers() and getattr(logger, '_configured_by_setup_logging', False):
        # Уже настроен этим методом, просто возвращаем
        logger.setLevel(level) # Позволяем менять уровень для уже настроенного логгера
        return logger

    logger.setLevel(level)
    logger.propagate = False # Предотвращаем дублирование логов в родительский логгер, если он тоже настроен
    setattr(logger, '_configured_by_setup_logging', True)

    # Форматтер
    # Включаем correlation_id в формат логов
    log_format = f'%(asctime)s - %(name)s - %(levelname)s - CORR_ID:{correlation_id} - %(message)s'
    formatter = logging.Formatter(log_format)

    # Обработчик для вывода в консоль (stdout)
    # Используем StreamHandler(sys.stdout), чтобы избежать проблем с выводом в某些IDE или окружениях, где stderr может быть перенаправлен.
    console_handler = logging.StreamHandler(sys.stdout) 
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    if log_to_file and LOGS_DIR:
        # Имя файла логов: YYYY-MM-DD_correlation_id.log
        safe_correlation_id = correlation_id.replace('/', '_').replace('\\', '_')
        log_file_name = f"{datetime.now().strftime('%Y-%m-%d')}_{safe_correlation_id}.log"
        log_file_path = os.path.join(LOGS_DIR, log_file_name)
        
        # Обработчик для записи в файл
        file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Базовая конфигурация для root логгера, чтобы логи из библиотек тоже куда-то шли
    # Делаем это только один раз
    if not _base_config_applied:
        logging.basicConfig(level=logging.WARNING, handlers=[console_handler]) # По умолчанию WARNING для библиотек
        _base_config_applied = True
        # Отключаем слишком 'болтливые' логгеры библиотек, если необходимо
        # logging.getLogger("some_library").setLevel(logging.WARNING)

    return logger

# Пример использования, если файл запускается напрямую
if __name__ == '__main__':
    # Настройка логгера для этого модуля
    main_logger = setup_logging(correlation_id="main_logger_test_001", logger_name=__name__, level=logging.DEBUG)
    main_logger.debug("Это тестовое DEBUG сообщение от главного логгера.")
    main_logger.info("Это тестовое INFO сообщение от главного логгера.")
    main_logger.warning("Это тестовое WARNING сообщение от главного логгера.")
    main_logger.error("Это тестовое ERROR сообщение от главного логгера.")

    # Пример использования в другом 'модуле'
    module_logger = setup_logging(correlation_id="module_logger_test_002", logger_name="my_module", level=logging.INFO)
    module_logger.info("Это INFO из 'my_module'.")
    
    another_logger_for_same_module = setup_logging(correlation_id="module_logger_test_002", logger_name="my_module", level=logging.DEBUG)
    another_logger_for_same_module.debug("Это DEBUG из 'my_module' после смены уровня.")

    # Проверка, что логи пишутся в файл (если LOGS_DIR доступен)
    if LOGS_DIR:
        print(f"Проверьте файлы логов в директории: {LOGS_DIR}")
    else:
        print("Директория для логов не была создана, логи только в консоли.") 