# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the script and model
COPY meter_reading.py .
COPY model.tflite .
COPY sample.jpg .

# Run the script
CMD ["python", "meter_reading.py"]