
import json
import re
import subprocess
import uuid

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from sqlalchemy import select

from database.database import SessionLocal
from database.models import USBDevice, USBActivity
from modules.windows_artifacts.usb_file_monitor import USBFileMonitor


class USBMonitor(QObject):

    def __init__(self, parent=None, interval_ms=5000):
        super().__init__(parent)

        self.timer = QTimer(self)
        self.timer.setInterval(interval_ms)
        self.timer.timeout.connect(self.scan_devices)

        self.known_devices = {}
        self.initialized = False

        # File activity monitoring
        self.file_monitor = USBFileMonitor()
        self.monitored_paths = {}

    @staticmethod
    def current_time():
        return datetime.now().astimezone().isoformat(
            timespec="seconds"
        )

    @staticmethod
    def get_usb_devices():
        """
        USB bellek, harici SSD ve HDD cihazlarını algılar.
        Dahili diskleri USB olarak değerlendirmez.
        """

        powershell_script = r'''
        $results = @()

        $usbDisks = Get-Disk | Where-Object {
            $_.BusType -eq 'USB'
        }

        foreach ($disk in $usbDisks) {

            $driveLetters = @()
            $volumeLabels = @()

            $partitions = Get-Partition -DiskNumber $disk.Number `
                -ErrorAction SilentlyContinue

            foreach ($partition in $partitions) {

                $volume = $partition | Get-Volume `
                    -ErrorAction SilentlyContinue

                if ($volume) {

                    if ($volume.DriveLetter) {
                        $driveLetters += "$($volume.DriveLetter):"
                    }

                    if ($volume.FileSystemLabel) {
                        $volumeLabels += $volume.FileSystemLabel
                    }
                }
            }

            $physicalPath = "\\.\PHYSICALDRIVE$($disk.Number)"

            $cimDisk = Get-CimInstance Win32_DiskDrive |
                Where-Object {
                    $_.DeviceID -eq $physicalPath
                }

            $results += [PSCustomObject]@{
                DiskNumber = $disk.Number
                Model = $disk.FriendlyName
                SerialNumber = $disk.SerialNumber
                UniqueId = $disk.UniqueId
                PNPDeviceID = $cimDisk.PNPDeviceID
                DeviceID = $physicalPath
                DriveLetters = @($driveLetters)
                VolumeLabels = @($volumeLabels)
            }
        }

        ConvertTo-Json -InputObject @($results) -Depth 4 -Compress
        '''

        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    powershell_script
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )

            if result.returncode != 0:
                raise RuntimeError(result.stderr.strip())

            output = result.stdout.strip()

            if not output:
                return {}

            raw_devices = json.loads(output)

            if isinstance(raw_devices, dict):
                raw_devices = [raw_devices]

            devices = {}

            for item in raw_devices:

                pnp_id = item.get("PNPDeviceID") or ""
                serial = (item.get("SerialNumber") or "").strip()
                model = (
                    item.get("Model") or "Unknown USB Device"
                ).strip()

                if pnp_id:
                    device_key = f"PNP:{pnp_id}"
                elif serial:
                    device_key = f"SERIAL:{serial}"
                else:
                    device_key = (
                        f"UNIQUE:{item.get('UniqueId') or item.get('DeviceID')}"
                    )

                vendor_match = re.search(
                    r"VEN_([^&]+)",
                    pnp_id,
                    re.IGNORECASE
                )

                product_match = re.search(
                    r"PROD_([^&]+)",
                    pnp_id,
                    re.IGNORECASE
                )

                drive_letters = item.get("DriveLetters") or []
                volume_labels = item.get("VolumeLabels") or []

                if isinstance(drive_letters, str):
                    drive_letters = [drive_letters]

                if isinstance(volume_labels, str):
                    volume_labels = [volume_labels]

                devices[device_key] = {
                    "device_key": device_key,
                    "instance_id": pnp_id or None,
                    "hardware_id": (
                        pnp_id.split("\\")[0] if pnp_id else None
                    ),
                    "vendor_id": (
                        vendor_match.group(1) if vendor_match else None
                    ),
                    "product_id": (
                        product_match.group(1) if product_match else None
                    ),
                    "manufacturer": None,
                    "device_name": model,
                    "serial_number": serial or None,
                    "disk_number": item.get("DiskNumber"),
                    "physical_device": item.get("DeviceID"),
                    "drive_letters": drive_letters,
                    "volume_labels": volume_labels
                }

            return devices

        except Exception as exc:
            print(f"[USB MONITOR] Device scan error: {exc}")
            return {}

    def start(self):

        if self.timer.isActive():
            return

        print("[USB MONITOR] Started.")

        self.scan_devices()
        self.timer.start()

    def stop(self):

        if self.timer.isActive():
            self.timer.stop()

        self.file_monitor.stop_all()
        self.monitored_paths.clear()

        print("[USB MONITOR] Stopped.")

    def scan_devices(self):

        try:
            current_devices = self.get_usb_devices()

            # İlk tarama
            if not self.initialized:

                for key, device in current_devices.items():

                    session_id = self.record_connection(
                        device,
                        event_type="DETECTED_AT_STARTUP",
                        source="LIVE_STARTUP_SCAN"
                    )

                    device["session_id"] = session_id

                    if session_id:
                        self.sync_file_watchers(device)

                self.known_devices = current_devices
                self.initialized = True

                return

            # Yeni bağlanan veya hâlihazırda bağlı cihazlar
            for key, device in current_devices.items():

                if key not in self.known_devices:

                    session_id = self.record_connection(
                        device,
                        event_type="CONNECTED",
                        source="LIVE_MONITOR"
                    )

                    device["session_id"] = session_id

                else:

                    previous_device = self.known_devices[key]

                    device["session_id"] = previous_device.get(
                        "session_id"
                    )

                if device.get("session_id"):
                    self.sync_file_watchers(device)

            # Bağlantısı kesilen cihazlar
            for key, previous_device in self.known_devices.items():

                if key not in current_devices:

                    self.stop_device_watchers(key)

                    self.record_disconnection(previous_device)

            self.known_devices = current_devices

        except Exception as exc:
            print(f"[USB MONITOR] Scan error: {exc}")

    # -------------------------------------------------
    # FILE MONITOR INTEGRATION
    # -------------------------------------------------

    def sync_file_watchers(self, device):

        device_key = device["device_key"]
        session_id = device.get("session_id")

        if not session_id:
            return

        desired_paths = set()

        for letter in device.get("drive_letters", []):

            letter = letter.strip().upper()

            if not letter:
                continue

            drive_path = f"{letter.rstrip(':')}:\\"

            if Path(drive_path).exists():
                desired_paths.add(drive_path)

        current_paths = self.monitored_paths.get(
            device_key,
            set()
        )

        # Artık mevcut olmayan sürücüleri durdur
        for old_path in current_paths - desired_paths:

            self.file_monitor.stop_monitoring(old_path)

        # Yeni sürücüleri izlemeye başla
        for new_path in desired_paths - current_paths:

            self.file_monitor.start_monitoring(
                drive_path=new_path,
                device_key=device_key,
                session_id=session_id
            )

        self.monitored_paths[device_key] = desired_paths

    def stop_device_watchers(self, device_key):

        paths = self.monitored_paths.pop(
            device_key,
            set()
        )

        for drive_path in paths:
            self.file_monitor.stop_monitoring(drive_path)

    # -------------------------------------------------
    # DATABASE OPERATIONS
    # -------------------------------------------------

    def get_or_create_device(self, session, device_data):

        device = session.scalar(
            select(USBDevice).where(
                USBDevice.device_key == device_data["device_key"]
            )
        )

        now = self.current_time()

        if device is None:

            device = USBDevice(
                device_key=device_data["device_key"],
                instance_id=device_data["instance_id"],
                hardware_id=device_data["hardware_id"],
                vendor_id=device_data["vendor_id"],
                product_id=device_data["product_id"],
                manufacturer=device_data["manufacturer"],
                device_name=device_data["device_name"],
                serial_number=device_data["serial_number"],
                first_seen_at=now,
                last_seen_at=now,
                created_at=now
            )

            session.add(device)
            session.flush()

        else:

            device.last_seen_at = now
            device.device_name = device_data["device_name"]

        return device

    def create_activity(
        self,
        session,
        device,
        device_data,
        event_type,
        source,
        session_id
    ):

        now = self.current_time()

        drive_letters = device_data.get("drive_letters", [])
        volume_labels = device_data.get("volume_labels", [])

        activity = USBActivity(
            device_id=device.id,
            session_id=session_id,
            event_type=event_type,
            event_time=now,
            source=source,
            drive_letter=(
                drive_letters[0] if drive_letters else None
            ),
            volume_label=(
                ", ".join(volume_labels) if volume_labels else None
            ),
            file_name=None,
            file_path=(
                drive_letters[0] + "\\" if drive_letters else None
            ),
            details=(
                f"Model: {device_data['device_name']}; "
                f"Serial: {device_data['serial_number']}; "
                f"Physical device: {device_data['physical_device']}; "
                f"Drive letters: {', '.join(drive_letters) or 'None'}"
            )
        )

        session.add(activity)

    def record_connection(self, device_data, event_type, source):

        session_id = str(uuid.uuid4())

        try:

            with SessionLocal() as session:

                device = self.get_or_create_device(
                    session,
                    device_data
                )

                self.create_activity(
                    session,
                    device,
                    device_data,
                    event_type,
                    source,
                    session_id
                )

                session.commit()

            print(
                f"[USB MONITOR] {event_type}: "
                f"{device_data['device_name']} "
                f"({', '.join(device_data['drive_letters']) or 'No drive letter'})"
            )

            return session_id

        except Exception as exc:

            print(
                f"[USB MONITOR] Connection save error: {exc}"
            )

            return None

    def record_disconnection(self, device_data):

        try:

            with SessionLocal() as session:

                device = session.scalar(
                    select(USBDevice).where(
                        USBDevice.device_key == device_data["device_key"]
                    )
                )

                if device is None:
                    return

                self.create_activity(
                    session,
                    device,
                    device_data,
                    "DISCONNECTED",
                    "LIVE_MONITOR",
                    None
                )

                device.last_seen_at = self.current_time()

                session.commit()

            print(
                f"[USB MONITOR] DISCONNECTED: "
                f"{device_data['device_name']}"
            )

        except Exception as exc:

            print(
                f"[USB MONITOR] Disconnection save error: {exc}"
            )
