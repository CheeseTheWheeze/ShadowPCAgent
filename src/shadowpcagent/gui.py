import json
import os
import platform
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import tkinter as tk
from tkinter import scrolledtext


DEFAULT_MODEL = "huihui_ai/qwen2.5-coder-abliterate:7b"
LAST_PATCH_PATH: str | None = None


@dataclass
class OverlayTask:
    """Simple task object for kid-friendly task cards."""

    title: str
    task_type: str
    detail: str
    created_at: float = field(default_factory=time.time)
    status: str = "Queued"

    def label(self) -> str:
        icon = {
            "Code Change": "🧩",
            "Self Modify": "🪄",
            "Desktop Action": "🖱️",
            "System Scan": "🧠",
        }.get(self.task_type, "⭐")
        return f"{icon} {self.title} [{self.status}]"


TASK_TYPES = ["Code Change", "Self Modify", "Desktop Action", "System Scan"]


def _repo_root_from_this_file() -> Path:
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

    pending_tasks: list[OverlayTask] = []
    archived_tasks: list[OverlayTask] = []

    root = tk.Tk()
    root.title("ShadowPCAgent Overlay")
    root.configure(bg="#10151f")
    root.geometry("1280x850+20+20")

    palette = {
        "bg": "#10151f",
        "panel": "#172132",
        "soft": "#20314d",
        "text": "#eff4ff",
        "sub": "#a5b8df",
        "accent": "#6de9c5",
        "warn": "#ffc66d",
        "danger": "#ff7c7c",
    }

    main = tk.Frame(root, bg=palette["bg"])
    main.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    header = tk.Frame(main, bg=palette["panel"], bd=0, highlightthickness=1, highlightbackground="#2b3e61")
    header.pack(fill=tk.X, pady=(0, 8))

    title = tk.Label(
        header,
        text="✨ ShadowPCAgent Mission Overlay",
        font=("Segoe UI", 16, "bold"),
        bg=palette["panel"],
        fg=palette["text"],
        pady=8,
    )
    title.pack(side=tk.LEFT, padx=10)

    status_var = tk.StringVar(value=f"Ready. Watching {repo_root}")
    tk.Label(header, textvariable=status_var, bg=palette["panel"], fg=palette["sub"]).pack(side=tk.LEFT, padx=8)

    overlay_enabled = tk.BooleanVar(value=False)

    def set_overlay_mode(enabled: bool) -> None:
        overlay_enabled.set(enabled)
        root.wm_attributes("-topmost", bool(enabled))
        root.overrideredirect(bool(enabled))
        root.wm_attributes("-alpha", 0.93 if enabled else 1.0)
        if enabled:
            root.geometry("1280x220+0+0")
            status_var.set("Overlay mode ON: always-on-top command ribbon")
        else:
            root.geometry("1280x850+20+20")
            status_var.set(f"Overlay mode OFF. Working in full console at {repo_root}")

    overlay_btn = tk.Button(
        header,
        text="Toggle Overlay",
        command=lambda: set_overlay_mode(not overlay_enabled.get()),
        bg=palette["soft"],
        fg=palette["text"],
        activebackground=palette["accent"],
        relief=tk.FLAT,
        padx=12,
    )
    overlay_btn.pack(side=tk.RIGHT, padx=10, pady=6)

    body = tk.PanedWindow(main, orient=tk.HORIZONTAL, sashrelief=tk.FLAT, bg=palette["bg"])
    body.pack(fill=tk.BOTH, expand=True)

    left = tk.Frame(body, bg=palette["panel"], highlightthickness=1, highlightbackground="#2b3e61")
    right = tk.Frame(body, bg=palette["panel"], highlightthickness=1, highlightbackground="#2b3e61")
    body.add(left, minsize=370)
    body.add(right, minsize=650)

    # LEFT: task planner
    tk.Label(left, text="🗂️ Kid-Simple Task Board", bg=palette["panel"], fg=palette["text"], font=("Segoe UI", 13, "bold")).pack(anchor="w", padx=10, pady=(10, 5))

    controls = tk.Frame(left, bg=palette["panel"])
    controls.pack(fill=tk.X, padx=10)

    task_title = tk.Entry(controls, bg="#0d1420", fg=palette["text"], insertbackground=palette["text"])
    task_title.pack(fill=tk.X, pady=(0, 4))
    task_title.insert(0, "Tell Shadow what to do")

    task_detail = tk.Entry(controls, bg="#0d1420", fg=palette["text"], insertbackground=palette["text"])
    task_detail.pack(fill=tk.X, pady=(0, 4))
    task_detail.insert(0, "Example: optimize renderer.py and then open browser game")

    selected_task_type = tk.StringVar(value=TASK_TYPES[0])
    tk.OptionMenu(controls, selected_task_type, *TASK_TYPES).pack(fill=tk.X, pady=(0, 6))

    pending_list = tk.Listbox(left, height=11, bg="#0d1420", fg=palette["text"], selectbackground=palette["soft"], relief=tk.FLAT)
    pending_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

    archived_list = tk.Listbox(left, height=8, bg="#0d1420", fg=palette["sub"], selectbackground=palette["soft"], relief=tk.FLAT)
    archived_list.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    task_explain = tk.StringVar(value="Tasks can include code edits, self-modification, desktop actions, and hardware scans.")
    tk.Label(left, textvariable=task_explain, wraplength=350, justify=tk.LEFT, bg=palette["panel"], fg=palette["sub"]).pack(anchor="w", padx=10, pady=(0, 8))

    # RIGHT: execution + visibility
    top = tk.LabelFrame(right, text="Action Launcher", bg=palette["panel"], fg=palette["text"], labelanchor="nw")
    top.pack(fill=tk.X, padx=10, pady=(10, 6))

    tk.Label(top, text="Command:", bg=palette["panel"], fg=palette["text"]).grid(row=0, column=0, sticky="w", padx=5, pady=3)
    cmd_entry = tk.Entry(top, width=58)
    cmd_entry.grid(row=0, column=1, padx=5, pady=3)
    cmd_entry.insert(0, "--help")

    tk.Label(top, text="Args:", bg=palette["panel"], fg=palette["text"]).grid(row=1, column=0, sticky="w", padx=5, pady=3)
    args_entry = tk.Entry(top, width=58)
    args_entry.grid(row=1, column=1, padx=5, pady=3)

    run_btn = tk.Button(top, text="▶ Run", bg=palette["soft"], fg=palette["text"], relief=tk.FLAT)
    run_btn.grid(row=0, column=2, rowspan=2, padx=8, sticky="ns")

    vision = tk.LabelFrame(right, text="What I am doing right now", bg=palette["panel"], fg=palette["text"], labelanchor="nw")
    vision.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

    activity_feed = scrolledtext.ScrolledText(vision, height=6, wrap=tk.WORD, bg="#0d1420", fg=palette["text"], relief=tk.FLAT)
    activity_feed.pack(fill=tk.X, padx=8, pady=8)

    tk.Label(vision, text="Codex Prompt", bg=palette["panel"], fg=palette["text"]).pack(anchor="w", padx=8)
    prompt_box = scrolledtext.ScrolledText(vision, height=6, wrap=tk.WORD, bg="#0d1420", fg=palette["text"], relief=tk.FLAT)
    prompt_box.pack(fill=tk.X, padx=8, pady=5)

    row = tk.Frame(vision, bg=palette["panel"])
    row.pack(fill=tk.X, padx=8)

    tk.Label(row, text="Model", bg=palette["panel"], fg=palette["text"]).pack(side=tk.LEFT)
    model_entry = tk.Entry(row, width=42)
    model_entry.pack(side=tk.LEFT, padx=6)
    model_entry.insert(0, DEFAULT_MODEL)

    propose_btn = tk.Button(row, text="Propose", bg=palette["soft"], fg=palette["text"], relief=tk.FLAT)
    propose_btn.pack(side=tk.LEFT, padx=4)
    apply_btn = tk.Button(row, text="Apply", bg=palette["soft"], fg=palette["text"], relief=tk.FLAT)
    apply_btn.pack(side=tk.LEFT, padx=4)
    scan_btn = tk.Button(row, text="Scan Machine", bg=palette["warn"], fg="#1a1a1a", relief=tk.FLAT)
    scan_btn.pack(side=tk.RIGHT, padx=4)

    tk.Label(vision, text="Diff Preview", bg=palette["panel"], fg=palette["text"]).pack(anchor="w", padx=8, pady=(7, 0))
    diff_box = scrolledtext.ScrolledText(vision, height=10, wrap=tk.NONE, bg="#0d1420", fg=palette["text"], relief=tk.FLAT)
    diff_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    bottom = tk.LabelFrame(right, text="Logs", bg=palette["panel"], fg=palette["text"], labelanchor="nw")
    bottom.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

    log_box = scrolledtext.ScrolledText(bottom, height=8, wrap=tk.NONE, state=tk.DISABLED, bg="#0d1420", fg=palette["text"], relief=tk.FLAT)
    log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def run_in_thread(fn):
        t = threading.Thread(target=fn, daemon=True)
        t.start()

    def _log(line: str) -> None:
        root.after(0, lambda: _append_text(log_box, line))

    def _activity(line: str) -> None:
        root.after(0, lambda: _append_text(activity_feed, line))

    def _set_status(text: str) -> None:
        root.after(0, lambda: status_var.set(text))

    def _set_diff(text: str) -> None:
        def _do():
            diff_box.delete("1.0", tk.END)
            diff_box.insert(tk.END, text)
            diff_box.see("1.0")

        root.after(0, _do)

    def refresh_lists() -> None:
        pending_list.delete(0, tk.END)
        for task in pending_tasks:
            pending_list.insert(tk.END, task.label())

        archived_list.delete(0, tk.END)
        for task in archived_tasks:
            archived_list.insert(tk.END, task.label())

    def add_task() -> None:
        title_text = task_title.get().strip()
        detail_text = task_detail.get().strip()
        if not title_text or title_text == "Tell Shadow what to do":
            task_explain.set("Pick a fun clear name for the task first.")
            return
        task = OverlayTask(title=title_text, task_type=selected_task_type.get(), detail=detail_text)
        pending_tasks.append(task)
        refresh_lists()
        task_explain.set(f"Queued: {task.task_type} task. Shadow will narrate each step.")
        _activity(f"[TASK QUEUED] {task.title}\nDetail: {task.detail}\n")

    def archive_selected() -> None:
        selected = pending_list.curselection()
        if not selected:
            task_explain.set("Select a task to archive.")
            return
        task = pending_tasks.pop(selected[0])
        task.status = "Archived"
        archived_tasks.append(task)
        refresh_lists()
        _activity(f"[TASK ARCHIVED] {task.title}\n")

    task_buttons = tk.Frame(left, bg=palette["panel"])
    task_buttons.pack(fill=tk.X, padx=10, pady=(0, 10))
    tk.Button(task_buttons, text="➕ Set Task", command=add_task, bg=palette["accent"], fg="#0f1f1a", relief=tk.FLAT).pack(side=tk.LEFT)
    tk.Button(task_buttons, text="📦 Archive", command=archive_selected, bg=palette["soft"], fg=palette["text"], relief=tk.FLAT).pack(side=tk.LEFT, padx=6)

    def do_run_cli():
        command = cmd_entry.get().strip()
        extra = args_entry.get().strip()
        args = extra.split() if extra else []
        if not command:
            _log("No command provided.\n")
            return

        def worker():
            _set_status("Running CLI command...")
            _activity(f"[DESKTOP ACTION] Running python -m shadowpcagent {command} {extra}\n")
            _log(f"\n[CLI] python -m shadowpcagent {command} {extra}\n")
            env = os.environ.copy()
            env.setdefault("PYTHONPATH", str(repo_root / "src"))

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
            _set_status("Planning code changes...")
            _activity("[CODE MODIFICATION] Building patch proposal.\n")
            _log(f"\n[CODEX] Propose patch -> {patch_path}\n")

            env = os.environ.copy()
            env.setdefault("OPENAI_API_KEY", "local")
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

            with open(stderr_path, "w", encoding="utf-8") as ef:
                p = subprocess.run(
                    cmd,
                    input=prompt,
                    cwd=str(repo_root),
                    env=env,
                    text=True,
                    capture_output=True,
                )
                ef.write(p.stderr or "")

            if p.returncode != 0:
                _log(f"[CODEX ERROR] exit={p.returncode}\n")
                if p.stderr:
                    _log(p.stderr + ("\n" if not p.stderr.endswith("\n") else ""))
                _set_status("Codex failed (see log + stderr file)")
                return

            out = p.stdout or ""
            start = out.find("diff --git")
            if start == -1:
                _log("[CODEX] No unified diff found in output.\n")
                _set_status("No diff produced")
                _set_diff(out)
                return

            diff = out[start:]
            patch_path.write_text(diff, encoding="utf-8")
            LAST_PATCH_PATH = str(patch_path)
            touched = sorted({line.split(" b/")[-1] for line in diff.splitlines() if line.startswith("diff --git")})
            _activity("[CODE MODIFICATION] Proposed changes for:\n" + "\n".join(f" - {f}" for f in touched) + "\n")
            _set_diff(diff)
            _log(f"[CODEX] Saved patch: {patch_path}\n")
            _set_status("Patch proposed and previewed")

        run_in_thread(worker)

    def do_apply_patch():
        global LAST_PATCH_PATH
        if not LAST_PATCH_PATH or not Path(LAST_PATCH_PATH).exists():
            _log("No valid patch file to apply. Click 'Propose' first.\n")
            _set_status("No patch to apply")
            return

        patch_path = Path(LAST_PATCH_PATH)

        def worker():
            _set_status("Applying patch...")
            _activity(f"[SELF MODIFICATION] Applying patch file {patch_path.name}\n")
            _log(f"\n[GIT] git apply --check {patch_path}\n")
            p1 = subprocess.run(["git", "apply", "--check", str(patch_path)], cwd=str(repo_root), text=True, capture_output=True)
            if p1.returncode != 0:
                _log("[GIT] Patch check FAILED:\n")
                if p1.stderr:
                    _log(p1.stderr + ("\n" if not p1.stderr.endswith("\n") else ""))
                if p1.stdout:
                    _log(p1.stdout + ("\n" if not p1.stdout.endswith("\n") else ""))
                _set_status("Patch check failed")
                return

            p2 = subprocess.run(["git", "apply", str(patch_path)], cwd=str(repo_root), text=True, capture_output=True)
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

        run_in_thread(worker)

    def run_system_scan() -> None:
        def worker():
            _set_status("Scanning host system for optimization hints...")
            _activity("[SYSTEM SCAN] Checking CPU, memory, disk, and project size.\n")
            cpu_count = os.cpu_count() or 1
            total, used, free = shutil.disk_usage(repo_root)
            py_files = sum(1 for _ in repo_root.rglob("*.py"))
            summary = {
                "platform": platform.platform(),
                "cpu_count": cpu_count,
                "disk_total_gb": round(total / (1024**3), 2),
                "disk_free_gb": round(free / (1024**3), 2),
                "python_files": py_files,
                "optimization_hint": "Good multicore machine" if cpu_count >= 8 else "Consider lighter local model for faster responses",
            }
            scan_path = workflow_dir / "system_scan_gui.json"
            scan_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
            _activity("[SYSTEM SCAN] " + json.dumps(summary, indent=2) + "\n")
            _log(f"[SCAN] Wrote report to {scan_path}\n")
            _set_status("System scan complete")

        run_in_thread(worker)

    run_btn.config(command=do_run_cli)
    propose_btn.config(command=do_propose_patch)
    apply_btn.config(command=do_apply_patch)
    scan_btn.config(command=run_system_scan)

    root.mainloop()


if __name__ == "__main__":
    start_gui()
