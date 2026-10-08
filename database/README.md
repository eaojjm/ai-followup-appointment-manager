# Контракт PostgreSQL

**Полная подтверждённая миграция БД пока отсутствует.** Workflow вызывают серверные SQL-функции, определения которых не были предоставлены вместе с JSON. Не заменяйте их упрощёнными самодельными функциями и не считайте таблицы из старого handoff актуальной схемой.

## Пять таблиц

| Таблица | Роль |
| --- | --- |
| `leads` | Контакт, статус, состояние записи, контекст и версия ожидающего follow-up |
| `appointments` | Временной интервал, статус встречи, связь переноса, claims и timestamps отправок |
| `availability_rules` | Дни недели, начало/конец рабочего времени, длительность слота и timezone |
| `handoff_sessions` | Открытая/закрытая сессия передачи менеджеру |
| `conversation_messages` | История входящих/исходящих сообщений и связь с handoff |

Workflow обращаются, в частности, к `pending_followup_version`, `pending_followup_status`, `booking_state`, `name_confirmed`, `rescheduling_appointment_id`, `reminder_24h_claimed_at`, `outcome_prompt_claimed_at` и timestamps завершения отправок. Наличие таблицы с базовыми полями недостаточно для запуска.

## Внешние SQL-функции

В экспортированных SQL-нодах найдены вызовы:

- `public.get_available_slots(date)`.
- `public.book_appointment(uuid, timestamptz)`.
- `public.start_reschedule(uuid)`.
- `public.reschedule_appointment(uuid, timestamptz)`.
- `public.cancel_appointment(uuid)`.
- `public.set_appointment_outcome(...)` - точную сигнатуру нужно подтвердить по БД.

Полный контракт аргументов/возвращаемых колонок и DDL необходимо сверять с рабочей схемой, а не восстанавливать по названиям.

## Индексы и ограничения

SQL в нодах предполагает, среди прочего:

- Уникальность Telegram chat ID для upsert лида.
- Partial unique index сообщений по `(telegram_chat_id, telegram_message_id)` при ненулевых значениях.
- Partial unique index открытой handoff-сессии по `lead_id`, где `status = 'open'`.
- Внешние ключи между лидами, встречами, handoff и сообщениями.
- Серверную защиту конфликтов бронирования внутри функций/ограничений.

Это требования из кода, не полный DDL и не подтверждение корректности всех ограничений в production.

## Получение структуры без клиентских строк

[export-structure.sql](export-structure.sql) читает системные каталоги: колонки, defaults, ограничения, индексы, функции и триггеры перечисленных таблиц. Запрос не выгружает строки клиентов или переписок и не изменяет БД.

Сначала просмотрите результат приватно: function bodies и defaults сами могут содержать hardcoded secrets. Результат нельзя автоматически считать безопасным для GitHub. Запрос не заменяет полный schema-only dump: отдельно нужны проверка зависимых функций, extensions, прав и RLS. Расписание доступности можно предоставить отдельно на вымышленных правилах.
