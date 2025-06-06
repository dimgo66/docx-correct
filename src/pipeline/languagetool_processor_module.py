import os
import logging
import subprocess
from typing import Optional
import tempfile
from bs4 import BeautifulSoup
import sys
import json

class LanguageToolProcessorModule:
    """
    Модуль для запуска проверки HTML-файла с помощью LanguageTool и интеграции с ИИ.
    Вызывает tools/check_text_languagetool.py как подпроцесс.
    """
    def __init__(self, correlation_id: str):
        self.correlation_id = correlation_id
        self.logger = logging.getLogger(f"LanguageToolProcessorModule.{correlation_id}")

    def run(self, html_path: str, output_dir: str) -> Optional[str]:
        """
        Запускает проверку HTML-файла, возвращает путь к JSON-отчету или None.
        """
        if not os.path.exists(html_path):
            self.logger.error(f"HTML-файл не найден: {html_path}")
            return None
        # === Запуск check_text_languagetool.py как подпроцесса для гарантии lang="ru" ===
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')) # Получаем путь к корню проекта
        check_script_path = os.path.join(project_root, 'tools', 'check_text_languagetool.py')
        python_interpreter = os.path.join(project_root, '.venv', 'bin', 'python3')

        try:
            subprocess.run([
                python_interpreter,
                check_script_path,
                html_path
            ], check=True, capture_output=True, text=True)
            self.logger.info(f"Successfully ran check_text_languagetool.py for {html_path}")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"Error running check_text_languagetool.py for {html_path}: {e.stderr}")
            return None # Если скрипт с лангуатулом завершился с ошибкой, дальше нет смысла идти
        # === Конец запуска подпроцесса ===

        os.makedirs(output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(html_path))[0]
        output_report_path = os.path.join(output_dir, f"{base_name}_languagetool_report.json")
        # --- Извлекаем plain text из HTML ---
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.body.get_text(separator='\n', strip=True) if soup.body else soup.get_text(separator='\n', strip=True)
        with tempfile.NamedTemporaryFile('w+', delete=False, encoding='utf-8', suffix='.txt') as tmp_txt:
            tmp_txt.write(text)
            tmp_txt_path = tmp_txt.name
        # --- Логируем содержимое временного .txt-файла (первые 10 строк) ---
        try:
            with open(tmp_txt_path, 'r', encoding='utf-8') as f_txt:
                lines = f_txt.readlines()
                preview = ''.join(lines[:10])
                text_full = ''.join(lines)
                debug_info = (
                    f"\n===LANGTOOL_DEBUG===\n"
                    f"correlation_id: {self.correlation_id}\n"
                    f"tmp_txt_path: {tmp_txt_path}\n"
                    f"Кодировка: utf-8\n"
                    f"Длина текста (символов): {len(text_full)}\n"
                    f"Первые 10 строк:\n{preview}"
                    f"\n===END_LANGTOOL_DEBUG===\n"
                )
                print(debug_info, file=sys.stderr)
                print(debug_info)
                self.logger.info(f"[DEBUG] Содержимое временного .txt-файла для LT (первые 10 строк):\n{preview}")
                # Дублируем в отдельный лог-файл
                logs_dir = os.path.join('workspace', 'logs')
                os.makedirs(logs_dir, exist_ok=True)
                debug_log_path = os.path.join(logs_dir, 'langtool_debug.log')
                with open(debug_log_path, 'a', encoding='utf-8') as debug_log:
                    debug_log.write(debug_info)
        except Exception as e:
            self.logger.warning(f"Не удалось прочитать временный .txt-файл для логирования: {e}")
        # --- Запускаем LanguageTool на plain text ---
        command = [
            "java",
            "-Xmx256m",
            "-jar",
            "LanguageTool-6.6/languagetool-commandline.jar",
            "-l", "ru",
            "-c", "utf-8",
            "--json",
            tmp_txt_path
        ]
        self.logger.info(f"[LT_DEBUG] Готовимся к запуску LanguageTool. Команда: {' '.join(command)}")
        print(f"[LT_DEBUG] Готовимся к запуску LanguageTool. Команда: {' '.join(command)}", file=sys.stderr)

        try:
            self.logger.info("[LT_DEBUG] Перед subprocess.Popen()")
            print("[LT_DEBUG] Перед subprocess.Popen()", file=sys.stderr)
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.logger.info("[LT_DEBUG] После subprocess.Popen(), перед proc.communicate()")
            print("[LT_DEBUG] После subprocess.Popen(), перед proc.communicate()", file=sys.stderr)
            
            stdout, stderr = proc.communicate() # Может быть длительным и потреблять память
            
            self.logger.info("[LT_DEBUG] После proc.communicate()")
            print("[LT_DEBUG] После proc.communicate()", file=sys.stderr)

            stdout_decoded = stdout.decode('utf-8', errors='ignore').strip() if stdout else ''
            stderr_decoded = stderr.decode('utf-8', errors='ignore').strip() if stderr else ''

            self.logger.info(f"LanguageTool process return code: {proc.returncode}")

            if stdout_decoded:
                self.logger.info(f"LanguageTool process stdout (first 500 chars):\n{stdout_decoded[:500]}")
            else:
                self.logger.info("LanguageTool process stdout was empty.")

            if stderr_decoded:
                self.logger.info(f"LanguageTool process full stderr:\n{stderr_decoded}")
            else:
                self.logger.info("LanguageTool process stderr was empty.")

            # --- Более строгая проверка результата LanguageTool ---
            if proc.returncode != 0:
                self.logger.error(f"LanguageTool exited with non-zero code {proc.returncode}. Full stderr: {stderr_decoded}. Full stdout (first 500): {stdout_decoded[:500]}")
                return None

            if not stdout_decoded:
                self.logger.error(f"LanguageTool exited with 0, but stdout was empty. Stderr: {stderr_decoded}")
                return None

            try:
                json_output = json.loads(stdout_decoded)
            except json.JSONDecodeError as je:
                self.logger.error(f"LanguageTool output (stdout) was not valid JSON despite return code 0. JSONDecodeError: {je}. Stdout (first 500): {stdout_decoded[:500]}...")
                return None
            
            # Если дошли сюда, значит returncode == 0, stdout не пуст и является валидным JSON
            with open(output_report_path, "w", encoding="utf-8") as fout:
                json.dump(json_output, fout, ensure_ascii=False, indent=2)
            self.logger.info(f"LanguageTool JSON output successfully parsed and written to {output_report_path}")
            
            # Проверка stderr на наличие только некритичных сообщений (если они есть и returncode == 0)
            non_critical_msgs = [
                'Expected text language: Russian',
                'Working on',
                'Picked up _JAVA_OPTIONS:'
            ]
            def is_critical_stderr(line_content):
                return not any(msg in line_content for msg in non_critical_msgs)

            if stderr_decoded:
                stderr_lines_for_check = [line.strip() for line in stderr_decoded.splitlines() if line.strip()]
                critical_stderr_detected = any(is_critical_stderr(line) for line in stderr_lines_for_check)
                if critical_stderr_detected:
                    self.logger.warning(f"LanguageTool exited with 0 and valid JSON, but had unexpected messages in stderr: {stderr_decoded}")
                    # Решение о том, считать ли это ошибкой пайплайна, может быть здесь. 
                    # Пока что, если JSON есть, считаем успехом для этого модуля, но логируем предупреждение.
                elif stderr_lines_for_check: # Есть только некритичные
                    self.logger.info(f"LanguageTool non-critical stderr messages: {stderr_decoded}")
            # --- Конец строгой проверки ---

        except Exception as e:
            self.logger.error(f"Ошибка при запуске LanguageTool: {e}")
            return None
        finally:
            try:
                os.remove(tmp_txt_path)
            except Exception:
                pass
        # Сохраняем служебный SUCCESS.json
        success_path = os.path.join(output_dir, "LanguageToolProcessorModule_SUCCESS.json")
        with open(success_path, "w", encoding="utf-8") as f:
            json.dump({"output_report_path": output_report_path, "status": "success"}, f, ensure_ascii=False, indent=2)
        return output_report_path 