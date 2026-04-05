# Personal Health AI - V1 Backend

The backend is built with Python, FastAPI, and SQLite. The primary goal of V1 is reliable data ingestion from multiple messy sources into a clean relational model. 

**Note: Ingestion pipelines are currently in progress. Only the Apple Health parsing pipeline is ready for testing.**

## Setup

1. **Virtual Environment**:
   ```bash
   cd backend
   python -m venv .venv
   .venv\Scripts\activate
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Initialize Database**:
   Run the following to initialize the schema. This builds your `data/health.db` file and the `data/raw/` directories.
   ```bash
   python init_db.py
   ```

## Ingestion Pipelines

Currently, only Apple Health ingestion is implemented. Support for historical Lab CSVs and recent PDF Lab results will follow.

### Apple Health
Imports a streamed `export.xml` from Apple Health safely without blowing up memory. 

To run the Apple Health ingestion:
```bash
cd backend
python -m app.ingestion.apple_health path/to/export.xml
```
