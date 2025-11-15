# QMS Cherga - Покращення системи

Цей документ описує покращення, внесені в систему QMS Cherga.

## 📋 Зміст

1. [Rate Limiting](#rate-limiting)
2. [Database Indexes](#database-indexes)
3. [Race Condition Fix](#race-condition-fix)
4. [Error Boundaries](#error-boundaries)
5. [Structured Logging](#structured-logging)
6. [API Refactoring](#api-refactoring)
7. [Caching](#caching)
8. [Testing](#testing)

---

## 🚦 Rate Limiting

**Проблема:** Публічні API endpoints були вразливі до DDoS атак та зловживань.

**Рішення:** Додано rate limiting для всіх публічних endpoints:

- **Kiosk API**: 30-60 запитів на хвилину
- **Display Board API**: 120 запитів на хвилину (часті оновлення)
- **Appointments API**: 20-30 запитів на хвилину

**Реалізація:**
```python
from qms_cherga.utils.rate_limiter import rate_limit

@frappe.whitelist(allow_guest=True)
@rate_limit(max_requests=30, window_seconds=60)
def create_live_queue_ticket(service, office, visitor_phone=None):
    # ...
```

**Файл:** `qms_cherga/utils/rate_limiter.py`

---

## 📊 Database Indexes

**Проблема:** Повільні запити при великій кількості талонів.

**Рішення:** Додано оптимізовані індекси:

```sql
-- Для пошуку талонів в черзі
CREATE INDEX idx_qms_ticket_office_status_creation
ON `tabQMS Ticket` (office, status, creation);

-- Для пошуку талонів оператора
CREATE INDEX idx_qms_ticket_operator_status
ON `tabQMS Ticket` (operator, status);

-- Для записів на прийом
CREATE INDEX idx_qms_ticket_appointment_datetime
ON `tabQMS Ticket` (appointment_datetime);

-- Для статистики
CREATE INDEX idx_qms_ticket_completion_time
ON `tabQMS Ticket` (completion_time);

-- Для atomic counter
CREATE INDEX idx_qms_daily_counter_office_date
ON `tabQMS Daily Counter` (office, date);
```

**Міграція:** `qms_cherga/patches/add_performance_indexes.py`

---

## 🔒 Race Condition Fix

**Проблема:** При одночасному виклику `call_next_visitor` двома операторами, один і той же талон міг бути призначений обом.

**Рішення:** Використання pessimistic locking (SELECT FOR UPDATE):

```python
# SQL запит з FOR UPDATE для блокування рядка
waiting_tickets_query = """
    SELECT name
    FROM `tabQMS Ticket`
    WHERE office = %(office)s
    AND status = 'Waiting'
    AND service IN %(skills)s
    ORDER BY priority DESC, creation ASC
    LIMIT 1
    FOR UPDATE
"""

frappe.db.begin()
waiting_tickets = frappe.db.sql(waiting_tickets_query, ...)
# ... оновлення талону ...
frappe.db.commit()
```

**Файл:** `qms_cherga/api/operator.py:call_next_visitor()`

---

## 🛡️ Error Boundaries

**Проблема:** Помилки у Vue компонентах ламали весь інтерфейс.

**Рішення:** Додано ErrorBoundary компонент для всіх Vue застосунків:

```vue
<template>
  <ErrorBoundary>
    <KioskView />
  </ErrorBoundary>
</template>
```

**Функції:**
- Перехоплення помилок на рівні компонента
- Відображення user-friendly повідомлення
- Логування помилок
- Можливість оновлення сторінки або повторної спроби

**Файли:**
- `frontend/src/components/ErrorBoundary.vue`
- `frontend/src/AppKiosk.vue`
- `frontend/src/AppDisplayBoard.vue`
- `frontend/src/AppOperatorDashboard.vue`

---

## 📝 Structured Logging

**Проблема:** Складно аналізувати логи та відстежувати події.

**Рішення:** Structured logging з JSON форматом:

```python
from qms_cherga.utils.logger import log_api_call, log_ticket_event, log_error

# Логування API викликів
log_api_call("create_live_queue_ticket", service=service, office=office)

# Логування подій талонів
log_ticket_event("created", ticket_name, ticket_number, office=office)

# Логування помилок
log_error("ticket_creation_error", str(e), service=service)
```

**Формат логу:**
```json
{
  "timestamp": "2025-11-15T10:30:00",
  "level": "INFO",
  "message": "API call: create_live_queue_ticket",
  "data": {
    "event_type": "api_call",
    "function": "create_live_queue_ticket",
    "service": "SRV-001",
    "office": "OFFICE-001"
  }
}
```

**Файл:** `qms_cherga/utils/logger.py`

---

## 🔄 API Refactoring

**Проблема:** Монолітний `api.py` файл (1184 рядки) - важко підтримувати.

**Рішення:** Модульна структура:

```
qms_cherga/api/
├── __init__.py           # Експорт всіх функцій
├── common.py             # Спільні утиліти
├── kiosk.py              # API кіоску
├── display.py            # API display board
├── operator.py           # API оператора
└── appointments.py       # API записів
```

**Зворотна сумісність:**
`qms_cherga/api.py` імпортує всі функції з нових модулів, тому старий код продовжує працювати.

---

## ⚡ Caching

**Проблема:** Повторні запити за однаковими даними навантажують БД.

**Рішення:** Redis/memcached кешування:

```python
from qms_cherga.utils.cache import cached

@cached(ttl=3600, key_prefix="office_info")
def get_office_info_cached(office_id):
    return frappe.get_doc("QMS Office", office_id)
```

**Кешовані дані:**
- **Office Info**: TTL 1 година
- **Kiosk Services**: TTL 10 хвилин

**Інвалідація кешу:**
Автоматична при оновленні DocTypes через хуки:

```python
doc_events = {
    "QMS Office": {
        "on_update": "qms_cherga.utils.hooks_handlers.on_office_update",
    },
    "QMS Service": {
        "on_update": "qms_cherga.utils.hooks_handlers.on_service_update",
    }
}
```

**Файли:**
- `qms_cherga/utils/cache.py`
- `qms_cherga/utils/hooks_handlers.py`
- `qms_cherga/hooks.py`

---

## 🧪 Testing

**Додано comprehensive test suite:**

### Unit Tests:
- `test_api_kiosk.py` - тестування Kiosk API
- `test_api_operator.py` - тестування Operator API
- `test_cache.py` - тестування кешування
- `test_rate_limiter.py` - тестування rate limiting

### Integration Tests:
- `test_ticket_lifecycle.py` - повний lifecycle талону:
  - Створення → Виклик → Обслуговування → Завершення
  - Postpone/Recall
  - No-Show

**Запуск тестів:**
```bash
# Всі тести
bench run-tests --app qms_cherga

# Конкретний тест
bench run-tests --app qms_cherga --module qms_cherga.tests.test_ticket_lifecycle
```

---

## 📈 Покращення продуктивності

### Очікувані результати:

| Метрика | До | Після | Покращення |
|---------|-----|-------|------------|
| Час відповіді API (avg) | 200ms | 50ms | **4x швидше** |
| Запити до БД | 15-20 | 3-5 | **4x менше** |
| Cache hit rate | 0% | 70-80% | **нове** |
| Concurrent call_next_visitor | ❌ race condition | ✅ безпечно | **виправлено** |

---

## 🔧 Міграція

### Для існуючих інсталяцій:

1. **Оновити код:**
   ```bash
   cd ~/frappe-bench/apps/qms_cherga
   git pull origin <branch>
   ```

2. **Застосувати міграції:**
   ```bash
   bench --site <your-site> migrate
   ```

3. **Збілдити фронтенд:**
   ```bash
   cd apps/qms_cherga/frontend
   npm install
   npm run build
   ```

4. **Перезапустити:**
   ```bash
   bench restart
   ```

---

## 📚 Документація

### Нові модулі:

- **Utils:**
  - `utils/rate_limiter.py` - Rate limiting decorator
  - `utils/logger.py` - Structured logging
  - `utils/cache.py` - Caching utilities
  - `utils/hooks_handlers.py` - Event handlers

- **API:**
  - `api/common.py` - Common utilities
  - `api/kiosk.py` - Kiosk endpoints
  - `api/display.py` - Display Board endpoints
  - `api/operator.py` - Operator endpoints
  - `api/appointments.py` - Appointments endpoints

### Конфігурація:

- `hooks.py` - оновлено з doc_events
- `patches/add_performance_indexes.py` - міграція індексів

---

## ⚠️ Breaking Changes

**Немає!** Всі зміни зворотно сумісні.

Старий імпорт продовжує працювати:
```python
from qms_cherga.api import get_office_info  # ✅ OK
```

---

## 🎯 Наступні кроки

1. ✅ **Моніторинг:** Налаштувати Prometheus/Grafana для метрик
2. ✅ **CI/CD:** GitHub Actions для автотестів
3. ✅ **Documentation:** API documentation (Swagger/OpenAPI)
4. 📱 **Mobile App:** React Native/Flutter app
5. 📧 **Notifications:** SMS/Email integration

---

## 👥 Автор

Покращення розроблено з використанням:
- **Python 3.10+**
- **Frappe Framework 15.x**
- **Vue.js 3.5**
- **MariaDB**
- **Redis**

---

## 📄 Ліцензія

MIT License - як і основний проект.
