# D-DW-D Portal (DICOM → DICOMweb → DICOM Portal)

An automated medical imaging pipeline that seamlessly transfers DICOM studies through a DICOMweb intermediary, providing a modern bridge between traditional DICOM systems.

## Overview

The D-DW-D Portal implements a fully automated pipeline that:
1. **Receives** DICOM studies via traditional DIMSE protocol at Orthanc1
2. **Auto-forwards** studies to Orthanc2 using modern DICOMweb (HTTP/REST)
3. **Auto-extracts** studies from Orthanc2 back to DIMSE and saves to local filesystem

This creates a transparent portal that modernizes DICOM workflows while maintaining compatibility with legacy systems.

## Architecture

```
┌─────────────┐     DIMSE      ┌─────────────┐    DICOMweb    ┌─────────────┐     DIMSE      ┌─────────────┐
│   DICOM     │ ─────────────> │  Orthanc1   │ ────────────> │  Orthanc2   │ ─────────────> │    Local    │
│   Source    │                 │  (Gateway)  │                │  (Storage)  │                │  Directory  │
└─────────────┘                 └─────────────┘                └─────────────┘                └─────────────┘
                                      ↓                              ↓                              ↑
                                 Auto-forward                    Monitored                         │
                                 Lua Script                      by Python                         │
                                                                 Service ──────────────────────────┘
```

## Components

### 1. Orthanc1 (DICOM Gateway)
- **Role**: DICOM entry point and DICOMweb forwarder
- **Port**: 4242 (DIMSE), 8042 (HTTP)
- **AE Title**: ORTHANC1
- **Features**:
  - Receives traditional DICOM via DIMSE
  - Auto-forwards to Orthanc2 via DICOMweb using Lua script
  - PostgreSQL backend for performance

### 2. Orthanc2 (DICOMweb Storage)
- **Role**: DICOMweb storage and DIMSE provider
- **Port**: 4243 (DIMSE), 8043 (HTTP)
- **AE Title**: ORTHANC2
- **Features**:
  - Receives studies via DICOMweb from Orthanc1
  - Provides DIMSE access for retrieval
  - PostgreSQL backend for performance

### 3. Monitor Service
- **Role**: Automated study extractor
- **Features**:
  - Polls Orthanc2 every 5 seconds for new studies
  - Pulls studies via DIMSE C-MOVE
  - Saves to organized directory structure
  - Tracks processed studies to avoid duplicates

## Quick Start

### Prerequisites
- Docker and Docker Compose installed
- Port 4242 available for DICOM reception
- DICOM files to send (or use sample files)

### 1. Start the D-DW-D Portal

```bash
# Clone the repository (if not already done)
git clone https://github.com/your-repo/pyupsrs-dicomweb-stack.git
cd pyupsrs-dicomweb-stack

# Start all services
docker-compose -f docker-compose-auto-pipeline.yml up -d

# Verify services are running
docker-compose -f docker-compose-auto-pipeline.yml ps
```

### 2. Send DICOM Files

Using the included DICOM tools:
```bash
# Send a directory of DICOM files
docker run --rm --network pyupsrs-dicomweb-stack_orthanc-network \
  -v $(pwd)/your_dicom_files:/dicom/input \
  dicom-tools \
  python dicom_sender.py /dicom/input orthanc1 4242 ORTHANC1
```

Or from an external DICOM node:
```bash
# Configure your DICOM node to send to:
# Host: localhost (or server IP)
# Port: 4242
# AE Title: ORTHANC1
```

### 3. Monitor the Pipeline

Watch the automated flow in real-time:
```bash
# View monitor service logs
docker-compose -f docker-compose-auto-pipeline.yml logs -f orthanc2-monitor

# Check Orthanc1 logs (see forwards)
docker-compose -f docker-compose-auto-pipeline.yml logs -f orthanc1

# Check output directory
ls -la ./received_dicom/
```

### 4. Access the Output

Files are automatically organized in `./received_dicom/`:
```
received_dicom/
├── PatientID1/
│   └── StudyInstanceUID1/
│       └── SeriesInstanceUID1/
│           ├── SOPInstanceUID1.dcm
│           ├── SOPInstanceUID2.dcm
│           └── ...
└── PatientID2/
    └── StudyInstanceUID2/
        └── ...
```

## Configuration

### Environment Variables

Create a `.env` file to customize ports and settings:
```bash
# Orthanc1 ports
DICOM_PORT1=4242
HTTP_PORT1=8042

# Orthanc2 ports  
DICOM_PORT2=4243
HTTP_PORT2=8043

# PostgreSQL password
POSTGRES_PASSWORD=secure_password
```

### Monitor Service Settings

The monitor service can be configured via environment variables in docker-compose:
```yaml
environment:
  POLL_INTERVAL: 5        # Seconds between checks
  OUTPUT_DIR: /dicom/output
```

### Auto-forward Lua Script

The `orthanc1-autoforward.lua` script triggers on stable studies (default: 3 seconds after last instance received). Modify the `ORTHANC__STABLE_AGE` environment variable to adjust this timing.

## Web Interfaces

Access Orthanc web UIs for monitoring and management:
- **Orthanc1**: http://localhost:8042
- **Orthanc2**: http://localhost:8043

## Troubleshooting

### No files appearing in output directory
1. Check monitor service logs: `docker-compose -f docker-compose-auto-pipeline.yml logs orthanc2-monitor`
2. Verify Orthanc2 has studies: http://localhost:8043
3. Check DICOM connectivity between services

### Auto-forward not working
1. Check Orthanc1 logs: `docker-compose -f docker-compose-auto-pipeline.yml logs orthanc1`
2. Verify Lua script is loaded (should see in startup logs)
3. Check peer configuration in Orthanc1 settings

### C-MOVE failures
1. Verify DICOM modalities configuration in Orthanc2
2. Check network connectivity between containers
3. Ensure PYTHON_SCP modality is correctly configured

### Port conflicts
1. Change ports in `.env` file
2. Restart services: `docker-compose -f docker-compose-auto-pipeline.yml restart`

## Advanced Usage

### Scaling for Production

1. **Increase PostgreSQL resources**:
   ```yaml
   postgres1:
     deploy:
       resources:
         limits:
           memory: 2G
   ```

2. **Add data persistence**:
   ```yaml
   volumes:
     - ./orthanc1-storage:/var/lib/orthanc/db
     - ./postgres1-data:/var/lib/postgresql/data
   ```

3. **Configure SSL/TLS** for DICOMweb transfers

### Integration with Existing Systems

The D-DW-D Portal can be integrated into existing workflows:

1. **As a DICOM Router**: Forward specific studies based on rules
2. **As a Protocol Bridge**: Convert DIMSE-only systems to DICOMweb
3. **As a Study Archive**: Long-term storage with modern API access

## Demo Scenarios

### Scenario 1: Basic Transfer
```bash
# 1. Send sample DICOM files
docker run --rm --network pyupsrs-dicomweb-stack_orthanc-network \
  -v $(pwd)/sample_dicom:/dicom/input \
  dicom-tools \
  python dicom_sender.py /dicom/input orthanc1 4242 ORTHANC1

# 2. Watch the transfer
docker-compose -f docker-compose-auto-pipeline.yml logs -f orthanc2-monitor

# 3. Verify output
find ./received_dicom -name "*.dcm" | wc -l
```

### Scenario 2: Continuous Monitoring
```bash
# Start monitoring in one terminal
docker-compose -f docker-compose-auto-pipeline.yml logs -f orthanc2-monitor

# In another terminal, send files periodically
while true; do
  docker run --rm --network pyupsrs-dicomweb-stack_orthanc-network \
    -v $(pwd)/sample_dicom:/dicom/input \
    dicom-tools \
    python dicom_sender.py /dicom/input orthanc1 4242 ORTHANC1
  sleep 30
done
```

## Stopping the Portal

```bash
# Stop all services
docker-compose -f docker-compose-auto-pipeline.yml down

# Stop and remove all data (careful!)
docker-compose -f docker-compose-auto-pipeline.yml down -v
```

## Architecture Benefits

1. **Protocol Bridge**: Seamlessly converts between DIMSE and DICOMweb
2. **Automatic Flow**: No manual intervention required
3. **Scalable**: Each component can be scaled independently
4. **Monitored**: Full visibility into transfer status
5. **Organized Output**: Automatic directory structure by Patient/Study/Series
6. **Persistent State**: Remembers processed studies across restarts

## License

Same as parent project - see LICENSE file.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs from all services
3. Open an issue with detailed logs and configuration