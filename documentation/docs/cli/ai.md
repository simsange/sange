# `sange ai`

Sub-app for AI provider introspection + prompt preview. Two commands.

## `sange ai providers`

List every registered provider + whether its SDK extra is installed.

```bash
sange ai providers
sange --json ai providers
```

Plain output:

```
PROVIDER       SDK        STREAM   JSON   TOOLS  DEFAULT-MODEL
-------------- ---------- -------- ------ ------ --------------------
mock           installed  yes      yes    no     mock-1
anthropic      missing    — install sange[ai-anthropic]
openai         installed  yes      yes    yes    gpt-4o
ollama         missing    — install sange[ai-ollama]
gemini         missing    — install sange[ai-google]
bedrock        missing    — install sange[ai-bedrock]
```

JSON mode emits the full capability matrix per provider.

## `sange ai preview`

Render the prompt that **would** be sent for a task, without
actually sending it. The `--task` flag selects the task template;
v0.1 supports `commit-msg`. The `--provider` flag selects the
formatting strategy.

```bash
git diff --staged | sange ai preview --task commit-msg --provider anthropic
sange ai preview --diff /tmp/staged.diff --provider openai --branch feat/auth
```

Plain output (truncated):

```
=== SYSTEM ===
You are an expert Conventional Commits 1.0.0 author. ...

=== USER ===
<task>
Write a Conventional Commits 1.0.0 message for the staged changes below.
...
<diff>
+ added passkey support
</diff>
</task>

<output_schema>
{ "type": "object", "required": ["type", "subject", ...] }
</output_schema>
```

The output shape changes per provider:

- **`anthropic`** uses XML delimiters (`<task>`, `<output_schema>`).
- **`openai`** uses JSON-mode hints + fenced ```json blocks.
- **`ollama`** / **`gemini`** / **`bedrock`** / **`mock`** use plain
  markdown.

`--json` mode emits the messages array directly:

```json
{
  "task": "commit-msg",
  "provider": "anthropic",
  "requires_json": true,
  "messages": [
    {"role": "system",  "content": "You are an expert ..."},
    {"role": "user",    "content": "<task>...</task>"}
  ]
}
```

## Why preview matters

Two reasons:

1. **Forensics.** When an AI-generated message is wrong, the first
   question is "what did we send?" `sange ai preview` answers it
   without burning another API call.

2. **Redaction sanity-check.** Run preview on a diff containing
   secrets; verify the T-030 redaction layer scrubbed them before
   the payload would have been transmitted. Useful before pointing
   the tool at a sensitive repo for the first time.
