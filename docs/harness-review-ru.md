# Ревью харнесса Open-Model SDLC Kit

> **Внутренний обзор, не публичный файл кита.** Написан по-русски и ссылается на конкретную
> инсталляцию, поэтому намеренно НЕ соблюдает правила кита «English-only / stay generic».
> Не коммитить в публичный репозиторий (держать вне git или добавить в `.gitignore`).
> CI leak-check (`git grep '/home/[a-z]+/work'`) и Cyrillic-scan этот файл не заденут, пока он
> не содержит внутренних идентификаторов и не попадает в tracked-поверхность кита.

Дата: 2026-07-26.

> **Статус реализации (2026-07-26):** P0 (§6.1 permissions+hooks для Qwen, §6.2 `port-to-qwen.py`) и
> P1 (§6.3 per-role модели, общий guard-скрипт для Claude+Qwen) — **реализованы**; §7.1 (pi MCP-bridge
> fallback) — **удалён**; сверх плана добавлен сквозной скилл `requirements-clarify` (подключён ко всем
> агентам). Матрица паритета (§11) описывает состояние *до* этих правок — по итогу Qwen стал first-class.

---

## 1. TL;DR

Кит архитектурно **здоров и хорошо продуман**: один источник правил (`AGENTS.md`), гейтированный
8-фазный пайплайн, data-driven ростер агентов (`config/pipeline.yaml`), многослойный enforcement,
сильный контент (агенты/команды/скиллы написаны в стиле show-don't-tell — это реально сильная
сторона). Верификатор `scripts/check-kit.sh` + CI дают нетривиальную для «инструкционного» проекта
гарантию целостности.

**Главная структурная проблема — Qwen Code.** Кит декларирует миссию «поднять слабую *открытую*
модель структурой + инструментами + гейтами», но именно Qwen получает **меньше всего структуры**:
только MCP + проза `AGENTS.md`. При этом Qwen Code — **самый Claude-совместимый** из всех открытых
харнессов (см. §4): он нативно принимает Claude-frontmatter агентов, имеет хуки с тем же контрактом
`exit 2 = block`, permissions с тем же синтаксисом `Bash(...)`, скиллы и нативный plan-mode. Кит
портирует агентов/команды в pi и opencode, но **не в Qwen** — хотя портировать туда проще всего.

Вердикт: **«подключить Qwen и идти делать задачи» — функционально да** (MCP + проза + команды-как-runbooks
достаточно, чтобы вручную прогнать пайплайн), **но это второсортный режим**: не будет автоделегирования
на фазовых агентов, не будет slash-команд `/spec … /pr`, не будет скиллов, и — критично для автономного
YOLO-режима — **не будет mid-session enforcement** (защита срабатывает только на `git commit`).

Приоритеты: **P0** — сделать Qwen first-class (портер + permissions + хуки); **P1** — вынести guard-скрипт
в общий для Claude и Qwen, добавить per-role модели для Qwen; **P2** — убрать лишний fallback, добавить
`/goal`-оркестрацию. Убирать в ките почти нечего — он компактен.

---

## 2. Что проверено (методология)

Прочитаны первоисточники, а не только README:

- `README.md`, `KIT-DEV.md`, `FLOW.md`, `CONTRIBUTING.md`, `INSTALL.md` (частично).
- `setup.sh` (полностью — вся логика bootstrap/backup/uninstall и ветка `qwen`).
- `config/pipeline.yaml`, `config/security-policy.yaml`.
- `.mcp.json`, `.claude/settings.json` (permissions + hooks).
- `.claude/hooks/format-and-guard.sh`, `.githooks/pre-commit` (слой enforcement).
- `.claude/agents/engineer.md`, `.claude/commands/spec.md`, `.claude/skills/serena-first/SKILL.md`,
  `.claude/rules/go-layers.md` (репрезентативные экземпляры контента).
- `agents-config/qwen/.qwen/{settings.json,.env.example}` (вся Qwen-обвязка).
- `scripts/check-kit.sh`, `.github/workflows/ci.yml`.
- **Qwen Code ground truth**: глобальный `~/.qwen/settings.json` на этой машине + официальная
  документация Qwen Code (`sub-agents.md`, `commands.md`, `hooks.md`) — чтобы рекомендации опирались
  на реальные конвенции, а не догадки (принцип кита «verify before claim»).

---

## 3. Что сделано хорошо (сильные стороны)

1. **Контент — главный актив.** `engineer.md`, `spec.md`, `serena-first/SKILL.md` написаны образцово:
   обязательное напоминание фазы + Definition-of-Done вверху, нумерованный workflow, конкретные
   tool-call рецепты (`get_symbols_overview → find_symbol → find_referencing_symbols → replace_symbol_body`),
   живые Go-примеры «❌/✅». Это именно то, что нужно слабой модели (копирует паттерны лучше, чем
   рассуждает из абстракций).
2. **Один источник — много харнессов.** `AGENTS.md` каноничен; `CLAUDE.md` — shim `@AGENTS.md`;
   вложенный `AGENTS.md` для per-service (nearest-wins). Правило выдержано.
3. **Data-driven ростер.** `config/pipeline.yaml` + единственный парсер `scripts/pipeline_config.py`
   (без PyYAML, stdlib) — импортируется портерами и shell-скриптами. Анти-drift правило соблюдено:
   парсинг YAML не дублируется. Механизм `.md → .md.disabled` — изящный, обратимый, git-legible,
   fail-open.
4. **Многослойный enforcement.** prose → Claude `settings.json` (permissions + hooks) → `.githooks/pre-commit`
   + CI. `security-policy.yaml` — человекочитаемый источник, синхронизированный с хуком и `AGENTS.md §8`.
5. **Обратимость setup.** Манифест + бэкапы + `--uninstall` (с корректным reverse-order restore),
   `.env` никогда не трекается. Зрелая инженерия.
6. **Верификатор = тест-сьют.** `check-kit.sh` проверяет структуру, JSON, frontmatter, English-only,
   консистентность pipeline-конфига, синтаксис портеров и workflow. CI добавляет leak-check. Для
   «инструкционного» проекта это выше среднего.
7. **Разделение ядра и опций.** Тяжёлый graph-engine вынесен в `docs/optional-graph-engine.md`
   (не ядро); `rlm` — utility, а не фаза. Хорошая гигиена скоупа.

---

## 4. Ключевая проблема: Qwen — второсортный харнесс (с доказательствами)

### 4.1 Что Qwen Code умеет на самом деле (подтверждено)

Из официальной документации Qwen Code и глобального `~/.qwen/settings.json`:

| Возможность | Поддержка в Qwen Code | Следствие для кита |
|---|---|---|
| **Агенты** | `.qwen/agents/*.md` (project, высший приоритет), `~/.qwen/agents/` (user). **Принимает Claude Code 2.1.168 frontmatter** (`permissionMode`, `maxTurns`, `color`, `mcpServers`, `hooks`). `model: inherit\|fast\|<id>`, `approvalMode`, `tools`/`disallowedTools`. | `.claude/agents/*.md` портируются почти копированием. Не поддерживается пока только поле `skills` (dropped at parse). |
| **Команды** | Кастомные slash-команды `.qwen/commands/*.md`, `$ARGUMENTS`/`$1`. | `.claude/commands/*.md` портируются напрямую. |
| **Скиллы** | Нативная система: `.qwen/skills/<name>/SKILL.md`, `/skills`, `/<skill-name>`. | `.claude/skills/*` портируются напрямую. |
| **Хуки** | `settings.json` → `hooks.PreToolUse/PostToolUse/...`, тип `command`, **`exit 2` = blocking error (stderr → модели)** — тот же контракт, что у Claude. Поля входа `tool_input.file_path` / `tool_input.command`. | **Тот же `format-and-guard.sh` работает без переписывания** — нужны только матчеры под id инструментов Qwen. |
| **Permissions** | `permissions.allow/ask/deny` с синтаксисом `Bash(...)`, `Read(...)`, `Edit(...)`, `Write(...)` — идентично Claude (подтверждено реальным `~/.qwen/settings.json`). | Блок `permissions` из `.claude/settings.json` переносится в Qwen почти 1-в-1. |
| **Plan mode** | Нативный `approvalMode: plan` (per-session и per-agent). | Аналог `@pi-vault/pi-plan` для pi — но для Qwen бесплатно, из коробки. |
| **Автономия** | `/goal <condition>` (работать, пока условие не выполнено), `/fork`, background-агенты, `cron`/`loop`. | Прямое попадание в сценарий длинных автономных сессий; кит это не использует. |
| **Context-файлы** | `context.fileName` — работает (эта сессия загрузила и `AGENTS.md`, и `QWEN.md`). | Обвязка кита `context.fileName: ["AGENTS.md","QWEN.md"]` корректна. |

### 4.2 Что кит реально даёт Qwen сегодня

Вся Qwen-обвязка — это `agents-config/qwen/.qwen/`:

- `settings.json`: `context.fileName` + 6 MCP-серверов (serena, atlassian, context7,
  sequential-thinking, git, fetch). **Всё.**
- `.env.example`: OpenAI-совместимый эндпоинт + заметка «source ../../.env».

**Нет:** агентов, команд, скиллов, хуков, блока `permissions`. В `setup.sh` ветка `qwen` делает
только `track_copy settings.json` + `.env`. Портера для Qwen нет (есть только `pi/port-agents.py`
и `opencode/port-to-opencode.py`). В `scripts/` — только `apply-pipeline.sh`, `check-kit.sh`,
`pipeline_config.py`.

### 4.3 Почему это проблема именно для кита

Миссия кита — «заставить слабую открытую модель писать качественно, дав ей **структуру + инструменты
+ гейты**». Из трёх опор Qwen получает в полной мере только **инструменты** (MCP). **Структура**
(фазовые агенты с автоделегированием) и **гейты** (команды + enforcement) для Qwen отсутствуют —
остаётся только проза `AGENTS.md`, которую слабая модель следует хуже, чем явным подпромптам агентов.

Парадокс: pi (заявлен primary) и opencode получают сгенерированных агентов/команд, а Qwen — нет,
хотя Qwen портировать **легче** (CC-совместимость). Фактически Qwen поставлен в один ряд с Crush
(prose-only), при том что по возможностям он ближе к Claude.

---

## 5. Чего не хватает (приоритизировано)

### P0 — блокирует полноценную работу Qwen

1. **Нет first-class харнесса для Qwen.** Нужен `agents-config/qwen/port-to-qwen.py`, генерирующий
   `.qwen/{agents,commands,skills}/` из `.claude/` (по образцу `port-to-opencode.py`), с:
   - дропом неподдерживаемого поля `skills:` из frontmatter агентов и **добавлением ранбуков скиллов
     в тело агента футером** (как это делает opencode-портер);
   - маппингом `model: inherit` (работает нативно) и опционально `fast` для лёгких агентов;
   - конверсией `$1` → `$ARGUMENTS` для команд (если требуется);
   - интеграцией в `setup.sh qwen`, `scripts/apply-pipeline.sh` (skip disabled) и `check-kit.sh`
     (сверка числа активных агентов с `pipeline.yaml`).
2. **Нет `permissions` в Qwen `settings.json`.** Сейчас Qwen работает с тем, что задано в глобальном
   `~/.qwen/settings.json` (у пользователя — `yolo` + allow-all). Значит, deny-правила кита
   (не редактировать `sqlc/`, `mocks/`, `gen/`, `*.pb.go`; не читать `.env`) **не действуют на уровне
   инструментов** для Qwen — только проза + commit-time guard.
3. **Нет хуков в Qwen `settings.json`.** Для автономного YOLO-агента это главный риск: он может
   руками править сгенерированный код или выполнить деструктивную команду **внутри сессии**, и это
   поймается только на `git commit` (или никогда, если коммита нет). У Claude это блокируется
   PreToolUse-хуком мгновенно.

### P1 — существенно улучшает качество/безопасность

4. **Guard-логика раздвоена и неравномерна.** `format-and-guard.sh` написан под Claude-матчеры
   (`Edit|Write|MultiEdit`, `Bash`) и живёт только в `.claude/hooks/`. Тот же скрипт **уже совместим**
   с Qwen (контракт `exit 2`, поля `tool_input.file_path`/`tool_input.command`), но не подключён.
   Стоит вынести его в общее место (например, `scripts/guard.sh` или оставить один файл, на который
   ссылаются оба харнесса) и подключить в Qwen с матчерами под id инструментов Qwen.
5. **Per-role модели только для pi.** `agents-config/pi/subagent-config.json` мапит разные модели на
   разные роли (сильная — на plan/review, быстрая — на implement). Для Qwen это доступно нативно
   (`model:` во frontmatter + селектор `fast` + `fastModel` в settings) — но не используется.
6. **Слабый commit-time guard по partial structs.** `.githooks/pre-commit` блокирует только литералы
   с маркерами `TODO|FIXME|partial` — реальная partial-struct без маркера пройдёт. Это эвристика, и
   она честно названа таковой, но для open-агентов это единственный рубеж — стоит усилить (хотя бы
   документировать ограничение + оставить на ревьюера).

### P2 — гигиена и гибкость

7. **Нет шаблона `QWEN.md` в ките.** Qwen `settings.json` ссылается на `QWEN.md` через `context.fileName`,
   но кит не поставляет шаблона `QWEN.md` (в отличие от `templates/*` для фаз). Мелкий пробел.
8. **`/goal`-оркестрация не описана.** Для Qwen нативный `/goal` — идеальный способ гнать фазы
   автономно; кит это не документирует и не использует.
9. **`.env.example` для Qwen перекошен в self-hosted** (`http://localhost:8000/v1`). Работает с любым
   OpenAI-совместимым провайдером, но примеры стоит расширить hosted-вариантом (z.ai / Together /
   Aliyun-compatible), чтобы не создавать впечатления «только локальный сервер».

---

## 6. Что стоит добавить (конкретно)

### 6.1 Qwen `settings.json`: permissions + hooks (P0)

Добавить в `agents-config/qwen/.qwen/settings.json` (синтаксис подтверждён реальным Qwen-конфигом):

```jsonc
{
  "context": { "fileName": ["AGENTS.md", "QWEN.md"] },
  "permissions": {
    "allow": [
      "Bash(task fmt:*)", "Bash(task lint:*)", "Bash(task test:*)",
      "Bash(task sqlc:*)", "Bash(task mocks:*)", "Bash(task gen:*)",
      "Bash(go test:*)", "Bash(go build:*)", "Bash(go vet:*)",
      "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)",
      "Bash(grep:*)", "Bash(rg:*)"
    ],
    "ask": [
      "Bash(git push:*)", "Bash(git commit:*)", "Bash(git reset --hard:*)",
      "Bash(task db:migrate:*)", "Bash(go get:*)", "Bash(gh pr merge:*)",
      "Bash(kubectl delete:*)", "Bash(terraform apply:*)"
    ],
    "deny": [
      "Read(./.env)", "Read(./**/.env)",
      "Edit(**/repository/postgres/sqlc/**)", "Edit(**/mocks/**)", "Edit(**/gen/**)",
      "Edit(**/*.pb.go)", "Edit(**/*_gen.go)",
      "Write(**/repository/postgres/sqlc/**)", "Write(**/mocks/**)", "Write(**/gen/**)"
    ]
  },
  "hooks": {
    "PreToolUse": [
      { "matcher": "(edit|write_file)",
        "hooks": [{ "type": "command", "command": "bash .claude/hooks/format-and-guard.sh pre-edit", "timeout": 10 }] },
      { "matcher": "run_shell_command",
        "hooks": [{ "type": "command", "command": "bash .claude/hooks/format-and-guard.sh pre-bash", "timeout": 10 }] }
    ],
    "PostToolUse": [
      { "matcher": "(edit|write_file)",
        "hooks": [{ "type": "command", "command": "bash .claude/hooks/format-and-guard.sh post-edit", "timeout": 30 }] }
    ]
  },
  "mcpServers": { /* …без изменений… */ }
}
```

Замечания:
- Матчеры Qwen используют **id инструментов** (`edit`, `write_file`, `run_shell_command`); display-имена
  (`Edit`, `Write`, `Bash`) принимаются как алиасы, но новые конфиги должны использовать id.
- Контракт `exit 2 = block` у Qwen идентичен Claude — `format-and-guard.sh` **переиспользуется без правок**.
- `hooks` в Qwen поддерживают также тип `prompt` (LLM-оценка) — можно позже сделать «умный» guard,
  но для старта достаточно command-хуков.

### 6.2 `agents-config/qwen/port-to-qwen.py` (P0)

По образцу `agents-config/opencode/port-to-opencode.py`:

- читает `config/pipeline.yaml` через общий `scripts/pipeline_config.py` (skip disabled — анти-drift);
- `.claude/agents/<name>.md` → `.qwen/agents/<name>.md`: frontmatter почти 1-в-1 (`name`, `description`,
  `tools`, `model`), поле `skills:` удаляется, ранбуки скиллов добавляются футером тела; опционально
  `approvalMode: plan` для `go-code-reviewer` (read-only ревью — нативный аналог pi-plan);
- `.claude/commands/<name>.md` → `.qwen/commands/<name>.md` (`$1` → `$ARGUMENTS`);
- `.claude/skills/<name>/SKILL.md` → `.qwen/skills/<name>/SKILL.md`;
- печатает список созданных файлов (для `track_created` в `setup.sh`).

Интеграция: `setup.sh qwen` вызывает портер; `apply-pipeline.sh` пере-портирует при reconcile;
`check-kit.sh` сверяет число `.qwen/agents/*.md` с enabled-счетом (если `.qwen/` существует).

### 6.3 Общий guard + per-role модели (P1)

- Зафиксировать один guard-скрипт как общий источник (сейчас это `.claude/hooks/format-and-guard.sh`;
  можно оставить его, просто начав ссылаться из Qwen-хуков — без переноса, чтобы не ломать Claude-пути).
- В Qwen-агентах проставить `model:` по ролям: `go-code-reviewer`/`planner`/`tech-designer` → сильная
  модель, `engineer`/`qa-lead` → `fast`. Это даёт ту же экономию, что pi `subagent-config.json`.

### 6.4 Мелочи (P2)

- Положить `templates/qwen-template.md` (или генерировать `QWEN.md` из `AGENTS.md` shim-ом, как
  `CLAUDE.md`), чтобы `context.fileName: QWEN.md` не ссылался в пустоту.
- Документировать `/goal`-сценарий для автономного прогона фаз в Qwen (раздел в `INSTALL.md`/`FLOW.md`).
- Расширить `.env.example` hosted-провайдерами.

---

## 7. Что стоит убрать / упростить

Кит компактен, «жира» почти нет. Кандидаты:

1. **Hand-rolled pi MCP bridge (`agents-config/pi/mcp-extension/`) — УДАЛЁН (выполнено 2026-07-26).**
   Был *disabled* fallback при `pi-mcp-adapter`; дополнительная поверхность (TS-исходники, `package.json`,
   README), которая по умолчанию не используется. Убран вместе со всеми ссылками (setup.sh, KIT-DEV,
   README, INSTALL, readme-ru, .gitignore, pi/README, pi/mcp.json) — остался только `pi-mcp-adapter`.
2. **Дублирование deny-правил в трёх местах** (`security-policy.yaml` ↔ `.claude/settings.json` ↔
   `AGENTS.md §8`) — это *осознанная* избыточность (текст = контекст, конфиг = enforcement), её не
   «убирать», а **расширить на Qwen** (см. §6.1), чтобы триада стала тетрадой.

Больше убирать нечего — риск «переусложнения» у кита низкий.

---

## 8. Достаточно ли гибкости?

**Сильные стороны гибкости:**
- Ростер агентов — данные (`pipeline.yaml`), обратимо, fail-open, git-legible.
- Per-role модели (pi), read-only Atlassian-профиль одной env-переменной, security-policy как
  централизованный источник.
- Опциональный graph-engine и `rlm` отделены от ядра.
- Выбор агента при setup, обратимый `--uninstall`.

**Слабые стороны гибкости:**
- **Паритет харнессов неравномерный.** Гибкость «один источник — много харнессов» реализована для
  Claude/pi/opencode и **не реализована для Qwen/Crush**. Обещание выполнено примерно на 60%.
- **Enforcement Claude-центричен.** Открытые агенты получают только commit-time guard. Для автономного
  YOLO (ваш режим) это главный пробел гибкости/безопасности.
- **Per-role модели только для pi** — для Qwen доступно нативно, но не задействовано.
- **Оркестрация автономных фаз** (`/goal`, background-агенты, cron) не документирована — а это именно
  то, что нужно для длинных автономных сессий.

Вывод: гибкости **достаточно для ручного/полуавтономного прогона**, но **недостаточно для безопасной
полной автономии на Qwen** — пока не добавлены permissions + хуки (§6.1).

---

## 9. Готовность «подключить Qwen Code и идти делать задачи»

### Что работает уже сегодня

- **MCP:** Serena/Atlassian/context7/sequential-thinking/git/fetch сконфигурированы в
  `agents-config/qwen/.qwen/settings.json`. После `./setup.sh qwen` + заполнения `.qwen/.env`
  (и `source .env` для `${VAR}`) — работают.
- **Инструкции:** `context.fileName: ["AGENTS.md","QWEN.md"]` загружает канон (подтверждено: эта сессия
  видит оба файла).
- **Команды как ранбуки:** `.claude/commands/*.md` явно написаны как исполняемые вручную ранбуки
  («any agent … can execute the numbered steps by hand») — можно копировать шаги в Qwen.
- **Commit-time guard:** `.githooks/pre-commit` (после `git config core.hooksPath .githooks`) ловит
  generated-code/`.env`/Cyrillic на коммите.

### Чего не хватает для комфортной/безопасной работы

- Нет автоделегирования на фазовых агентов (их нет в `.qwen/agents/`) — фазы придётся запускать руками.
- Нет `/spec … /pr` (нет `.qwen/commands/`) — вставлять ранбуки вручную.
- Нет скиллов (`/serena-first` и пр.) — держать рецепты в голове/контексте.
- **Нет mid-session enforcement** (permissions + хуки) — в YOLO агент ничем не остановлен до коммита.

### Минимальный путь к продуктивности

- **Прямо сейчас (без доработок кита):** `./setup.sh qwen` → заполнить `.qwen/.env` + `source .env`
  → `git config core.hooksPath .githooks` → гнать фазы вручную по ранбукам `.claude/commands/*.md`,
  опираясь на `AGENTS.md`. Работоспособно, но «на ручном приводе».
- **После P0 (§6.1–6.2):** полноценный first-class Qwen — автоделегирование, slash-команды, скиллы,
  permissions и хуки. Это превращает Qwen из второго сорта в равный Claude/pi/opencode харнесс.

---

## 10. Рекомендуемый план действий

1. **(P0)** Добавить `permissions` + `hooks` в `agents-config/qwen/.qwen/settings.json` (§6.1) —
   переиспользует существующий `format-and-guard.sh`, закрывает главный риск автономии.
2. **(P0)** Написать `agents-config/qwen/port-to-qwen.py` (§6.2) по образцу opencode-портера;
   интегрировать в `setup.sh` / `apply-pipeline.sh` / `check-kit.sh`.
3. **(P1)** Проставить per-role `model:`/`approvalMode` в Qwen-агентах (§6.3).
4. **(P1)** Документировать ограничение commit-time partial-struct guard; оставить финальный контроль
   на `go-code-reviewer`.
5. **(P2)** Шаблон `QWEN.md`, `/goal`-оркестрация, hosted-провайдеры в `.env.example` (§6.4).
6. **(P2)** ~~Решить судьбу pi MCP-bridge fallback (§7.1)~~ — **выполнено: удалён** (2026-07-26).

Каждый пункт следует правилам кита: править канон в `.claude/` → регенерировать → `bash scripts/check-kit.sh`.

---

## 11. Приложение: матрица паритета харнессов

| Возможность | Claude | pi | opencode | **Qwen** | Crush |
|---|:--:|:--:|:--:|:--:|:--:|
| Канон правил (`AGENTS.md`) | ✅ (shim) | ✅ | ✅ | ✅ | ✅ |
| MCP | ✅ | ✅ (adapter) | ✅ | ✅ | ✅ |
| Фазовые агенты (автоделегирование) | ✅ | ✅ (gen) | ✅ (gen) | ❌ | ❌ |
| Slash-команды `/spec…/pr` | ✅ | ✅ (`/run`,`/chain`) | ✅ (gen) | ❌ (ранбуки) | ❌ (ранбуки) |
| Скиллы | ✅ | ✅ | ⚠ (футер) | ❌ | ❌ |
| Permissions (deny generated/.env) | ✅ | ⚠ (пакеты) | ⚠ | ❌ | ❌ |
| Mid-session хуки (guard) | ✅ | ⚠ | ⚠ | ❌ | ❌ |
| Commit-time guard (`.githooks`) | ✅ | ✅ | ✅ | ✅ | ✅ |
| Per-role модели | ✅ | ✅ | ⚠ | ❌ | ❌ |
| Read-only plan-mode | ✅ | ✅ (pi-plan) | ⚠ | ❌ (нативно доступен) | ❌ |

**Легенда:** ✅ полноценно · ⚠ частично/обход · ❌ отсутствует.

**Чтение матрицы:** Qwen — единственный харнесс, который при полной Claude-совместимости (агенты,
хуки, permissions, скиллы, plan-mode доступны нативно) остаётся на уровне prose-only Crush. Это и есть
главный вывод ревью: **самый дешёвый и самый impactful апгрейд кита — сделать Qwen first-class.**
