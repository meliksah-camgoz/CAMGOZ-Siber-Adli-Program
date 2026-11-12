
import json

from modules.file_forensics.analyzer import analyze_file


file_path = input("Analyze file path: ").strip().strip('"')

try:
    result = analyze_file(file_path)

    print("\n========== CAMGOZ FORENSICS ==========\n")

    print(json.dumps(
        result,
        indent=4,
        ensure_ascii=False
    ))

    print("\n========== ANALYSIS COMPLETED ==========")

except Exception as error:
    print(f"\nAnalysis failed: {error}")
