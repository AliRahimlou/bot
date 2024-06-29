# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /usr/src/app

# Copy the current directory contents into the container at /usr/src/app
COPY . .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port available to the world outside this container
EXPOSE ${PORT}

# Define environment variable
ENV FLASK_APP=${FLASK_APP}

# Run server.py when the container launches
CMD ["flask", "run", "--host=127.0.0.1", "--port=${PORT}"]
