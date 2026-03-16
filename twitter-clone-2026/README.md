Ошибка возникает из-за отсутствия файла `README.md` в корневой папке проекта. Hatchling (библиотека для сборки пакетов) требует наличия этого файла для корректной работы.

**Решение:**

Создайте файл `README.md` в корневой папке проекта (рядом с `pyproject.toml`) со следующим содержимым:

```markdown
# Twitter Clone 2026

Микросервисный клон Twitter (Modular Monolith).

## Описание

Учебный проект, реализующий бэкенд сервиса микроблогов.

## Запуск

```bash
docker-compose -f deploy/docker-compose.yml up -d --build
```

## Документация

После запуска доступна по адресу: http://localhost:8000/api/docs
```

**После создания файла:**
1. Остановите текущие контейнеры: `docker-compose -f deploy/docker-compose.yml down`
2. Запустите сборку снова: `docker-compose -f deploy/docker-compose.yml up -d --build`

Теперь сборка должна пройти успешно.