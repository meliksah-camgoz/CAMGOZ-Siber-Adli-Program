
from core.evidence_manager import EvidenceManager
from core.audit_logger import verify_audit_chain


def main():

    print("\n========== CAMGOZ INTEGRITY TEST ==========\n")

    evidence_id = int(input("Evidence ID: "))

    result = EvidenceManager.verify_evidence_integrity(
        evidence_id
    )

    print("\n========== VERIFICATION RESULT ==========\n")

    for key, value in result.items():
        print(f"{key}: {value}")

    print("\n========== AUDIT CHAIN ==========\n")

    audit_result = verify_audit_chain()

    print(audit_result)

    if audit_result["valid"]:
        print("\nAUDIT CHAIN: VALID")
    else:
        print("\nAUDIT CHAIN: INVALID")


if __name__ == "__main__":
    main()
