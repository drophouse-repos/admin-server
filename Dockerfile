# Use an official Python runtime as a parent image
FROM python:3.11

# Set the working directory to /app
WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    curl

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -

# Add Poetry to PATH
ENV PATH="/root/.local/bin:${PATH}"

# Copy only the necessary files for installation (avoid unnecessary cache invalidations)
COPY pyproject.toml poetry.lock /app/

# Install dependencies
RUN poetry install --no-root --only main

# Copy the rest of the application files
COPY . /app

# Expose port 80 for FastAPI application
EXPOSE 8080

# Define environment variable for FastAPI
ENV FASTAPI_ENV production

# Command to run your application
WORKDIR /app/server

CMD ["poetry", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
