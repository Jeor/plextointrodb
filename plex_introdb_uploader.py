#!/usr/bin/env python3
"""Upload Plex intro/credits markers to IntroDB with a small GUI."""

from __future__ import annotations

import json
import sqlite3
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tkinter import BooleanVar, END, IntVar, StringVar, Tk, filedialog, messagebox, ttk
from tkinter.scrolledtext import ScrolledText

CONFIG_PATH = Path.home() / ".plex_introdb_uploader.json"
DEFAULT_API_BASE = "https://api.introdb.app"
DEFAULT_ENDPOINT = "/submissions"


@dataclass
class Marker:
    marker_type: str
    start_ms: int | None
    end_ms: int | None
    metadata_item_id: int | None
    guid: str | None
    title: str | None

    def to_payload(self) -> dict:
        return {
            "source": "plex",
            "marker_type": self.marker_type,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "metadata_item_id": self.metadata_item_id,
            "guid": self.guid,
            "title": self.title,
        }


class IntroDBUploaderApp:
    def __init__(self, root: Tk) -> None:
        self.root = root
        self.root.title("Plex IntroDB Uploader")
        self.root.geometry("860x640")

        self.db_path = StringVar()
        self.api_base = StringVar(value=DEFAULT_API_BASE)
        self.endpoint = StringVar(value=DEFAULT_ENDPOINT)
        self.api_key = StringVar()

        self.dry_run = BooleanVar(value=True)
        self.use_limit = BooleanVar(value=True)
        self.limit = IntVar(value=10)
        self.include_intro = BooleanVar(value=True)
        self.include_credits = BooleanVar(value=True)

        self._load_config()
        self._build_ui()

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill="both", expand=True)

        row = 0
        ttk.Label(frame, text="Plex DB file (com.plexapp.plugins.library.db)").grid(row=row, column=0, sticky="w")
        ttk.Entry(frame, textvariable=self.db_path, width=75).grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Button(frame, text="Browse...", command=self._pick_db_file).grid(row=row, column=2, sticky="e")

        row += 1
        ttk.Label(frame, text="IntroDB API base URL").grid(row=row, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frame, textvariable=self.api_base).grid(row=row, column=1, columnspan=2, sticky="ew", padx=8, pady=(10, 0))

        row += 1
        ttk.Label(frame, text="Endpoint path").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.endpoint).grid(row=row, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0))

        row += 1
        ttk.Label(frame, text="API token (Bearer)").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=self.api_key, show="*").grid(row=row, column=1, columnspan=2, sticky="ew", padx=8, pady=(8, 0))

        row += 1
        opts = ttk.LabelFrame(frame, text="Options", padding=8)
        opts.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 0))

        ttk.Checkbutton(opts, text="Dry run (no network submissions)", variable=self.dry_run).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(opts, text="Limit submissions", variable=self.use_limit).grid(row=0, column=1, sticky="w", padx=(20, 0))
        ttk.Spinbox(opts, from_=1, to=5000, textvariable=self.limit, width=8).grid(row=0, column=2, sticky="w", padx=(8, 0))

        ttk.Checkbutton(opts, text="Include intro markers", variable=self.include_intro).grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Checkbutton(opts, text="Include credits markers", variable=self.include_credits).grid(row=1, column=1, sticky="w", pady=(8, 0), padx=(20, 0))

        row += 1
        actions = ttk.Frame(frame)
        actions.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.submit_button = ttk.Button(actions, text="Extract + Submit", command=self._start_submit)
        self.submit_button.pack(side="left")
        self.status_label = ttk.Label(actions, text="Ready")
        self.status_label.pack(side="left", padx=16)

        row += 1
        self.log_box = ScrolledText(frame, height=24, wrap="word")
        self.log_box.grid(row=row, column=0, columnspan=3, sticky="nsew", pady=(12, 0))

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(row, weight=1)

    def _pick_db_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose Plex database",
            filetypes=[("SQLite DB", "*.db"), ("All files", "*.*")],
        )
        if path:
            self.db_path.set(path)

    def _log(self, message: str) -> None:
        self.log_box.insert(END, message + "\n")
        self.log_box.see(END)

    def _set_status(self, text: str) -> None:
        self.status_label.configure(text=text)

    def _start_submit(self) -> None:
        if not self.db_path.get().strip():
            messagebox.showerror("Missing DB", "Please choose your Plex database file.")
            return
        if not self.dry_run.get() and not self.api_key.get().strip():
            messagebox.showerror("Missing token", "API token is required when dry run is off.")
            return

        self.submit_button.configure(state="disabled")
        self.log_box.delete("1.0", END)
        self._set_status("Running...")
        self._save_config()

        worker = threading.Thread(target=self._run_submission, daemon=True)
        worker.start()

    def _run_submission(self) -> None:
        try:
            markers = extract_markers(Path(self.db_path.get()))
            self.root.after(0, lambda: self._log(f"Found {len(markers)} candidate markers."))

            filtered = [
                m
                for m in markers
                if (m.marker_type == "intro" and self.include_intro.get())
                or (m.marker_type == "credits" and self.include_credits.get())
            ]
            if self.use_limit.get():
                filtered = filtered[: max(1, self.limit.get())]

            self.root.after(0, lambda: self._log(f"After filters: {len(filtered)} markers."))

            sent = 0
            failed = 0
            for idx, marker in enumerate(filtered, start=1):
                payload = marker.to_payload()
                if self.dry_run.get():
                    self.root.after(0, lambda p=payload: self._log("DRY RUN: " + json.dumps(p, ensure_ascii=False)))
                    sent += 1
                else:
                    ok, response = post_submission(
                        base_url=self.api_base.get().strip(),
                        endpoint=self.endpoint.get().strip(),
                        token=self.api_key.get().strip(),
                        payload=payload,
                    )
                    if ok:
                        sent += 1
                        self.root.after(0, lambda i=idx, r=response: self._log(f"[{i}] Submitted OK: {r}"))
                    else:
                        failed += 1
                        self.root.after(0, lambda i=idx, r=response: self._log(f"[{i}] Submit failed: {r}"))

            summary = f"Done. sent={sent}, failed={failed}, dry_run={self.dry_run.get()}"
            self.root.after(0, lambda: self._set_status(summary))
            self.root.after(0, lambda: self._log(summary))
        except Exception as exc:  # noqa: BLE001
            self.root.after(0, lambda: self._set_status("Error"))
            self.root.after(0, lambda: self._log(f"ERROR: {exc}"))
        finally:
            self.root.after(0, lambda: self.submit_button.configure(state="normal"))

    def _load_config(self) -> None:
        if not CONFIG_PATH.exists():
            return
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            return

        self.db_path.set(data.get("db_path", ""))
        self.api_base.set(data.get("api_base", DEFAULT_API_BASE))
        self.endpoint.set(data.get("endpoint", DEFAULT_ENDPOINT))
        self.api_key.set(data.get("api_key", ""))
        self.dry_run.set(bool(data.get("dry_run", True)))
        self.use_limit.set(bool(data.get("use_limit", True)))
        self.limit.set(int(data.get("limit", 10)))
        self.include_intro.set(bool(data.get("include_intro", True)))
        self.include_credits.set(bool(data.get("include_credits", True)))

    def _save_config(self) -> None:
        data = {
            "db_path": self.db_path.get().strip(),
            "api_base": self.api_base.get().strip(),
            "endpoint": self.endpoint.get().strip(),
            "api_key": self.api_key.get().strip(),
            "dry_run": self.dry_run.get(),
            "use_limit": self.use_limit.get(),
            "limit": self.limit.get(),
            "include_intro": self.include_intro.get(),
            "include_credits": self.include_credits.get(),
        }
        CONFIG_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def extract_markers(db_path: Path) -> list[Marker]:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(
            """
            SELECT tg.*, t.tag AS tag_name, mi.guid AS media_guid, mi.title AS media_title
            FROM taggings tg
            LEFT JOIN tags t ON t.id = tg.tag_id
            LEFT JOIN metadata_items mi ON mi.id = tg.metadata_item_id
            """
        ).fetchall()
    finally:
        con.close()

    markers: list[Marker] = []
    for row in rows:
        marker_type = infer_marker_type(row)
        if not marker_type:
            continue
        start_ms, end_ms = infer_offsets(row)
        markers.append(
            Marker(
                marker_type=marker_type,
                start_ms=start_ms,
                end_ms=end_ms,
                metadata_item_id=row["metadata_item_id"] if "metadata_item_id" in row.keys() else None,
                guid=row["media_guid"] if "media_guid" in row.keys() else None,
                title=row["media_title"] if "media_title" in row.keys() else None,
            )
        )
    return markers


def infer_marker_type(row: sqlite3.Row) -> str | None:
    candidates = []
    for key in row.keys():
        value = row[key]
        if isinstance(value, str):
            candidates.append(value.lower())

    haystack = " | ".join(candidates)
    if "intro" in haystack:
        return "intro"
    if "credit" in haystack:
        return "credits"
    return None


def infer_offsets(row: sqlite3.Row) -> tuple[int | None, int | None]:
    start_candidates = ["time_offset", "start_time_offset", "start_time_ms", "start_ms", "start_time"]
    end_candidates = ["end_time_offset", "end_time_ms", "end_ms", "end_time"]

    start = first_int_field(row, start_candidates)
    end = first_int_field(row, end_candidates)
    return start, end


def first_int_field(row: sqlite3.Row, names: list[str]) -> int | None:
    for name in names:
        if name not in row.keys():
            continue
        value = row[name]
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def post_submission(base_url: str, endpoint: str, token: str, payload: dict) -> tuple[bool, str]:
    url = base_url.rstrip("/") + "/" + endpoint.lstrip("/")
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urllib.request.urlopen(req, timeout=25) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return True, raw[:500]
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        return False, f"HTTP {exc.code}: {details[:500]}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main() -> None:
    root = Tk()
    IntroDBUploaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
