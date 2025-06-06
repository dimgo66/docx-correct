"""
Модуль для применения типографики к HTML-файлу с использованием Node.js скрипта typografize.js.

@file: typograf_processor_module.py
@description: Модуль для применения типографики к HTML-файлу с использованием Node.js скрипта typografize.js.
@dependencies: Node.js, tools/typografize.js, src/utils/logger_setup.py, src/utils/exceptions.py
@created: 2024-07-31
"""

import os
import subprocess
import json
import logging
import sys
from ..utils.exceptions import TypografProcessingError
from ..utils.logger_setup import setup_logging
from typing import Optional

class TypografProcessorModule:
    """
    Модуль для применения типографики к HTML через tools/typografize.js.
    """
    def __init__(self, correlation_id: str):
        self.correlation_id = correlation_id
        self.logger = logging.getLogger(f"TypografProcessorModule.{correlation_id}")

    def run(self, html_path: str, output_dir: str) -> Optional[str]:
        if not os.path.exists(html_path):
            self.logger.error(f"HTML-файл не найден: {html_path}")
            return None
        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(html_path))[0]
        output_html = os.path.join(output_dir, f"{base_name}_typograf.html")
        script_path = os.path.abspath(os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "tools", "typografize.js"))
        if not os.path.exists(script_path):
            self.logger.error(f"Скрипт typografize.js не найден: {script_path}")
            return None
        cmd = ["node", script_path, html_path, output_html]
        self.logger.info(f"Запуск typografize.js через: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                self.logger.error(f"typografize.js завершился с ошибкой: {result.stderr}")
                return None
            self.logger.info(f"typografize.js успешно завершён. Stdout: {result.stdout}")
        except Exception as e:
            self.logger.error(f"Ошибка при запуске typografize.js: {e}")
            return None
        if not os.path.exists(output_html):
            self.logger.error(f"Типографированный HTML не найден: {output_html}")
            return None
        # Сохраняем SUCCESS.json
        status_path = os.path.join(output_dir, "TypografProcessorModule_SUCCESS.json")
        status = {"status": "success", "output_file": output_html}
        try:
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.logger.warning(f"Не удалось сохранить статус-файл: {e}")
        return output_html

# Для возможности тестирования модуля отдельно (необязательно)
if __name__ == '__main__':
    # Пример использования (потребует создания тестовых файлов и структуры)
    test_correlation_id = "typograf-test-001"
    
    # Настройка корневого логгера для вывода в консоль, если setup_logging не делает этого глобально
    # logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Создание временных директорий для теста
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(current_dir, "..", "..")) # /piskulin/
    
    # Убедимся, что путь к tools/typografize.js корректен относительно project_root
    # Для этого теста, мы должны быть уверены, что tools/typografize.js существует
    # и Node.js установлен и доступен.

    test_input_dir = os.path.join(project_root, "workspace", "input_for_typograf_test")
    test_module_workspace = os.path.join(project_root, "workspace", "processing", test_correlation_id, "TypografProcessorModule")
    
    os.makedirs(test_input_dir, exist_ok=True)
    os.makedirs(test_module_workspace, exist_ok=True)

    sample_html_path = os.path.join(test_input_dir, "sample.html")
    with open(sample_html_path, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html>
<html lang=\"ru\">
<head><title>Test</title></head>
<body><p>Это \"тестовый\" текст - для проверки.</p></body>
</html>""")

    # Предполагается, что tools/typografize.js существует и работоспособен
    # Также предполагается, что src/utils/logger_setup.py и src/utils/exceptions.py существуют

    if not os.path.exists(os.path.join(project_root, "tools", "typografize.js")):
        print(f"Тест не может быть выполнен: tools/typografize.js не найден в {os.path.join(project_root, 'tools')}")
    elif not os.path.exists(os.path.join(project_root, "src", "utils", "logger_setup.py")) or \
         not os.path.exists(os.path.join(project_root, "src", "utils", "exceptions.py")):
        print(f"Тест не может быть выполнен: отсутствуют src/utils/logger_setup.py или src/utils/exceptions.py")
    else:
        print(f"Запуск тестового прогона TypografProcessorModule...")
        print(f"Входной файл: {sample_html_path}")
        print(f"Рабочая директория модуля: {test_module_workspace}")
        
        # Установим путь, чтобы относительные импорты работали при прямом запуске
        sys.path.insert(0, project_root)
        from src.utils.exceptions import TypografProcessingError # Повторный импорт после sys.path
        from src.utils.logger_setup import setup_logging

        typograf_module = TypografProcessorModule(test_correlation_id)
        try:
            output_path = typograf_module.run(sample_html_path, test_module_workspace)
            print(f"Тестовый прогон завершен. Результат в: {output_path}")
            # Можно добавить чтение и вывод содержимого output_path для проверки
        except TypografProcessingError as e:
            print(f"Ошибка в тестовом прогоне: {e}")
        except ImportError as e:
            print(f"Ошибка импорта при тестовом прогоне: {e}. Убедитесь, что запускаете из корневой директории проекта или настройте PYTHONPATH.") 