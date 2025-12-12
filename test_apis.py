"""
API Testing Script for Two-Phase Search Workflow

This script tests both query-only and query+image searches:
- 5 query-only searches using famous personalities
- 5 query+image searches using images from a folder

Results are saved to a single JSON file with timestamps.
"""

import requests
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

# Configuration
BASE_URL = "http://127.0.0.1:5000"
OUTPUT_FILE = "search_results.json"
IMAGES_FOLDER = "test_images"

# Famous personalities for query-only searches
QUERY_ONLY_SEARCHES = [
    "Bill Gates",
    "Dwayne Johnson",
]

# Query + Image searches (filename = query)
QUERY_IMAGE_SEARCHES = [
    "Steve Jobs",
    "Tom Cruise"
]


class APITester:
    def __init__(self, base_url: str, output_file: str):
        self.base_url = base_url
        self.output_file = output_file
        self.results = {
            "test_date": datetime.now().isoformat(),
            "query_only_searches": [],
            "query_image_searches": [],
            "summary": {
                "total_tests": 0,
                "successful": 0,
                "failed": 0
            }
        }

    def test_candidates_api(self, query: str, image_path: str = None) -> Dict[str, Any]:
        """Test the /candidates/ranked endpoint."""
        try:
            url = f"{self.base_url}/candidates/ranked"
            
            if image_path:
                # Query + Image: use multipart/form-data with file
                with open(image_path, 'rb') as img_file:
                    files = {
                        'query': (None, query),
                        'file': ('image.jpg', img_file, 'image/jpeg')
                    }
                    response = requests.post(url, files=files, timeout=600)
            else:
                # Query only: use multipart/form-data without file
                files = {
                    'query': (None, query)
                }
                response = requests.post(url, files=files, timeout=600)
            
            response.raise_for_status()
            return {
                "status": "success",
                "status_code": response.status_code,
                "data": response.json()
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }

    def test_search_api(self, query: str, candidate: Dict, reference_photo_id: str = None) -> Dict[str, Any]:
        """Test the /search endpoint."""
        try:
            url = f"{self.base_url}/search"
            
            payload = {
                "query": query,
                "candidate": candidate
            }
            
            if reference_photo_id:
                payload["referencePhotoId"] = reference_photo_id
            
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=600
            )
            
            response.raise_for_status()
            return {
                "status": "success",
                "status_code": response.status_code,
                "data": response.json()
            }
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }

    def run_query_only_search(self, query: str) -> Dict[str, Any]:
        """Run a query-only search (no image)."""
        print(f"\n[QUERY ONLY] Testing: {query}")
        
        # Step 1: Call candidates API without image
        print(f"  → Calling /candidates/ranked...")
        candidates_result = self.test_candidates_api(query)
        
        if candidates_result["status"] != "success":
            print(f"  ✗ Candidates API failed: {candidates_result.get('error')}")
            return {
                "query": query,
                "test_type": "query_only",
                "candidates_response": candidates_result,
                "search_response": None,
                "success": False
            }
        
        candidates_data = candidates_result["data"]
        print(f"  ✓ Found {len(candidates_data.get('candidates', []))} candidates")
        
        # Step 2: Call search API with top candidate
        if candidates_data.get("candidates"):
            top_candidate = candidates_data["candidates"][0]
            print(f"  → Calling /search with top candidate: {top_candidate['name']}")
            
            search_result = self.test_search_api(
                query,
                top_candidate,
                reference_photo_id=None  # No reference image for query-only
            )
            
            if search_result["status"] == "success":
                print(f"  ✓ Search API succeeded")
            else:
                print(f"  ✗ Search API failed: {search_result.get('error')}")
        else:
            search_result = None
            print(f"  ✗ No candidates found")
        
        return {
            "query": query,
            "test_type": "query_only",
            "candidates_response": candidates_result,
            "search_response": search_result,
            "success": candidates_result["status"] == "success" and search_result and search_result["status"] == "success"
        }

    def run_query_image_search(self, query: str, image_path: str) -> Dict[str, Any]:
        """Run a query + image search."""
        print(f"\n[QUERY + IMAGE] Testing: {query}")
        
        if not os.path.exists(image_path):
            print(f"  ✗ Image file not found: {image_path}")
            return {
                "query": query,
                "test_type": "query_image",
                "image_path": image_path,
                "candidates_response": None,
                "search_response": None,
                "success": False,
                "error": "Image file not found"
            }
        
        # Step 1: Call candidates API with image
        print(f"  → Calling /candidates/ranked with image...")
        candidates_result = self.test_candidates_api(query, image_path)
        
        if candidates_result["status"] != "success":
            print(f"  ✗ Candidates API failed: {candidates_result.get('error')}")
            return {
                "query": query,
                "test_type": "query_image",
                "image_path": image_path,
                "candidates_response": candidates_result,
                "search_response": None,
                "success": False
            }
        
        candidates_data = candidates_result["data"]
        reference_photo_id = candidates_data.get("referencePhotoId")
        print(f"  ✓ Found {len(candidates_data.get('candidates', []))} candidates")
        print(f"  ✓ Reference Photo ID: {reference_photo_id}")
        
        # Step 2: Call search API with top candidate and reference photo ID
        if candidates_data.get("candidates"):
            top_candidate = candidates_data["candidates"][0]
            print(f"  → Calling /search with top candidate: {top_candidate['name']}")
            
            search_result = self.test_search_api(
                query,
                top_candidate,
                reference_photo_id=reference_photo_id
            )
            
            if search_result["status"] == "success":
                print(f"  ✓ Search API succeeded")
            else:
                print(f"  ✗ Search API failed: {search_result.get('error')}")
        else:
            search_result = None
            print(f"  ✗ No candidates found")
        
        return {
            "query": query,
            "test_type": "query_image",
            "image_path": image_path,
            "reference_photo_id": reference_photo_id,
            "candidates_response": candidates_result,
            "search_response": search_result,
            "success": candidates_result["status"] == "success" and search_result and search_result["status"] == "success"
        }

    def run_all_tests(self) -> None:
        """Run all tests."""

        # Test 1: Query-only searches
        print("\n" + "=" * 80)
        print("PHASE 1: QUERY-ONLY SEARCHES")
        print("=" * 80)
        
        for query in QUERY_ONLY_SEARCHES:
            result = self.run_query_only_search(query)
            self.results["query_only_searches"].append(result)
            self.results["summary"]["total_tests"] += 1
            if result["success"]:
                self.results["summary"]["successful"] += 1
            else:
                self.results["summary"]["failed"] += 1
        
        # Test 2: Query + Image searches
        print("\n" + "=" * 80)
        print("PHASE 2: QUERY + IMAGE SEARCHES")
        print("=" * 80)
        
        for query in QUERY_IMAGE_SEARCHES:
            # Look for image file with query name
            image_path = os.path.join(IMAGES_FOLDER, f"{query}.jpg")
            
            # Try alternative extensions if jpg doesn't exist
            if not os.path.exists(image_path):
                for ext in [".png", ".webp", ".jpeg", ".JPEG", ".PNG"]:
                    alt_path = os.path.join(IMAGES_FOLDER, f"{query}{ext}")
                    if os.path.exists(alt_path):
                        image_path = alt_path
                        break
            
            result = self.run_query_image_search(query, image_path)
            self.results["query_image_searches"].append(result)
            self.results["summary"]["total_tests"] += 1
            if result["success"]:
                self.results["summary"]["successful"] += 1
            else:
                self.results["summary"]["failed"] += 1
        
        # Save results
        self.save_results()

    def save_results(self) -> None:
        """Save all results to JSON file."""
        print("\n" + "=" * 80)
        print("SAVING RESULTS")
        print("=" * 80)
        
        with open(self.output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        
        print(f"\n✓ Results saved to: {self.output_file}")
        print(f"\nSummary:")
        print(f"  Total Tests: {self.results['summary']['total_tests']}")
        print(f"  Successful: {self.results['summary']['successful']}")
        print(f"  Failed: {self.results['summary']['failed']}")
        print(f"  Success Rate: {(self.results['summary']['successful'] / max(1, self.results['summary']['total_tests']) * 100):.1f}%")


def main():
    
    tester = APITester(BASE_URL, OUTPUT_FILE)
    tester.run_all_tests()
    
if __name__ == "__main__":
    main()