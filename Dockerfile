# Use Python as the base image
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app

# Install system dependencies, and patch OS packages to latest available
# in this Debian release (reduces known CVEs in the base image)
RUN apt-get update && apt-get upgrade -y && apt-get install -y gifsicle && apt-get clean

# Install Python dependencies in compatible versions
RUN pip install --no-cache-dir \
    numpy \
    networkx \
    scipy \
    matplotlib \
    imageio \
    pygifsicle \
    "protobuf>=4.21.5,<4.23" \
    "ortools==9.5.2237"

# Force uninstall incompatible protobuf version
RUN pip uninstall -y protobuf && pip install --no-cache-dir "protobuf>=4.21.5,<4.23"

# Install Maxfield without using its protobuf requirement
RUN pip install --no-deps .

# Define the default command
ENTRYPOINT ["maxfield-plan"]
