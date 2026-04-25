import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.application.generate_clinical_report import generate_clinical_report
from app.application.generate_patient_report import generate_patient_report
from app.ai.client import get_usage_summary

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


def main():
    physician = generate_clinical_report()
    patient = generate_patient_report(clinical_report_id=physician["report_id"])
    print({"physician_report": physician, "patient_report": patient})
    summary = get_usage_summary()
    print("\n=== AI USAGE FOR THIS RUN ===")
    print(f"Calls:         {summary['calls']}")
    print(f"Input tokens:  {summary['input_tokens']:,}")
    print(f"Output tokens: {summary['output_tokens']:,}")
    if summary["estimated_cost_usd"] is not None:
        print(f"Est. cost USD: ${summary['estimated_cost_usd']:.4f}")
    else:
        print("Est. cost USD: (model not in pricing table)")


if __name__ == "__main__":
    main()
