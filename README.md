# IntentOS

> From human intent to executable action.

IntentOS is a local, voice-native agentic layer that turns a user's goals into controlled, verifiable actions over their own applications and data. Kori is the Hindi, Hinglish, and regional-language voice of the runtime.

## Core Loop

```text
Remember -> Retrieve -> Reason -> Act -> Verify
```

IntentOS is not primarily a chatbot. It interprets intent, uses a schema-aware memory layer, creates execution plans, routes calls through validated tools, and verifies the resulting state.

## Architecture

```text
Voice or text
     |
     v
Intent Engine -> Schema Manifest -> Structured Memory
     |                         |
     +------> Query / Plan <---+
                    |
                    v
             Validated Tools
                    |
                    v
          Execution -> Verification
                    |
                    v
              User Response
```

## Database

The MVP uses a local SQLite database in `database.py`. The core schema is domain-neutral:

- `profiles`: local runtime users and language/timezone settings
- `entities`: structured personal memory with typed entity categories
- `entities.memory_class`: risk category for context, preference, personal data, or secrets
- `entities.consent_status`: records whether sensitive memory was explicitly approved
- `conversation_sessions` and `conversation_messages`: active context and history
- `intents`: structured user goals, entities, and constraints
- `plans` and `plan_steps`: executable multi-step goals
- `tool_executions`: controlled tool calls, arguments, results, and failures
- `verifications`: expected versus observed post-action state
- `tasks`: reminders and future actions
- `preferences`: persistent user defaults
- `events`: append-only operational history
- `offline_queue`: actions waiting for local processing
- `schema_manifest`: machine-readable entities, relationships, retrieval hints, and allowed operations

The database does not store hidden chain-of-thought. It stores structured state and operational audit metadata only.

## Risk-Aware Memory

IntentOS does not ask the user to confirm every small preference. Memory is
classified by risk:

| Memory type | Behavior |
| --- | --- |
| `context` | Saved automatically for the active conversation or task |
| `preference` | Saved automatically for ordinary preferences such as language or reminder time |
| `personal` | Requires explicit user confirmation before storage |
| `secret` | Rejected from normal memory; use a password manager or encrypted secret store |

For example, Kori may automatically remember that the user prefers concise
Hindi responses. If the user asks Kori to remember a private address or health
detail, Kori must ask before saving it. Passwords, API keys, tokens, OTPs, and
private keys are never written to the normal SQLite memory tables.

## Domain Adapters

VyapaarSaathi is a validation domain, not the IntentOS core identity or schema. A future adapter can add shop-specific capabilities such as customers, inventory, orders, or credit without putting those tables in the general runtime database.

## Quick Start

Requirements are defined in `pyproject.toml`. With Python 3.12 or newer:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m py_compile database.py tools.py prompts.py agent.py
```

Set the required LiveKit and Google environment variables from `.env.sample`, then run:

```powershell
python agent.py dev
```

The default local database is `intentOS.db`. Existing databases from the retired VyapaarSaathi schema are not migrated automatically. Back them up and use a fresh database or write an explicit export migration.

## Local-First Positioning

IntentOS is designed around local memory, low latency, and reduced cloud dependence. The current project must not claim complete privacy, offline inference, Snapdragon NPU acceleration, zero latency, or no hallucinations unless those properties have been deployed and measured.

## Current Runtime Capabilities

- The current model integration is Google LiveKit realtime, not a fully local model.
- Voice input depends on the configured LiveKit and model services.
- Generic structured memory can be saved and retrieved.
- Tasks can be created, listed by status, and completed.
- Preferences can be saved and retrieved.
- Conversation context can be updated and retrieved for follow-up references.
- Low-risk context and preferences can be saved without repeated confirmation.
- Personal memory requires explicit confirmation; secret-like values are refused.
- Plans reject tool names that are not in the registered IntentOS tool set.
- The complete VyapaarSaathi adapter is a separate implementation.

## Hackathon MVP Status

IntentOS demonstrates the core runtime architecture:

- Voice-first interaction through Kori
- Structured intent representation
- Schema-guided memory through `schema_manifest`
- Local SQLite persistence
- Multi-step plan storage
- Controlled tool registration
- Tool execution and failure records
- Post-action verification records
- Persistent tasks, preferences, and events

The current prototype uses Google Realtime inference. It is designed for local Snapdragon deployment, but Snapdragon NPU acceleration and fully local inference are not claimed until benchmarked.

## Demonstration Flow

The intended MVP demonstration follows one continuous conversation:

1. User states a goal through voice.
2. Kori identifies the structured intent.
3. IntentOS consults the schema manifest.
4. Relevant local memory is retrieved.
5. IntentOS creates an execution plan.
6. Validated tools perform the requested action.
7. The resulting state is verified.
8. Kori reports the verified result.

Example:

```text
User goal
  -> Structured intent
  -> Schema-guided retrieval
  -> Action plan
  -> Registered tool execution
  -> State verification
  -> Spoken response
```

The current runtime can demonstrate generic memory, task, preference, context,
planning, execution logging, and verification operations. A domain adapter is
required for the full overdue-customer example described in `secreats.md`.

## Hackathon Evaluation Alignment

### Technical Implementation

- SQLite-based structured local memory
- Machine-readable schema manifest
- Intent and plan persistence
- Registered-tool validation before plan storage
- Tool execution and failure records
- Task lifecycle and preference persistence
- Conversation context persistence
- Post-action verification records
- Transactional database access, foreign keys, and indexes

### Use Case and Innovation

IntentOS changes interaction from:

```text
Application -> menu -> form -> action
```

to:

```text
Human intent -> understanding -> retrieval -> action -> verification
```

The central innovation is Schema-Guided Intent Execution: the agent understands
the structure of its memory instead of sending all stored data to an LLM.

### Deployment and Accessibility

- Voice-first interaction through Kori
- Hindi, Hinglish, and regional-language support
- Local SQLite memory
- Designed for low-latency local execution
- Compatible with a future local Snapdragon inference deployment

### Presentation and Documentation

- Runtime architecture
- Database schema
- Intent execution lifecycle
- Local-first positioning
- Explicit implementation limitations
- Future adapter roadmap

## Future Scope

### Phase 1: IntentOS Runtime

- Structured memory and schema manifest
- Intent and multi-step plan persistence
- Registered tool validation
- Task and preference lifecycle
- Conversational context
- Execution logs and verification records
- Voice interaction through Kori

### Phase 2: VyapaarSaathi Adapter

- Customer and transaction entities
- Inventory and sales entities
- Domain-specific retrieval tools
- Reminder creation for overdue customers
- Business analytics

### Phase 3: Local Snapdragon Deployment

- Local speech recognition
- Local language model or small language model
- Snapdragon AI Hub integration
- NPU benchmarking
- Offline inference measurements
- Latency and memory comparisons

### Phase 4: IntentOS SDK

Developers will define an application adapter with:

```text
Application -> Schema -> Capabilities -> Validated Tools -> IntentOS Adapter
```

Potential adapters include developer tools, file management, personal
productivity, education, media, and business applications.

## Submission Honesty
Since it is just a prototype build for hackathon it doesn't use the local NPU for inference. 
The current prototype does not claim complete privacy, fully offline inference,
Snapdragon NPU acceleration, zero latency, or autonomous computer control.
But it can be transformed easily to use the NPU and offline models because this mvp is build to test the core logic and functioning of complete pipeline not the deployment. 
Those are deployment goals. The implemented MVP is the local structured runtime,
schema manifest, controlled tool surface, task/preferences/context memory, plan
validation, and execution verification records.

