/**
 * @file: parse-lt-report.js
 * @description: Парсер отчёта LanguageTool (lt-report.txt) с выводом ошибок в Markdown и JSON
 * @dependencies: lt-report.txt, index.html
 * @created: 2024-07-05
 */

const fs = require('fs');

const args = process.argv.slice(2);
const reportFile = args[0] || 'lt-report.txt';
const htmlFile = args[1] || 'index.html';
const mdOutFile = reportFile.replace(/\.txt$/, '.md');
const jsonOutFile = reportFile.replace(/\.txt$/, '.json');

const report = fs.readFileSync(reportFile, 'utf8');
const errorBlocks = report.split(/\n(?=\d+\.\) Line )/).filter(Boolean);

const errors = [];
let md = `# LanguageTool Report\n\nИсходный файл: ${htmlFile}\n\n`;

for (const block of errorBlocks) {
    const lineMatch = block.match(/Line (\d+), column (\d+), Rule ID: ([^\s]+).*?\nMessage: (.*?)\n(?:Suggestion: (.*?)\n)?([\s\S]*)/);
    if (lineMatch) {
        const [, line, column, ruleId, message, suggestion = '', context = ''] = lineMatch;
        errors.push({
            line: Number(line),
            column: Number(column),
            ruleId,
            message,
            suggestion: suggestion.trim(),
            context: context.trim()
        });
        md += `- **Строка:** ${line}, **Позиция:** ${column}\n  - **Тип:** ${ruleId}\n  - **Сообщение:** ${message}\n`;
        if (suggestion) md += `  - **Вариант исправления:** ${suggestion}\n`;
        if (context) md += `  - **Контекст:**\n\n    \`${context.trim().replace(/\n/g, '\n    ')}\`\n`;
        md += '\n';
    }
}

fs.writeFileSync(mdOutFile, md, 'utf8');
fs.writeFileSync(jsonOutFile, JSON.stringify(errors, null, 2), 'utf8');

console.log(`Готово!\nMarkdown: ${mdOutFile}\nJSON: ${jsonOutFile}\nОшибок найдено: ${errors.length}`); 