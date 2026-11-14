import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, scrolledtext, ttk

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_DIR = PROJECT_ROOT / "data"
USER_STORIES_DIR = DATA_DIR / "user_stories"
OUTPUT_DIR = PROJECT_ROOT / "output"

VIEWER_FILES = [
    ("Comparison Report", OUTPUT_DIR / "comparison_report.md"),
    ("NeoDataset Report", OUTPUT_DIR / "comparison_report_neodataset.md"),
    ("Agent Messages", OUTPUT_DIR / "agent_messages.log"),
]


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Estimation Assistant")
        self.geometry("1040x660")
        self.minsize(760, 460)

        self.proc = None
        self.current_name = ""
        self.elapsed_mark = 0.0
        self._busy = False
        self.log_queue = queue.Queue()
        self.command_buttons = []
        self.report_neodataset_var = tk.BooleanVar(value=False)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_viewers()
        self.after(50, self._poll)

    def _build_ui(self):
        self.left = ttk.Frame(self, padding=10)
        self.left.pack(side="left", fill="y")

        self.report_frame = ttk.Frame(self.left)
        ttk.Checkbutton(
            self.report_frame,
            text="Use NeoDataset inputs",
            variable=self.report_neodataset_var,
        ).pack(side="left", fill="x", expand=True)

        buttons = [
            ("Estimate…", self._cmd_estimate),
            ("Record Actual…", self._cmd_record_actual),
            ("Evaluate", self._cmd_evaluate),
            ("Run Demo", self._cmd_demo),
            ("Run NeoDataset", self._cmd_neodataset),
            ("Learn Over Time…", self._cmd_learn),
            ("Generate Report", self._cmd_report),
        ]
        for text, command in buttons:
            btn = ttk.Button(self.left, text=text, command=command)
            if text == "Generate Report":
                btn.pack(side="top", fill="x", pady=2)
                self.report_frame.pack(side="top", fill="x", pady=(0, 6))
            else:
                btn.pack(side="top", fill="x", pady=2)
            self.command_buttons.append(btn)

        ttk.Separator(self.left, orient="horizontal").pack(side="top", fill="x", pady=8)

        btn = ttk.Button(self.left, text="Open Outputs", command=self._cmd_open_outputs)
        btn.pack(side="top", fill="x", pady=2)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        console_tab = ttk.Frame(self.notebook)
        self.notebook.add(console_tab, text="Console")
        self.log_text = scrolledtext.ScrolledText(console_tab, wrap="word", state="disabled")
        self.log_text.pack(fill="both", expand=True)

        self.viewers = []
        for title, path in VIEWER_FILES:
            tab = ttk.Frame(self.notebook)
            self.notebook.add(tab, text=title)
            widget = scrolledtext.ScrolledText(tab, wrap="word", state="disabled")
            widget.pack(fill="both", expand=True)
            self.viewers.append({"title": title, "path": path, "widget": widget})

        self.status_var = tk.StringVar()
        self.status_bar = ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(10, 4))
        self.status_bar.pack(side="bottom", fill="x")

    def _cmd_estimate(self):
        path = filedialog.askopenfilename(
            title="Select a user story JSON file",
            initialdir=str(USER_STORIES_DIR),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            self._run_command(["estimate", path], "estimate")

    def _cmd_record_actual(self):
        story_id = simpledialog.askstring("Record Actual", "Story ID:", parent=self)
        if not story_id:
            return
        hours = simpledialog.askstring("Record Actual", "Hours actually spent:", parent=self)
        if not hours:
            return
        try:
            float(hours)
        except ValueError:
            messagebox.showerror("Record Actual", "Hours must be a number.")
            return
        self._run_command(["record-actual", story_id, hours], "record-actual")

    def _cmd_evaluate(self):
        self._run_command(["evaluate"], "evaluate")

    def _cmd_demo(self):
        self._run_command(["demo"], "demo")

    def _cmd_neodataset(self):
        self._run_command(["run-neodataset"], "run-neodataset")

    def _cmd_learn(self):
        runs = simpledialog.askinteger(
            "Learn Over Time", "Number of runs:", parent=self, initialvalue=5, minvalue=1
        )
        if runs is None:
            return
        self._run_command(["learn-over-time", "--runs", str(runs)], "learn-over-time")

    def _cmd_report(self):
        args = ["report"]
        if self.report_neodataset_var.get():
            args.append("--neodataset")
        self._run_command(args, "report")

    def _cmd_open_outputs(self):
        target = str(OUTPUT_DIR)
        try:
            if hasattr(os, "startfile"):
                os.startfile(target)
            else:
                subprocess.Popen(["xdg-open", target])
        except OSError as exc:
            messagebox.showerror("Open Outputs", f"Could not open outputs folder:\n{exc}")

    def _run_command(self, args, display_name):
        if self.proc is not None:
            messagebox.showwarning("Busy", "A command is already running.")
            return
        self._write_log(f"$ python -m estimation_assistant {' '.join(args)}")
        self.current_name = display_name
        self.elapsed_mark = time.monotonic()
        self._set_status(f"Running: {display_name} ...")
        self._set_busy(True)
        cmdline = [sys.executable, "-m", "estimation_assistant"] + args
        try:
            self.proc = subprocess.Popen(
                cmdline,
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            self._set_status(f"Failed to start {display_name}: {exc}")
            self._set_busy(False)
            return
        threading.Thread(target=self._reader, args=(self.proc,), daemon=True).start()

    def _reader(self, proc):
        try:
            for line in proc.stdout:
                self.log_queue.put(line.rstrip("\n"))
        finally:
            self.log_queue.put(None)

    def _poll(self):
        try:
            while True:
                line = self.log_queue.get_nowait()
                if line is None:
                    self._finish_run()
                    return
                self._write_log(line)
        except queue.Empty:
            pass
        self.after(50, self._poll)

    def _finish_run(self):
        proc = self.proc
        rc = proc.poll()
        if rc is None:
            proc.wait(timeout=10)
            rc = proc.returncode
        self.proc = None
        elapsed = time.monotonic() - self.elapsed_mark
        label = "Finished" if rc == 0 else "Failed"
        self._set_status(f"{label}: {self.current_name} (exit {rc}) in {elapsed:.1f}s")
        self._set_busy(False)
        self._refresh_viewers()

    def _write_log(self, line):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _refresh_viewers(self):
        for view in self.viewers:
            path = view["path"]
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                text = f"(missing) {path}"
            widget = view["widget"]
            widget.configure(state="normal")
            widget.delete("1.0", "end")
            widget.insert("1.0", text)
            widget.configure(state="disabled")

    def _set_busy(self, busy):
        self._busy = busy
        state = "disabled" if busy else "normal"
        for btn in self.command_buttons:
            btn.configure(state=state)

    def _set_status(self, text):
        self.status_var.set(text)

    def _on_close(self):
        if self.proc is not None:
            if not messagebox.askyesno(
                "Running", "A command is still running. Terminate it and exit?"
            ):
                return
            try:
                self.proc.terminate()
            except OSError:
                pass
        self.destroy()


def main():
    App().mainloop()


if __name__ == "__main__":
    main()