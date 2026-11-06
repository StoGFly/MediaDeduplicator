# MediaDeduplicator — AI Development Instructions

## Project identity

- Project: MediaDeduplicator
- Local directory: `F:\MediaDeduplicator`
- Platform: Windows
- Language: Python 3.12+
- GUI: PySide6
- CLI: Typer
- Version control: Git
- Main branch: `main`

## Source of truth

The local Git repository and its documentation are the authoritative project records.

Never assume previous ChatGPT conversation history is available.

Before making changes:

1. Read this file.
2. Read `PROJECT_STATUS.md`.
3. Read `docs/development/HANDOFF.md`.
4. Read relevant architecture and design documentation.
5. Inspect the current Git branch, working-tree status and recent commits.
6. Inspect the actual source and tests relevant to the task.

Never invent implementation details, test results, commit history or project status.

Distinguish clearly between:
- Implemented and tested.
- Implemented but not fully tested.
- Experimentally investigated.
- Planned.
- Not yet started.

## Development workflow

Work incrementally.

1. Explain the next task and why it is needed.
2. Give manageable, command-by-command PowerShell instructions.
3. Wait for the user's output before proceeding.
4. Make focused changes rather than broad rewrites.
5. Run relevant tests.
6. Run the complete test suite when appropriate.
7. Inspect Git changes before committing.
8. Commit only when the user agrees.

Never claim a command or operation succeeded without seeing its result.

## User preferences

- Use PowerShell for Windows instructions.
- Use Notepad++ for file editing, not Windows Notepad.
- Explain technical concepts as we go.
- Keep instructions manageable and avoid overwhelming the user.
- Do not skip verification steps.
- Maintain a friendly, conversational tone.

## Git safety

- Never stage or commit `TestMedia/`.
- Never stage personal sample photographs or contact sheets.
- Inspect `git status` before staging or committing.
- Prefer focused commits with descriptive messages.
- Do not rewrite Git history without explicit permission.
- Do not push to GitHub until the user explicitly agrees that the project is ready.

## Project safety principles

MediaDeduplicator should prioritise user data safety.

- Scanning should be read-only.
- Exact duplicate identification must use cryptographic file hashes.
- Similarity detection must not be treated as proof of identical files.
- Never permanently delete files automatically.
- Quarantine and restoration must be designed with safeguards and clear user confirmation.
- Avoid destructive operations without explicit user approval.

## Testing

The project uses pytest.

Activate the environment from the project directory:

```powershell
.\.venv\Scripts\Activate.ps1
```

Run the complete suite:

```powershell
python -m pytest -v
```

Run a focused test module:

```powershell
python -m pytest tests/test_image.py -v
```

Only report tests as passing when their actual output confirms it.

## Experimental research

Experimental scripts and results must be distinguished from production implementation.

Do not integrate experimental algorithms into production code until:
- Their behaviour has been investigated.
- Positive and negative controls have been tested.
- Limitations and failure cases have been considered.
- Appropriate automated tests have been designed.

Preserve useful experimental findings in `docs/experiments/`.

## Design and architecture

Preserve established project architecture and decisions unless a change is discussed and agreed with the user.

The project is intended to support:
- Images.
- Videos.
- Audio.
- Command-line operation.
- A graphical interface.
- Optional AI-assisted capabilities.

The GUI is intended to offer:
- Basic mode for ordinary users.
- Advanced mode for users who want to adjust detection parameters.
- Sensible defaults.
- Safeguards and explanations for settings that affect speed, sensitivity and false-positive risk.

## AI tool availability

Development must not depend on ChatGPT Work or Codex being available.

When local computer-use or repository tools are unavailable:
- Use PowerShell instructions executed by the user.
- Work incrementally and inspect command output.
- Never assume direct access to local files.
- Do not claim to have modified or inspected files unless verified.
- Keep all project changes under the user's control.

## Documentation maintenance

Keep project documentation consistent with actual implementation.

Update `PROJECT_STATUS.md` when significant implementation or testing milestones occur.

Update `docs/development/HANDOFF.md` whenever a development session ends or the conversation needs to move to a fresh chat.

Record significant technical decisions and experimental results in their appropriate documentation files.