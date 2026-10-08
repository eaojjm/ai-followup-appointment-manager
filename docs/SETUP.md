# Настройка публичного шаблона

## Что это за экспорт

Шесть workflow отражают разделённую архитектуру MVP. Это очищенные шаблоны, а не резервная копия рабочего n8n. Из них удалены credentials, instance/workflow/webhook IDs, теги и execution payloads. Личные ID заменены конфигурацией, ссылки на подworkflow - placeholders.

Все workflow импортируются неактивными. Экспорт очищен статически; импорт в отдельный n8n и запуск этого набора пока не проверены. Не импортируйте его поверх рабочего бота.

## Требования

- Отдельный n8n с PostgreSQL, Telegram и AI/LangChain-нодами соответствующих версий. Сверяйте `typeVersion` внутри JSON; версия сервера, на котором снято демо, в экспорт не записана.
- PostgreSQL со схемой, функциями, ограничениями и индексами проекта: [контракт БД](../database/README.md).
- Отдельный тестовый Telegram-бот и клиентский/менеджерский аккаунты, которые уже начали диалог с ботом.
- OpenAI credential с доступом к выбранной модели; PostgreSQL credential с минимальными необходимыми правами; Telegram credential.
- Для Telegram Trigger - работающее HTTPS webhook-подключение согласно [документации Telegram Trigger](https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.telegramtrigger/). Не используйте production bot token для тестового n8n: регистрация webhook может повлиять на рабочую интеграцию.

## Порядок импорта

1. `01-log-bot-message.json`.
2. `02-workflow-error-alerts.json`.
3. `03-appointment-booking.json`.
4. `04-appointment-lifecycle.json`.
5. `05-followup-engine.json`.
6. `06-telegram-router.json`.

После импорта назначьте новые локальные credentials в каждой PostgreSQL, Telegram/Telegram Trigger и OpenAI Chat Model ноде. Они намеренно отсутствуют в публичном JSON.

### Подworkflow и обработчик ошибок

В каждом Execute Workflow выберите соответствующий импортированный workflow. Полный список находится в [workflow-links.json](workflow-links.json). Не копируйте ID из чужого экземпляра n8n.

| Placeholder | Выбрать после импорта |
| --- | --- |
| `REPLACE_WITH_LOG_BOT_MESSAGE_ID` | Log Bot Message |
| `REPLACE_WITH_APPOINTMENT_BOOKING_ID` | Appointment Booking |
| `REPLACE_WITH_APPOINTMENT_LIFECYCLE_ID` | Appointment Lifecycle |
| `REPLACE_WITH_FOLLOWUP_ENGINE_ID` | Follow-up Engine |
| `REPLACE_WITH_WORKFLOW_ERROR_ALERTS_ID` | Workflow Error Alerts в Settings → Error Workflow |

На назначении Error Workflow проверьте все процессы, где эта настройка присутствует. Подworkflow-вызовы и error handler настраиваются раздельно.

## Конфигурация Telegram

Публичные выражения читают:

- `$env.MANAGER_TELEGRAM_CHAT_ID` - ID менеджерского чата. Используется и для уведомлений, и для проверки роли/manager callback.
- `$env.TELEGRAM_BOT_TOKEN` - токен отдельного тестового бота для четырёх HTTP Request нод Appointment Booking. Telegram credential остальных нод должен использовать тот же бот.

`.env.example` - пример имён, не Docker Compose и не автоматическая настройка credentials. Не заполняйте публичный файл реальными значениями. Настраивайте их только в защищённой конфигурации своего изолированного окружения.

### Ограничение `$env`

Доступ к `$env` зависит от версии и security policy n8n. Если доступ заблокирован, выражения не заработают. **Не отключайте защиту всего рабочего сервера ради импорта портфельного шаблона.** Для окружения с недоверенными редакторами используйте разрешённое администратором хранение секретов и адаптируйте выражения локально. Токен не нужно вставлять в экспортируемый JSON.

Для локального доверенного тестового self-hosted окружения администратор должен явно проверить разрешённый способ доступа к конфигурации. Пакет не содержит команды, которая меняет настройки вашего сервера.

Источники: [Telegram credentials](https://docs.n8n.io/integrations/builtin/credentials/telegram/), [изменения безопасности n8n 2.0](https://docs.n8n.io/2-0-breaking-changes/).

### HTTP Request ноды с токеном в пути API

В публичной копии URL строится из `$env.TELEGRAM_BOT_TOKEN` в нодах:

- `Send Available Slots` - `sendMessage`.
- `Remove Slot Keyboard` - `editMessageReplyMarkup`.
- `Refresh Slot Keyboard` - `editMessageText`.
- `Remove Appointment Keyboard` - `editMessageReplyMarkup`.

В исполнении конечный URL всё равно содержит токен по формату Telegram Bot API. Контролируйте доступ и retention execution/error logs; не публикуйте их. Переменная защищает экспорт от hardcode, но сама по себе не делает runtime-логи безопасными.

## Часовой пояс и расписания

В проекте используется `Asia/Barnaul` в разборе дат, выдаче слотов и SQL-форматировании времени. При смене региона согласованно измените все эти места и правила доступности, а не только timezone workflow.

Напоминания и запросы результата проверяются каждые 15 минут. Follow-up Schedule Trigger экспортирован с интервалом по умолчанию (`interval: [{}]`); перед запуском задайте нужное расписание явно. Для демонстрации есть Manual Trigger в Follow-up Engine.

## Перед активацией

1. Схема БД и функции установлены и проверены на вымышленных данных.
2. Credentials и конфигурация manager/token назначены; `$env` разрешён согласно политике изолированного окружения.
3. Все placeholders ссылок заменены выбранными workflow.
4. Выполнены проверки из [TESTING.md](TESTING.md).
5. Только после этого активируйте процессы с Telegram Trigger и расписаниями.

Ручной запуск может отправлять сообщения и изменять БД. Не используйте настоящих клиентов для smoke-test.
