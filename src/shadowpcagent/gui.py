import os
import threading
import subprocess
from pathlib import Path
import tkinter as tk
from tkinter import scrolledtext


# Default local model (matches what you used successfully)
DEFAULT_MODEL = "huihui_ai/qwen2.5-coder-abliterate:7b"

# Stores the most recent patch path created by "Propose Patch"
LAST_PATCH_PATH: str | None = None


def _repo_root_from_this_file() -> Path:
    # gui.py is at: <repo>\src\shadowpcagent\gui.py
    # repo root is 3 parents up from this file: gui.py -> shadowpcagent -> src -> repo
    return Path(__file__).resolve().parents[2]


def _ensure_workflow_dir(repo_root: Path) -> Path:
    wf = repo_root / ".data" / "workflow"
    wf.mkdir(parents=True, exist_ok=True)
    return wf


def _append_text(widget: tk.Text, text: str) -> None:
    widget.configure(state=tk.NORMAL)
    widget.insert(tk.END, text)
    widget.see(tk.END)
    widget.configure(state=tk.DISABLED)


def start_gui() -> None:
    global LAST_PATCH_PATH

    repo_root = _repo_root_from_this_file()
    workflow_dir = _ensure_workflow_dir(repo_root)

    root = tk.Tk()
    root.title("ShadowPCAgent GUI")

    # -----------------------------
    # Layout
    # -----------------------------
    top = tk.Frame(root)
    top.pack(fill=tk.X, padx=10, pady=10)

    tk.Label(top, text="Command:").grid(row=0, column=0, sticky="w")
    cmd_entry = tk.Entry(top, width=60)
    cmd_entry.grid(row=0, column=1, padx=5)
    cmd_entry.insert(0, "--help")

    tk.Label(top, text="Args:").grid(row=1, column=0, sticky="w")
    args_entry = tk.Entry(top, width=60)
    args_entry.grid(row=1, column=1, padx=5)

    run_btn = tk.Button(top, text="Run CLI Command")
    run_btn.grid(row=0, column=2, rowspan=2, padx=8, sticky="ns")

    mid = tk.LabelFrame(root, text="Local Codex Patch Workflow")
    mid.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    tk.Label(mid, text="Prompt to Codex:").pack(anchor="w")
    prompt_box = scrolledtext.ScrolledText(mid, height=8, wrap=tk.WORD)
    prompt_box.pack(fill=tk.BOTH, expand=False, pady=5)

    btn_row = tk.Frame(mid)
    btn_row.pack(fill=tk.X, pady=5)

    tk.Label(btn_row, text="Model:").pack(side=tk.LEFT)
    model_entry = tk.Entry(btn_row, width=45)
    model_entry.pack(side=tk.LEFT, padx=5)
    model_entry.insert(0, DEFAULT_MODEL)

    propose_btn = tk.Button(btn_row, text="Propose Patch (Codex)")
    propose_btn.pack(side=tk.LEFT, padx=5)

    apply_btn = tk.Button(btn_row, text="Apply Patch (git apply)")
    apply_btn.pack(side=tk.LEFT, padx=5)

    tk.Label(mid, text="Patch preview (diff):").pack(anchor="w")
    diff_box = scrolledtext.ScrolledText(mid, height=14, wrap=tk.NONE)
    diff_box.pack(fill=tk.BOTH, expand=True, pady=5)

    bottom = tk.LabelFrame(root, text="Logs")
    bottom.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    log_box = scrolledtext.ScrolledText(bottom, height=10, wrap=tk.NONE, state=tk.DISABLED)
    log_box.pack(fill=tk.BOTH, expand=True)

    status_var = tk.StringVar(value=f"Repo: {repo_root}")
    status = tk.Label(root, textvariable=status_var, anchor="w")
    status.pack(fill=tk.X, padx=10, pady=(0, 8))

    # -----------------------------
    # Worker helpers
    # -----------------------------
    def run_in_thread(fn):
        t = threading.Thread(target=fn, daemon=True)
        t.start()

    def _log(line: str) -> None:
        root.after(0, lambda: _append_text(log_box, line))

    def _set_status(text: str) -> None:
        root.after(0, lambda: status_var.set(text))

    def _set_diff(text: str) -> None:
        def _do():
            diff_box.delete("1.0", tk.END)
            diff_box.insert(tk.END, text)
            diff_box.see("1.0")
        root.after(0, _do)

    # -----------------------------
    # Actions
    # -----------------------------
    def do_run_cli():
        command = cmd_entry.get().strip()
        extra = args_entry.get().strip()
        args = []
        if extra:
            # simple split; user can paste quoted args if needed
            args = extra.split()

        if not command:
            _log("No command provided.\n")
            return

        def worker():
            _set_status("Running CLI command...")
            _log(f"\n[CLI] python -m shadowpcagent {command} {extra}\n")
            env = os.environ.copy()
            env.setdefault("PYTHONPATH", str(repo_root / "src"))

            try:
                # Run from repo root so relative paths behave
                p = subprocess.run(
                    ["python", "-m", "shadowpcagent", command, *args],
                    cwd=str(repo_root),
                    env=env,
                    text=True,
                    capture_output=True,
                )
                if p.stdout:
                    _log(p.stdout + ("\n" if not p.stdout.endswith("\n") else ""))
                if p.stderr:
                    _log(p.stderr + ("\n" if not p.stderr.endswith("\n") else ""))
                _set_status(f"CLI exit code: {p.returncode}")
            except Exception as e:
                _log(f"[CLI ERROR] {e}\n")
                _set_status("CLI error (see log)")

        run_in_thread(worker)

    def do_propose_patch():
        global LAST_PATCH_PATH

        prompt = prompt_box.get("1.0", "end-1c").strip()
        if not prompt:
            _log("Prompt is empty.\n")
            return

        model = model_entry.get().strip() or DEFAULT_MODEL
        patch_path = workflow_dir / "PATCH_GUI.diff"
        stderr_path = workflow_dir / "CODEX_GUI.stderr.txt"

        def worker():
            _set_status("Running Codex (read-only) to propose patch...")
            _log(f"\n[CODEX] Propose patch -> {patch_path}\n")

            # Always ensure local env variables exist
            env = os.environ.copy()
            env.setdefault("OPENAI_API_KEY", "local")
            # These help many wrappers decide to use local endpoints
            env.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:11434/v1")
            env.setdefault("OLLAMA_HOST", "http://127.0.0.1:11434")

            cmd = [
                "codex",
                "exec",
                "--oss",
                "--local-provider",
                "ollama",
                "--model",
                model,
                "--sandbox",
                "read-only",
                "--cd",
                str(repo_root),
            ]

            try:
                with open(stderr_path, "w", encoding="utf-8") as ef:
                    p = subprocess.run(
                        cmd,
                        input=prompt,
                        cwd=str(repo_root),
                        env=env,
                        text=True,
                        capture_output=True,
                    )
                    # Write stderr to file too
                    ef.write(p.stderr or "")

                if p.returncode != 0:
                    _log(f"[CODEX ERROR] exit={p.returncode}\n")
                    if p.stderr:
                        _log(p.stderr + ("\n" if not p.stderr.endswith("\n") else ""))
                    _set_status("Codex failed (see log + stderr file)")
                    return

                out = p.stdout or ""
                # Extract the unified diff starting at first "diff --git"
                start = out.find("diff --git")
                if start == -1:
                    _log("[CODEX] No unified diff found in output.\n")
                    _set_status("No diff produced")
                    _set_diff(out)
                    return

                diff = out[start:]
                patch_path.write_text(diff, encoding="utf-8")
                LAST_PATCH_PATH = str(patch_path)

                _set_diff(diff)
                _log(f"[CODEX] Saved patch: {patch_path}\n")
                _set_status("Patch proposed (preview populated)")

            except Exception as e:
                _log(f"[CODEX EXCEPTION] {e}\n")
                _set_status("Codex exception (see log)")

        run_in_thread(worker)

    def do_apply_patch():
        global LAST_PATCH_PATH
        if not LAST_PATCH_PATH or not Path(LAST_PATCH_PATH).exists():
            _log("No valid patch file to apply. Click 'Propose Patch' first.\n")
            _set_status("No patch to apply")
            return

        patch_path = Path(LAST_PATCH_PATH)

        def worker():
            _set_status("Applying patch (git apply)...")
            _log(f"\n[GIT] git apply --check {patch_path}\n")

            try:
                p1 = subprocess.run(
                    ["git", "apply", "--check", str(patch_path)],
                    cwd=str(repo_root),
                    text=True,
                    capture_output=True,
                )
                if p1.returncode != 0:
                    _log("[GIT] Patch check FAILED:\n")
                    if p1.stderr:
                        _log(p1.stderr + ("\n" if not p1.stderr.endswith("\n") else ""))
                    if p1.stdout:
                        _log(p1.stdout + ("\n" if not p1.stdout.endswith("\n") else ""))
                    _set_status("Patch check failed")
                    return

                _log(f"[GIT] git apply {patch_path}\n")
                p2 = subprocess.run(
                    ["git", "apply", str(patch_path)],
                    cwd=str(repo_root),
                    text=True,
                    capture_output=True,
                )
                if p2.returncode != 0:
                    _log("[GIT] Patch apply FAILED:\n")
                    if p2.stderr:
                        _log(p2.stderr + ("\n" if not p2.stderr.endswith("\n") else ""))
                    if p2.stdout:
                        _log(p2.stdout + ("\n" if not p2.stdout.endswith("\n") else ""))
                    _set_status("Patch apply failed")
                    return

                _log("[GIT] Patch applied successfully.\n")
                _set_status("Patch applied successfully")

            except Exception as e:
                _log(f"[GIT EXCEPTION] {e}\n")
                _set_status("Git exception (see log)")

        run_in_thread(worker)

    # Wire buttons
    run_btn.config(command=do_run_cli)
    propose_btn.config(command=do_propose_patch)
    apply_btn.config(command=do_apply_patch)

    root.mainloop()


if __name__ == "__main__":
    start_gui()