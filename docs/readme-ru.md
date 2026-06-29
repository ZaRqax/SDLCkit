# Open-Model SDLC Kit — описание (RU)

> Русскоязычный обзор кита. Канонические инструкции для агентов — в `AGENTS.md` (на английском, по
> правилу «no Russian in code»). Этот файл — для людей: что это, зачем, как устроено и как пользоваться.
> Краткая англоязычная версия — `README.md`; пошаговая установка — `INSTALL.md`; процесс — `FLOW.md`;
> логика дизайна — `docs/weak-model-playbook.md`.

---

## 1. Что это и зачем

Автономная **«обвязка» для разработки (SDLC-кит)** под воркспейс Acme (~15 Go-микросервисов,
gRPC/Kafka/Postgres/OpenSearch). Единственная цель кита — заставить **лёгкую open-модель**
(GLM-5.1 / Qwen3-Coder-Next, в стиле агента pi.dev) писать **качественный код, соблюдающий конвенции
команды**, за счёт более явной структуры и более сильных тулов. Тот же кит **без изменений работает
в Claude Code**.

Ключевая мысль: слабые open-модели проваливаются не из-за нехватки «мозгов», а из-за конкретных
паттернов отказа — поверхностное следование инструкциям, неглубокое планирование, галлюцинации API,
частичные правки, преждевременное «готово», деградация на длинном контексте. Кит бьёт по каждому
из этих паттернов точечно (подробно — в `docs/weak-model-playbook.md`).

Кит — **стендэлоун** (свежий, написан с нуля), но вобрал лучшие идеи из существующих spec-driven
китов: фазовый процесс, формат скиллов/сабагентов, концепцию handoff/прогресса.

**Поставка:** этот git-репозиторий (публикуется на GitHub под лицензией MIT). `Acme`, `PROJ`/`TEAM`
и `your-org.atlassian.net` — это плейсхолдеры; замените их под свой проект (см. README → Customize).

---

## 2. Две несущие идеи

1. **Один источник — много агентов.** Все долгоживущие правила живут один раз в `AGENTS.md`.
   `CLAUDE.md` — это строка `@AGENTS.md` + крошечная Claude-секция. `AGENTS.md` нативно читают
   pi, Qwen Code, Crush, opencode, Codex, Cursor; Claude Code — через импорт. Правишь правило один
   раз — его получают все агенты. Для отдельного сервиса — вложенный `AGENTS.md` (ближайший файл
   побеждает), шаблон — `AGENTS.nested.example.md`.

2. **Фазовый пайплайн с гейтами:** `spec → clarify → plan → tasks → implement → test → review → pr`.
   Каждая фаза читает артефакт предыдущей и пишет следующий в `specs/<TASK_ID>-<slug>/`. Модель
   обязана **объявлять текущую фазу** и пройти **Definition of Done** (реальные `task lint`/`task test`),
   прежде чем сказать «готово». Три человеческих гейта держат слабую модель в рамках: подтвердить
   уточнённый spec, утвердить список задач `tasks.md`, заревьюить PR.

---

## 3. Тулы (MCP) — то, что вытягивает слабую модель

| Сервер | Зачем именно слабой модели |
|---|---|
| **Serena** (семантический код через gopls) | Правки и чтение на уровне символов вместо целых файлов → меньше токенов и почти нет «битых» патчей. Главный выигрыш. |
| **Atlassian / Jira** (sooperset, через `uvx` — процесс, не Docker) | Читает реальный тикет; в read-write профиле создаёт/обновляет/переводит истории. Скоуп `JIRA_PROJECTS_FILTER=PROJ,TEAM`. |
| **context7** | Живая, версионно-привязанная документация библиотек → убивает галлюцинации/устаревшие API. |
| **sequential-thinking** | Принудительная декомпозиция задачи перед кодом. |
| **git**, **fetch** | Безопасные структурные git-операции; подтягивание внешних спек/доков по запросу. |

**Core-набор** (в `.mcp.json`): serena, atlassian, context7, sequential-thinking, git, fetch.
**Опциональные** (в `mcp.example.json`): filesystem (core для open-агентов), postgres-mcp-pro
(только `--access-mode=restricted`), playwright (для UI-репозиториев), официальный github.
**Забанены:** архивный `@modelcontextprotocol/server-postgres` (CVE: SQL-инъекция / обход read-only) и
архивный `@modelcontextprotocol/server-github`.

> Серверы прописаны один раз; для open-агентов конфиг идентичен — отличается только `--context`
> у Serena (`claude-code` → `agent`). Секреты везде по `${VAR}` и подставляются в рантайме из
> gitignore-нутого `.env`; токены не коммитятся.

---

## 4. Состав кита

```
AGENTS.md             ← КАНОНИЧЕСКИЕ инструкции (читают все агенты)
CLAUDE.md             ← шим @AGENTS.md + Claude-секция
README.md / INSTALL.md / FLOW.md / KIT-DEV.md   ← обзор / установка / процесс / факты для сопровождения
.mcp.json             ← активный MCP-набор (Serena + Atlassian + context7 + sequential-thinking + git + fetch)
mcp.example.json      ← полное «меню» MCP, включая опциональные
.env.example          ← шаблон секретов
setup.sh              ← idempotent-бутстрап (выбор агента, разводка MCP, проверка)
scripts/check-kit.sh  ← верификатор кита

agents-config/        ← адаптеры под агентов, все на один OpenAI-совместимый /v1
  pi/                 ← PRIMARY: models.json + SYSTEM.md + settings.json (пакеты pi-mcp-adapter,
                        pi-subagents, pi-plan, pi-patty-bg-tasks) + сгенерированные субагенты +
                        запасной MCP-мост (fallback)
  qwen/ crush/ opencode/   ← вторичные агенты (нативный MCP)
  sampling-params.md  ← запиненный sampling GLM-5.1 / Qwen3-Coder-Next

config/    ← pipeline.yaml (включение/отключение агентов) + security-policy.yaml (политика безопасности)

.claude/
  agents/   ← субагенты-фазы: planner, tech-designer, engineer, qa-lead, go-code-reviewer,
              devops-lead + rlm (рекурсивный солвер, утилита). Активный набор задаёт config/pipeline.yaml
              (отключить агента: enabled: false, затем ./setup.sh --pipeline)
  commands/ ← 8 команд-фаз: /spec /clarify /plan /tasks /implement /test /review /pr
  skills/   ← 7 скиллов: serena-first, precommit, go-grpc-handler, sqlc-migration, testify-suite,
              commit-message, jira-flow
  rules/    ← path-scoped правила слоёв Go (грузятся только при правке internal/**)
  settings.json + hooks/   ← enforcement для Claude (permissions + хуки)
.githooks/pre-commit  ← ТЕ ЖЕ гарды для open-агентов (у них нет хук-слоя) + CI

templates/            ← шаблоны-«заполни пропуск»: spec, plan, tasks, pr, handoff
specs/                ← артефакты по фичам: specs/<TASK_ID>-<slug>/{spec,plan,tasks,handoff}.md
docs/                 ← weak-model-playbook.md (зачем всё так) + optional-graph-engine.md + этот файл
.claude-plugin/       ← манифесты плагина и маркетплейса (опциональный канал распространения)
```

---

## 5. Пайплайн и состояние

```
тикет Jira → /spec → /clarify ◆ → /plan → /tasks ◆ → /implement → /test ◆DoD → /review ◆ → /pr ◆
             planner   planner    tech-designer    engineer      qa-lead      reviewer   engineer
```
`◆` — гейт (человек уточняет spec / утверждает tasks / ревьюит и мёржит PR; DoD — обязательная проверка).

Артефакты по фиче в `specs/<TASK_ID>-<slug>/`: `spec.md`, `plan.md`, `tasks.md`, `test-plan.md` и
**`handoff.md`** — читаемый, коммитимый файл состояния (Статус, Фаза, Следующий агент, чек-лист
пайплайна, quality-гейты, решения, блокеры, append-only лог). Любой агент (или новая сессия) читает
`handoff.md` и понимает, где работа и кто следующий. `specs/INDEX.md` — сводный статус по всем фичам.
(JSON-зеркало `handoff/<TASK_ID>.json` со схемой `handoff/schema.json` — только для опционального
слоя автоматизации/графа, см. `docs/optional-graph-engine.md`.)

---

## 6. Почему именно так (кратко)

Кит хардкодит пять «рычагов компенсации» под слабую модель (полностью — в `docs/weak-model-playbook.md`):
1. **Обязательные фазы с гейтами** — против неглубокого планирования и преждевременного «готово».
2. **Show-don't-tell: один реальный компилируемый пример на каждое правило** — слабые модели лучше
   копируют по образцу, чем рассуждают из абстракции.
3. **Serena + валидация на уровне тулов** — против галлюцинаций API и деградации контекста.
4. **Явный Definition of Done + запрет частичных правок/«…»/частичных структов** — против обрывков
   и ложного «готово».
5. **Запиненный sampling + явный «спроси-если-застрял»** — против бесконтрольного «тыканья».

---

## 7. Быстрый старт

```bash
cp .env.example .env      # заполнить токены: GITHUB_PAT, JIRA_*, OPENAI_*
./setup.sh                # выбрать агента, развести MCP, поставить git-хуки, проверить
# не интерактивно: ./setup.sh pi | qwen | crush | opencode | claude
```
Прогон тикета по пайплайну:
- **Claude Code:** зайти в репозиторий сервиса с китом и выполнять `/spec PROJ-1234` … `/pr PROJ-1234`
  (или дать Claude авто-делегировать сабагентам по описанию).
- **pi (pi.dev):** `./setup.sh pi`, затем `pi --model selfhosted/Qwen3-Coder-Next`. Кит ставит набор
  пакетов: **pi-mcp-adapter** (MCP), **pi-subagents** (субагенты — `/run`, `/chain`; генерятся из
  `.claude/agents/`), **@pi-vault/pi-plan** (read-only режим планирования), **pi-patty-bg-tasks**
  (фоновые задачи) — это даёт pi паритет с Claude Code. Подробности — `agents-config/pi/README.md`.
- **Qwen Code / Crush / opencode:** запустить агента в репозитории; он читает `AGENTS.md` + свой MCP-конфиг.

Подробности по каждому агенту, пререквизиты и троблшутинг — в `INSTALL.md`.

**Пререквизиты:** `uv`/`uvx` (Serena, git/fetch MCP), Node 18+ (`npx`-серверы, pi/Qwen), Docker
(Atlassian MCP), Go + `go-task`, и `GITHUB_PAT` (чтобы Serena/gopls индексировали приватные модули
`github.com/acme`).

---

## 8. Enforcement в три слоя

Текст инструкций — это только контекст; реально правила держатся механически:
1. **Правила + примеры** в `AGENTS.md` (портируемая основа).
2. **Жёсткий enforcement для Claude:** `.claude/settings.json` (`permissions.deny` на правки
   `sqlc/`,`mocks/`,`gen/` и чтение `.env`; `ask` на миграции и `git push`) + `PreToolUse`/`PostToolUse`
   хуки (`.claude/hooks/format-and-guard.sh`: блок правок генерённого кода и пушей в protected-ветки;
   gofumpt после правок).
3. **Фолбэк для open-агентов** (у них нет хук-слоя): `.githooks/pre-commit` + CI — те же проверки
   (генерённый код, частичные структуры по эвристике, кириллица в Go, имя ветки, `task lint`/`test`).

---

## 9. Модели и sampling

Co-primary модели: **GLM-5.1** и **Qwen3-Coder-Next**, по OpenAI-совместимому `/v1`. Sampling — это
свойство **сервера инференса/запроса**, поэтому пинится на уровне serving (vLLM/SGLang или хостед-провайдер),
а не в конфиге агента. Официальные значения (см. `agents-config/sampling-params.md`):
`temperature 1.0 / top_p 0.95 / top_k 40`, max output 65536. Для Qwen3-Coder-Next в vLLM нужен
`--tool-call-parser qwen3_coder`; для GLM через OpenAI-совместимый эндпойнт у pi выставлен
`compat.thinkingFormat: "zai"`, для Qwen — `"qwen-chat-template"`.

> ⚠ Не занижать temperature «ради детерминизма» — для Qwen3-Coder это **ухудшает** tool-calling.

---

## 10. Что проверить перед проднём (помечено в файлах)

- **Точные sampling GLM-5.1** — модель новая; в `sampling-params.md` стоит официальный бейслайн
  с пометкой «verify» — свериться с актуальной карточкой модели / доками Z.ai.
- **MCP в pi — пакет `pi-mcp-adapter`** (ставится `setup.sh pi`, читает `~/.pi/agent/mcp.json`);
  у pi нет нативного MCP, поэтому серверы бриджит именно этот пакет.
- **Версии pi-пакетов запинены** (сверено по npm-реестру 2026-06-24): `pi-mcp-adapter@2.10.0`,
  `pi-subagents@0.31.0`, `@pi-vault/pi-plan@0.1.0`, `pi-patty-bg-tasks@0.2.0`; pi CLI
  `@earendil-works/pi-coding-agent@0.80.2`. **`@pi-vault/pi-plan` требует Node ≥ 24.15.0.** Сверить имена
  встроенных тулов pi (`/tools`) и Serena `directTools` (`/mcp tools`) после установки.
- **Токены:** `GITHUB_PAT` (иначе Serena `find_symbol` пустой на приватных модулях), `JIRA_*`/
  `CONFLUENCE_*` (сервис-аккаунт для read-write), `OPENAI_*` (эндпойнт open-модели).
- **Atlassian read-write по умолчанию** — переключение в read-only одной переменной:
  `ATLASSIAN_READ_ONLY=true`.

---

## 11. Проверка кита

```bash
./scripts/check-kit.sh --mcp
```
Проверяет: наличие ключевых файлов, валидность всех JSON, число сабагентов/команд/скиллов, frontmatter,
отсутствие кириллицы в коде/инструкциях (этот RU-док в `docs/` не сканируется), и доступность бинарей
MCP (`uvx`/`docker`/`npx`).

---

## 12. Как кит собирался

Research-workflow (7 параллельных потоков: ландшафт open-агентов и pi.dev, существующие SDLC-киты,
Serena, Atlassian MCP, прочие MCP, промптинг слабых моделей, конфиг-формат Claude Code) → маппинг
лучших идей прайор-арта → отдельный workflow на 23 leaf-файла с пайплайном **author → verify**
(каждый файл написан и затем проверен против `KIT-DEV.md`) → ручная сборка «хребта» и нормализация →
верификация `check-kit.sh`.

---

## 13. Дальнейшие шаги (по желанию)

- Склонировать репозиторий и адаптировать плейсхолдеры под свой проект (README → Customize).
- Прогнать кит на реальном тикете (например, через Claude Code в одном из сервисов).
- Добавить рабочий пример заполненного `specs/<TASK_ID>/` для наглядности.
- Включить опциональный граф-движок дрейфа (`docs/optional-graph-engine.md`), если нужен контроль
  «spec ↔ код».
