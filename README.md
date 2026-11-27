# Мемовоз

Одно Python-приложение на asyncio: общее ядро очереди, источник Pinterest, Telegram (aiogram 3), Discord (discord.py 2) и FastAPI-админка. Используются APScheduler и SQLAlchemy 2 с SQLite по умолчанию. Данные сохраняются в `./data`.

## Pinterest: источник и ограничения

Основной способ — Pinterest API v5: официальный API умеет листать пины конкретной доски с пагинацией. Для чтения нужны OAuth scopes `boards:read` и `pins:read`, подключённое приложение Pinterest и выданный приложению доступ; Trial-доступ тоже включает чтение, но на практике запрос доступа/одобрение может занять время. Создайте Pinterest developer app, подключите аккаунт, получите user access token и скопируйте ID нужной доски в `PINTEREST_BOARD_ID`. URL доски задаётся отдельно для ссылки в публикациях.

Резервный источник — RSS по URL `https://www.pinterest.com/<user>/<board>.rss` (либо конкретный `PINTEREST_RSS_URL`). Это не гарантированный Pinterest API: доступность и формат зависят от Pinterest, а RSS обычно показывает только недавние записи и может не содержать видео. Он не подходит для надёжной первоначальной выгрузки полной доски. Скрапинг намеренно не используется из-за нестабильности и возможного конфликта с условиями Pinterest.

Официальные материалы: [List Pins on Board и формат пинов](https://developers.pinterest.com/docs/work-with-organic-content-and-users/create-boards-and-pins/), [OAuth и scopes](https://developers.pinterest.com/docs/getting-started/set-up-authentication-and-authorization/), [уровни доступа](https://developer.pinterest.com/docs/key-concepts/access-tiers/), [пагинация](https://developers.pinterest.com/docs/reference/pagination/).

## Быстрый запуск Docker

1. Скопируйте `.env.example` в `.env` и заполните токены, ID доски, цели и Pinterest-доступ.
2. Установите пароль админки в виде scrypt-хэша. В PowerShell из каталога проекта:

   ```powershell
   @'
   import secrets, hashlib
   password = input("Пароль админки: ")
   salt = secrets.token_bytes(16)
   digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1).hex()
   print(f"scrypt${salt.hex()}${digest}")
   '@ | python -
   ```

   Запишите напечатанное значение в `ADMIN_PASSWORD_HASH`. Установите длинный уникальный `SECRET_KEY`.
3. Запустите `docker compose up --build -d`.
4. Откройте `http://localhost:8000`, войдите с `ADMIN_USERNAME` и паролем из шага 2.

Для локального запуска без Docker: Python 3.11+, `python -m venv .venv`, активируйте окружение, `pip install -r requirements.txt`, затем `python -m app`.

## Настройка `.env`

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен от BotFather. Пустое значение отключает Telegram. |
| `TELEGRAM_ADMIN_ID` | Числовой user ID для команд управления в Telegram. |
| `TELEGRAM_TARGETS` | ID чатов через запятую. Бот должен быть добавлен в каждый чат/канал; для канала назначьте администратора с правом публикации. |
| `DISCORD_BOT_TOKEN` | Bot token из Developer Portal. Пустое значение отключает Discord. |
| `DISCORD_TARGETS` | ID каналов через запятую. |
| `PINTEREST_SOURCE` | `api` (рекомендуется) или `rss`. |
| `PINTEREST_BOARD_URL` | URL доски Pinterest. |
| `PINTEREST_BOARD_ID` | ID доски для `/v5/boards/{board_id}/pins` (это не URL и не slug). |
| `PINTEREST_ACCESS_TOKEN` | Pinterest OAuth access token со scopes `boards:read,pins:read`. |
| `PINTEREST_RSS_URL` | Необязательный полный RSS URL при `PINTEREST_SOURCE=rss`. |
| `POST_INTERVAL_MINUTES` | Начальный интервал публикации в минутах. Его можно изменить из админки. |
| `POLL_INTERVAL_MINUTES` | Начальный интервал проверки доски; редактируется в админке. |
| `NEW_PIN_MODE` | `immediate` отправляет новые пины сразу, `queue` оставляет их в очереди. |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD_HASH` | Логин и scrypt-хэш пароля для веб-панели. Обычный пароль не хранится. |
| `SECRET_KEY` | Секрет для подписания cookie-сессии; задайте уникальное случайное значение. |
| `COOKIE_HTTPS_ONLY` | Установите `true`, когда админка доступна через HTTPS reverse proxy. Для локального `http://localhost` оставьте `false`. |
| `DATABASE_URL` | По умолчанию SQLite. Для PostgreSQL используйте `postgresql+asyncpg://user:password@host:5432/dbname`. |
| `MAX_MEDIA_MB` | Максимальный размер файла для загрузки; большие файлы отправляются ссылкой. |
| `WEB_HOST`, `WEB_PORT`, `LOG_LEVEL` | Адрес панели, порт и уровень логирования. |

Начальные target ID из `.env` импортируются в БД при запуске. Добавленные через админку цели хранятся в БД. Настройки интервалов, пауза и режим новых пинов также сохраняются в БД и переживают перезапуск.

## Telegram

1. В Telegram откройте `@BotFather`, выполните `/newbot`, задайте имя и username.
2. Скопируйте выданный токен в `TELEGRAM_BOT_TOKEN`.
3. Узнайте свой числовой user ID и задайте `TELEGRAM_ADMIN_ID`.
4. Добавьте бота в группы/каналы назначения. Для каналов дайте право отправлять сообщения. В `TELEGRAM_TARGETS` укажите числовой ID группы/канала или `@username` публичного канала.
5. Команды `/status`, `/pause`, `/resume`, `/post_now` отвечают только заданному `TELEGRAM_ADMIN_ID`.

## Discord

1. В [Discord Developer Portal](https://discord.com/developers/applications) создайте Application, откройте **Bot** и сбросьте/скопируйте токен в `DISCORD_BOT_TOKEN`.
2. Для работы боту не нужен Message Content intent: приложение само рассылает сообщения и не читает пользовательские сообщения. Оставьте включёнными стандартные intents.
3. Через OAuth2 URL Generator выберите `bot`, разрешения `View Channels`, `Send Messages`, `Attach Files`, затем добавьте бота на сервер.
4. Включите Developer Mode в Discord, скопируйте ID нужного текстового канала и добавьте его в `DISCORD_TARGETS`.

## Поведение очереди и медиа

При пустой БД первая синхронизация помечает все найденные пины как старые, и постинг начинает брать их случайно без повторов. Когда все элементы цикла отправлены, статус отправленных мемов возвращается в очередь и начинается новый случайный цикл. Новые пины получают `is_new`; в режиме `immediate` отправляются при проверке источника, в `queue` идут следующими после старой очереди. Ошибки отдельной доставки пишутся в лог; удачные платформы фиксируются, а мем останется в очереди для повторной попытки доставки неудачным целям.

Изображения, GIF и видео скачиваются потоком с ограничением размера, затем отправляются файлом, когда платформа и её лимиты это позволяют. При ошибке загрузки или превышении лимита бот отправляет ссылку на сам пин и медиа. Лимиты загрузки платформ могут меняться, поэтому при росте лимита платформы можно скорректировать `MAX_MEDIA_MB`.

Админ-панель: список последних 500 мемов, поиск/фильтр, отправка, пропуск, удаление и возврат в очередь; настройки планировщика, целей и паузы; статистика и последние 200 строк `data/memovoz.log`. Веб-панель следует размещать за HTTPS reverse proxy, если она доступна из интернета.

## Проверка после запуска

1. Проверьте `docker compose logs -f` и наличие `data/memovoz.db` и `data/memovoz.log`.
2. Убедитесь, что Pinterest API отвечает и пины появились в панели. Для большого борда дождитесь завершения прохода по страницам.
3. Добавьте тестовые Telegram/Discord цели и нажмите «Отправить» у одного мема.
4. Проверьте команду `/status`, поставьте паузу из панели и убедитесь, что запланированные публикации остановлены.
5. Добавьте тестовый пин в доску и проверьте режим `immediate` или `queue` после очередного цикла проверки.

## Дальнейшие улучшения

- OAuth-процесс Pinterest внутри приложения с автоматическим обновлением токенов.
- Миграции Alembic и пакетная отправка с журналом статуса на каждую цель.
- Очередь с блокировками для горизонтального запуска нескольких worker-процессов.
- Кеширование и локальное хранение медиа для превью, удаления источником и временных URL.
- Ограничение частоты попыток входа и встроенная ротация Pinterest OAuth-токенов.
