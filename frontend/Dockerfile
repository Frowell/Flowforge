FROM node:22-slim AS base

WORKDIR /app

# Dependencies
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

# Application code
COPY frontend/ .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
