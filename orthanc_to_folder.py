#!/usr/bin/env python3
"""
Orthanc to Folder - Pull studies from Orthanc2 via DIMSE C-MOVE and save to folder
This script acts as both a C-MOVE SCU (to request studies) and a C-STORE SCP (to receive them)
"""

import os
import sys
import threading
import time
from datetime import datetime
from pydicom import dcmread
from pynetdicom import AE, evt, StoragePresentationContexts, QueryRetrievePresentationContexts
from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelMove

class OrthancToFolder:
    def __init__(self, orthanc_host='localhost', orthanc_port=4243, orthanc_aet='ORTHANC2',
                 local_aet='PYTHON_SCP', scp_port=11112, output_dir='./received_dicom'):
        """
        Initialize the Orthanc to Folder service
        
        Args:
            orthanc_host: Orthanc hostname
            orthanc_port: Orthanc DIMSE port
            orthanc_aet: Orthanc AE Title
            local_aet: Local AE Title for the SCP
            scp_port: Port for the local SCP to listen on
            output_dir: Directory to save received files
        """
        self.orthanc_host = orthanc_host
        self.orthanc_port = orthanc_port
        self.orthanc_aet = orthanc_aet
        self.local_aet = local_aet
        self.scp_port = scp_port
        self.output_dir = output_dir
        self.scp_thread = None
        self.scp_ae = None
        self.received_instances = 0
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
    
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
        """Start the Storage SCP in a separate thread"""
        self.scp_ae = AE(ae_title=self.local_aet)
        
        # Support all storage contexts
        self.scp_ae.supported_contexts = StoragePresentationContexts
        
        # Set handler
        handlers = [(evt.EVT_C_STORE, self.handle_store)]
        
        print(f"Starting Storage SCP on port {self.scp_port}...")
        
        # Start server in non-blocking mode
        self.scp_ae.start_server(
            ('', self.scp_port), 
            evt_handlers=handlers,
            block=False
        )
        print(f"✓ Storage SCP started (AE Title: {self.local_aet})")
    
    def stop_scp(self):
        """Stop the Storage SCP"""
        if self.scp_ae:
            self.scp_ae.shutdown()
            print("Storage SCP stopped")
    
    def query_all_studies(self):
        """Query all studies from Orthanc"""
        # Create SCU
        ae = AE(ae_title=self.local_aet)
        ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        
        # Associate with Orthanc
        assoc = ae.associate(self.orthanc_host, self.orthanc_port, ae_title=self.orthanc_aet)
        
        studies = []
        if assoc.is_established:
            # Create query dataset
            from pydicom.dataset import Dataset
            ds = Dataset()
            ds.QueryRetrieveLevel = 'STUDY'
            ds.StudyInstanceUID = ''
            
            # Send C-FIND to get all studies
            responses = assoc.send_c_find(ds, PatientRootQueryRetrieveInformationModelMove)
            
            for (status, identifier) in responses:
                if status and identifier and hasattr(identifier, 'StudyInstanceUID'):
                    studies.append(identifier.StudyInstanceUID)
            
            assoc.release()
        
        return studies
    
    def move_study(self, study_uid):
        """Request a study via C-MOVE"""
        print(f"\nRequesting study {study_uid} via C-MOVE...")
        self.received_instances = 0
        
        # Create SCU for C-MOVE
        ae = AE(ae_title=self.local_aet)
        
        # Add query/retrieve contexts
        ae.requested_contexts = QueryRetrievePresentationContexts
        
        # Associate with Orthanc
        assoc = ae.associate(self.orthanc_host, self.orthanc_port, ae_title=self.orthanc_aet)
        
        if assoc.is_established:
            # Create identifier dataset
            from pydicom.dataset import Dataset
            ds = Dataset()
            ds.QueryRetrieveLevel = 'STUDY'
            ds.StudyInstanceUID = study_uid
            
            # Send C-MOVE request
            # The destination AE title should be our local SCP
            responses = assoc.send_c_move(ds, self.local_aet, PatientRootQueryRetrieveInformationModelMove)
            
            for (status, identifier) in responses:
                if status:
                    # Check if C-MOVE completed
                    if status.Status in [0x0000, 0xFF00]:  # Success or Pending
                        pass
                    else:
                        print(f"  C-MOVE status: 0x{status.Status:04x}")
            
            assoc.release()
            print(f"✓ Study transfer completed. Received {self.received_instances} instances.")
            return True
        else:
            print("✗ Failed to establish association for C-MOVE")
            return False
    
    def pull_all_studies(self):
        """Pull all studies from Orthanc2"""
        print(f"\nQuerying studies from {self.orthanc_aet}...")
        
        # First, let's try a simple HTTP request to check what's in Orthanc2
        try:
            import requests
            response = requests.get(f"http://{self.orthanc_host}:8042/studies")
            orthanc_studies = response.json()
            
            if not orthanc_studies:
                print("No studies found in Orthanc2")
                return
            
            print(f"Found {len(orthanc_studies)} studies in Orthanc2")
            
            # Pull each study
            for study_id in orthanc_studies:
                if study_id:
                    # Get the actual Study Instance UID
                    study_details = requests.get(f"http://{self.orthanc_host}:8042/studies/{study_id}").json()
                    dicom_study_uid = study_details.get('MainDicomTags', {}).get('StudyInstanceUID', '')
                    
                    if dicom_study_uid:
                        self.move_study(dicom_study_uid)
                        time.sleep(1)  # Brief pause between studies
                        
        except Exception as e:
            print(f"Error querying Orthanc2: {e}")
            print("Falling back to DIMSE query...")
            
            # Fallback to DIMSE C-FIND
            studies = self.query_all_studies()
            if not studies:
                print("No studies found via DIMSE query")
                return
            
            print(f"Found {len(studies)} studies")
            for study_uid in studies:
                self.move_study(study_uid)
                time.sleep(1)

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--help':
        print("Orthanc to Folder - Pull studies from Orthanc via DIMSE")
        print("\nUsage: python orthanc_to_folder.py [orthanc_host] [orthanc_port] [orthanc_aet] [output_dir]")
        print("\nDefaults:")
        print("  orthanc_host: localhost")
        print("  orthanc_port: 4243")
        print("  orthanc_aet: ORTHANC2") 
        print("  output_dir: ./received_dicom")
        print("\nExample: python orthanc_to_folder.py localhost 4243 ORTHANC2 ./output")
        sys.exit(0)
    
    orthanc_host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'
    orthanc_port = int(sys.argv[2]) if len(sys.argv) > 2 else 4243
    orthanc_aet = sys.argv[3] if len(sys.argv) > 3 else 'ORTHANC2'
    output_dir = sys.argv[4] if len(sys.argv) > 4 else './received_dicom'
    
    print("Orthanc to Folder Service")
    print("========================")
    print(f"Orthanc: {orthanc_aet}@{orthanc_host}:{orthanc_port}")
    print(f"Output: {os.path.abspath(output_dir)}")
    
    service = OrthancToFolder(orthanc_host, orthanc_port, orthanc_aet, output_dir=output_dir)
    
    try:
        # Start the SCP
        service.start_scp()
        
        # Give the SCP a moment to start
        time.sleep(2)
        
        # Pull all studies
        service.pull_all_studies()
        
        # Keep SCP running for a bit to ensure all transfers complete
        print("\nWaiting for any remaining transfers...")
        time.sleep(5)
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        service.stop_scp()
        print(f"\nFiles saved to: {os.path.abspath(output_dir)}")

if __name__ == "__main__":
    main()