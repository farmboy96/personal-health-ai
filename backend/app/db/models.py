from sqlalchemy import Column, Integer, String, Date, DateTime, Float, Text, ForeignKey, UniqueConstraint
from sqlalchemy.sql import func

from app.db.database import Base


class SourceFile(Base):
    __tablename__ = "source_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_hash = Column(String, unique=True, nullable=False, index=True)
    file_type = Column(String, nullable=True)
    stored_path = Column(String, nullable=True)
    source_category = Column(String, nullable=True)
    created_at = Column(DateTime, default=func.now())


class ImportRun(Base):
    __tablename__ = "import_runs"

    id = Column(Integer, primary_key=True, index=True)
    source_file_id = Column(Integer, ForeignKey("source_files.id"), nullable=True)
    import_type = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    status = Column(String, nullable=True)
    records_seen = Column(Integer, default=0)
    records_added = Column(Integer, default=0)
    records_skipped = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)


class LabTestMaster(Base):
    __tablename__ = "lab_test_master"

    id = Column(Integer, primary_key=True, index=True)
    canonical_name = Column(String, nullable=True)
    display_name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    default_unit = Column(String, nullable=True)


class LabResult(Base):
    __tablename__ = "lab_results"

    id = Column(Integer, primary_key=True, index=True)
    source_file_id = Column(Integer, ForeignKey("source_files.id"), nullable=True)
    import_run_id = Column(Integer, ForeignKey("import_runs.id"), nullable=True, index=True)
    test_id = Column(Integer, ForeignKey("lab_test_master.id"), nullable=True)

    lab_date = Column(Date, nullable=False, index=True)
    source_test_name = Column(String, nullable=False)
    result_value_text = Column(String, nullable=True)
    result_value_numeric = Column(Float, nullable=True)
    unit = Column(String, nullable=True)
    reference_range = Column(String, nullable=True)
    abnormal_flag = Column(String, nullable=True)
    dedupe_hash = Column(String, nullable=True, index=True)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    # next-phase normalization fields
    canonical_test_code = Column(String, nullable=True, index=True)
    canonical_test_name = Column(String, nullable=True)
    test_category = Column(String, nullable=True)
    panel_name = Column(String, nullable=True)


class LabTestCatalog(Base):
    __tablename__ = "lab_test_catalog"

    id = Column(Integer, primary_key=True, index=True)
    canonical_code = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String, nullable=False)
    category = Column(String, nullable=True)
    panel_name = Column(String, nullable=True)
    default_unit = Column(String, nullable=True)
    active = Column(Integer, nullable=False, default=1)


class LabTestAlias(Base):
    __tablename__ = "lab_test_alias"

    id = Column(Integer, primary_key=True, index=True)
    raw_name = Column(String, unique=True, nullable=False)
    normalized_lookup = Column(String, nullable=False, index=True)
    canonical_code = Column(String, nullable=False, index=True)
    source_scope = Column(String, nullable=True)
    notes = Column(String, nullable=True)


class GeneticVariant(Base):
    __tablename__ = "genetic_variants"
    __table_args__ = (
        UniqueConstraint("rsid", "genotype", name="uq_genetic_variants_rsid_genotype"),
    )

    id = Column(Integer, primary_key=True, index=True)
    rsid = Column(String(32), nullable=False, index=True)
    genotype = Column(String(16), nullable=False)
    magnitude = Column(Float, nullable=True)
    repute = Column(String(16), nullable=True)
    genes = Column(String(256), nullable=True)
    summary = Column(Text, nullable=True)
    detail = Column(Text, nullable=True)
    source_file_id = Column(Integer, ForeignKey("source_files.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())


class RawMeasurement(Base):
    __tablename__ = "raw_measurements"

    id = Column(Integer, primary_key=True, index=True)
    source_file_id = Column(Integer, ForeignKey("source_files.id"), nullable=True)
    import_run_id = Column(Integer, ForeignKey("import_runs.id"), nullable=True, index=True)
    metric_type = Column(String, nullable=False, index=True)
    source_name = Column(String, nullable=True)
    source_version = Column(String, nullable=True)
    device = Column(String, nullable=True)
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False)
    value = Column(Float, nullable=True)
    value_text = Column(String, nullable=True)
    unit = Column(String, nullable=True)
    dedupe_hash = Column(String, unique=True, nullable=False, index=True)
    raw_payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())