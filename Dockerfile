# Stage 1: Authentication
FROM python:3.10-slim as auth-stage

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Ensure the directory for the session file exists and has the right permissions
RUN mkdir -p /usr/src/app && chmod -R 777 /usr/src/app

# Run the authentication script
CMD ["python", "generate_session.py"]

# Stage 2: Final Stage
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container
COPY . .

# Copy the session file from the auth-stage
COPY --from=auth-stage /usr/src/app/session_name.session /usr/src/app/session_name.session

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port available to the world outside this container
EXPOSE ${PORT}

# Define environment variable
ENV FLASK_APP=server.py

# Run server.py when the container launches
CMD ["flask", "run", "--host=0.0.0.0", "--port=${PORT}"]
