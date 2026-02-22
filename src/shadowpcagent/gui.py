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
class AutoTask:
    title: str
    detail: str
    task_type: str
    created_at: float = field(default_factory=time.time)
    status: str = "Queued"

    def label(self) -> str:
        icon = {
            "Code": "🧩",
            "Scan": "🧠",
            "Command": "🖥️",
            "General": "⭐",
        }.get(self.task_type, "⭐")
        return f"{icon} {self.title} [{self.status}]"


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

    tasks: list[AutoTask] = []
    archived_tasks: list[AutoTask] = []
    chat_memory: list[dict[str, str]] = []

    root = tk.Tk()
    root.title("ShadowPCAgent Overlay")
    root.configure(bg="#10151f")
    root.geometry("1200x820+20+20")

    colors = {
        "bg": "#10151f",
        "panel": "#172132",
        "soft": "#20314d",
        "text": "#eff4ff",
        "sub": "#a5b8df",
        "accent": "#6de9c5",
        "warn": "#ffc66d",
    }

    status_var = tk.StringVar(value=f"Ready. Workspace: {repo_root}")
    target_var = tk.StringVar(value=str(repo_root))

    def run_in_thread(fn):
        threading.Thread(target=fn, daemon=True).start()

    def _set_status(text: str) -> None:
        root.after(0, lambda: status_var.set(text))

    def _chat(role: str, msg: str) -> None:
        stamp = time.strftime("%H:%M:%S")
        root.after(0, lambda: _append_text(chat_box, f"[{stamp}] {role}: {msg}\n\n"))

    def _log(msg: str) -> None:
        root.after(0, lambda: _append_text(log_box, msg))

    def refresh_task_list() -> None:
        task_list.delete(0, tk.END)
        for item in tasks:
            task_list.insert(tk.END, item.label())

        archived_list.delete(0, tk.END)
        for item in archived_tasks:
            archived_list.insert(tk.END, item.label())

    def add_auto_task(title: str, detail: str, task_type: str) -> None:
        tasks.append(AutoTask(title=title, detail=detail, task_type=task_type))
        refresh_task_list()

    def archive_selected_task() -> None:
        selected = task_list.curselection()
        if not selected:
            return
        task = tasks.pop(selected[0])
        task.status = "Archived"
        archived_tasks.append(task)
        refresh_task_list()

    def open_task_popup() -> None:
        popup = tk.Toplevel(root)
        popup.title("Auto Task Queue")
        popup.geometry("360x420+70+90")
        popup.configure(bg=colors["panel"])

        tk.Label(
            popup,
            text="Shadow builds tasks from chat.",
            bg=colors["panel"],
            fg=colors["text"],
            font=("Segoe UI", 11, "bold"),
        ).pack(anchor="w", padx=10, pady=(10, 5))

        info = scrolledtext.ScrolledText(popup, height=10, bg="#0d1420", fg=colors["text"], relief=tk.FLAT)
        info.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)

        def populate() -> None:
            info.delete("1.0", tk.END)
            for idx, task in enumerate(tasks, start=1):
                info.insert(tk.END, f"{idx}. {task.label()}\n   {task.detail}\n\n")
            if not tasks:
                info.insert(tk.END, "No active tasks yet. Say things like:\n- scan my system\n- edit src/app.py ...\n- run search index ...")

        populate()
        tk.Button(popup, text="Refresh", command=populate, bg=colors["soft"], fg=colors["text"], relief=tk.FLAT).pack(side=tk.LEFT, padx=10, pady=8)
        tk.Button(popup, text="Archive Selected", command=archive_selected_task, bg=colors["soft"], fg=colors["text"], relief=tk.FLAT).pack(side=tk.LEFT, padx=8, pady=8)

    def set_overlay(enabled: bool) -> None:
        root.wm_attributes("-topmost", bool(enabled))
        root.overrideredirect(bool(enabled))
        root.wm_attributes("-alpha", 0.94 if enabled else 1.0)
        if enabled:
            root.geometry("1200x200+0+0")
            _set_status("Overlay ON: seamless ribbon mode")
        else:
            root.geometry("1200x820+20+20")
            _set_status(f"Overlay OFF: full chat mode in {target_var.get()}")

    def perform_system_scan(scope: Path) -> None:
        _set_status("Scanning system...")
        _chat("Shadow", f"Running system analysis in: {scope}")

        cpu = os.cpu_count() or 1
        total, used, free = shutil.disk_usage(scope)
        py_files = sum(1 for _ in scope.rglob("*.py"))
        summary = {
            "platform": platform.platform(),
            "scope": str(scope),
            "cpu_count": cpu,
            "disk_total_gb": round(total / (1024**3), 2),
            "disk_free_gb": round(free / (1024**3), 2),
            "python_files": py_files,
            "optimization_hint": "Good multicore machine" if cpu >= 8 else "Use lighter model for faster runs",
        }
        out = workflow_dir / "system_scan_gui.json"
        out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        _chat("Shadow", f"System scan done. Report saved: {out.name}\n{json.dumps(summary, indent=2)}")
        _log(f"[SCAN] Wrote report to {out}\n")
        _set_status("System scan complete")

    def run_cli_command(command: str, args: str) -> None:
        _set_status("Running command...")
        _chat("Shadow", f"Executing command: shadowpcagent {command} {args}")
        _log(f"\n[CLI] python -m shadowpcagent {command} {args}\n")

        env = os.environ.copy()
        env.setdefault("PYTHONPATH", str(repo_root / "src"))
        p = subprocess.run(
            ["python", "-m", "shadowpcagent", command, *([a for a in args.split(" ") if a])],
            cwd=target_var.get(),
            env=env,
            text=True,
            capture_output=True,
        )
        if p.stdout:
            _log(p.stdout + ("\n" if not p.stdout.endswith("\n") else ""))
        if p.stderr:
            _log(p.stderr + ("\n" if not p.stderr.endswith("\n") else ""))
        _chat("Shadow", f"Command finished with code {p.returncode}.")
        _set_status(f"Last command exit: {p.returncode}")

    def propose_patch_from_chat(user_text: str) -> None:
        global LAST_PATCH_PATH
        _set_status("Thinking about code edits...")

        context_tail = "\n".join(f"{m['role']}: {m['content']}" for m in chat_memory[-8:])
        prompt = (
            "You are editing code for ShadowPCAgent. Use conversation context below. "
            "Return unified diff only.\n\n"
            f"Conversation context:\n{context_tail}\n\n"
            f"Current user request:\n{user_text}\n"
        )

        model = model_entry.get().strip() or DEFAULT_MODEL
        patch_path = workflow_dir / "PATCH_GUI.diff"
        stderr_path = workflow_dir / "CODEX_GUI.stderr.txt"

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
            target_var.get(),
        ]

        with open(stderr_path, "w", encoding="utf-8") as ef:
            p = subprocess.run(cmd, input=prompt, cwd=target_var.get(), env=env, text=True, capture_output=True)
            ef.write(p.stderr or "")

        if p.returncode != 0:
            _chat("Shadow", "Patch planning failed. See logs.")
            _log(f"[CODEX ERROR] exit={p.returncode}\n{p.stderr or ''}\n")
            _set_status("Patch planning failed")
            return

        out = p.stdout or ""
        start = out.find("diff --git")
        if start == -1:
            _chat("Shadow", "No diff was produced. Try a clearer edit request.")
            diff_box.delete("1.0", tk.END)
            diff_box.insert(tk.END, out)
            _set_status("No diff produced")
            return

        diff = out[start:]
        patch_path.write_text(diff, encoding="utf-8")
        LAST_PATCH_PATH = str(patch_path)

        touched = sorted({line.split(" b/")[-1] for line in diff.splitlines() if line.startswith("diff --git")})
        diff_box.delete("1.0", tk.END)
        diff_box.insert(tk.END, diff)
        _chat("Shadow", "I prepared an edit patch for:\n" + "\n".join(f"- {item}" for item in touched))
        _log(f"[CODEX] Saved patch: {patch_path}\n")
        _set_status("Patch ready. Say 'apply patch' in chat to apply.")

    def apply_patch() -> None:
        global LAST_PATCH_PATH
        if not LAST_PATCH_PATH or not Path(LAST_PATCH_PATH).exists():
            _chat("Shadow", "There is no patch to apply yet.")
            return

        patch_path = Path(LAST_PATCH_PATH)
        p1 = subprocess.run(["git", "apply", "--check", str(patch_path)], cwd=target_var.get(), text=True, capture_output=True)
        if p1.returncode != 0:
            _chat("Shadow", "Patch check failed; I did not apply it.")
            _log(f"[GIT CHECK FAILED]\n{p1.stderr or ''}{p1.stdout or ''}\n")
            return

        p2 = subprocess.run(["git", "apply", str(patch_path)], cwd=target_var.get(), text=True, capture_output=True)
        if p2.returncode != 0:
            _chat("Shadow", "Patch apply failed.")
            _log(f"[GIT APPLY FAILED]\n{p2.stderr or ''}{p2.stdout or ''}\n")
            return

        _chat("Shadow", f"Patch applied: {patch_path.name}")
        _log("[GIT] Patch applied successfully\n")
        _set_status("Patch applied")

    def process_chat() -> None:
        user_text = input_box.get("1.0", "end-1c").strip()
        if not user_text:
            return

        input_box.delete("1.0", tk.END)
        chat_memory.append({"role": "user", "content": user_text})
        _chat("You", user_text)

        lowered = user_text.lower()

        if any(k in lowered for k in ["scan", "analyze machine", "optimize hardware", "analyze computer"]):
            add_auto_task("System analysis", user_text, "Scan")
            run_in_thread(lambda: perform_system_scan(Path(target_var.get())))
            return

        if any(k in lowered for k in ["apply patch", "apply changes"]):
            add_auto_task("Apply prepared patch", user_text, "Code")
            run_in_thread(apply_patch)
            return

        if any(k in lowered for k in ["edit", "modify", "change code", "patch"]):
            add_auto_task("Code update", user_text, "Code")
            run_in_thread(lambda: propose_patch_from_chat(user_text))
            return

        if lowered.startswith("run "):
            raw = user_text[4:].strip()
            pieces = raw.split(" ", 1)
            cmd = pieces[0]
            args = pieces[1] if len(pieces) > 1 else ""
            add_auto_task("Run command", user_text, "Command")
            run_in_thread(lambda: run_cli_command(cmd, args))
            return

        add_auto_task("General request", user_text, "General")
        _chat(
            "Shadow",
            "I understood your request and added it to the intelligent queue. "
            "If you want action now, start with 'edit ...', 'scan ...', or 'run ...'.",
        )

    # Layout
    top = tk.Frame(root, bg=colors["panel"], highlightbackground="#2b3e61", highlightthickness=1)
    top.pack(fill=tk.X, padx=10, pady=(10, 6))

    tk.Label(top, text="✨ Shadow Chat", bg=colors["panel"], fg=colors["text"], font=("Segoe UI", 16, "bold")).pack(side=tk.LEFT, padx=10, pady=8)
    tk.Label(top, textvariable=status_var, bg=colors["panel"], fg=colors["sub"]).pack(side=tk.LEFT, padx=8)

    overlay_mode = tk.BooleanVar(value=False)
    tk.Button(
        top,
        text="Toggle Overlay",
        command=lambda: (overlay_mode.set(not overlay_mode.get()), set_overlay(overlay_mode.get())),
        bg=colors["soft"],
        fg=colors["text"],
        relief=tk.FLAT,
        padx=10,
    ).pack(side=tk.RIGHT, padx=8)

    tk.Button(top, text="Tasks", command=open_task_popup, bg=colors["soft"], fg=colors["text"], relief=tk.FLAT).pack(side=tk.RIGHT, padx=8)

    target_row = tk.Frame(root, bg=colors["bg"])
    target_row.pack(fill=tk.X, padx=10, pady=(0, 6))
    tk.Label(target_row, text="Target Folder:", bg=colors["bg"], fg=colors["text"]).pack(side=tk.LEFT)
    tk.Entry(target_row, textvariable=target_var, width=100).pack(side=tk.LEFT, padx=8, fill=tk.X, expand=True)

    center = tk.Frame(root, bg=colors["bg"])
    center.pack(fill=tk.BOTH, expand=True, padx=10)

    chat_box = scrolledtext.ScrolledText(center, wrap=tk.WORD, bg="#0d1420", fg=colors["text"], relief=tk.FLAT, state=tk.DISABLED)
    chat_box.pack(fill=tk.BOTH, expand=True)

    input_row = tk.Frame(root, bg=colors["bg"])
    input_row.pack(fill=tk.X, padx=10, pady=8)

    input_box = scrolledtext.ScrolledText(input_row, height=4, wrap=tk.WORD, bg="#0d1420", fg=colors["text"], relief=tk.FLAT)
    input_box.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    tk.Button(input_row, text="Send", command=process_chat, bg=colors["accent"], fg="#0f1f1a", relief=tk.FLAT, padx=14).pack(side=tk.LEFT, padx=8)

    tools = tk.LabelFrame(root, text="Power Tools", bg=colors["panel"], fg=colors["text"], labelanchor="nw")
    tools.pack(fill=tk.BOTH, padx=10, pady=(0, 10))

    mini_top = tk.Frame(tools, bg=colors["panel"])
    mini_top.pack(fill=tk.X, padx=8, pady=(6, 4))
    tk.Label(mini_top, text="Model", bg=colors["panel"], fg=colors["text"]).pack(side=tk.LEFT)
    model_entry = tk.Entry(mini_top, width=44)
    model_entry.insert(0, DEFAULT_MODEL)
    model_entry.pack(side=tk.LEFT, padx=6)

    tk.Button(mini_top, text="Propose from chat", command=lambda: run_in_thread(lambda: propose_patch_from_chat(chat_memory[-1]["content"] if chat_memory else "")), bg=colors["soft"], fg=colors["text"], relief=tk.FLAT).pack(side=tk.LEFT, padx=4)
    tk.Button(mini_top, text="Apply patch", command=lambda: run_in_thread(apply_patch), bg=colors["soft"], fg=colors["text"], relief=tk.FLAT).pack(side=tk.LEFT, padx=4)
    tk.Button(mini_top, text="Scan now", command=lambda: run_in_thread(lambda: perform_system_scan(Path(target_var.get()))), bg=colors["warn"], fg="#1a1a1a", relief=tk.FLAT).pack(side=tk.RIGHT, padx=4)

    task_list = tk.Listbox(tools, height=4, bg="#0d1420", fg=colors["text"], selectbackground=colors["soft"], relief=tk.FLAT)
    task_list.pack(fill=tk.X, padx=8, pady=4)

    archived_list = tk.Listbox(tools, height=3, bg="#0d1420", fg=colors["sub"], selectbackground=colors["soft"], relief=tk.FLAT)
    archived_list.pack(fill=tk.X, padx=8, pady=4)

    tk.Button(tools, text="Archive selected task", command=archive_selected_task, bg=colors["soft"], fg=colors["text"], relief=tk.FLAT).pack(anchor="w", padx=8, pady=(0, 6))

    tk.Label(tools, text="Patch Diff Preview", bg=colors["panel"], fg=colors["text"]).pack(anchor="w", padx=8)
    diff_box = scrolledtext.ScrolledText(tools, height=8, wrap=tk.NONE, bg="#0d1420", fg=colors["text"], relief=tk.FLAT)
    diff_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 8))

    tk.Label(tools, text="Logs", bg=colors["panel"], fg=colors["text"]).pack(anchor="w", padx=8)
    log_box = scrolledtext.ScrolledText(tools, height=6, wrap=tk.NONE, bg="#0d1420", fg=colors["text"], relief=tk.FLAT, state=tk.DISABLED)
    log_box.pack(fill=tk.BOTH, expand=True, padx=8, pady=(2, 8))

    _chat("Shadow", "Hi! Just chat naturally. I will auto-create tasks and choose actions.")
    _chat("Shadow", "Examples: 'scan my computer', 'edit src/shadowpcagent/gui.py to ...', 'run search query --term gui'.")

    root.bind("<Control-Return>", lambda _e: process_chat())
    root.mainloop()


if __name__ == "__main__":
    start_gui()
