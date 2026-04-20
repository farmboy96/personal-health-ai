import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.application.generate_clinical_report import generate_clinical_report


def main():
    result = generate_clinical_report()
    print(result)


if __name__ == "__main__":
    main()
