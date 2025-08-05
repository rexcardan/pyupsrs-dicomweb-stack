# D-DW-D Portal - Quick Demo Guide

## 5-Minute Demo Setup

### 1. Start the Portal (30 seconds)
```bash
# Start all services
docker-compose -f docker-compose-auto-pipeline.yml up -d

# Wait for services to be ready
sleep 10

# Verify all services are running
docker-compose -f docker-compose-auto-pipeline.yml ps
```

### 2. Open Monitoring Terminal (10 seconds)
```bash
# In a new terminal, watch the automated pipeline
docker-compose -f docker-compose-auto-pipeline.yml logs -f orthanc2-monitor
```

### 3. Send Test DICOM Files (30 seconds)
```bash
# In another terminal, send sample DICOM files
docker run --rm --network pyupsrs-dicomweb-stack_orthanc-network \
  -v $(pwd)/sample_dicom:/dicom/input \
  dicom-tools \
  python dicom_sender.py /dicom/input orthanc1 4242 ORTHANC1
```

### 4. Watch the Magic Happen! 

In the monitoring terminal, you'll see:
```
[2024-01-15 10:30:45] Found 1 new studies
Processing study: 2.25.123456789...
  → Requesting study via C-MOVE...
  ✓ Received instance 1: 1.2.3.4.5.dcm
  ✓ Received instance 2: 1.2.3.4.6.dcm
  ✓ Study transfer completed. Received 2 instances.
```

### 5. Check the Results (20 seconds)
```bash
# See the organized output
tree ./received_dicom/

# Count transferred files
find ./received_dicom -name "*.dcm" | wc -l
```

## What Just Happened?

1. **DICOM files** were sent to **Orthanc1** via traditional DIMSE
2. **Orthanc1** automatically forwarded them to **Orthanc2** via DICOMweb
3. **Monitor service** detected new studies and pulled them via DIMSE
4. **Files** were saved to `./received_dicom/` in organized folders

## Key Demo Points

### 🚀 Fully Automated
- No manual intervention required
- Studies flow automatically through the pipeline

### 🌐 Protocol Bridge
- Input: Traditional DIMSE (port 4242)
- Transport: Modern DICOMweb (HTTP/REST)
- Output: DIMSE to filesystem

### 📁 Smart Organization
```
received_dicom/
├── PATIENT001/
│   └── 2.25.123.../      # Study UID
│       └── 1.2.840.../   # Series UID
│           ├── image1.dcm
│           └── image2.dcm
```

### 🔄 Continuous Operation
- Monitors every 5 seconds
- Remembers processed studies
- Survives restarts

## Live Dashboard Views

Open in browser during demo:
- **Orthanc1**: http://localhost:8042 (See incoming studies)
- **Orthanc2**: http://localhost:8043 (See stored studies)

## Clean Demo Reset

```bash
# Stop services
docker-compose -f docker-compose-auto-pipeline.yml down

# Clear output directory
rm -rf ./received_dicom/*

# Restart fresh
docker-compose -f docker-compose-auto-pipeline.yml up -d
```

## Demo Talking Points

1. **Healthcare Integration Challenge**: "Many hospitals have legacy DICOM systems that can't speak modern protocols"

2. **D-DW-D Solution**: "This portal transparently bridges old and new, enabling modern workflows without replacing infrastructure"

3. **Real-world Use Cases**:
   - Cloud migration of imaging data
   - Multi-site image sharing
   - AI/ML pipeline integration
   - Disaster recovery systems

4. **Technical Benefits**:
   - Zero-configuration for DICOM sources
   - RESTful API in the middle for integration
   - Automatic error handling and retry
   - Scalable architecture

## Troubleshooting Demo Issues

**Nothing showing in monitor?**
- Check if Orthanc1 received files: http://localhost:8042
- Verify network: `docker network ls | grep orthanc`

**Files not appearing?**
- Check permissions: `ls -la ./received_dicom/`
- Look for errors: `docker-compose -f docker-compose-auto-pipeline.yml logs orthanc2-monitor | grep -i error`

**Services not starting?**
- Check ports: `netstat -an | grep -E '4242|4243|8042|8043'`
- Free up ports if needed

## Advanced Demo Options

### Show High Volume
```bash
# Send 100 files in batches
for i in {1..10}; do
  docker run --rm --network pyupsrs-dicomweb-stack_orthanc-network \
    -v $(pwd)/sample_dicom:/dicom/input \
    dicom-tools \
    python dicom_sender.py /dicom/input orthanc1 4242 ORTHANC1
  sleep 2
done
```

### Show Resilience
```bash
# Stop Orthanc2 temporarily
docker-compose -f docker-compose-auto-pipeline.yml stop orthanc2

# Send files (they queue in Orthanc1)
# ... send files ...

# Start Orthanc2 - watch automatic catch-up
docker-compose -f docker-compose-auto-pipeline.yml start orthanc2
```

### Show API Access
```bash
# Query studies via DICOMweb
curl -s http://localhost:8043/dicom-web/studies | jq .

# Get study metadata
curl -s http://localhost:8043/dicom-web/studies/[StudyUID]/metadata | jq .[0]
```

---

**Demo Duration**: 5-10 minutes
**Key Message**: "D-DW-D Portal: Bridging Legacy DICOM with Modern Healthcare IT"