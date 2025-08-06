#!/bin/bash

echo "Resetting D-DW-D Pipeline..."
echo "============================="

# Stop all services
echo "Stopping services..."
docker-compose -f docker-compose-auto-pipeline.yml down

# Remove volumes to clear all stored data
echo "Removing data volumes..."
docker volume rm pyupsrs-dicomweb-stack-main_postgres1-data 2>/dev/null
docker volume rm pyupsrs-dicomweb-stack-main_postgres2-data 2>/dev/null
docker volume rm pyupsrs-dicomweb-stack-main_orthanc1-storage 2>/dev/null
docker volume rm pyupsrs-dicomweb-stack-main_orthanc2-storage 2>/dev/null

# Clear received files
echo "Clearing received DICOM files..."
rm -rf ./received_dicom/*
rm -f ./received_dicom/.processed_studies.json

# Create fresh output directory
mkdir -p ./received_dicom

echo ""
echo "Pipeline has been reset!"
echo ""
echo "To start fresh, run:"
echo "  docker-compose -f docker-compose-auto-pipeline.yml up -d"
echo ""