# Внедрение кита в multi-repo workspace (пошагово)

> Сценарий: у вас **N независимых репозиториев** (для примера — 10 микросервисов), каждый отвечает за
> своё и может быть не связан с другими. Нужно подключить **Open-Model SDLC Kit** так, чтобы одна
> инструкция + один гейтированный пайплайн + один набор MCP-инструментов работали сразу со всеми
> репозиториями, а у каждого сервиса была своя локальная детализация.
>
> Все имена ниже — плейсхолдеры: workspace `~/work/acme`, сервисы `catalog` / `marketplace` / …,
> Jira-ключ `PROJ`. Подставьте свои.

---

## 0. Что вы получите и почему это работает

- **Один источник правил** (`AGENTS.md`) на весь workspace + **вложенный `AGENTS.md`** в каждом сервисе
  (только то, что отличается). Агент читает **ближайший** `AGENTS.md` к файлу, который правит, —
  поэтому сервисные правила не форкают общие, а дополняют их.
- **Гейтированный пайплайн** `spec → clarify → plan → tasks → implement → test → review → pr`
  с тремя человеческими гейтами (clarify, tasks, pr).
- **MCP-инструменты** (Serena — символы Go, Atlassian — Jira/Confluence, context7 — свежие доки,
  git/filesystem — навигация по workspace) доступны из любой точки.
- **Скиллы**, в т.ч. `requirements-clarify`: на размытую просьбу («добавь сортировку») агент сам
  предложит варианты (по каким полям / порядок / как реализовать / кто пользуется) и сначала
  попробует ответить сам, а спросит только то, что не может решить.

**Ключевая идея размещения:** корневой `AGENTS.md` кита должен лежать **выше** всех сервисов
(быть их предком), чтобы правило «ближайший AGENTS.md» работало корректно. Поэтому кит ставится
в **корень workspace**, а ваши репозитории кладутся **внутрь** него как подкаталоги (каждый со своим
`.git`). Тогда:

```
~/work/acme/                      ← WORKSPACE_ROOT; агент запускается ОТСЮДА
│  AGENTS.md                      ← общие правила на весь workspace (из кита)
│  QWEN.md  CLAUDE.md             ← шимы (для Qwen / Claude)
│  .claude/  .qwen/  templates/  scripts/  config/  specs/  .mcp.json  .env
│
├── catalog/          (git repo)  ← сервис + свой вложенный catalog/AGENTS.md
├── marketplace/      (git repo)
├── orders/           (git repo)
├── ...               (ещё 7 репозиториев)
└── proto-contracts/  (git repo)  ← опционально: общий репо контрактов
```

Сервисы остаются **независимыми git-репозиториями** — кит их не поглощает и не требует, чтобы они были
связаны. Связность нужна только в одном месте: общий `WORKSPACE_ROOT`, чтобы Serena/git/filesystem-MCP
видели всё дерево.

---

## 1. Предварительные требования

| Что | Зачем |
|---|---|
| `uv` / `uvx` | Serena, Atlassian, git/fetch MCP |
| Node 18+ | `npx`-MCP (context7, sequential-thinking) + Qwen Code CLI |
| `python3` | портеры агентов + JSON-разбор в guard-хуке |
| Go + `go-task` | только если сервисы на Go (цели `task fmt/lint/test`) |
| `GITHUB_PAT` | чтобы Serena/gopls индексировали приватные модули (scope `repo` + `read:packages`) |
| Jira/Confluence token | опционально — для фаз spec/clarify через Atlassian MCP |

---

## 2. Шаг 1 — положить кит в корень workspace

**Как.** Клонируйте кит как корень workspace (или скопируйте его содержимое в `~/work/acme/`):

```bash
mkdir -p ~/work/acme && cd ~/work/acme
git clone <url-кита> .            # кит становится содержимым ~/work/acme
```

Затем склонируйте ваши 10 репозиториев **внутрь**:

```bash
cd ~/work/acme
git clone <url>/catalog.git
git clone <url>/marketplace.git
# ... остальные 8
```

**Зачем.** Корневой `AGENTS.md`/`QWEN.md` кита оказывается предком файлов каждого сервиса →
вложенные `AGENTS.md` сервисов корректно «побеждают» для своих файлов, а общие правила остаются
в контексте. Агент запускается из `~/work/acme` и дотягивается до любого сервиса по пути.

**Чтобы кит не пытался трекать сервисы**, добавьте их имена в локальный exclude (не в коммит):

```bash
cd ~/work/acme
printf '%s\n' catalog marketplace orders payments search auth notifications shipping billing proto-contracts \
  >> .git/info/exclude
```

---

## 3. Шаг 2 — заполнить `.env`

**Как.** В корне workspace:

```bash
cd ~/work/acme
cp .env.example .env              # .env в .gitignore — не коммитится
$EDITOR .env
```

Минимум к заполнению:

```bash
WORKSPACE_ROOT=~/work/acme        # корень, который видят git/filesystem MCP
GITHUB_PAT=ghp_...                # индексация приватных модулей Seren'ой
# Jira/Confluence — если нужны фазы spec/clarify через Atlassian:
JIRA_URL=https://your-org.atlassian.net
JIRA_USERNAME=sdlc-bot@your-org.com
JIRA_API_TOKEN=...
JIRA_PROJECTS_FILTER=PROJ,TEAM
# OpenAI-совместимый эндпоинт открытой модели (для pi/Qwen): self-hosted ИЛИ hosted-провайдер:
OPENAI_BASE_URL=http://localhost:8000/v1   # или https://api.z.ai/api/paas/v1 и т.п.
OPENAI_API_KEY=...
OPENAI_MODEL=qwen3-coder-next
```

**Зачем.** `setup.sh` и MCP-серверы берут переменные из `.env`; `${VAR}` в конфигах MCP резолвятся
из него. Без `GITHUB_PAT` Serena вернёт пустые `find_symbol` по приватным модулям.

---

## 4. Шаг 3 — настроить агента (`setup.sh`)

**Как.** Из корня workspace выберите харнесс (для Qwen Code):

```bash
cd ~/work/acme
./setup.sh qwen
```

Что делает `setup.sh qwen`:
- копирует `.qwen/settings.json` (MCP + `permissions` + guard-`hooks`) и ставит шим `QWEN.md`;
- **генерирует** `.qwen/{agents,commands,skills}/` из канона `.claude/` (с учётом `config/pipeline.yaml`);
- ставит git-хук `core.hooksPath .githooks` **для корневого репозитория**;
- гоняет верификатор `check-kit.sh`.

Проверка:

```bash
bash scripts/check-kit.sh         # должно быть "Kit OK"
qwen                              # внутри: /agents · /skills · /mcp
```

**Зачем.** Одна команда wiring'ит всё: MCP, подпромпты фазовых агентов (автоделегирование),
slash-команды `/spec … /pr`, скиллы и mid-session enforcement (deny на правку генерированного кода
и чтение `.env`; хуки блокируют деструктивные команды и push в защищённые ветки).

> Для Claude Code: `./setup.sh claude` (использует `.mcp.json` + `.claude/` напрямую).
> Для pi / opencode: `./setup.sh pi` / `./setup.sh opencode` (генерация своих форматов агентов).
> Для omp (oh-my-pi): `./setup.sh omp` — только ставит бинарь; `.claude/` + `AGENTS.md` + `.mcp.json`
> читаются нативно (генерация не нужна, см. `agents-config/omp/README.md`).

---

## 5. Шаг 4 — вложенный `AGENTS.md` в каждый сервис

**Как.** Для каждого сервиса, где есть сервисная специфика, положите заполненный шаблон в корень репо:

```bash
cp ~/work/acme/AGENTS.nested.example.md ~/work/acme/catalog/AGENTS.md
$EDITOR ~/work/acme/catalog/AGENTS.md
```

Заполните только то, что **отличается** от общих правил (шаблон короткий):

```markdown
# AGENTS.md — Catalog
Inherits all workspace rules from the root AGENTS.md. Service-specific notes:
## This service in one line
Products, categories, documents. gRPC :50051, publishes catalog.product.v1.
## Commands
- DB: task db:migrate:up against `catalog` on Postgres :15000
- Codegen: task sqlc
## Domain & layout notes
- Kafka topics: catalog.product.v1 (produces)
- External: OpenSearch index `products`
## Gotchas
- Pricing comes from the pricing service, never recomputed here.
```

**Зачем.** Агент, правящий `catalog/internal/...`, прочитает `catalog/AGENTS.md` (ближайший) поверх
общего — без дублирования правил. Для сервисов, где нечего добавить, вложенный файл можно не создавать.
Это работает и для **несвязанных** репозиториев: каждый описывает только себя.

---

## 6. Шаг 5 — общие commit-time guardrails на все репозитории

`setup.sh` ставит `core.hooksPath` только для корневого репо. Чтобы прекоммит-защита (блок правки
генерированного кода, `.env`, кириллицы в коде) действовала в **каждом** сервисе:

```bash
cd ~/work/acme
for r in catalog marketplace orders payments search auth notifications shipping billing proto-contracts; do
  git -C "$r" config core.hooksPath "$PWD/.githooks"
done
```

**Зачем.** Для открытых агентов commit-time хук — последний рубеж; без этого он сработает только в
корневом репо. `core.hooksPath` может указывать на общий абсолютный путь — один набор хуков на всех.

---

## 7. Шаг 6 — MCP видит весь workspace

- **Serena** стартует с `--project-from-cwd`: запускайте агента из `~/work/acme` — тогда индексируется
  всё дерево сервисов; `GITHUB_PAT` даёт резолв приватных кросс-модульных импортов. Для прицельной
  работы с символами конкретного сервиса агент (и Serena) оперирует внутри модуля этого сервиса.
- **git / filesystem MCP** используют `WORKSPACE_ROOT` из `.env`.

Проверка внутри агента: `/mcp` (серверы подняты), `/mcp tools` (у Serena видны `find_symbol`,
`get_symbols_overview`, `replace_symbol_body`, …).

---

## 8. Шаг 7 — прогнать задачу сквозь пайплайн

Из корня workspace (на примере Qwen):

```
/spec PROJ-1234            # planner: читает Jira, пишет specs/PROJ-1234-<slug>/spec.md
                           #   на размытое ТЗ сработает скилл requirements-clarify — агент сам
                           #   предложит варианты ответов и спросит только то, что не решил
/clarify PROJ-1234         # ◆ ГЕЙТ: человек отвечает на открытые вопросы
/plan PROJ-1234            # tech-designer: plan.md (архитектура, контракты, файлы)
/tasks PROJ-1234           # tasks.md; ◆ ГЕЙТ: человек одобряет задачи до кода
/implement PROJ-1234       # engineer: код по одной задаче, Serena-правки символов
/test PROJ-1234            # qa-lead: тесты на каждую AC, task lint/test green (Definition of Done)
/review PROJ-1234          # go-code-reviewer: ревью диффа; блокеры → откат к engineer
/pr PROJ-1234              # ◆ ГЕЙТ: [WIP] [PROJ-1234] PR, человек ревьюит и мержит
```

Артефакты фаз ложатся в `~/work/acme/specs/<TASK_ID>-<slug>/` (`spec.md`, `plan.md`, `tasks.md`,
`handoff.md`); `specs/INDEX.md` сводит статусы по workspace. Агент сам заходит в нужный сервис(ы)
через Serena/grep; вложенный `AGENTS.md` сервиса подсказывает локальные команды/топики/gotchas.
`handoff.md` — коммитимый источник состояния: любая новая сессия читает его и продолжает с того же места.

**Если сервисы не связаны между собой** — это не мешает: задача просто целится в один репозиторий,
кросс-сервисные spec'ы не создаются. Пайплайн тот же, меняется только скоуп в `spec.md §5`.

---

## 9. Шаг 8 — настроить ростер агентов под себя

Ростер — данные, не код. Если у вас нет infra-задач или не нужен RLM-солвер:

```bash
$EDITOR config/pipeline.yaml      # enabled: false для devops-lead / rlm
./setup.sh --pipeline             # уберёт их из всех харнессов + перегенерирует + проверит
```

Пять core-агентов (planner, tech-designer, engineer, qa-lead, go-code-reviewer) владеют фазами —
их держите включёнными, иначе соответствующую команду придётся выполнять вручную.

---

## 10. Где что лежит (шпаргалка)

| Что | Где | Комментарий |
|---|---|---|
| Общие правила | `~/work/acme/AGENTS.md` | предок всех сервисов |
| Шим Qwen / Claude | `~/work/acme/QWEN.md`, `CLAUDE.md` | `@AGENTS.md` / context.fileName |
| Агенты/команды/скиллы (канон) | `.claude/{agents,commands,skills}/` | правите здесь |
| То же для Qwen (генерируемое) | `.qwen/{agents,commands,skills}/` | `port-to-qwen.py`, не редактировать руками |
| Конфиг MCP | `.mcp.json` (Claude), `.qwen/settings.json` (Qwen) | permissions + hooks у Qwen |
| Секреты | `.env` (gitignored) | `WORKSPACE_ROOT`, `GITHUB_PAT`, `JIRA_*`, `OPENAI_*` |
| Ростер агентов | `config/pipeline.yaml` | `./setup.sh --pipeline` |
| Политика безопасности | `config/security-policy.yaml` | источник для хуков/permissions |
| Артефакты задач | `specs/<TASK_ID>-<slug>/` | spec/plan/tasks/handoff + `INDEX.md` |
| Правила сервиса | `<service>/AGENTS.md` | вложенный, из `AGENTS.nested.example.md` |
| Guard-хуки | `.githooks/pre-commit` | общий `core.hooksPath` на все репо |

---

## 11. Частые вопросы / подводные камни

- **Откуда запускать агента?** Из `~/work/acme` (корень workspace). Тогда загружаются корневые
  `AGENTS.md`+`QWEN.md`+`.qwen/`, а при правке файла сервиса подтягивается его вложенный `AGENTS.md`.
- **Сервисы в разных git-репо — не проблема?** Да. Кит не требует монорепы; нужен лишь общий
  `WORKSPACE_ROOT`. Исключите имена сервисов из индекса кита через `.git/info/exclude` (шаг 1).
- **Куда писать spec'ы?** По умолчанию — в `specs/` корневого кита (удобно для кросс-сервисных фич,
  сводится в `INDEX.md`). Для чисто сервисной задачи можно держать артефакты в самом сервисе —
  команды резолвят `specs/<TASK_ID>-*/` от cwd.
- **`task lint/test` не находятся?** Цели go-task живут **в сервисе** — агент запускает их из
  каталога сервиса (это описано во вложенном `AGENTS.md`).
- **Qwen: как включить автономию безопасно?** `permissions`+`hooks` в `.qwen/settings.json` уже
  блокируют правку генерированного кода, чтение `.env`, деструктивные команды и push в защищённые
  ветки — даже в YOLO. Для длинного автономного прогона используйте `/goal <условие-готовности>`.
- **Serena медленно/неточно индексирует 10 модулей?** Для глубокой работы с символами агент оперирует
  внутри конкретного модуля сервиса; убедитесь, что `GITHUB_PAT` задан для приватных импортов.

---

## 12. Быстрый чек-лист внедрения

- [ ] Кит в корне `~/work/acme`, сервисы склонированы внутрь, их имена — в `.git/info/exclude`
- [ ] `.env` заполнен (`WORKSPACE_ROOT`, `GITHUB_PAT`, опц. `JIRA_*`, `OPENAI_*`)
- [ ] `./setup.sh qwen` → `check-kit.sh` = **Kit OK**; `/agents`, `/skills`, `/mcp` работают
- [ ] Вложенные `<service>/AGENTS.md` созданы там, где есть специфика
- [ ] `core.hooksPath` выставлен на все сервисные репо
- [ ] `config/pipeline.yaml` подрезан под ваши роли (`./setup.sh --pipeline`)
- [ ] Пробный прогон: `/spec PROJ-0000` → … → `/pr`
