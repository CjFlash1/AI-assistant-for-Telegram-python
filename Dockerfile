# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for pyzbar (QR code reading) and other libraries
# libzbar0 is critical for QR detection on Linux
RUN apt-get update && apt-get install -y \
    libzbar0 \
    libgl1 \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create directory for local storage if needed (though we use Pinecone)
# RUN mkdir -p data

# Define environment variable for unbuffered logging
ENV PYTHONUNBUFFERED=1

# Run the bot
CMD ["python", "run.py"]
