# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install uv using the system pip
RUN pip install --no-cache-dir uv

# Create a virtual environment
RUN uv venv /opt/venv

# Activate the virtual environment
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy the dependencies file to the working directory
COPY requirements.txt .

# Install dependencies using uv
RUN uv pip install --no-cache -r requirements.txt

# Copy the application code
COPY main.py .

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Run uvicorn when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
