#!/usr/bin/env python3
"""
DICOM Receiver (SCP) - Receive DICOM files via DIMSE and save to folder
"""

import os
import sys
import time
from datetime import datetime
from pydicom import dcmread
from pydicom.dataset import Dataset
from pynetdicom import AE, evt, AllStoragePresentationContexts
from pynetdicom.sop_class import VerificationSOPClass

def handle_store(event, output_dir):
    """Handle a C-STORE request event"""
    ds = event.dataset
    
    # Add file meta information
    ds.file_meta = event.file_meta
    
    # Create subdirectories based on patient and study
    patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else 'Unknown'
    study_uid = str(ds.StudyInstanceUID) if hasattr(ds, 'StudyInstanceUID') else 'Unknown'
    series_uid = str(ds.SeriesInstanceUID) if hasattr(ds, 'SeriesInstanceUID') else 'Unknown'
    
    # Clean up IDs for use as folder names
    patient_id = patient_id.replace('/', '_').replace('\\', '_')
    
    # Create directory structure
    study_dir = os.path.join(output_dir, patient_id, study_uid, series_uid)
    os.makedirs(study_dir, exist_ok=True)
    
    # Generate filename
    sop_instance_uid = str(ds.SOPInstanceUID) if hasattr(ds, 'SOPInstanceUID') else f'instance_{int(time.time())}'
    filename = f"{sop_instance_uid}.dcm"
    filepath = os.path.join(study_dir, filename)
    
    # Save the dataset
    try:
        ds.save_as(filepath, write_like_original=False)
        print(f"✓ Received and saved: {filename}")
        print(f"  Patient: {patient_id}")
        print(f"  Study: {study_uid}")
        print(f"  Location: {filepath}")
        
        # Return success status
        return 0x0000
    except Exception as e:
        print(f"✗ Error saving file: {str(e)}")
        # Return failure status
        return 0xC000

def handle_echo(event):
    """Handle a C-ECHO request event"""
    print("Received C-ECHO request")
    return 0x0000

def start_scp(port=11112, ae_title='PYTHON_SCP', output_dir='./received_dicom'):
    """
    Start a DICOM Storage SCP
    
    Args:
        port: Port to listen on
        ae_title: AE Title of this SCP
        output_dir: Directory to save received DICOM files
    """
    # Create output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Initialize the Application Entity
    ae = AE(ae_title=ae_title)
    
    # Support verification (C-ECHO)
    ae.add_supported_context(VerificationSOPClass)
    
    # Support all storage SOP Classes
    ae.supported_contexts = AllStoragePresentationContexts
    
    # Set up handlers
    handlers = [
        (evt.EVT_C_STORE, handle_store, [output_dir]),
        (evt.EVT_C_ECHO, handle_echo),
    ]
    
    print(f"Starting DICOM SCP")
    print(f"AE Title: {ae_title}")
    print(f"Port: {port}")
    print(f"Output Directory: {os.path.abspath(output_dir)}")
    print(f"Ready to receive DICOM files...")
    print("Press Ctrl+C to stop\n")
    
    # Start listening for incoming associations
    ae.start_server(('', port), evt_handlers=handlers)

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 11112
    ae_title = sys.argv[2] if len(sys.argv) > 2 else 'PYTHON_SCP'
    output_dir = sys.argv[3] if len(sys.argv) > 3 else './received_dicom'
    
    print("DICOM Storage SCP (Service Class Provider)")
    print("==========================================")
    print(f"Usage: python {sys.argv[0]} [port] [ae_title] [output_dir]")
    print(f"Example: python {sys.argv[0]} 11112 MY_SCP ./received_files\n")
    
    try:
        start_scp(port, ae_title, output_dir)
    except KeyboardInterrupt:
        print("\n\nStopping SCP...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)