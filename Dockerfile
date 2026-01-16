# Build webapp
FROM node:20-alpine AS webapp-builder
WORKDIR /app/webapp
COPY webapp/package*.json ./
RUN npm install
COPY webapp/ ./
RUN npm run build

# Python runtime
FROM python:3.11-slim
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY Procfile ./

# Copy built webapp
COPY --from=webapp-builder /app/webapp/dist ./webapp/dist

# Run
CMD ["python", "-m", "src.main"]
