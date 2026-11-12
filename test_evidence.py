from database.database import init_database
from core.evidence_manager import EvidenceManager
from modules.file_forensics.analyzer import analyze_file


def main():

    print("Initializing CAMGOZ database...")

    init_database()

    file_path = input("\nEvidence file path: ").strip().strip('"')

    try:
        print("\nAnalyzing file...")

        result = analyze_file(file_path)

        evidence_id = EvidenceManager.add_evidence(
            result,
            notes="Initial forensic examination"
        )

        print(f"\nEvidence successfully saved!")
        print(f"Evidence ID: {evidence_id}")

        print("\n========== EVIDENCE RECORDS ==========")

        records = EvidenceManager.get_all_evidence()

        for evidence in records:

            print(f"\nID: {evidence.id}")
            print(f"File: {evidence.file_name}")
            print(f"SHA256: {evidence.sha256}")
            print(f"Type: {evidence.file_type}")
            print(f"Analyzed: {evidence.analyzed_at}")

        print("\n========== COMPLETED ==========")

    except Exception as error:
        print(f"\nOperation failed: {error}")


if __name__ == "__main__":
    main()
