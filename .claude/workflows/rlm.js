export const meta = {
  name: 'rlm',
  description: 'Recursive Language Model solver (arXiv:2512.24601): decompose a too-big task, delegate each independent piece to a fresh sub-solver, aggregate. Bounded depth/fanout/budget. Read-only.',
  phases: [
    { title: 'RLM', detail: 'recursive decompose → delegate → aggregate' },
  ],
}

// --- inputs (Workflow args) ---------------------------------------------------
// Pass: { task: "<the big task>", maxDepth?: 3, fanout?: 5, maxNodes?: 40 }
const TASK = args && (typeof args === 'string' ? args : args.task)
const MAX_DEPTH = (args && args.maxDepth) || 3
const FANOUT = (args && args.fanout) || 5
const MAX_NODES = (args && args.maxNodes) || 40
const BUDGET_FLOOR = 60_000 // stop decomposing when fewer output tokens than this remain

if (!TASK) {
  log('rlm: no task provided — pass args.task (a string) or args = "<task>"')
  return { error: 'no task provided' }
}

// Each node decides: solve directly, or decompose into independent subtasks.
const NODE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  properties: {
    mode: { type: 'string', enum: ['solve', 'decompose'] },
    result: { type: 'string', description: 'concise, cited answer — required when mode=solve' },
    subtasks: {
      type: 'array',
      items: { type: 'string' },
      description: '2..fanout INDEPENDENT subtasks, each over a snippet of the context — required when mode=decompose',
    },
  },
  required: ['mode'],
}

let nodes = 0
let idSeq = 0

// Recursive solver: one fresh agent() per node. This IS the recursion — a node that decomposes
// awaits fresh child nodes (in parallel) before aggregating their results.
async function solve(task, depth) {
  const id = ++idSeq
  nodes++
  const lowBudget = budget.total ? budget.remaining() < BUDGET_FLOOR : false
  const mustSolve = depth <= 0 || nodes >= MAX_NODES || lowBudget

  const decision = await agent(
    `You are an RLM node (depth=${depth}, max fanout=${FANOUT}). You are READ-ONLY: read/grep/analyze, never edit.\n` +
      `TASK:\n${task}\n\n` +
      (mustSolve
        ? `Depth or budget is exhausted — you MUST solve directly now: set mode="solve" and put a concise, source-cited answer (file:line / ticket / URL) in "result". Read only what you need.`
        : `If this fits ONE focused read-only pass (small/atomic, single sub-goal), set mode="solve" with a concise cited answer in "result".\n` +
          `Otherwise set mode="decompose" and list 2-${FANOUT} INDEPENDENT subtasks — each scoped to a snippet of the context (one service / file-group / chunk / question), none depending on another's output. Keep any dependent chain inside a single subtask.`),
    { schema: NODE_SCHEMA, label: `rlm#${id} d${depth}`, phase: 'RLM' },
  )

  if (!decision) return null
  if (decision.mode === 'solve' || mustSolve || !decision.subtasks || decision.subtasks.length === 0) {
    return decision.result || '(no result)'
  }

  const subs = decision.subtasks.slice(0, FANOUT)
  const kids = await parallel(
    subs.map((st) => () => solve(st, depth - 1).then((r) => ({ st, r }))),
  )
  const lines = kids
    .filter(Boolean)
    .map((k) => `- SUBTASK: ${k.st}\n  RESULT: ${k.r}`)
    .join('\n')

  return agent(
    `Aggregate these sub-results into ONE coherent answer to the task. Reconcile overlaps, remove duplicates, resolve contradictions, keep every source citation. Do NOT just concatenate.\n\n` +
      `TASK:\n${task}\n\nSUB-RESULTS:\n${lines}`,
    { label: `rlm#${id} aggregate d${depth}`, phase: 'RLM' },
  )
}

phase('RLM')
log(`rlm: solving (maxDepth=${MAX_DEPTH}, fanout=${FANOUT}, maxNodes=${MAX_NODES})`)
const answer = await solve(TASK, MAX_DEPTH)
log(`rlm: done — ${nodes} node(s) spawned`)
return { task: TASK, answer, nodesSpawned: nodes }
