#!/bin/bash
# Generate self-signed cert for localhost development
mkdir -p nginx/certs
openssl req -x509 -nodes -days 365 \
  -newkey rsa:2048 \
  -keyout nginx/certs/key.pem \
  -out nginx/certs/cert.pem \
  -subj "/CN=localhost"
echo "Created self-signed cert in nginx/certs/"