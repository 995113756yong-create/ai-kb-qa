FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (better caching)
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend and frontend code
COPY backend/ backend/
COPY frontend/ frontend/

# Create uploads directory
RUN mkdir -p backend/uploads

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]