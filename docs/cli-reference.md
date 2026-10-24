# Hermes CLI reference (Hermes Agent v0.21.5+6841.g8b66a51, captured 2026-10-24)

## Observed behaviour (probed against the real CLI, 2026-10-24)

Help text gives flag shapes only. These are the state rules the bridge must respect,
verified on a throwaway `bridge-dev` task:

| Command | From | Result |
|---|---|---|
| `create --initial-status running` | — | lands in **ready** (no claim is made; `running` only means "not blocked") |
| `claim` | ready | running, opens a run |
| `request-review --summary` | running / ready | review, run closed |
| `request-changes <reason>` | review | **fails**: `task is not in an active review run` — only valid while a reviewer run claimed *from review* is active |
| `request-changes <reason>` | running (not claimed from review) | fails: `active run was not claimed from review` |
| `reopen-review --reason` | review | ready (or todo while parents are open); reason stored as `CHANGES REQUESTED:` comment |
| `complete` with no `--result` | ready / running | fails: `completion blocked: … no result or summary evidence` (review approvals are exempt) |
| `complete` | running with a live worker | fails: `a live worker is running it` unless `--force` |
| `unblock` | blocked | the phase it was blocked from (ready / review), or todo while parents are open |
| `block <reason>` | ready / running | blocked; reason stored as `BLOCKED:` comment |

- Free-text positionals starting with `-` are parsed as flags; `--` before them works on every verb.
- `--body-file` is the documented way to pass bodies with flag-like lines.
- Without `--author`, comments are attributed to `$HERMES_PROFILE` (here `default`).
- Without `--board` / `HERMES_KANBAN_BOARD`, commands hit the *current* board (`hermes kanban boards switch`).

## `hermes` --help

```
usage: hermes [-h] [--version] [-z PROMPT] [--usage-file PATH] [-m MODEL]
              [--provider PROVIDER] [--reasoning LEVEL] [-t TOOLSETS]
              [--resume SESSION] [--no-restore-cwd] [--in DIR]
              [--continue [SESSION_NAME]] [--worktree] [--accept-hooks]
              [--skills SKILLS] [--yolo] [--pass-session-id]
              [--ignore-user-config] [--ignore-rules] [--safe-mode] [--tui]
              [--native] [--cli] [--dev]
              <command> ...

Hermes Agent - AI assistant with tool-calling capabilities

positional arguments:
  <command>             Command to run
    chat                Interactive chat with the agent
    model               Select default model and provider
    moa                 Configure Mixture of Agents provider/model slots
    fallback            Manage fallback providers (tried when the primary
                        model fails)
    worktree            Audit and reclaim accumulated git worktrees and merged
                        branches
    browser             Real-profile browsing helpers (close a browser locking
                        its profile)
    secrets             Manage external secret sources (Bitwarden, 1Password)
    egress              Manage the iron-proxy egress credential-injection
                        firewall
    migrate             Migrate configuration for retired models or deprecated
                        settings
    codex-runtime       Manage the optional codex app-server runtime (migrate
                        MCP config)
    gateway             Messaging gateway management
    proxy               Local OpenAI-compatible proxy to OAuth providers
    lsp                 Language Server Protocol management
    setup               Interactive setup wizard
    whatsapp            Set up WhatsApp integration
    whatsapp-cloud      Set up WhatsApp Business Cloud API integration
    slack               Slack integration helpers (manifest generation, etc.)
    send                Send a message to a configured platform (scripts, cron
                        jobs, CI).
    logout              Clear authentication for an inference provider
    auth                Manage pooled provider credentials
    status              Show status of all components
    pause               Emergency stop: pause cron/kanban dispatch and new
                        gateway turns
    resume              Lift the emergency stop set by `hermes pause`
    cron                Cron job management
    webhook             Manage dynamic webhook subscriptions
    peer                Bot-to-bot DMs across machines (peer Hermes gateways)
    portal              Set up Nous Portal (login, model pick, Tool Gateway);
                        see also `portal info`
    kanban              Multi-profile collaboration board (tasks, links,
                        comments)
    project             Manage projects (named, multi-folder workspaces)
    hooks               Inspect and manage shell-script hooks
    doctor              Check configuration and dependencies
    verify              Detect a project's run recipe and smoke-test it
    security            Supply-chain audit (OSV.dev) for venv, plugins, and
                        MCP servers
    approvals           Approval-prompt tools (mine history into allowlist
                        proposals)
    dump                Dump setup summary for support/debugging
    debug               Debug tools — upload logs and system info for support
    backup              Back up Hermes home directory to a zip file
    checkpoints         Inspect / prune / clear ~/.hermes/checkpoints/
    import              Restore a Hermes backup from a zip file
    import-agent        Import a Claude Code or Codex CLI setup into Hermes
    config              View and edit configuration
    skin                List, switch, and tweak skins
    console             Open the safe Hermes command console
    pairing             Manage DM pairing codes for user authorization
    skills              Search, install, configure, and manage skills
    bundles             Create, list, and manage skill bundles (aliases for
                        multiple skills)
    plugins             Manage and validate plugins
    curator             Background skill maintenance (curator) — status, run,
                        pause, pin
    pets                Browse, install, and select petdex animated pets
    journey (learning, memory-graph)
                        Timeline of learned skills + memories over time
    memory              Configure external memory provider
    tools               Configure which tools are enabled per platform
    computer-use        Manage the Computer Use (cua-driver) backend
                        (macOS/Windows/Linux)
    mcp                 Manage MCP servers and run Hermes as an MCP server
    sessions            Manage session history (list, rename, export, prune,
                        delete)
    insights            Show usage insights and analytics
    usage               Show account rate-limit windows (the /usage block)
                        without starting a session
    monitoring          Inspect gateway monitoring (health & diagnostics
                        export)
    claw                OpenClaw migration tools
    vault               Manage the local encrypted autofill vault (add/list/rm
                        credentials)
    update              Update Hermes Agent to the latest version
    uninstall           Uninstall Hermes Agent
    acp                 Run Hermes Agent as an ACP (Agent Client Protocol)
                        server
    profile             Manage profiles — multiple isolated Hermes instances
    completion          Print shell completion script (bash, zsh, or fish)
    dashboard           Start the web UI dashboard
    serve               Start the Hermes backend server (headless; powers the
                        desktop app and remote backends)
    desktop (gui)       Build and launch the native desktop app
    logs                View and filter Hermes log files
    prompt-size         Show a byte breakdown of the system prompt + tool
                        schemas

options:
  -h, --help            show this help message and exit
  --version, -V         Show version and exit
  -z, --oneshot PROMPT  One-shot mode: send a single prompt and print ONLY the
                        final response text to stdout. No banner, no spinner,
                        no tool previews, no session_id line. Tools, memory,
                        rules, and AGENTS.md in the CWD are loaded as normal;
                        approvals are auto-bypassed. Intended for scripts /
                        pipes.
  --usage-file PATH     One-shot mode only: after the run, write a JSON usage
                        report (estimated cost, token counts, model,
                        api_calls) to PATH. The report is written even when
                        the run fails, so pipelines can always account for
                        spend. No effect outside -z/--oneshot.
  -m, --model MODEL     Model override for this invocation (e.g.
                        anthropic/claude-sonnet-4.6). Applies to -z/--oneshot
                        and --tui. Also settable via HERMES_INFERENCE_MODEL
                        env var.
  --provider PROVIDER   Provider override for this invocation (e.g.
                        openrouter, anthropic). Applies to -z/--oneshot and
                        --tui. The persistent provider lives in config.yaml
                        under model.provider — use `hermes setup` or edit the
                        file to change it.
  --reasoning LEVEL     Reasoning effort for this invocation: none, minimal,
                        low, medium, high, xhigh, max, or ultra. Overrides
                        agent.reasoning_effort in config.yaml for this run
                        only; the persistent level lives there (or per-model
                        under agent.reasoning_overrides).
  -t, --toolsets TOOLSETS
                        Comma-separated toolsets to enable for this
                        invocation. Applies to -z/--oneshot and --tui.
  --resume, -r SESSION  Resume a previous session by ID or title, or pass
                        'latest' for the most recent session (workspace-
                        scoped, like -c with no name)
  --no-restore-cwd      Don't cd into a resumed session's recorded working
                        directory.
  --in DIR              Change into DIR before starting or resuming. Combined
                        with '--resume latest' or -c, the most recent session
                        for DIR's workspace is picked, and the session stays
                        in DIR (skips the recorded-cwd restore).
  --continue, -c [SESSION_NAME]
                        Resume a session by name, or the most recent if no
                        name given
  --worktree, -w        Run in an isolated git worktree (for parallel agents)
  --accept-hooks        Auto-approve any unseen shell hooks declared in
                        config.yaml without a TTY prompt. Equivalent to
                        HERMES_ACCEPT_HOOKS=1 or hooks_auto_accept: true in
                        config.yaml. Use on CI / headless runs that can't
                        prompt.
  --skills, -s SKILLS   Preload one or more skills for the session (repeat
                        flag or comma-separate)
  --yolo                Bypass all dangerous command approval prompts (use at
                        your own risk)
  --pass-session-id     Include the session ID in the agent's system prompt
  --ignore-user-config  Ignore ~/.hermes/config.yaml and fall back to built-in
                        defaults (credentials in .env are still loaded)
  --ignore-rules        Skip auto-injection of AGENTS.md, SOUL.md,
                        .cursorrules, memory, and preloaded skills
  --safe-mode           Troubleshooting mode: disable ALL customizations —
                        user config, AGENTS.md/memory injection, plugins, and
                        MCP servers (implies --ignore-user-config and
                        --ignore-rules)
  --tui                 Launch the modern TUI instead of the classic REPL
  --native, --tui-native
                        With --tui: use native terminal scrollback and disable
                        mouse tracking
  --cli                 Force the classic prompt_toolkit REPL (overrides
                        display.interface=tui)
  --dev                 With --tui: run TypeScript sources via tsx (skip dist
                        build)

Examples:
    hermes                        Start interactive chat
    hermes chat -q "Hello"        Single query mode
    hermes --tui                  Launch the modern TUI (or set display.interface: tui)
    hermes --cli                  Force the classic REPL (overrides display.interface: tui)
    hermes -c                     Resume the most recent session
    hermes -c "my project"        Resume a session by name (latest in lineage)
    hermes --resume <session_id>  Resume a specific session by ID
    hermes --resume latest        Resume the most recent session (same as -c)
    hermes --tui --resume latest --in ./dir   Resume ./dir's latest session in the TUI
    hermes setup                  Run setup wizard
    hermes logout                 Clear stored authentication
    hermes auth add <provider>    Add a pooled credential
    hermes auth list              List pooled credentials
    hermes auth remove <p> <t>    Remove pooled credential by index, id, or label
    hermes auth reset <p> [t]     Clear exhaustion status for a provider, or one credential
    hermes auth priority <p> <t> <n>  Move a pooled credential to priority n (0 = tried first)
    hermes auth refresh <p> [t]   Refresh a pooled OAuth credential and clear its cooldown
    hermes model                  Select default model
    hermes fallback [list]        Show fallback provider chain
    hermes fallback add           Add a fallback provider (same picker as `hermes model`)
    hermes fallback remove        Remove a fallback provider from the chain
    hermes config                 View configuration
    hermes config edit            Edit config in $EDITOR
    hermes config set model gpt-4 Set a config value
    hermes gateway                Run messaging gateway
    hermes gateway install        Install gateway background service
    hermes gateway start          Start the installed gateway service
    hermes gateway stop           Stop the gateway service
    hermes gateway status         Show gateway status
    hermes -p <profile> <cmd>     Run any command against a named profile's
                                  home (also --profile) — e.g. hermes -p coder gateway stop
    hermes -s hermes-agent-dev,github-auth
    hermes -w                     Start in isolated git worktree
    hermes sessions list          List past sessions
    hermes sessions browse        Interactive session picker
    hermes sessions rename ID T   Rename/title a session
    hermes logs                   View agent.log (last 50 lines)
    hermes logs -f                Follow agent.log in real time
    hermes logs errors            View errors.log
    hermes logs --since 1h        Lines from the last hour
    hermes debug share             Upload debug report for support
    hermes console                Open the safe Hermes command console
    hermes update                 Update to latest version
    hermes dashboard              Start web UI dashboard (port 9119)
    hermes dashboard --stop       Stop running dashboard processes
    hermes dashboard --status     List running dashboard processes

For more help on a command:
    hermes <command> --help
```

## `hermes kanban` --help

```
usage: hermes kanban [-h] [--board <slug>]
                     {init,boards,create,swarm,list,ls,show,assign,set-model,reclaim,reassign,diagnostics,diag,link,unlink,claim,comment,attach,attachments,attach-rm,complete,edit,block,schedule,unblock,request-review,request-changes,reopen-review,promote,archive,tail,dispatch,daemon,watch,stats,notify-subscribe,notify-list,notify-unsubscribe,log,runs,heartbeat,assignees,context,specify,decompose,gc,repair} ...

Durable SQLite-backed task board shared across Hermes profiles. Tasks are
claimed atomically, can depend on other tasks, and are executed by a named
profile in an isolated workspace. See https://hermes-
agent.nousresearch.com/docs/user-guide/features/kanban.

positional arguments:
  {init,boards,create,swarm,list,ls,show,assign,set-model,reclaim,reassign,diagnostics,diag,link,unlink,claim,comment,attach,attachments,attach-rm,complete,edit,block,schedule,unblock,request-review,request-changes,reopen-review,promote,archive,tail,dispatch,daemon,watch,stats,notify-subscribe,notify-list,notify-unsubscribe,log,runs,heartbeat,assignees,context,specify,decompose,gc,repair}
    init                Create kanban.db if missing (idempotent)
    boards              Manage kanban boards (one board per project /
                        workstream)
    create              Create a new task
    swarm               Create a Kanban Swarm v1 graph (parallel workers →
                        verifier → synthesizer)
    list (ls)           List tasks
    show                Show a task with comments + events
    assign              Assign or reassign a task
    set-model           Set or clear a task's model/provider override (takes
                        effect on the next dispatch)
    reclaim             Release an active worker claim on a running task
    reassign            Reassign a task to a different profile, optionally
                        reclaiming first
    diagnostics (diag)  List active diagnostics on the current board
    link                Add a parent->child dependency
    unlink              Remove a parent->child dependency
    claim               Atomically claim a ready task (prints resolved
                        workspace path)
    comment             Append a comment
    attach              Attach a local file to a task
    attachments         List a task's attachments
    attach-rm           Delete an attachment by id
    complete            Mark one or more tasks done
    edit                Edit task fields or recovery fields on an already-
                        completed task
    block               Mark one or more tasks blocked
    schedule            Park one or more tasks in Scheduled (waiting on time,
                        not human input)
    unblock             Return blocked/scheduled tasks to ready, or todo while
                        parents remain open
    request-review      Move a task to 'review' (implementation done, awaiting
                        review) — NOT a block
    request-changes     Reviewer verdict: return the active review run to its
                        implementer
    reopen-review       Send one or more review tasks back for changes (review
                        -> ready/todo)
    promote             Manually move one or more todo/blocked tasks to ready
                        (recovery path)
    archive             Archive one or more tasks
    tail                Follow a task's event stream
    dispatch            One dispatcher pass: reclaim stale, promote ready,
                        spawn workers
    daemon              DEPRECATED — dispatcher now runs in the gateway. Use
                        `hermes gateway start`.
    watch               Live-stream task_events to the terminal (Ctrl+C to
                        exit)
    stats               Per-status + per-assignee counts + oldest-ready age
    notify-subscribe    Subscribe a gateway source to a task's terminal events
                        (used by /kanban subscribe in the gateway adapter)
    notify-list         List notification subscriptions (optionally for a
                        single task)
    notify-unsubscribe  Remove a gateway subscription from a task
    log                 Print the worker log for a task (from <kanban-
                        root>/kanban/logs/)
    runs                Show attempt history for a task (one row per run:
                        profile, outcome, elapsed, summary)
    heartbeat           Emit a heartbeat event for a running task (worker
                        liveness signal)
    assignees           List known profiles + per-profile task counts (union
                        of ~/.hermes/profiles/ and current assignees on the
                        board)
    context             Print the full context a worker sees for a task (title
                        + body + parent results + comments).
    specify             Flesh out a triage-column task into a concrete spec
                        (title + body) and promote it to todo. Uses the
                        auxiliary LLM configured under
                        auxiliary.triage_specifier.
    decompose           Decompose a triage-column task into a graph of child
                        tasks routed to specialist profiles by description.
                        Falls back to specify-style single-task promotion when
                        the task doesn't benefit from fan-out. Uses
                        auxiliary.kanban_decomposer.
    gc                  Garbage-collect archived-task workspaces, old events,
                        and old logs
    repair              Check kanban.db integrity and auto-repair index-only
                        corruption

options:
  -h, --help            show this help message and exit
  --board <slug>        Board slug to operate on. Defaults to the current
                        board (set via `hermes kanban boards switch <slug>` or
                        the HERMES_KANBAN_BOARD env var). Use `hermes kanban
                        boards list` to see all boards.
```

## `hermes send` --help

```
usage: hermes send [-h] [-t TARGET] [-f PATH] [-s LINE]
                   [--mention PHONE_OR_JID] [-l] [-q] [--json]
                   [message]

Pipe text from any shell script to any messaging platform Hermes is already configured for. Reuses the gateway's platform credentials (/Users/lobsy/.hermes/.env + /Users/lobsy/.hermes/config.yaml) — no LLM, no agent loop, no running gateway required for bot-token platforms like Telegram/Discord/Slack/Signal.

positional arguments:
  message               Message text. If omitted, read from --file or stdin.

options:
  -h, --help            show this help message and exit
  -t, --to TARGET       Delivery target. Format: 'platform' (home channel),
                        'platform:chat_id', 'platform:chat_id:thread_id', or
                        'platform:#channel-name'. Examples: telegram,
                        telegram:-1001234567890:17585, discord:#ops,
                        slack:C0123ABCD, signal:+15551234567.
  -f, --file PATH       Read message body from PATH (text only). Use '-' to
                        force stdin. To send an image/document as an
                        attachment, use MEDIA:<path> in the message text
                        instead.
  -s, --subject LINE    Prepend a subject/header line before the message body.
  --mention PHONE_OR_JID
                        WhatsApp only: add a native participant mention.
                        Repeat for multiple recipients; bare phone numbers are
                        normalized to JIDs. Include each matching @<number>
                        near the start of the message text.
  -l, --list            List available targets. Optional positional filter:
                        `hermes send --list telegram`.
  -q, --quiet           Suppress stdout on success (exit code only).
  --json                Emit raw JSON result instead of human-readable output.

Examples:
  hermes send --to telegram "deploy finished"
  echo "RAM 92%" | hermes send --to telegram:-1001234567890
  hermes send --to discord:#ops --file ./report.md
  hermes send --to slack:#eng --subject "[CI]" --file build.log
  hermes send --to whatsapp:GROUP@g.us --mention 15551234567 "@15551234567 hello"
  hermes send --to telegram "MEDIA:./chart.png"   # send a media attachment
  hermes send --list                  # all platforms
  hermes send --list telegram         # filter by platform

Exit codes: 0 ok, 1 delivery/backend error, 2 usage error.
```

## `hermes kanban create` --help

```
usage: hermes kanban create [-h] [--body BODY] [--body-file PATH]
                            [--assignee ASSIGNEE] [--parent PARENT]
                            [--workspace WORKSPACE] [--branch BRANCH]
                            [--project PROJECT] [--tenant TENANT]
                            [--priority PRIORITY] [--triage]
                            [--idempotency-key IDEMPOTENCY_KEY]
                            [--max-runtime MAX_RUNTIME]
                            [--created-by CREATED_BY] [--skill SKILLS]
                            [--max-retries N] [--model MODEL_OVERRIDE]
                            [--provider PROVIDER_OVERRIDE]
                            [--completion-contract CONTRACT] [--goal]
                            [--goal-max-turns N]
                            [--initial-status {blocked,running}] [--json]
                            title

positional arguments:
  title                 Task title

options:
  -h, --help            show this help message and exit
  --body BODY           Optional opening post
  --body-file PATH      Read the opening post from a file ('-' = stdin), so
                        bodies with embedded newlines or flag-like lines
                        survive shell quoting. Mutually exclusive with --body.
  --assignee ASSIGNEE   Profile name to assign
  --parent PARENT       Parent task id (repeatable)
  --workspace WORKSPACE
                        scratch | worktree | worktree:<path> | dir:<path>
                        (default: scratch; an explicit 'scratch' also opts out
                        of a project-scoped board's project)
  --branch BRANCH       Branch name for worktree tasks, e.g. wt/t6-wire
  --project PROJECT     Link to a project (id or slug). Anchors the task's
                        worktree under the project's primary repo with a
                        deterministic branch. See `hermes project list`.
  --tenant TENANT       Tenant namespace
  --priority PRIORITY   Priority tiebreaker
  --triage              Park in triage — a specifier will flesh out the spec
                        and promote to todo
  --idempotency-key IDEMPOTENCY_KEY
                        Dedup key. If a non-archived task with this key
                        exists, its id is returned instead of creating a
                        duplicate.
  --max-runtime MAX_RUNTIME
                        Per-task runtime cap. Accepts seconds (300) or
                        durations (90s, 30m, 2h, 1d). When exceeded, the
                        dispatcher SIGTERMs (then SIGKILLs) the worker and re-
                        queues the task.
  --created-by CREATED_BY
                        Author name recorded on the task (default: user)
  --skill SKILLS        Skill to force-load into the worker (repeatable). The
                        kanban lifecycle is already injected automatically.
                        Example: --skill translation --skill github-code-
                        review
  --max-retries N       Per-task override for the consecutive-failure circuit
                        breaker. Trip on the Nth failure — e.g. --max-retries
                        1 blocks on the first failure (no retries), --max-
                        retries 3 allows two retries. Omit to use the
                        dispatcher's kanban.failure_limit config (default 2).
  --model MODEL_OVERRIDE
                        Pin the worker to this model (passed as -m <model>)
                        without changing the profile's configured model.
                        Combine with --provider when the model belongs to a
                        different backend than the profile's default.
  --provider PROVIDER_OVERRIDE
                        Provider the --model belongs to (passed as --provider
                        <name> to the worker). Requires --model.
  --completion-contract CONTRACT
                        local-only (default), OWNER/REPO for publication, or
                        exact GitHub PR URL; required CI gates done.
  --goal                Run the worker in a goal loop: after each turn a judge
                        checks the response against the card title/body and,
                        if not done, the worker keeps going in the same
                        session until the judge agrees it's complete (or the
                        turn budget runs out, which blocks the card for
                        review). Best for open-ended cards one shot rarely
                        finishes.
  --goal-max-turns N    Turn budget for --goal workers (default 20). Ignored
                        without --goal.
  --initial-status {blocked,running}
                        Initial card status. Use 'blocked' for cards that
                        require immediate human ops (R3 gate) to skip the
                        brief running-to-blocked transition.
  --json                Emit JSON output
```

## `hermes kanban edit` --help

```
usage: hermes kanban edit [-h] [--title TITLE] [--body BODY]
                          [--priority PRIORITY] [--result RESULT]
                          [--summary SUMMARY] [--metadata METADATA]
                          task_id

positional arguments:
  task_id

options:
  -h, --help           show this help message and exit
  --title TITLE        Replace the task title
  --body BODY          Replace the task body
  --priority PRIORITY  Replace the task priority
  --result RESULT      Backfilled task result text for a done task
  --summary SUMMARY    Structured handoff summary. Falls back to --result if
                       omitted.
  --metadata METADATA  JSON dict of structured facts to store on the latest
                       completed run.
```

## `hermes kanban attach` --help

```
usage: hermes kanban attach [-h] [--content-type CONTENT_TYPE] [--name NAME]
                            [--author AUTHOR]
                            task_id path

positional arguments:
  task_id
  path                  Path to the local file to attach

options:
  -h, --help            show this help message and exit
  --content-type CONTENT_TYPE
                        MIME type (default: guessed from the file extension)
  --name NAME           Stored filename (default: the source file's basename)
  --author AUTHOR       uploaded_by label (default: $HERMES_PROFILE or 'user')
```

## `hermes kanban comment` --help

```
usage: hermes kanban comment [-h] [--author AUTHOR] [--max-len MAX_LEN]
                             task_id text [text ...]

positional arguments:
  task_id
  text               Comment body

options:
  -h, --help         show this help message and exit
  --author AUTHOR    Author name (default: $HERMES_PROFILE or 'user')
  --max-len MAX_LEN  Trim the stored comment body to this many characters
```

## `hermes kanban claim` --help

```
usage: hermes kanban claim [-h] [--ttl TTL] task_id

positional arguments:
  task_id

options:
  -h, --help  show this help message and exit
  --ttl TTL   Claim TTL in seconds (default: 900)
```

## `hermes kanban assign` --help

```
usage: hermes kanban assign [-h] task_id profile

positional arguments:
  task_id
  profile     Profile name (or 'none' to unassign)

options:
  -h, --help  show this help message and exit
```

## `hermes kanban promote` --help

```
usage: hermes kanban promote [-h] [--ids IDS [IDS ...]] [--dry-run] [--json]
                             task_id [reason ...]

positional arguments:
  task_id
  reason               Audit-trail reason (recorded on the task_events row)

options:
  -h, --help           show this help message and exit
  --ids IDS [IDS ...]  Additional task ids to promote with the same reason
                       (bulk mode)
  --dry-run            Validate the promotion without mutating state
  --json               Emit machine-readable JSON result
```

## `hermes kanban reclaim` --help

```
usage: hermes kanban reclaim [-h] [--reason REASON] task_id

positional arguments:
  task_id

options:
  -h, --help       show this help message and exit
  --reason REASON  Human-readable reason (recorded on the reclaimed event)
```

## `hermes kanban reopen-review` --help

```
usage: hermes kanban reopen-review [-h] [--reason REASON]
                                   task_ids [task_ids ...]

positional arguments:
  task_ids

options:
  -h, --help       show this help message and exit
  --reason REASON  Optional reason/note — recorded as a comment before
                   reopening. Quote multi-word reasons.
```

## `hermes kanban block` --help

```
usage: hermes kanban block [-h] [--ids IDS [IDS ...]]
                           [--kind {capability,dependency,needs_input,transient}]
                           task_id [reason ...]

positional arguments:
  task_id
  reason                Reason (also appended as a comment)

options:
  -h, --help            show this help message and exit
  --ids IDS [IDS ...]   Additional task ids to block with the same reason
                        (bulk mode)
  --kind {capability,dependency,needs_input,transient}
                        Typed block reason. 'dependency' waits in todo (auto-
                        promoted when parents finish, no human);
                        'needs_input'/'capability' go to blocked for a human;
                        'transient' marks a maybe-flaky failure. Repeated
                        same-kind re-blocks after unblock route the task to
                        triage to break unblock loops. Omit for a generic
                        block.
```

## `hermes kanban unblock` --help

```
usage: hermes kanban unblock [-h] [--reason REASON] task_ids [task_ids ...]

positional arguments:
  task_ids

options:
  -h, --help       show this help message and exit
  --reason REASON  Optional reason/note — recorded as a comment before
                   unblocking. Quote multi-word reasons.
```

## `hermes kanban request-review` --help

```
usage: hermes kanban request-review [-h] [--summary SUMMARY]
                                    [--reviewer REVIEWER]
                                    [--metadata METADATA] [--force]
                                    task_id

positional arguments:
  task_id

options:
  -h, --help           show this help message and exit
  --summary SUMMARY    What was implemented and how it was verified — shown to
                       the reviewer.
  --reviewer REVIEWER  Optional reviewer profile; reassigns the task before
                       review dispatch.
  --metadata METADATA  JSON object with structured reviewer handoff facts.
  --force              Override the live-claim guard: move a running, claimed
                       task to review even without owning its run (clears the
                       worker's claim).
```

## `hermes kanban request-changes` --help

```
usage: hermes kanban request-changes [-h] task_id reason [reason ...]

positional arguments:
  task_id
  reason      Concrete changes required before re-review

options:
  -h, --help  show this help message and exit
```

## `hermes kanban complete` --help

```
usage: hermes kanban complete [-h] [--result RESULT] [--summary SUMMARY]
                              [--metadata METADATA] [--force]
                              task_ids [task_ids ...]

positional arguments:
  task_ids             One or more task ids (only --result applies to all of
                       them)

options:
  -h, --help           show this help message and exit
  --result RESULT      Result summary
  --summary SUMMARY    Structured handoff summary for downstream tasks. Falls
                       back to --result if omitted.
  --metadata METADATA  JSON dict of structured facts (e.g. '{"changed_files":
                       [...], "tests_run": 12}'). Stored on the closing run.
  --force              Override the live-claim guard: complete a running,
                       claimed task even without owning its run (closes the
                       worker's run).
```

## `hermes kanban archive` --help

```
usage: hermes kanban archive [-h] [--rm PURGE_IDS [PURGE_IDS ...]]
                             [task_ids ...]

positional arguments:
  task_ids              Task ids to archive (default mode)

options:
  -h, --help            show this help message and exit
  --rm PURGE_IDS [PURGE_IDS ...]
                        Permanently delete already-archived task ids from the
                        board
```
