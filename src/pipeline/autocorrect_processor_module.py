import os
import json
import logging
import shutil
import re
from typing import Optional
import openai

class AutocorrectProcessorModule:
    """
    Модуль для автоматического применения исправлений из отчёта LanguageTool к HTML с подтверждением через LLM OpenRouter (Qwen).
    """
    # --- Константы и настройки ---
    AUTOFIX_CANDIDATE_RULE_IDS = {
        "MORFOLOGIK_RULE_RU_RU",
        "COMMA_DEFIS",
        "NO_KAK_POPALO",
    }
    EXCLUDE_WORD_CATEGORIES = {
        "имена_собственные": [r"[А-Я][а-я]+"],
        "термины_хутор": [r"хут\.", r"хутор\s+[А-Я][а-я]+"],
        "диалектизмы": [r"угорь", r"трошки", r"гутарил"],
        "специфические_слова": [r"сказилось", r"бушковать", r"чиниться"]
    }
    MODEL_NAME = "qwen/qwen3-235b-a22b:free"
    # OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY") # Будет использоваться в confirm_fix_with_openrouter_qwen
    # YOUR_SITE_URL = os.environ.get("YOUR_SITE_URL", "http://localhost:8000") # Будет использоваться в confirm_fix_with_openrouter_qwen
    # YOUR_APP_NAME = os.environ.get("YOUR_APP_NAME", "piskulin-processor") # Будет использоваться в confirm_fix_with_openrouter_qwen


    def __init__(self, correlation_id: str):
        self.correlation_id = correlation_id
        self.logger = logging.getLogger(f"AutocorrectProcessorModule.{self.correlation_id}")
        # Инициализация клиента OpenRouter будет здесь или в методе confirm_fix_with_openrouter_qwen
        self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
        self.your_site_url = os.environ.get("YOUR_SITE_URL", "http://localhost:8000")
        self.your_app_name = os.environ.get("YOUR_APP_NAME", "piskulin-processor")

        if not self.openrouter_api_key:
            self.logger.warning("OPENROUTER_API_KEY не найдена в переменных окружения. Автокоррекция LLM не будет работать.")
            # Можно установить фиктивный ключ для локальной разработки без LLM, если это нужно
            # self.openrouter_api_key = "фиктивный-ключ-для-локальной-разработки" 
        
        self.client = None
        if self.openrouter_api_key:
            try:
                self.client = openai.OpenAI(
                    base_url="https://openrouter.ai/api/v1",
                    api_key=self.openrouter_api_key,
                )
                self.logger.info("Клиент OpenRouter успешно инициализирован.")
            except Exception as e:
                self.logger.error(f"Ошибка инициализации клиента OpenRouter: {e}")
                self.client = None


    def should_exclude_match(self, error_segment, context):
        for category, patterns in self.EXCLUDE_WORD_CATEGORIES.items():
            for pattern in patterns:
                if re.search(pattern, error_segment) or re.search(pattern, context, re.IGNORECASE):
                    return True, category
        return False, None

    def generate_llm_prompt(self, match_info, html_content):
        original_text = match_info.get('context', {}).get('text', '')
        global_offset = match_info.get('offset', 0)
        context_offset = match_info.get('context', {}).get('offset', 0)
        length = match_info.get('context', {}).get('length', 0)
        error_segment = original_text[context_offset:context_offset + length]
        # Расширенный контекст
        context_size = 500
        start = max(0, global_offset - context_size)
        end = min(len(html_content), global_offset + context_size)
        extended_context = html_content[start:end]
        prompt = (
            f"Обнаружена потенциальная ошибка в тексте:\n\n"
            f"Расширенный контекст:\n\"\"\"{extended_context}\"\"\"\n\n"
            f"Ошибка (выделенный текст): \"{error_segment}\"\n"
            f"Сообщение LanguageTool: {match_info.get('message', 'N/A')}\n"
            f"Правило LanguageTool ID: {match_info.get('rule', {}).get('id', 'N/A')}\n"
            f"Предлагаемая LanguageTool замена: \"{match_info.get('replacements', [{}])[0].get('value', 'N/A')}\"\n\n"
            f"ЗАДАЧА: Оцените, является ли предлагаемое исправление корректным и уместным в данном контексте.\n"
            f"ОТВЕТ: Ответьте ОДНИМ СЛОВОМ: \"ДА\" (если исправление корректно) или \"НЕТ\" (если исправление некорректно или сомнительно)."
        )
        return prompt

    def confirm_fix_with_openrouter_qwen(self, prompt: str) -> bool:
        """
        Использует OpenRouter (модель Qwen) для подтверждения исправления.
        Возвращает True, если LLM считает исправление корректным (ответ начинается с 'ДА').
        """
        if not self.client:
            self.logger.warning("Клиент OpenRouter не инициализирован. Пропускаю подтверждение LLM, исправление будет отклонено.")
            return False

        self.logger.info(f"Отправка запроса к OpenRouter модели {self.MODEL_NAME} для подтверждения исправления.")
        # print(f"\n--- PROMPT ДЛЯ OPENROUTER QWEN ---\n{prompt}\n--- КОНЕЦ ПРОМПТА ---\n") # Можно раскомментировать для отладки

        try:
            completion = self.client.chat.completions.create(
                extra_headers={ # Необходимые заголовки для OpenRouter
                    "HTTP-Referer": self.your_site_url, 
                    "X-Title": self.your_app_name,
                },
                model=self.MODEL_NAME,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=10, # Ожидаем короткий ответ "ДА" или "НЕТ"
                temperature=0.1, # Низкая температура для детерминированного ответа
            )
            response_text = completion.choices[0].message.content.strip().upper()
            self.logger.info(f"Ответ от OpenRouter ({self.MODEL_NAME}): {response_text}")
            # print(f"ОТВЕТ OPENROUTER QWEN: {response_text}\n") # Можно раскомментировать для отладки
            return response_text.startswith("ДА")
        except Exception as e:
            self.logger.error(f"Ошибка при обращении к OpenRouter API: {e}")
            return False # В случае ошибки считаем, что исправление не подтверждено

    def run(self, html_path: str, json_report_path: str, output_dir: str) -> Optional[str]:
        if not os.path.exists(html_path) or not os.path.exists(json_report_path):
            self.logger.error(f"HTML или JSON-отчёт не найден: {html_path}, {json_report_path}")
            return None
        os.makedirs(output_dir, exist_ok=True)
        with open(json_report_path, 'r', encoding='utf-8') as f:
            report_data = json.load(f)
        with open(html_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
        backup_path = os.path.join(output_dir, os.path.basename(html_path) + ".bak")
        shutil.copy2(html_path, backup_path)
        log_path = os.path.join(output_dir, os.path.basename(html_path) + ".rejected_fixes.log")
        approved_corrections = []
        rejected_corrections = []
        sorted_matches = sorted(report_data.get('matches', []), key=lambda m: m.get('offset', 0), reverse=True)
        for match in sorted_matches:
            rule_id = match.get('rule', {}).get('id')
            replacements = match.get('replacements', [])
            global_offset = match.get('offset', 0)
            length = match.get('length', 0)
            original = html_content[global_offset:global_offset+length]
            if rule_id in self.AUTOFIX_CANDIDATE_RULE_IDS and len(replacements) == 1:
                replacement = replacements[0].get('value', '')
                exclude_match, exclude_category = self.should_exclude_match(original, html_content[max(0, global_offset-50):global_offset+length+50])
                if exclude_match:
                    rejected_corrections.append({'offset': global_offset, 'length': length, 'replacement': replacement, 'original': original, 'reason': f"Автоматически отклонено (категория: {exclude_category})"})
                    continue
                if ' ' in replacement and ' ' not in original:
                    rejected_corrections.append({'offset': global_offset, 'length': length, 'replacement': replacement, 'original': original, 'reason': "Автоматически отклонено (замена одного слова на несколько)"})
                    continue
                llm_prompt = self.generate_llm_prompt(match, html_content)
                if self.confirm_fix_with_openrouter_qwen(llm_prompt):
                    approved_corrections.append({'offset': global_offset, 'length': length, 'replacement': replacement, 'original': original})
                else:
                    rejected_corrections.append({'offset': global_offset, 'length': length, 'replacement': replacement, 'original': original, 'reason': f"Отклонено LLM ({self.MODEL_NAME}) или ошибка LLM API"})
        content = html_content
        for fix in approved_corrections:
            offset = fix['offset']
            length = fix['length']
            replacement = fix['replacement']
            content = content[:offset] + replacement + content[offset+length:]
        output_html_path = os.path.join(output_dir, os.path.basename(html_path).replace('.html', '_autocorrected.html'))
        with open(output_html_path, 'w', encoding='utf-8') as f:
            f.write(content)
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Отклонённые исправления для {html_path}:\n")
            f.write(f"Всего отклонено: {len(rejected_corrections)}\n\n")
            for i, fix in enumerate(rejected_corrections):
                f.write(f"{i+1}. Оригинал: '{fix['original']}' -> Предложено: '{fix['replacement']}'\n")
                f.write(f"   Причина: {fix.get('reason', 'Не указана')}\n")
                f.write(f"   Смещение: {fix['offset']}, Длина: {fix['length']}\n\n")
        # SUCCESS.json
        status = {
            "module": __name__,
            "correlation_id": self.correlation_id,
            "input_file": html_path,
            "output_file": output_html_path,
            "status": "success",
            "approved": len(approved_corrections),
            "rejected": len(rejected_corrections)
        }
        with open(os.path.join(output_dir, f"AutocorrectProcessorModule_SUCCESS.json"), 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=4)
        self.logger.info(f"Автокоррекция завершена. Исправлено: {len(approved_corrections)}, отклонено: {len(rejected_corrections)}. Результат: {output_html_path}")
        return output_html_path 