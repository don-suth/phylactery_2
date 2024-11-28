# Base Image
FROM tiangolo/uwsgi-nginx:python3.11

# Install requirements
COPY ./requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Install utility for Docker Secrets
RUN pip install --no-cache-dir --upgrade get_docker_secret

# Install utility for monitoring server perfomance
RUN pip install --no-cache-dir --upgrade uwsgitop

# Copy App
COPY . .

# Replace entrypoint
COPY entrypoint.sh /entrypoint.sh