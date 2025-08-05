#!/usr/bin/env python3
"""
DICOMweb to DIMSE Forwarder - Retrieve studies from DICOMweb and forward via DIMSE
"""

import sys
import requests
from io import BytesIO
from pydicom import dcmread
from pynetdicom import AE
from pynetdicom.sop_class import (
    CTImageStorage,
    MRImageStorage,
    EnhancedCTImageStorage,
    EnhancedMRImageStorage,
    RTStructureSetStorage,
    RTDoseStorage,
    RTPlanStorage,
    SecondaryCaptureImageStorage,
    DigitalXRayImageStorageForPresentation,
    DigitalMammographyXRayImageStorageForPresentation,
    ComputedRadiographyImageStorage,
    UltrasoundImageStorage,
    PositronEmissionTomographyImageStorage,
    NuclearMedicineImageStorage,
    XRayAngiographicImageStorage,
    XRayRadiofluoroscopicImageStorage,
)

def get_all_studies(dicomweb_url):
    """Query all studies from DICOMweb server"""
    try:
        response = requests.get(f"{dicomweb_url}/studies")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error querying studies: {e}")
        return []

def get_study_instances(dicomweb_url, study_uid):
    """Get all instances for a specific study"""
    try:
        response = requests.get(f"{dicomweb_url}/studies/{study_uid}")
        response.raise_for_status()
        
        # Parse multipart DICOM response
        content_type = response.headers.get('Content-Type', '')
        if 'multipart' in content_type:
            # Extract boundary
            boundary = content_type.split('boundary=')[-1].strip('"')
            return parse_multipart_dicom(response.content, boundary)
        else:
            # Single instance
            return [response.content]
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving study {study_uid}: {e}")
        return []

def parse_multipart_dicom(data, boundary):
    """Parse multipart DICOM response"""
    instances = []
    parts = data.split(f'--{boundary}'.encode())
    
    for part in parts[1:-1]:  # Skip first and last parts
        # Find the start of DICOM data (after headers)
        dicom_start = part.find(b'\r\n\r\n')
        if dicom_start != -1:
            dicom_data = part[dicom_start + 4:]
            if dicom_data:
                instances.append(dicom_data)
    
    return instances

def forward_to_dimse(dicom_data_list, scp_address, scp_port, scp_ae_title):
    """Forward DICOM instances to a DIMSE SCP"""
    # Initialize the Application Entity
    ae = AE(ae_title='DICOMWEB_SCU')
    
    # Add presentation contexts
    storage_classes = [
        CTImageStorage,
        MRImageStorage,
        EnhancedCTImageStorage,
        EnhancedMRImageStorage,
        RTStructureSetStorage,
        RTDoseStorage,
        RTPlanStorage,
        SecondaryCaptureImageStorage,
        DigitalXRayImageStorageForPresentation,
        DigitalMammographyXRayImageStorageForPresentation,
        ComputedRadiographyImageStorage,
        UltrasoundImageStorage,
        PositronEmissionTomographyImageStorage,
        NuclearMedicineImageStorage,
        XRayAngiographicImageStorage,
        XRayRadiofluoroscopicImageStorage,
    ]
    
    for storage_class in storage_classes:
        ae.add_requested_context(storage_class)
    
    # Associate with the SCP
    print(f"Connecting to {scp_ae_title} at {scp_address}:{scp_port}")
    assoc = ae.associate(scp_address, scp_port, ae_title=scp_ae_title)
    
    if assoc.is_established:
        print("Association established")
        
        success_count = 0
        for dicom_data in dicom_data_list:
            try:
                # Read DICOM from bytes
                ds = dcmread(BytesIO(dicom_data))
                
                # Send the dataset
                status = assoc.send_c_store(ds)
                
                if status and status.Status == 0x0000:
                    print(f"✓ Successfully forwarded: {ds.SOPInstanceUID}")
                    success_count += 1
                else:
                    print(f"✗ Failed to forward instance")
                    
            except Exception as e:
                print(f"✗ Error forwarding instance: {str(e)}")
        
        # Release the association
        assoc.release()
        print(f"\nCompleted: {success_count}/{len(dicom_data_list)} instances forwarded")
        return success_count
    else:
        print("Failed to establish association")
        return 0

def dicomweb_to_dimse_pipeline(dicomweb_url, scp_address, scp_port, scp_ae_title, study_uid=None):
    """
    Main pipeline: Retrieve from DICOMweb and forward to DIMSE
    
    Args:
        dicomweb_url: Base URL of DICOMweb server
        scp_address: Target DIMSE SCP address
        scp_port: Target DIMSE SCP port
        scp_ae_title: Target DIMSE SCP AE Title
        study_uid: Specific study UID to forward (optional, if None forwards all)
    """
    print(f"DICOMweb to DIMSE Pipeline")
    print(f"Source: {dicomweb_url}")
    print(f"Target: {scp_ae_title}@{scp_address}:{scp_port}\n")
    
    if study_uid:
        # Forward specific study
        print(f"Retrieving study {study_uid}...")
        instances = get_study_instances(dicomweb_url, study_uid)
        if instances:
            print(f"Retrieved {len(instances)} instances")
            forward_to_dimse(instances, scp_address, scp_port, scp_ae_title)
        else:
            print("No instances found")
    else:
        # Forward all studies
        studies = get_all_studies(dicomweb_url)
        print(f"Found {len(studies)} studies\n")
        
        total_forwarded = 0
        for study in studies:
            study_uid = study.get('0020000D', {}).get('Value', [None])[0]
            if study_uid:
                print(f"\nProcessing study {study_uid}...")
                instances = get_study_instances(dicomweb_url, study_uid)
                if instances:
                    print(f"Retrieved {len(instances)} instances")
                    forwarded = forward_to_dimse(instances, scp_address, scp_port, scp_ae_title)
                    total_forwarded += forwarded
        
        print(f"\n\nTotal instances forwarded: {total_forwarded}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python dicomweb_to_dimse.py <dicomweb_url> <scp_address> <scp_port> <scp_ae_title> [study_uid]")
        print("Example: python dicomweb_to_dimse.py http://localhost:9080/dicom-web localhost 11112 DESTINATION_SCP")
        print("         python dicomweb_to_dimse.py http://localhost:9080/dicom-web localhost 11112 DESTINATION_SCP 1.2.3.4.5")
        sys.exit(1)
    
    dicomweb_url = sys.argv[1].rstrip('/')
    scp_address = sys.argv[2]
    scp_port = int(sys.argv[3])
    scp_ae_title = sys.argv[4]
    study_uid = sys.argv[5] if len(sys.argv) > 5 else None
    
    dicomweb_to_dimse_pipeline(dicomweb_url, scp_address, scp_port, scp_ae_title, study_uid)