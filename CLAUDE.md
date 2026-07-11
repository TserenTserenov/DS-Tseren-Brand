# DS-Tseren-Brand — Инструкции для Claude Code

> **Тип репозитория:** `DS/surface` (personal brand)
> **Назначение:** Мастерская личного бренда. Здесь живут все черновики, стили, идеи, видео в работе, аналитика.

## Структура

| Директория | Содержание |
|------------|------------|
| `style/` | Каноны стиля: `post.md` — посты/эссе; `video.md` — короткие видео; `README.md` |
| `content/drafts/` | Черновики постов D-NNN + `draft-list.md` (реестр) + `archive/` + `assets/` |
| `content/video/` | Видео-пайплайн: сценарии-черновики прямо в `video/` (без подпапки), `in-progress/`, `done/`, `как-снимать.md` |
| `content/templates/` | Шаблоны для написания контента |
| `content/topic-log.yaml` | Реестр тем C-NNN: статусы idea → accepted → written → published |
| `analytics/` | Статистика публикаций, отчёты, A/B-тесты |
| `profile/01-09-*.md` | Профиль бренда: позиционирование, голос, истории, границы |

## Pre-action Gate (БЛОКИРУЮЩЕЕ)

Перед написанием или редактированием любого поста / сценария — прочитать:
1. **`style/post.md`** — канон стиля постов (тон, голос, эталон ~140 постов). Для видео — `style/video.md`
2. `DP.SC.005 § Антипаттерны текста` (тире, ИИ-налёт, абстрактность)
3. **Дедуп-проверка (БЛОКИРУЮЩЕЕ, WP-442, 11.07.26):** прежде чем предложить новую тему — свериться с `content/topic-log.yaml` (темы за последний месяц, поле `hook`) и с текущими черновиками в `content/posts/` + `content/video/` (status `written`/`draft`). Совпадение образа/примера допустимо, если урок/тезис другой — тогда явно указать в `notes`, чем новая тема отличается. Совпадение урока — не заводить новую тему: обновить существующий черновик (дописать материал, обновить `notes`/`source_knowledge`), а не плодить дубль. Источник правила: занятие 2 марафона (11.07.26) вскрыло id-коллизию (C-016 x2) и файл-дубль (C-008/D-057) в реестре.

Проверка перед финалом: прочитать текст вслух. Звучит как робот или маркетинг → переписать.

## Правила

### Knowledge Index ≠ Мастерская
- **DS-Tseren-Brand** (этот репо) = мастерская: все черновики, идеи, `status: draft`
- **DS-Knowledge-Index-Tseren** = публичная полка: только готовые к публикации материалы, всегда `status: ready`
- Файл попал в Knowledge Index → он уже `ready`, черновиков в KI нет

### Черновики постов D-NNN
- Дом черновиков: `content/drafts/` (SoT)
- DS-my-strategy/drafts/ → deprecated (README указывает сюда)
- Номерация непрерывная: следующий = `D-<max+1>`
- Реестр: `content/drafts/draft-list.md`

### Видео-пайплайн
- Идеи: файлы прямо в `content/video/` (статус `draft`), без подпапки `ideas/`
- В работе: `content/video/in-progress/`
- Записанные видео: `content/video/done/` (тексты уже снятых роликов)
- Готовые к публикации сценарии → `DS-Knowledge-Index-Tseren/video/done/` (после финализации)
- Инструкция по съёмке: `content/video/как-снимать.md`

### topic-log.yaml
- Реестр тем контент-плана. Статусы: `idea` → `accepted` → `written` → `published`
- При создании поста в KI: обновить `status: written`, записать `draft_path`
- При публикации: `status: published`, `published_date`, `published_url`

## Связи

- **Стиль голоса:** `profile/01-who-i-am.md`, `profile/02-positioning.md`, `profile/04-voice-and-style.md`
- **Темы:** `profile/08-content-themes.md`, `content/topic-log.yaml`
- **Публикации:** `DS-Knowledge-Index-Tseren/docs/`
- **Стратегия:** `~/IWE/DS-my-strategy/inbox/WP-442/WP-442.md` (WP-167 контент-пайплайн, WP-433 видео)
- **Для кого пишем/снимаем (профессиональный портрет, не голос):** карта целевых аудиторий экосистемы (РП471) — `DS-ecosystem-development/A.Systems-Builder/A1.Teams-and-Communities/A1.1.Meaning/1.1.2. Marketing/Целевые аудитории 1.1.md`. `style/post.md` и `style/video.md` задают ГОЛОС (не меняется); карта задаёт, каким ТОНОМ и для какого профессионального адресата конкретный текст/видео.
