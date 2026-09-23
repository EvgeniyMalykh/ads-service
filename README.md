# Сервис объявлений — REST API

Тестовое задание Y_LAB: backend на Django для создания, публикации и поиска объявлений.

**Стек:** Python 3.12, Django 5.2, Django REST Framework, PostgreSQL 17, Celery + Celery Beat + Redis,
uv, Docker Compose, pytest-django, Ruff, pre-commit.

## Быстрый старт (Docker Compose)

Требуется Docker с плагином Compose v2.

```bash
git clone <URL репозитория> ads-service
cd ads-service
cp .env.example .env          # при желании поменяйте DJANGO_SECRET_KEY и пароль БД
docker compose up --build -d
```

Поднимаются 5 сервисов: `db` (PostgreSQL, данные в volume `pgdata`), `redis`, `web`
(API на gunicorn), `worker` (Celery worker) и `beat` (Celery Beat).

При старте `web` автоматически применяет миграции и загружает фикстуру авторов
(`ads/fixtures/authors.json`, id 1–3). API доступно по адресу <http://localhost:8000/api/ads/>.

```bash
docker compose ps             # статус сервисов
docker compose logs -f web    # логи API
docker compose logs -f beat worker   # логи фоновой архивации
docker compose down           # остановить (данные БД сохраняются в volume)
docker compose down -v        # остановить и удалить данные
```

## Тесты

Одна команда (при запущенном `docker compose up`):

```bash
docker compose exec web pytest
```

Или без предварительного запуска стека:

```bash
docker compose run --rm web pytest
```

Тесты работают с **отдельной тестовой БД PostgreSQL** `test_ads` (имя задаётся
`POSTGRES_TEST_DB`): pytest-django создаёт её перед прогоном и удаляет после, рабочая БД `ads`
не затрагивается. SQLite не используется.

Покрыто (112 тестов, `ads/tests/`):

| Файл | Что проверяется |
|---|---|
| `test_crud.py` | создание (201, `draft` по умолчанию, read-only поля), получение в любом статусе, частичное обновление, смена автора, любые переходы статусов, удаление (204 без тела), 404 для отсутствующего/удалённого id, запрет PUT |
| `test_validation.py` | обязательные поля, пустые строки и строки из пробелов, `null`, длина title/description, границы и точность цены, недопустимый `status`, неизвестный `author_id`, битый JSON |
| `test_list.py` | видимость только `published` по умолчанию, публикация через PATCH, фильтр `status`, невалидный фильтр → 400, регистронезависимый поиск, сочетание фильтров, сортировка (`created_at` ↓, затем `id` ↓) |
| `test_tasks.py` | Celery-задача архивации: истёкшие / `expires_at = now` / будущие / без `expires_at`, не трогает draft и archived, идемпотентность повторного запуска, расписание Beat, поле `expires_at` в API |

## API

Формат обмена — JSON (`Content-Type: application/json`). Авторизация не требуется.

| Метод и путь | Поведение | Код |
|---|---|---|
| `POST /api/ads/` | Создать объявление | 201 |
| `GET /api/ads/` | Список с фильтрами (массив объектов) | 200 |
| `GET /api/ads/{id}/` | Объявление в любом статусе | 200 |
| `PATCH /api/ads/{id}/` | Частичное обновление | 200 |
| `DELETE /api/ads/{id}/` | Удаление из БД, без тела ответа | 204 |

### Поля объявления

| Поле | Правила |
|---|---|
| `id` | целое число, только чтение |
| `title` | обязательная непустая строка, до 120 символов |
| `description` | обязательная непустая строка, до 5000 символов |
| `price` | обязательное десятичное число 0 … 999 999 999.99, не более 2 знаков после точки (рубли). Принимается строкой или числом, возвращается строкой (`"15000.50"`) — чтобы не терять точность |
| `status` | `draft` / `published` / `archived`, по умолчанию `draft`; переходы без ограничений |
| `author_id` | только запись; id автора. Обязателен при POST, в PATCH — только при смене автора |
| `author` | только чтение; объект `{"id", "name"}` |
| `expires_at` | необязательно, ISO 8601 или `null` — окончание публикации (бонус) |
| `created_at`, `updated_at` | задаются сервером, только чтение |

Строки из одних пробелов отклоняются; крайние пробелы в `title`/`description` обрезаются.
Поля `id`, `created_at`, `updated_at` в запросе игнорируются.

### Параметры списка

- `status` — фильтр по статусу, по умолчанию `published`. Пустое или неизвестное значение → 400.
- `search` — поиск подстроки в `title` без учёта регистра (включая кириллицу).

Фильтры работают совместно. Сортировка: новые первыми, при равном `created_at` — по `id` по убыванию.

### Ошибки

| Ситуация | Код | Тело |
|---|---|---|
| Ошибки в полях, неизвестный `author_id` | 400 | `{"<поле>": ["причина", ...]}` |
| Неверный фильтр `status` | 400 | `{"status": ["Недопустимое значение «x». Допустимые значения: draft, published, archived."]}` |
| Некорректный JSON | 400 | `{"detail": "..."}` |
| Отсутствующий id объявления | 404 | `{"detail": "Объявление с id=42 не найдено."}` |
| PUT и другие неподдерживаемые методы | 405 | `{"detail": "..."}` |

Сообщения об ошибках — на русском (`LANGUAGE_CODE = "ru"`).

### Примеры

```bash
# Создать (статус draft по умолчанию)
curl -s -X POST http://localhost:8000/api/ads/ \
  -H 'Content-Type: application/json' \
  -d '{"title": "Велосипед", "description": "Горный, почти новый", "price": "15000.50", "author_id": 1}'

# Опубликовать с окончанием публикации
curl -s -X PATCH http://localhost:8000/api/ads/1/ \
  -H 'Content-Type: application/json' \
  -d '{"status": "published", "expires_at": "2030-01-01T12:00:00Z"}'

# Список: опубликованные, поиск по заголовку
curl -s 'http://localhost:8000/api/ads/?search=велос'

# Черновики с поиском
curl -s 'http://localhost:8000/api/ads/?status=draft&search=вел'

# Получить и удалить
curl -s http://localhost:8000/api/ads/1/
curl -s -X DELETE -o /dev/null -w '%{http_code}\n' http://localhost:8000/api/ads/1/
```

Пример ответа:

```json
{
  "id": 1,
  "title": "Велосипед",
  "description": "Горный, почти новый",
  "price": "15000.50",
  "status": "published",
  "author": {"id": 1, "name": "Иван Петров"},
  "expires_at": "2030-01-01T12:00:00Z",
  "created_at": "2026-09-23T01:22:59.725834Z",
  "updated_at": "2026-09-23T01:25:10.114202Z"
}
```

## Бонус: автоархивация (Celery + Beat + Redis)

- Поле `expires_at` необязательное. Без него объявление остаётся опубликованным.
- Celery Beat раз в минуту (`CELERY_BEAT_SCHEDULE` в `config/settings.py`) ставит задачу
  `ads.tasks.archive_expired_ads`; Redis — брокер; `worker` и `beat` — отдельные сервисы Compose.
- Задача выполняет один атомарный `UPDATE ... WHERE status = 'published' AND expires_at <= now()`,
  поэтому повторный или параллельный запуск безопасен: уже архивированные записи не меняются.
  Задача возвращает число архивированных объявлений. Запросы по ней ускоряет индекс `(status, expires_at)`.

Запустить вручную:

```bash
docker compose exec web python manage.py shell -c "from ads.tasks import archive_expired_ads; print(archive_expired_ads())"
```

## Конфигурация

Все настройки БД и секреты берутся из переменных окружения (шаблон — `.env.example`):

| Переменная | Назначение |
|---|---|
| `DJANGO_SECRET_KEY` | секретный ключ Django (обязательна) |
| `DJANGO_DEBUG` | режим отладки, по умолчанию `False` |
| `DJANGO_ALLOWED_HOSTS` | список хостов через запятую |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | параметры PostgreSQL (обязательны) |
| `POSTGRES_HOST`, `POSTGRES_PORT` | адрес БД; в Compose переопределяются на `db:5432` |
| `POSTGRES_TEST_DB` | имя отдельной тестовой БД, по умолчанию `test_<POSTGRES_DB>` |
| `CELERY_BROKER_URL` | URL брокера Redis; в Compose — `redis://redis:6379/0` |

## Локальная разработка без Docker

Нужны [uv](https://docs.astral.sh/uv/), PostgreSQL и (для Celery) Redis.

```bash
uv sync                                  # зависимости строго по uv.lock
cp .env.example .env                     # POSTGRES_HOST=localhost, CELERY_BROKER_URL=redis://localhost:6379/0
set -a && . ./.env && set +a
uv run python manage.py migrate
uv run python manage.py loaddata authors
uv run python manage.py runserver
uv run pytest                            # тесты (пользователю БД нужно право CREATEDB)
uv run celery -A config worker -B -l info   # worker + beat одним процессом для разработки
```

## Качество кода

```bash
uv run pre-commit install                # хуки на git commit
uv run pre-commit run --all-files        # прогон по всему репозиторию
```

Хуки: Ruff (lint с автоисправлением + format), проверки YAML/TOML/JSON, пробелы в конце строк,
перевод строки в конце файла, конфликтные маркеры, `uv-lock` (актуальность lock-файла).

## Решения и допущения

- **uv** выбран как менеджер зависимостей; `Dockerfile` ставит их командой
  `uv sync --locked --no-install-project`, т.е. строго по `uv.lock`. Dev-зависимости включены
  в образ, чтобы тесты запускались внутри контейнера одной командой.
- **DRF** используется для сериализации и валидации; включены только JSON-парсер и рендерер.
- Пагинация не добавлена: по условию список возвращается массивом объектов.
- `PUT` отключён — обновление только через `PATCH`, как в спецификации.
- Помимо валидации в API, инварианты продублированы `CHECK`-ограничениями в PostgreSQL
  (диапазон цены, допустимые статусы, непустые строки).
- Автор удаляется только если у него нет объявлений (`on_delete=PROTECT`) — API для авторов нет,
  так что это защита от случайной потери данных через админские скрипты.
- Все даты хранятся и возвращаются в UTC (ISO 8601).

## Структура

```
config/            настройки Django, URL, WSGI, приложение Celery
ads/
  models.py        Author, Ad (+ CHECK-ограничения и индексы)
  serializers.py   валидация и формат ответа
  filters.py       валидация query-параметров списка
  views.py         AdViewSet и JSON-обработчики 404/500
  tasks.py         Celery-задача archive_expired_ads
  fixtures/        фикстура авторов
  migrations/      миграции
  tests/           pytest-тесты
Dockerfile, compose.yaml, pyproject.toml, uv.lock, .env.example, .pre-commit-config.yaml
```
