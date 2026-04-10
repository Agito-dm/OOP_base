# База ООП

Проект по теме ООП: банковские счета, банк, транзакции, аудит и риск-анализ, демонстрация, отчёты и визуализация.

## Содержание (Day 1–7)

- **Day 1** — Базовая модель банковских счетов  
- **Day 2** — Продвинутые типы банковских счетов  
- **Day 3** — Система Bank (клиенты, банк, безопасность)  
- **Day 4** — Система транзакций (транзакции, очередь, процессор)  
- **Day 5** — Аудит и риск-анализ (AuditLog, RiskAnalyzer, блокировка опасных операций)  
- **Day 6** — Демонстрационная программа (инициализация, симуляция транзакций, логирование, отчёты)  
- **Day 7** — Система отчётности и визуализации (ReportBuilder: JSON/CSV + графики matplotlib)

## Установка

### Windows (PowerShell)
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Linux / macOS
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
## Проверка решения в виртуальном окружении (тесты)
```bash
python -m pytest -q
```
## Запуск демонстрации (Day 6) + отчёты и графики (Day 7)
```bash
python -m src.day6.demo
```

После запуска демо будут созданы файлы (игнорируются git):

```
docs/audit_day6.jsonl — аудит-лог
docs/reports/ — отчёты и графики (json/csv/png)
```

### Графики находятся в docs/reports/chart_*.png.

## ReportBuilder (Day 7)

Пример генерации отчётов, экспорта и сохранения графиков:

```
tests/day7/test_day7_reports.py
```
