# Securevantara

A local security-review foundation for developers reviewing their own source code.
This is **not a complete autonomous vulnerability discovery or bug-bounty platform**.
The default workflow needs no Xalgorix, cloud account, API key, or Python package.

## Capabilities and status

| Capability | Status |
| --- | --- |
| Python AST checks for direct `eval()` / `exec()` calls | Implemented; review suggestions only |
| Local Ollama source review, default `gemma4:e4b` | Implemented; strict source-evidence validation; model quality varies |
| Explicit authorization and exact local directory scope | Implemented input checks; not proof of ownership |
| Private JSON reports, raw model evidence and file hashes | Implemented |
| Optional Xalgorix v4.6.159 subprocess adapter | Partial; real version/help checked, source-review construction mocked |
| Xalgorix finding normalization | Unsupported; CLI text retained as raw evidence |
| Semgrep, Bandit, Ruff, pip-audit, Gitleaks adapters | Planned, not included |
| Website/HTTP observer, live vulnerability testing, GitHub ingestion, JAR analysis | Planned |
| Autonomous discovery, independent verification, fixes and bounty workflow | Planned |

The first milestone reviews **local source**, including a manually prepared snapshot of
an authorized GitHub repository. It does not clone repositories or contact websites.

## Architecture and data flow

```text
source folder + explicit authorization + matching scope
  -> scope / symlink / special-file checks
  -> Python AST rules
  -> optional source text sent only to loopback Ollama
  -> validate model JSON and evidence against source lines
  -> preserve provenance and write private JSON report
```

The model receives no tools and cannot execute code. Prompt injection in reviewed files
can still influence suggestions; exact evidence matching establishes a source citation,
not vulnerability validity. All model findings remain `unverified`.

## Local setup: macOS, Linux, Windows/WSL

Use Python 3.9+ (3.12 recommended). On macOS, install Python from python.org or your
package manager. On Debian/Ubuntu use `sudo apt install python3 python3-venv`.
On Windows use WSL2 with Ubuntu and run the Linux instructions inside WSL; native
Windows subprocess handling is not supported. Open this repository in VS Code and
use its integrated terminal. Do not mix Windows Python with a WSL environment.

From the repository root:

```bash
cd agents/securevantara
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p reports
```

`requirements.txt` deliberately has no dependencies. No `.env` file is loaded.
The included `.env.example` documents the optional Xalgorix settings only.

## Run immediately without an LLM or Xalgorix

```bash
python -m securevantara check \
  --source examples/source --scope examples/source --authorized \
  --report reports/check-1.json
python -m json.tool reports/check-1.json
```

The synthetic sample contains one deliberate direct `eval()` call at line 6. The
built-in rule labels it `needs-review`, severity `info`. A call alone does not prove
that an attacker controls its input. The sample is read, never executed.

## Run with your local model

Install and start Ollama using its [official instructions](https://docs.ollama.com/quickstart).
The model must already be installed; Securevantara never pulls models automatically.
For this workstation the selected model is `gemma4:e4b`.

```bash
ollama list
# Only if you need to download the requested model:
ollama pull gemma4:e4b
# If the local Ollama service is not already running, in another terminal:
ollama serve
```

```bash
python -m securevantara review \
  --source examples/source --scope examples/source --authorized \
  --model gemma4:e4b --timeout 120 \
  --report reports/review-1.json
python -m json.tool reports/review-1.json
```

Use the same command with an absolute source directory and exactly the same `--scope`
for your own sanitized, authorized snapshot. `--authorized` is your attestation that
source review is permitted; an open-source licence does not authorize live testing.
Another installed Ollama model can be selected with `--model`; other models have not
been benchmarked. Inference always uses `127.0.0.1:11434`, never a configurable remote
endpoint. Keep Ollama local. No API key is required, recorded, or sent.

Review includes at most ten source files, 12,000 bytes per file, and 24,000 source
characters in total. Supported extensions: py, js, ts, tsx, jsx, go, java, rs, php,
rb, cs. Tests, Git metadata, dependency folders and virtual environments are skipped
by the model. Skipped files appear in `local_llm.skipped`; this is partial coverage.
No supported files is an error. The built-in checks only understand Python.

## Reports, finding schema and statuses

Reports use `schema_version: "1.0"`, operation, source, scope, authorization flag,
UTC start/finish times, findings, errors and the wrapper's `exit_status`.
Each normalized finding has:

| Field | Meaning |
| --- | --- |
| `id` | SHA-256 of engine rule, relative path, line and exact evidence |
| `rule`, `title` | Detector identity and summary |
| `severity` | info / low / medium / high / critical; model rating is unvalidated |
| `status` | needs-review / unverified; confirmed is reserved for future independent verification |
| `kind` | source-review; never dynamic penetration testing |
| `path`, `line` | Relative source location and 1-based line |
| `evidence` | Exact source fragment |
| `provenance` | Engine, rule or local model identity |

Deduplication uses exact rule, path, line and evidence, merging provenance only for
that identity. Different engines remain distinct; no speculative semantic merging.
Model output must have the expected fields and a matching evidence substring at the
cited line. Invalid output is rejected as a whole, retained in `local_llm.raw_response`,
and reported as an error. Source hashes are recorded for reviewed files.

Exit `0` means the requested workflow completed, **not that the source is secure**.
Exit `2` means invalid authorization/input, execution failure, unavailable service,
model output validation failure, or report failure. Built-in findings survive a model
failure. Inspect `errors` and any skipped files. Reports use mode 0600 and exclusive
creation: choose a new filename for every run. Raw evidence may contain sensitive code;
keep reports private and do not render model text as executable HTML or commands.

## Docker

The default image is local-only and does not download Xalgorix:

```bash
docker build -t securevantara:local .
docker build --target tests -t securevantara-tests .
docker run --rm --network none --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=64m --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 64 --memory 256m --cpus 1 \
  securevantara-tests
```

For the built-in check, mount only your source and report folder:

```bash
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 64 --memory 256m --cpus 1 \
  --user "$(id -u):$(id -g)" \
  -v "$PWD/examples/source:/source:ro" -v "$PWD/reports:/reports" \
  securevantara:local check --source /source --scope /source --authorized \
  --report /reports/docker-check-1.json
```

Use native Python for local Ollama review on macOS/WSL: container loopback is not host
loopback. The restricted Docker command has no model access by design. Do not mount
home directories, Docker sockets, credentials or production datasets. Docker is an
additional boundary, not a guarantee against kernel or runtime vulnerabilities.

## Optional Xalgorix adapter (partial)

This is separate from the default workflow. Existing Xalgorix dashboards (for example
`http://localhost:9137`) are not accessed, stopped or treated as scan targets.

Pinned compatibility: **v4.6.159**, verified against the installed release and
[official source](https://github.com/xalgorix/xalgorix/blob/v4.6.159/cmd/xalgorix/main.go),
[README](https://github.com/xalgorix/xalgorix/blob/v4.6.159/README.md) and
[release assets](https://github.com/xalgorix/xalgorix/releases/tag/v4.6.159).
Official installation supports macOS/Linux prebuilt binaries; use Linux under WSL.
Source builds require Go 1.26+ and Node.js per the upstream README. Its Go module path
is different from the GitHub repository path; do not invent a `go install` path.
Prefer the pinned Docker target below, which checks the official Linux asset SHA-256.
For native installation download the appropriate pinned release asset, verify its
published SHA-256, make it executable and place it on PATH. Do not use `@latest` for
this adapter. Upstream is Apache-2.0; its code is not vendored here.

```bash
docker build --target xalgorix -t securevantara-xalgorix:local .
python -m securevantara xalgorix-info --report reports/xalgorix-info-1.json
```

For an already isolated environment with authorized local source, the experimental
command is:

```bash
export XALGORIX_LLM_PROVIDER=ollama
export XALGORIX_LLM=gemma4:e4b
export XALGORIX_API_BASE=http://127.0.0.1:11434
export XALGORIX_MAX_ITERATIONS=8
python -m securevantara xalgorix-review \
  --source examples/source --scope examples/source --authorized --sandboxed \
  --timeout 120 --report reports/xalgorix-review-1.json
```

`--sandboxed` is an operator acknowledgement, **not sandbox creation or detection**.
Xalgorix can execute tools; input scope checks cannot constrain every upstream tool.
Use a disposable sandbox with read-only source and restricted egress before review.
Hosted LLMs are upstream options but are not needed for this prototype; source may be
transmitted if you configure them. Native Xalgorix can read its own home configuration.
Never mount that configuration into the restricted default container.

Only `--version` and `--source PATH --code-scan review` are constructed. No target,
provision, update, install, exploit, patch or bounty submission command is exposed.
The adapter uses shell=False, closed stdin, a separate process group, wall timeouts
(maximum 3600 seconds), and bounded stdout/stderr capture (default 64 KiB each, maximum
1 MiB each). It records command, binary hash, exit status, timeout and truncation.
Auto-update and auto-install are disabled in its child environment. Captured output
is UTF-8 with replacement for invalid bytes, not a lossless binary archive. Truncated
text is explicitly marked. No confirmed CLI JSON finding format exists in this
adapter, so raw output produces **zero normalized Xalgorix findings**. A child exit
status cannot establish upstream review success. Real model-backed Xalgorix discovery
and independent verification have not been tested here.

## Tests, evaluations and troubleshooting

From this project directory:

```bash
python -m unittest discover -s tests -v
python -m compileall -q securevantara tests
# From the repository root:
git diff --check
```

No formatter, linter or type checker was configured in the original repository.
Unit tests mock subprocess and HTTP calls. Synthetic positive and negative AST cases,
model citation validation, scope rejection, symlink rejection, missing executable,
timeout, malformed output, non-zero exit, truncation and private report writing are
covered. They do not measure real-world vulnerability recall or exploitability.

If Ollama is unavailable, check `ollama list` and that its local server is running.
If model output is rejected, inspect raw evidence and use `check` for the deterministic
baseline. Model failure never promotes a suggestion to confirmed. A timeout needs a
new report filename before retry. Missing Xalgorix does not affect local commands.
For symlink or special-file errors prepare a sanitized regular-file snapshot. Runtime
scope checks are subject to filesystem races: avoid writable or adversarial live trees.
For report permission errors use a writable private directory. No report parent is
automatically created. Large repositories need a future streaming inventory/budget
implementation; model coverage is intentionally bounded and incomplete.

## Next milestones and evaluation gates

Evaluate Xalgorix first in a deliberately vulnerable, isolated local lab. Record target
and engine versions, model digest, seed vulnerabilities, negatives, independent
reproduction, scope violations, false positives, runtime and cost per verified finding.
Do not publish comparative quality claims without those runs. Then add optional
scanner adapters and verified output fixtures, broader language/dependency analysis,
website scope/egress enforcement, independent verification, remediation proposals,
and human-reviewed bounty report drafts. Public repository access is not permission
to test a deployment. Never automatically apply fixes, deploy or submit bounty reports.

## License

Contributed under the parent repository MIT licence. Optional external tools retain
their own licences. See [verification notes](VERIFICATION.md) for actual local results.
