#!/usr/bin/env python3
"""
DICOM Sender - Send DICOM files from a folder to Orthanc via DIMSE
"""

import os
import sys
from pydicom import dcmread
from pynetdicom import AE, debug_logger
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

# Configure logging (optional)
# debug_logger()

def send_dicom_files(source_folder, scp_address='localhost', scp_port=4242, scp_ae_title='ORTHANC'):
    """
    Send all DICOM files from a folder to an SCP via DIMSE C-STORE
    
    Args:
        source_folder: Path to folder containing DICOM files
        scp_address: IP address or hostname of the SCP
        scp_port: Port number of the SCP
        scp_ae_title: AE Title of the SCP
    """
    # Initialize the Application Entity
    ae = AE(ae_title='PYTHON_SCU')
    
    # Add presentation contexts for common SOP Classes
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
    
    # Find all DICOM files
    dicom_files = []
    for root, dirs, files in os.walk(source_folder):
        for file in files:
            filepath = os.path.join(root, file)
            try:
                # Try to read as DICOM
                ds = dcmread(filepath, force=True)
                dicom_files.append(filepath)
            except:
                # Not a DICOM file, skip
                pass
    
    if not dicom_files:
        print(f"No DICOM files found in {source_folder}")
        return
    
    print(f"Found {len(dicom_files)} DICOM files to send")
    
    # Associate with the SCP
    print(f"Connecting to {scp_ae_title} at {scp_address}:{scp_port}")
    assoc = ae.associate(scp_address, scp_port, ae_title=scp_ae_title)
    
    if assoc.is_established:
        print("Association established")
        
        success_count = 0
        for filepath in dicom_files:
            try:
                ds = dcmread(filepath)
                
                # Ensure we have the required SOP Class UID
                if hasattr(ds, 'SOPClassUID'):
                    # Send the dataset
                    status = assoc.send_c_store(ds)
                    
                    if status:
                        # Check the status of the storage request
                        if status.Status == 0x0000:
                            print(f"✓ Successfully sent: {os.path.basename(filepath)}")
                            success_count += 1
                        else:
                            print(f"✗ Failed to send {os.path.basename(filepath)}: Status 0x{status.Status:04x}")
                    else:
                        print(f"✗ Failed to send {os.path.basename(filepath)}: No status returned")
                else:
                    print(f"✗ Skipping {os.path.basename(filepath)}: No SOP Class UID")
                    
            except Exception as e:
                print(f"✗ Error sending {os.path.basename(filepath)}: {str(e)}")
        
        # Release the association
        assoc.release()
        print(f"\nCompleted: {success_count}/{len(dicom_files)} files sent successfully")
    else:
        print("Failed to establish association")
        print(f"Rejected: {assoc.acse.rejection}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python dicom_sender.py <source_folder> [scp_address] [scp_port] [scp_ae_title]")
        print("Example: python dicom_sender.py ./dicom_files localhost 4242 ORTHANC")
        sys.exit(1)
    
    source_folder = sys.argv[1]
    scp_address = sys.argv[2] if len(sys.argv) > 2 else 'localhost'
    scp_port = int(sys.argv[3]) if len(sys.argv) > 3 else 4242
    scp_ae_title = sys.argv[4] if len(sys.argv) > 4 else 'ORTHANC'
    
    send_dicom_files(source_folder, scp_address, scp_port, scp_ae_title)