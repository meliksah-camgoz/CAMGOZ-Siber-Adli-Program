
from pathlib import Path
from threading import Lock

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from database.database import SessionLocal
from database.models import USBDevice, USBActivity


class USBFileEventHandler(FileSystemEventHandler):

    def __init__(
        self,
        device_key: str,
        session_id: str,
        drive_letter: str
    ):
        super().__init__()

        self.device_key = device_key
        self.session_id = session_id
        self.drive_letter = drive_letter

    def record_event(self, event_type, file_path, details=None):

        path = Path(file_path)

        try:
            with SessionLocal() as session:

                device = session.query(USBDevice).filter_by(
                    device_key=self.device_key
                ).first()

                if device is None:
                    print("[USB FILE MONITOR] Device not found.")
                    return

                activity = USBActivity(
                    device_id=device.id,
                    session_id=self.session_id,
                    event_type=event_type,
                    event_time=USBFileMonitor.current_time(),
                    source="LIVE_FILE_MONITOR",
                    drive_letter=self.drive_letter,
                    volume_label=None,
                    file_name=path.name,
                    file_path=str(path),
                    details=details or event_type
                )

                session.add(activity)
                session.commit()

            print(
                f"[USB FILE MONITOR] {event_type}: {path}"
            )

        except Exception as exc:
            print(
                f"[USB FILE MONITOR] Database error: {exc}"
            )

    def on_created(self, event):

        if event.is_directory:
            return

        self.record_event(
            "FILE_CREATED",
            event.src_path,
            "New file detected on USB device."
        )

    def on_modified(self, event):

        if event.is_directory:
            return

        self.record_event(
            "FILE_MODIFIED",
            event.src_path,
            "File modification detected on USB device."
        )

    def on_deleted(self, event):

        if event.is_directory:
            return

        self.record_event(
            "FILE_DELETED",
            event.src_path,
            "File deletion detected on USB device."
        )

    def on_moved(self, event):

        if event.is_directory:
            return

        destination = event.dest_path

        self.record_event(
            "FILE_RENAMED",
            destination,
            f"Previous path: {event.src_path}"
        )


class USBFileMonitor:

    def __init__(self):

        self.observers = {}
        self.lock = Lock()

    @staticmethod
    def current_time():
        from datetime import datetime

        return datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

    def start_monitoring(
        self,
        drive_path: str,
        device_key: str,
        session_id: str
    ):

        drive_path = str(Path(drive_path))

        with self.lock:

            if drive_path in self.observers:
                return

            if not Path(drive_path).exists():
                print(
                    f"[USB FILE MONITOR] Drive unavailable: {drive_path}"
                )
                return

            drive_letter = Path(drive_path).drive

            handler = USBFileEventHandler(
                device_key=device_key,
                session_id=session_id,
                drive_letter=drive_letter
            )

            observer = Observer()

            observer.schedule(
                handler,
                drive_path,
                recursive=True
            )

            try:
                observer.start()

                self.observers[drive_path] = observer

                print(
                    f"[USB FILE MONITOR] Started: {drive_path}"
                )

            except Exception as exc:
                print(
                    f"[USB FILE MONITOR] Start error: {exc}"
                )

    def stop_monitoring(self, drive_path: str):

        drive_path = str(Path(drive_path))

        with self.lock:

            observer = self.observers.pop(
                drive_path,
                None
            )

        if observer is None:
            return

        observer.stop()
        observer.join(timeout=5)

        print(
            f"[USB FILE MONITOR] Stopped: {drive_path}"
        )

    def stop_all(self):

        with self.lock:
            observers = list(self.observers.items())
            self.observers.clear()

        for drive_path, observer in observers:

            observer.stop()
            observer.join(timeout=5)

            print(
                f"[USB FILE MONITOR] Stopped: {drive_path}"
            )
