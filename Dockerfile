# Use an official Python runtime as a parent  image
FROM python:3.9

# Set the working directory to /app
WORKDIR /app

RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0

# Copy only the necessary files for installation (avoid unnecessary cache invalidations)
COPY requirements.txt /app/requirements.txt

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files
COPY . /app

# Expose port 80 for FastAPI application
EXPOSE 80

# Define environment variable for FastAPI
ENV FASTAPI_ENV production

# Command to run your application
WORKDIR /app/server

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
