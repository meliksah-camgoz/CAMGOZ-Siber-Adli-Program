
from pathlib import Path

from modules.file_forensics.deep_inspector import (
    scan_embedded_signatures
)

test_path = Path("test_embedded.jpg")

# JPEG başlangıcı + test verisi + ZIP imzası
test_data = (
    b"\xFF\xD8\xFF"
    + b"CAMGOZ FORENSIC TEST DATA"
    + b"PK\x03\x04"
    + b"TEST ZIP CONTENT"
)

test_path.write_bytes(test_data)

results = scan_embedded_signatures(str(test_path))

print("\nCAMGOZ EMBEDDED SIGNATURE TEST")
print("-" * 40)

for result in results:
    print(f"Type: {result['file_type']}")
    print(f"Offset: {result['offset']}")
    print(f"Signature: {result['signature_hex']}")

if any(item["file_type"] == "ZIP Archive" for item in results):
    print("\nSUCCESS: Embedded ZIP signature detected!")
else:
    print("\nFAILED: ZIP signature was not detected.")
