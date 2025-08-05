#!/usr/bin/env python3
"""
Orthanc2 Monitor - Continuously monitors Orthanc2 for new studies and pulls them via DIMSE
"""

import os
import sys
import time
import json
import threading
from datetime import datetime
import requests
from pydicom.dataset import Dataset
from pynetdicom import AE, evt, StoragePresentationContexts, QueryRetrievePresentationContexts
from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove

class Orthanc2Monitor:
    def __init__(self, orthanc_host='orthanc2', orthanc_http_port=8042, orthanc_dicom_port=4242,
                 orthanc_aet='ORTHANC2', local_aet='PYTHON_SCP', scp_port=11112,
                 output_dir='/dicom/output', poll_interval=5):
        """
        Initialize the Orthanc2 monitoring service
        
        Args:
            orthanc_host: Orthanc hostname
            orthanc_http_port: Orthanc HTTP port
            orthanc_dicom_port: Orthanc DIMSE port
            orthanc_aet: Orthanc AE Title
            local_aet: Local AE Title for the SCP
            scp_port: Port for the local SCP to listen on
            output_dir: Directory to save received files
            poll_interval: Seconds between checks for new studies
        """
        self.orthanc_host = orthanc_host
        self.orthanc_http_port = orthanc_http_port
        self.orthanc_dicom_port = orthanc_dicom_port
        self.orthanc_aet = orthanc_aet
        self.local_aet = local_aet
        self.scp_port = scp_port
        self.output_dir = output_dir
        self.poll_interval = poll_interval
        self.scp_ae = None
        self.received_instances = 0
        self.processed_studies = set()
        self.state_file = os.path.join(output_dir, '.processed_studies.json')
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Load previously processed studies
        self.load_processed_studies()
    
    def load_processed_studies(self):
        """Load the list of previously processed studies"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    self.processed_studies = set(json.load(f))
                print(f"Loaded {len(self.processed_studies)} previously processed studies")
            except Exception as e:
                print(f"Error loading state file: {e}")
                self.processed_studies = set()
    
    def save_processed_studies(self):
        """Save the list of processed studies"""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(list(self.processed_studies), f)
        except Exception as e:
            print(f"Error saving state file: {e}")
    
    def handle_store(self, event):
        """Handle incoming C-STORE requests"""
        ds = event.dataset
        ds.file_meta = event.file_meta
        
        # Create subdirectories based on patient and study
        patient_id = str(ds.PatientID) if hasattr(ds, 'PatientID') else 'Unknown'
        study_uid = str(ds.StudyInstanceUID) if hasattr(ds, 'StudyInstanceUID') else 'Unknown'
        series_uid = str(ds.SeriesInstanceUID) if hasattr(ds, 'SeriesInstanceUID') else 'Unknown'
        
        # Clean up IDs for folder names
        patient_id = patient_id.replace('/', '_').replace('\\', '_')
        
        # Create directory structure
        study_dir = os.path.join(self.output_dir, patient_id, study_uid, series_uid)
        os.makedirs(study_dir, exist_ok=True)
        
        # Generate filename
        sop_instance_uid = str(ds.SOPInstanceUID) if hasattr(ds, 'SOPInstanceUID') else f'instance_{int(time.time())}'
        filename = f"{sop_instance_uid}.dcm"
        filepath = os.path.join(study_dir, filename)
        
        # Save the dataset
        try:
            ds.save_as(filepath, write_like_original=False)
            self.received_instances += 1
            print(f"  ✓ Received instance {self.received_instances}: {filename}")
            return 0x0000  # Success
        except Exception as e:
            print(f"  ✗ Error saving file: {str(e)}")
            return 0xC000  # Failure
    
    def start_scp(self):
        """Start the Storage SCP"""
        self.scp_ae = AE(ae_title=self.local_aet)
        
        # Support all storage contexts
        self.scp_ae.supported_contexts = StoragePresentationContexts
        
        # Set handler
        handlers = [(evt.EVT_C_STORE, self.handle_store)]
        
        print(f"Starting Storage SCP on port {self.scp_port}...")
        
        # Start server in non-blocking mode
        self.scp_ae.start_server(
            ('0.0.0.0', self.scp_port), 
            evt_handlers=handlers,
            block=False
        )
        print(f"✓ Storage SCP started (AE Title: {self.local_aet})")
    
    def stop_scp(self):
        """Stop the Storage SCP"""
        if self.scp_ae:
            self.scp_ae.shutdown()
            print("Storage SCP stopped")
    
    def move_study(self, study_uid):
        """Request a study via C-MOVE"""
        print(f"\n  → Requesting study {study_uid} via C-MOVE...")
        self.received_instances = 0
        
        # Create SCU for C-MOVE
        ae = AE(ae_title=self.local_aet)
        
        # Add query/retrieve contexts
        ae.requested_contexts = QueryRetrievePresentationContexts
        
        # Associate with Orthanc
        assoc = ae.associate(self.orthanc_host, self.orthanc_dicom_port, ae_title=self.orthanc_aet)
        
        if assoc.is_established:
            # Create identifier dataset
            ds = Dataset()
            ds.QueryRetrieveLevel = 'STUDY'
            ds.StudyInstanceUID = study_uid
            
            # Send C-MOVE request
            responses = assoc.send_c_move(ds, self.local_aet, PatientRootQueryRetrieveInformationModelMove)
            
            success = False
            for (status, identifier) in responses:
                if status:
                    # Check if C-MOVE completed successfully
                    if status.Status == 0x0000:  # Success
                        success = True
                    elif status.Status == 0xFF00:  # Pending
                        pass
                    else:
                        print(f"    C-MOVE status: 0x{status.Status:04x}")
            
            assoc.release()
            
            if success and self.received_instances > 0:
                print(f"  ✓ Study transfer completed. Received {self.received_instances} instances.")
                return True
            else:
                print(f"  ✗ Study transfer failed or no instances received.")
                return False
        else:
            print("  ✗ Failed to establish association for C-MOVE")
            return False
    
    def check_for_new_studies(self):
        """Check Orthanc2 for new studies"""
        try:
            # Get all studies from Orthanc2
            response = requests.get(f"http://{self.orthanc_host}:{self.orthanc_http_port}/studies")
            study_ids = response.json()
            
            new_studies = []
            for study_id in study_ids:
                if study_id not in self.processed_studies:
                    # Get study details
                    study_details = requests.get(f"http://{self.orthanc_host}:{self.orthanc_http_port}/studies/{study_id}").json()
                    study_uid = study_details.get('MainDicomTags', {}).get('StudyInstanceUID', '')
                    
                    if study_uid:
                        new_studies.append((study_id, study_uid))
            
            if new_studies:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Found {len(new_studies)} new studies")
                
                for study_id, study_uid in new_studies:
                    print(f"\nProcessing study: {study_uid}")
                    
                    # Pull the study via C-MOVE
                    if self.move_study(study_uid):
                        # Mark as processed
                        self.processed_studies.add(study_id)
                        self.save_processed_studies()
                        
                        # Brief pause between studies
                        time.sleep(1)
                    else:
                        print(f"  ⚠ Failed to retrieve study {study_uid}, will retry later")
            
        except Exception as e:
            print(f"\n✗ Error checking for new studies: {e}")
    
    def monitor(self):
        """Main monitoring loop"""
        print(f"\nMonitoring Orthanc2 for new studies...")
        print(f"Checking every {self.poll_interval} seconds")
        print(f"Output directory: {os.path.abspath(self.output_dir)}")
        print("\nPress Ctrl+C to stop\n")
        
        while True:
            try:
                self.check_for_new_studies()
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                print("\n\nStopping monitor...")
                break
            except Exception as e:
                print(f"\n✗ Unexpected error: {e}")
                time.sleep(self.poll_interval)

def main():
    # Parse command line arguments
    orthanc_host = os.environ.get('ORTHANC_HOST', 'orthanc2')
    orthanc_http_port = int(os.environ.get('ORTHANC_HTTP_PORT', '8042'))
    orthanc_dicom_port = int(os.environ.get('ORTHANC_DICOM_PORT', '4242'))
    orthanc_aet = os.environ.get('ORTHANC_AET', 'ORTHANC2')
    output_dir = os.environ.get('OUTPUT_DIR', '/dicom/output')
    poll_interval = int(os.environ.get('POLL_INTERVAL', '5'))
    
    print("Orthanc2 Monitor Service")
    print("=======================")
    print(f"Orthanc: {orthanc_aet}@{orthanc_host}:{orthanc_dicom_port}")
    print(f"HTTP API: http://{orthanc_host}:{orthanc_http_port}")
    print(f"Output: {os.path.abspath(output_dir)}")
    print(f"Poll interval: {poll_interval}s")
    
    monitor = Orthanc2Monitor(
        orthanc_host=orthanc_host,
        orthanc_http_port=orthanc_http_port,
        orthanc_dicom_port=orthanc_dicom_port,
        orthanc_aet=orthanc_aet,
        output_dir=output_dir,
        poll_interval=poll_interval
    )
    
    try:
        # Start the SCP
        monitor.start_scp()
        
        # Give the SCP a moment to start
        time.sleep(2)
        
        # Start monitoring
        monitor.monitor()
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        monitor.stop_scp()
        print(f"\nFiles saved to: {os.path.abspath(output_dir)}")

if __name__ == "__main__":
    main()