import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.application.generate_clinical_report import generate_clinical_report
from app.application.generate_patient_report import generate_patient_report


def main():
    physician = generate_clinical_report()
    patient = generate_patient_report(clinical_report_id=physician["report_id"])
    print({"physician_report": physician, "patient_report": patient})


if __name__ == "__main__":
    main()
