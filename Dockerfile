FROM python:3.11-slim

WORKDIR /app

# Install only the dependency needed for the broker
RUN pip install --no-cache-dir pyzmq

# Copy broker source
COPY src/broker.py ./

EXPOSE 5555

CMD ["python", "broker.py"]

