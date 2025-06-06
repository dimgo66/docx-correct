# /**
#  * @file: exceptions.py
#  * @description: Пользовательские исключения для проекта обработки текста.
#  * @dependencies: None
#  * @created: 2024-07-30 
#  */

class TextProcessingError(Exception):
    """Базовый класс для всех ошибок проекта."""
    def __init__(self, message, original_exception=None, error_code=None, **kwargs):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception
        self.error_code = error_code
        self.details = kwargs

    def __str__(self):
        return f"{self.__class__.__name__}: {self.message}"

# Общие исключения
class ConfigurationError(TextProcessingError):
    """Ошибка в конфигурации модуля."""
    pass

class FileOperationError(TextProcessingError):
    """Общая ошибка при работе с файлами."""
    pass

class InputFileNotFoundError(FileOperationError):
    """Не найден входной файл для модуля."""
    pass

class PermissionsError(FileOperationError):
    """Ошибка прав доступа к файлу/директории."""
    pass

class InvalidFileFormatError(TextProcessingError):
    """Некорректный формат входного файла."""
    pass

# Специфичные для модулей исключения
class PandocConversionError(TextProcessingError):
    """Ошибка при конвертации (DOCX <-> HTML) с помощью Pandoc."""
    pass

class LanguageToolConnectionError(TextProcessingError):
    """Ошибка соединения с сервером LanguageTool."""
    pass

class LanguageToolProcessingError(TextProcessingError):
    """Ошибка во время обработки текста LanguageTool."""
    pass

class AIModelAPIError(TextProcessingError):
    """Ошибка при взаимодействии с API ИИ-модели."""
    pass

class RateLimitError(AIModelAPIError):
    """Превышен лимит запросов к API ИИ-модели."""
    pass

class AIModelProcessingError(TextProcessingError):
    """Ошибка во время обработки текста самой ИИ-моделью."""
    pass

class TypografError(TextProcessingError):
    """Ошибка при работе Typograf."""
    pass

class DataValidationError(TextProcessingError):
    """Ошибка валидации данных."""
    pass 

class BaseProjectError(Exception):
    """Базовый класс для всех исключений проекта."""
    pass

class FileProcessingError(BaseProjectError):
    """Ошибка при обработке файла."""
    pass

class DocxToHtmlConversionError(FileProcessingError):
    """Ошибка при конвертации DOCX в HTML."""
    pass

class LanguageToolError(FileProcessingError):
    """Ошибка при работе с LanguageTool."""
    pass

class AICorrectionError(FileProcessingError):
    """Ошибка при получении или применении ИИ-коррекций."""
    pass

class AutocorrectHtmlError(FileProcessingError):
    """Ошибка при автоматическом применении исправлений к HTML."""
    pass

class TypografProcessingError(FileProcessingError):
    """Ошибка при обработке текста типографом."""
    pass

class HtmlToDocxConversionError(FileProcessingError):
    """Ошибка при конвертации HTML в DOCX."""
    pass

class PipelineConfigError(BaseProjectError):
    """Ошибка конфигурации пайплайна."""
    pass 