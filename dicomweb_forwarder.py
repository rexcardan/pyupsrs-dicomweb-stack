#!/usr/bin/env python3
"""
DICOMweb Forwarder - Automatically forward studies from Orthanc1 to Orthanc2 via DICOMweb
"""

import sys
import time
import requests
import json
from datetime import datetime

class DICOMWebForwarder:
    def __init__(self, source_url, target_url, poll_interval=5):
        """
        Initialize the forwarder
        
        Args:
            source_url: DICOMweb URL of source Orthanc (e.g., http://localhost:8042/dicom-web)
            target_url: DICOMweb URL of target Orthanc (e.g., http://localhost:8043/dicom-web)
            poll_interval: Seconds between polls (default: 5)
        """
        self.source_url = source_url.rstrip('/')
        self.target_url = target_url.rstrip('/')
        self.poll_interval = poll_interval
        self.forwarded_studies = set()
        
    def get_studies(self, url):
        """Query all studies from DICOMweb server"""
        try:
            response = requests.get(f"{url}/studies", headers={'Accept': 'application/dicom+json'})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error querying studies: {e}")
            return []
    
    def get_study_data(self, url, study_uid):
        """Retrieve complete study data"""
        try:
            # Get the study with all its instances
            response = requests.get(
                f"{url}/studies/{study_uid}",
                headers={'Accept': 'multipart/related; type="application/dicom"'}
            )
            response.raise_for_status()
            return response.content, response.headers.get('Content-Type', '')
        except requests.exceptions.RequestException as e:
            print(f"Error retrieving study {study_uid}: {e}")
            return None, None
    
    def forward_study(self, study_uid):
        """Forward a single study from source to target"""
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Forwarding study {study_uid}...")
        
        # Retrieve study from source
        study_data, content_type = self.get_study_data(self.source_url, study_uid)
        if not study_data:
            print(f"  ✗ Failed to retrieve study from source")
            return False
        
        print(f"  ✓ Retrieved study from source ({len(study_data)} bytes)")
        
        # Forward to target via STOW-RS
        try:
            headers = {
                'Content-Type': content_type if content_type else 'multipart/related; type="application/dicom"'
            }
            
            response = requests.post(
                f"{self.target_url}/studies",
                data=study_data,
                headers=headers
            )
            response.raise_for_status()
            
            print(f"  ✓ Successfully forwarded to target")
            self.forwarded_studies.add(study_uid)
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Failed to forward to target: {e}")
            return False
    
    def check_and_forward_studies(self):
        """Check for new studies and forward them"""
        # Get studies from source
        source_studies = self.get_studies(self.source_url)
        
        for study in source_studies:
            # Extract Study Instance UID
            study_uid = None
            if isinstance(study, dict):
                # Try different possible formats
                if '0020000D' in study and 'Value' in study['0020000D']:
                    study_uid = study['0020000D']['Value'][0]
                elif 'StudyInstanceUID' in study:
                    study_uid = study['StudyInstanceUID']
            
            if study_uid and study_uid not in self.forwarded_studies:
                # New study found, forward it
                self.forward_study(study_uid)
    
    def run(self):
        """Main loop - continuously check and forward studies"""
        print(f"DICOMweb Forwarder Started")
        print(f"Source: {self.source_url}")
        print(f"Target: {self.target_url}")
        print(f"Poll interval: {self.poll_interval} seconds")
        print(f"\nMonitoring for new studies...")
        
        while True:
            try:
                self.check_and_forward_studies()
                time.sleep(self.poll_interval)
            except KeyboardInterrupt:
                print("\n\nForwarder stopped by user")
                break
            except Exception as e:
                print(f"\nError in main loop: {e}")
                print("Continuing...")
                time.sleep(self.poll_interval)

def main():
    if len(sys.argv) < 3:
        print("Usage: python dicomweb_forwarder.py <source_url> <target_url> [poll_interval]")
        print("Example: python dicomweb_forwarder.py http://localhost:8042/dicom-web http://localhost:8043/dicom-web 5")
        sys.exit(1)
    
    source_url = sys.argv[1]
    target_url = sys.argv[2]
    poll_interval = int(sys.argv[3]) if len(sys.argv) > 3 else 5
    
    forwarder = DICOMWebForwarder(source_url, target_url, poll_interval)
    forwarder.run()

if __name__ == "__main__":
    main()