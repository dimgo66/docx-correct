#!/usr/bin/env python3
"""
@file: run_pipeline.py
@description: Единый пайплайн: DOCX → HTML → типографика → LanguageTool → автокоррекция (Qwen) → DOCX. На вход — DOCX, на выход — финальный DOCX.
@dependencies: src/pipeline/docx_to_html_converter.py, src/pipeline/typograf_processor_module.py, src/pipeline/languagetool_processor_module.py, src/pipeline/autocorrect_processor_module.py, src/pipeline/html_to_docx_processor_module.py
@created: 2024-07-31
"""
import sys
import os
import uuid
from src.pipeline.docx_to_html_converter import convert_docx_to_html
from src.pipeline.typograf_processor_module import TypografProcessorModule
from src.pipeline.languagetool_processor_module import LanguageToolProcessorModule
from src.pipeline.autocorrect_processor_module import AutocorrectProcessorModule
from src.pipeline.html_to_docx_processor_module import HtmlToDocxProcessorModule

def main():
    if len(sys.argv) != 3:
        print("Использование: python run_pipeline.py input.docx output.docx")
        sys.exit(1)
    input_docx = sys.argv[1]
    output_docx = sys.argv[2]
    # Извлекаем базовое имя из пути выходного файла
    output_basename = os.path.splitext(os.path.basename(output_docx))[0]
    correlation_id = str(uuid.uuid4())
    temp_dir = os.path.join("workspace", "processing", correlation_id)
    os.makedirs(temp_dir, exist_ok=True)
    # DOCX → HTML
    html_path = convert_docx_to_html(input_docx, os.path.join(temp_dir, "stage1.html"), temp_dir, correlation_id)
    if not html_path:
        print("Ошибка на этапе конвертации DOCX → HTML")
        sys.exit(2)
    # Типографика
    typograf = TypografProcessorModule(correlation_id)
    typograf_html_path = typograf.run(html_path, temp_dir)
    if not typograf_html_path:
        print("Ошибка на этапе типографики")
        sys.exit(3)
    # LanguageTool
    lt = LanguageToolProcessorModule(correlation_id)
    json_report_path = lt.run(typograf_html_path, temp_dir)
    if not json_report_path or not os.path.exists(json_report_path):
        print("Ошибка на этапе LanguageTool")
        sys.exit(4)
    # Автокоррекция
    autocorr = AutocorrectProcessorModule(correlation_id)
    corrected_html_path = autocorr.run(typograf_html_path, json_report_path, temp_dir)
    if not corrected_html_path or not os.path.exists(corrected_html_path):
        print("Ошибка на этапе автокоррекции")
        sys.exit(5)
    # HTML → DOCX
    html2docx = HtmlToDocxProcessorModule(correlation_id)
    # Передаем базовое имя в модуль конвертации
    final_docx_path = html2docx.run(corrected_html_path, temp_dir, basename=output_basename)
    if not final_docx_path or not os.path.exists(final_docx_path):
        print("Ошибка на этапе конвертации в DOCX")
        sys.exit(6)
    # Копируем результат в output_docx
    with open(final_docx_path, "rb") as fin, open(output_docx, "wb") as fout:
        fout.write(fin.read())
    print(f"[OK] Финальный DOCX сохранён: {output_docx}")

if __name__ == "__main__":
    main() 