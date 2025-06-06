import os
import json
import logging
import subprocess
from typing import Optional

class HtmlToDocxProcessorModule:
    """
    Модуль для конвертации HTML в DOCX с помощью pandoc.
    """
    def __init__(self, correlation_id: str):
        self.correlation_id = correlation_id
        self.logger = logging.getLogger(f"HtmlToDocxProcessorModule.{correlation_id}")

    def run(self, html_path: str, output_dir: str, basename: str = None) -> Optional[str]:
        if not os.path.exists(html_path):
            self.logger.error(f"HTML-файл не найден: {html_path}")
            return None
        os.makedirs(output_dir, exist_ok=True)
        if basename is None:
            base_name = os.path.splitext(os.path.basename(html_path))[0]
        else:
            base_name = basename
        output_docx = os.path.join(output_dir, f"{base_name}_final.docx")
        cmd = ["pandoc", html_path, "-o", output_docx, "--metadata", "title="]
        self.logger.info(f"Запуск pandoc: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode != 0:
                self.logger.error(f"pandoc завершился с ошибкой: {result.stderr}")
                return None
            self.logger.info(f"pandoc успешно завершён. Stdout: {result.stdout}")
        except Exception as e:
            self.logger.error(f"Ошибка при запуске pandoc: {e}")
            return None
        if not os.path.exists(output_docx):
            self.logger.error(f"DOCX-файл не найден: {output_docx}")
            return None
        # Сохраняем SUCCESS.json
        status_path = os.path.join(output_dir, "HtmlToDocxProcessorModule_SUCCESS.json")
        status = {"status": "success", "output_file": output_docx}
        try:
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status, f, ensure_ascii=False, indent=4)
        except Exception as e:
            self.logger.warning(f"Не удалось сохранить статус-файл: {e}")
        return output_docx 