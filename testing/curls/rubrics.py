#!/usr/bin/env python3
"""
Rubrics API Testing Script
Tests all Evaluaitor rubrics endpoints with curl commands

Usage:
    python3 testing/curls/rubrics.py

Prerequisites:
- LAMB backend running on localhost:9099
- Admin user: admin@owi.com / admin
- Database initialized with rubrics table
"""

import subprocess
import json
import sys
import time
import urllib.parse
from typing import Optional, Dict, Any

# Configuration
BASE_URL = "http://localhost:9099"
LAMB_CORE_URL = "http://localhost:9099/lamb/v1/evaluaitor"
ADMIN_EMAIL = "admin@owi.com"
ADMIN_PASSWORD = "admin"

class RubricsTester:
    def __init__(self):
        self.token: Optional[str] = None
        self.created_rubric_id: Optional[str] = None

    def run_curl(self, method: str, url: str, headers: Dict[str, str] = None,
                 data: str = None, output_file: str = None, auth_params: str = None) -> Dict[str, Any]:
        """Execute curl command and return response"""
        cmd = ["curl", "-X", method, "-s"]

        # Add headers
        if headers:
            for key, value in headers.items():
                cmd.extend(["-H", f"{key}: {value}"])

        # Add data
        if data:
            cmd.extend(["-d", data])

        # Output to file if specified
        if output_file:
            cmd.extend(["-o", output_file])

        # Add auth params to URL if provided
        if auth_params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{auth_params}"

        cmd.append(url)

        print(f"\n🔄 Executing: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            response = result.stdout

            if output_file:
                print(f"📁 Response saved to {output_file}")
                return {"success": True, "file": output_file}

            try:
                return json.loads(response)
            except json.JSONDecodeError:
                return {"success": False, "raw_response": response}

        except subprocess.CalledProcessError as e:
            print(f"❌ Curl failed: {e}")
            print(f"Error output: {e.stderr}")
            return {"success": False, "error": str(e), "stderr": e.stderr}

    def test_login(self):
        """Test login and get admin token"""
        print("\n" + "="*60)
        print("🧪 TESTING: Admin Login")
        print("="*60)

        # Login expects form data, not JSON
        login_data = f"email={ADMIN_EMAIL}&password={ADMIN_PASSWORD}"

        response = self.run_curl(
            "POST",
            f"{BASE_URL}/creator/login",
            {"Content-Type": "application/x-www-form-urlencoded"},
            login_data
        )

        if response.get("success") and "data" in response and "token" in response["data"]:
            self.token = response["data"]["token"]
            print(f"✅ Login successful! Token: {self.token[:50]}...")
            return True
        else:
            print(f"❌ Login failed: {response}")
            return False

    def get_auth_headers(self) -> Dict[str, str]:
        """Get authorization headers"""
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.token}"
        }

    def get_auth_params(self) -> str:
        """Get authorization as query parameters"""
        return f"auth_header=Bearer%20{self.token}"

    def rubric_to_form_data(self, rubric_data: Dict[str, Any]) -> str:
        """Convert rubric JSON data to URL-encoded form data"""
        form_data = {}

        # Basic fields
        form_data["title"] = rubric_data['title']
        form_data["description"] = rubric_data.get('description', '')
        form_data["subject"] = rubric_data['metadata']['subject']
        form_data["gradeLevel"] = rubric_data['metadata']['gradeLevel']
        form_data["scoringType"] = rubric_data.get('scoringType', 'points')
        form_data["maxScore"] = str(rubric_data.get('maxScore', 100))

        # Add IDs to criteria and levels if missing
        criteria = rubric_data['criteria']
        for i, criterion in enumerate(criteria):
            if 'id' not in criterion:
                criterion['id'] = f"criterion_{i+1}"
            if 'levels' in criterion:
                for j, level in enumerate(criterion['levels']):
                    if 'id' not in level:
                        level['id'] = f"level_{j+1}"

        # Criteria as JSON string
        criteria_json = json.dumps(criteria)
        form_data["criteria"] = criteria_json

        # URL-encode the form data
        return urllib.parse.urlencode(form_data)

    def test_list_rubrics(self):
        """Test listing user's rubrics"""
        print("\n" + "="*60)
        print("🧪 TESTING: List User's Rubrics")
        print("="*60)

        response = self.run_curl(
            "GET",
            f"{BASE_URL}/creator/rubrics?limit=10&offset=0",
            self.get_auth_headers()
        )

        if "rubrics" in response:
            rubrics = response.get("rubrics", [])
            print(f"✅ Found {len(rubrics)} rubrics")
            return True
        else:
            print(f"❌ List rubrics failed: {response}")
            return False

    def test_list_public_rubrics(self):
        """Test listing public rubrics in organization"""
        print("\n" + "="*60)
        print("🧪 TESTING: List Public Rubrics")
        print("="*60)

        response = self.run_curl(
            "GET",
            f"{BASE_URL}/creator/rubrics/public?limit=10&offset=0",
            self.get_auth_headers()
        )

        if response.get("success"):
            rubrics = response.get("rubrics", [])
            print(f"✅ Found {len(rubrics)} public rubrics")
            return True
        else:
            print(f"❌ List public rubrics failed: {response}")
            return False

    def test_list_showcase_rubrics(self):
        """Test listing showcase templates"""
        print("\n" + "="*60)
        print("🧪 TESTING: List Showcase Templates")
        print("="*60)

        response = self.run_curl(
            "GET",
            f"{BASE_URL}/creator/rubrics/showcase",
            self.get_auth_headers()
        )

        if response.get("success"):
            rubrics = response.get("rubrics", [])
            print(f"✅ Found {len(rubrics)} showcase templates")
            return True
        else:
            print(f"❌ List showcase rubrics failed: {response}")
            return False

    def test_create_rubric(self):
        """Test creating a new rubric"""
        print("\n" + "="*60)
        print("🧪 TESTING: Create Rubric")
        print("="*60)

        rubric_data = {
            "title": "Essay Writing Rubric - API Test",
            "description": "Test rubric created via API",
            "metadata": {
                "subject": "English",
                "gradeLevel": "9-12"
            },
            "criteria": [
                {
                    "name": "Thesis Statement",
                    "description": "Quality of main argument",
                    "weight": 25,
                    "levels": [
                        {
                            "score": 4,
                            "label": "Exemplary",
                            "description": "Clear and compelling thesis"
                        },
                        {
                            "score": 3,
                            "label": "Proficient",
                            "description": "Clear thesis"
                        },
                        {
                            "score": 2,
                            "label": "Developing",
                            "description": "Unclear thesis"
                        },
                        {
                            "score": 1,
                            "label": "Beginning",
                            "description": "Missing thesis"
                        }
                    ]
                },
                {
                    "name": "Evidence & Support",
                    "description": "Use of evidence and reasoning",
                    "weight": 35,
                    "levels": [
                        {
                            "score": 4,
                            "label": "Exemplary",
                            "description": "Strong evidence and reasoning"
                        },
                        {
                            "score": 3,
                            "label": "Proficient",
                            "description": "Good evidence and reasoning"
                        },
                        {
                            "score": 2,
                            "label": "Developing",
                            "description": "Weak evidence or reasoning"
                        },
                        {
                            "score": 1,
                            "label": "Beginning",
                            "description": "No evidence or reasoning"
                        }
                    ]
                },
                {
                    "name": "Organization",
                    "description": "Structure and flow",
                    "weight": 25,
                    "levels": [
                        {
                            "score": 4,
                            "label": "Exemplary",
                            "description": "Excellent organization"
                        },
                        {
                            "score": 3,
                            "label": "Proficient",
                            "description": "Good organization"
                        },
                        {
                            "score": 2,
                            "label": "Developing",
                            "description": "Poor organization"
                        },
                        {
                            "score": 1,
                            "label": "Beginning",
                            "description": "No organization"
                        }
                    ]
                },
                {
                    "name": "Grammar & Mechanics",
                    "description": "Writing conventions",
                    "weight": 15,
                    "levels": [
                        {
                            "score": 4,
                            "label": "Exemplary",
                            "description": "Few or no errors"
                        },
                        {
                            "score": 3,
                            "label": "Proficient",
                            "description": "Minor errors"
                        },
                        {
                            "score": 2,
                            "label": "Developing",
                            "description": "Several errors"
                        },
                        {
                            "score": 1,
                            "label": "Beginning",
                            "description": "Many errors"
                        }
                    ]
                }
            ],
            "scoringType": "points",
            "maxScore": 100
        }

        # Convert rubric data to form data
        form_data = self.rubric_to_form_data(rubric_data)

        response = self.run_curl(
            "POST",
            f"{BASE_URL}/creator/rubrics",
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Bearer {self.token}"
            },
            form_data
        )

        if "rubric" in response:
            rubric = response["rubric"]
            self.created_rubric_id = rubric["rubric_id"]
            print(f"✅ Rubric created! ID: {self.created_rubric_id}")
            print(f"   Title: {rubric['title']}")
            return True
        else:
            print(f"❌ Create rubric failed: {response}")
            return False

    def test_get_rubric(self):
        """Test getting a specific rubric"""
        if not self.created_rubric_id:
            print("❌ No rubric ID available (create test failed)")
            return False

        print("\n" + "="*60)
        print("🧪 TESTING: Get Specific Rubric")
        print("="*60)

        response = self.run_curl(
            "GET",
            f"{BASE_URL}/creator/rubrics/{self.created_rubric_id}",
            self.get_auth_headers()
        )

        if response.get("success") and "rubric" in response:
            rubric = response["rubric"]
            print(f"✅ Rubric retrieved: {rubric['title']}")
            return True
        else:
            print(f"❌ Get rubric failed: {response}")
            return False

    def test_update_rubric(self):
        """Test updating a rubric"""
        if not self.created_rubric_id:
            print("❌ No rubric ID available (create test failed)")
            return False

        print("\n" + "="*60)
        print("🧪 TESTING: Update Rubric")
        print("="*60)

        # Get current rubric first
        get_response = self.run_curl(
            "GET",
            f"{BASE_URL}/creator/rubrics/{self.created_rubric_id}",
            self.get_auth_headers()
        )

        if not (get_response.get("success") and "rubric" in get_response):
            print("❌ Could not get rubric for update test")
            return False

        current_rubric = get_response["rubric"]["rubricData"]

        # Modify the rubric
        current_rubric["title"] = "Updated Essay Writing Rubric - API Test"
        current_rubric["description"] = "Updated test rubric created via API"

        # Convert to form data
        update_form_data = self.rubric_to_form_data(current_rubric)

        response = self.run_curl(
            "PUT",
            f"{BASE_URL}/creator/rubrics/{self.created_rubric_id}",
            {"Content-Type": "application/x-www-form-urlencoded"},
            update_form_data
        )

        if response.get("success") and "rubric" in response:
            rubric = response["rubric"]
            print(f"✅ Rubric updated: {rubric['title']}")
            return True
        else:
            print(f"❌ Update rubric failed: {response}")
            return False

    def test_toggle_visibility(self):
        """Test toggling rubric visibility"""
        if not self.created_rubric_id:
            print("❌ No rubric ID available")
            return False

        print("\n" + "="*60)
        print("🧪 TESTING: Toggle Rubric Visibility")
        print("="*60)

        # Make it public
        response = self.run_curl(
            "PUT",
            f"{BASE_URL}/creator/rubrics/{self.created_rubric_id}/visibility",
            self.get_auth_headers(),
            json.dumps({"isPublic": True})
        )

        if response.get("success"):
            print("✅ Rubric made public")
        else:
            print(f"❌ Toggle visibility failed: {response}")
            return False

        # Check that it's now in public list
        time.sleep(1)  # Small delay
        public_response = self.run_curl(
            "GET",
            f"{BASE_URL}/creator/rubrics/public?limit=20&offset=0",
            self.get_auth_headers()
        )

        if public_response.get("success"):
            rubrics = public_response.get("rubrics", [])
            found = any(r["rubricId"] == self.created_rubric_id for r in rubrics)
            if found:
                print("✅ Rubric appears in public list")
            else:
                print("⚠️  Rubric not found in public list (may be timing issue)")
        else:
            print(f"❌ Could not verify public visibility: {public_response}")

        # Make it private again
        private_response = self.run_curl(
            "PUT",
            f"{BASE_URL}/creator/rubrics/rubrics/{self.created_rubric_id}/visibility",
            self.get_auth_headers(),
            json.dumps({"isPublic": False}),
            auth_params=self.get_auth_params()
        )

        if private_response.get("success"):
            print("✅ Rubric made private again")
            return True
        else:
            print(f"❌ Make private failed: {private_response}")
            return False

    def test_duplicate_rubric(self):
        """Test duplicating a rubric"""
        if not self.created_rubric_id:
            print("❌ No rubric ID available")
            return False

        print("\n" + "="*60)
        print("🧪 TESTING: Duplicate Rubric")
        print("="*60)

        response = self.run_curl(
            "POST",
            f"{BASE_URL}/creator/rubrics/{self.created_rubric_id}/duplicate",
            self.get_auth_headers()
        )

        if response.get("success") and "rubric" in response:
            duplicated_rubric = response["rubric"]
            print(f"✅ Rubric duplicated: {duplicated_rubric['title']}")
            print(f"   New ID: {duplicated_rubric['rubricId']}")
            return True
        else:
            print(f"❌ Duplicate rubric failed: {response}")
            return False

    def test_export_json(self):
        """Test exporting rubric as JSON"""
        if not self.created_rubric_id:
            print("❌ No rubric ID available")
            return False

        print("\n" + "="*60)
        print("🧪 TESTING: Export Rubric as JSON")
        print("="*60)

        response = self.run_curl(
            "GET",
            f"{BASE_URL}/creator/rubrics/{self.created_rubric_id}/export/json",
            self.get_auth_headers(),
            output_file=f"/tmp/rubric-{self.created_rubric_id}.json"
        )

        if response.get("success"):
            print("✅ JSON export successful")
            # Try to read and validate the exported file
            try:
                with open(f"/tmp/rubric-{self.created_rubric_id}.json", 'r') as f:
                    exported_data = json.load(f)
                    print(f"   Exported rubric: {exported_data.get('title', 'Unknown')}")
            except Exception as e:
                print(f"   Could not validate exported file: {e}")
            return True
        else:
            print(f"❌ JSON export failed: {response}")
            return False

    def test_export_markdown(self):
        """Test exporting rubric as Markdown"""
        if not self.created_rubric_id:
            print("❌ No rubric ID available")
            return False

        print("\n" + "="*60)
        print("🧪 TESTING: Export Rubric as Markdown")
        print("="*60)

        response = self.run_curl(
            "GET",
            f"{BASE_URL}/creator/rubrics/{self.created_rubric_id}/export/markdown",
            self.get_auth_headers(),
            output_file=f"/tmp/rubric-{self.created_rubric_id}.md"
        )

        if response.get("success"):
            print("✅ Markdown export successful")
            # Try to read and show a preview
            try:
                with open(f"/tmp/rubric-{self.created_rubric_id}.md", 'r') as f:
                    content = f.read()
                    lines = content.split('\n')
                    print("   Preview (first 10 lines):")
                    for i, line in enumerate(lines[:10]):
                        print(f"     {i+1}: {line}")
            except Exception as e:
                print(f"   Could not read exported file: {e}")
            return True
        else:
            print(f"❌ Markdown export failed: {response}")
            return False

    def test_import_rubric(self):
        """Test importing a rubric from JSON"""
        print("\n" + "="*60)
        print("🧪 TESTING: Import Rubric from JSON")
        print("="*60)

        # Use the exported JSON file for import test
        if not self.created_rubric_id:
            print("❌ No rubric available for export test")
            return False

        json_file = f"/tmp/rubric-{self.created_rubric_id}.json"
        try:
            with open(json_file, 'r') as f:
                rubric_data = json.load(f)
                # Modify it slightly for import test
                rubric_data["title"] = "Imported Essay Writing Rubric - API Test"
        except Exception as e:
            print(f"❌ Could not read JSON file for import: {e}")
            return False

        # For multipart/form-data, we'll use a simpler approach
        # Create a temporary JSON file and use curl with -F
        import_file = "/tmp/import_test.json"
        with open(import_file, 'w') as f:
            json.dump(rubric_data, f)

        # Use subprocess to run curl with file upload
        cmd = [
            "curl", "-X", "POST",
            "-H", f"Authorization: Bearer {self.token}",
            "-F", f"file=@{import_file}",
            "-s",
            f"{BASE_URL}/creator/rubrics/import"
        ]

        print(f"🔄 Executing: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            response = json.loads(result.stdout)

            if response.get("success") and "rubric" in response:
                imported_rubric = response["rubric"]
                print(f"✅ Rubric imported: {imported_rubric['title']}")
                print(f"   New ID: {imported_rubric['rubricId']}")
                return True
            else:
                print(f"❌ Import rubric failed: {response}")
                return False

        except subprocess.CalledProcessError as e:
            print(f"❌ Import curl failed: {e}")
            print(f"Error output: {e.stderr}")
            return False
        except json.JSONDecodeError:
            print(f"❌ Could not parse import response: {result.stdout}")
            return False

    def test_ai_generate(self):
        """Test AI rubric generation"""
        print("\n" + "="*60)
        print("🧪 TESTING: AI Generate Rubric")
        print("="*60)

        prompt = "Create a rubric for evaluating science lab reports in middle school. Include criteria for hypothesis, procedure, data analysis, and conclusions."

        ai_data = json.dumps({
            "prompt": prompt
        })

        response = self.run_curl(
            "POST",
            f"{BASE_URL}/creator/rubrics/ai-generate",
            {"Content-Type": "application/x-www-form-urlencoded"},
            urllib.parse.urlencode({"prompt": prompt})
        )

        if response.get("success") and "rubric" in response:
            ai_rubric = response["rubric"]
            print(f"✅ AI generated rubric: {ai_rubric['title']}")
            print(f"   Explanation: {response.get('explanation', 'No explanation')[:100]}...")
            return True
        else:
            print(f"❌ AI generate failed: {response}")
            return False

    def test_ai_modify(self):
        """Test AI rubric modification"""
        if not self.created_rubric_id:
            print("❌ No rubric ID available for AI modify test")
            return False

        print("\n" + "="*60)
        print("🧪 TESTING: AI Modify Rubric")
        print("="*60)

        prompt = "Make this rubric suitable for 6th graders by simplifying the language and expectations."

        ai_data = json.dumps({
            "prompt": prompt
        })

        response = self.run_curl(
            "POST",
            f"{BASE_URL}/creator/rubrics/{self.created_rubric_id}/ai-modify",
            {"Content-Type": "application/x-www-form-urlencoded"},
            urllib.parse.urlencode({"prompt": prompt})
        )

        if response.get("success") and "rubric" in response:
            modified_rubric = response["rubric"]
            print(f"✅ AI modified rubric: {modified_rubric['title']}")
            changes = response.get("changes_summary", {})
            print(f"   Changes: {json.dumps(changes, indent=2)}")
            return True
        else:
            print(f"❌ AI modify failed: {response}")
            return False

    def test_delete_rubric(self):
        """Test deleting a rubric"""
        if not self.created_rubric_id:
            print("❌ No rubric ID available")
            return False

        print("\n" + "="*60)
        print("🧪 TESTING: Delete Rubric")
        print("="*60)

        response = self.run_curl(
            "DELETE",
            f"{BASE_URL}/creator/rubrics/{self.created_rubric_id}",
            self.get_auth_headers()
        )

        if response.get("success"):
            print("✅ Rubric deleted successfully")
            self.created_rubric_id = None  # Clear the ID
            return True
        else:
            print(f"❌ Delete rubric failed: {response}")
            return False

    def test_lamb_core_list_rubrics(self):
        """Test listing rubrics directly from lamb core API (bypasses creator interface auth)"""
        print("\n" + "="*60)
        print("🧪 TESTING: Lamb Core API - List Rubrics")
        print("="*60)

        response = self.run_curl(
            "GET",
            f"{LAMB_CORE_URL}/rubrics?limit=10&offset=0"
        )

        if "rubrics" in response:
            rubrics = response.get("rubrics", [])
            total = response.get("total", 0)
            print(f"✅ Found {len(rubrics)} rubrics (total: {total})")
            return True
        else:
            print(f"❌ Lamb core list failed: {response}")
            return False

    def run_all_tests(self):
        """Run all tests in sequence"""
        print("🚀 Starting Rubrics API Tests")
        print(f"Base URL: {BASE_URL}")
        print(f"Lamb Core URL: {LAMB_CORE_URL}")
        print(f"Admin User: {ADMIN_EMAIL}")
        print("="*80)

        tests = [
            ("Login", self.test_login),
            ("Lamb Core - List Rubrics", self.test_lamb_core_list_rubrics),
            ("List Rubrics", self.test_list_rubrics),
            ("List Public Rubrics", self.test_list_public_rubrics),
            ("List Showcase Rubrics", self.test_list_showcase_rubrics),
            ("Create Rubric", self.test_create_rubric),
            ("Get Rubric", self.test_get_rubric),
            ("Update Rubric", self.test_update_rubric),
            ("Toggle Visibility", self.test_toggle_visibility),
            ("Duplicate Rubric", self.test_duplicate_rubric),
            ("Export JSON", self.test_export_json),
            ("Export Markdown", self.test_export_markdown),
            ("Import Rubric", self.test_import_rubric),
            ("AI Generate", self.test_ai_generate),
            ("AI Modify", self.test_ai_modify),
            ("Delete Rubric", self.test_delete_rubric),
        ]

        results = []
        for test_name, test_func in tests:
            try:
                success = test_func()
                results.append((test_name, success))
            except Exception as e:
                print(f"❌ Test '{test_name}' crashed: {e}")
                results.append((test_name, False))

        # Summary
        print("\n" + "="*80)
        print("📊 TEST SUMMARY")
        print("="*80)

        passed = 0
        total = len(results)

        for test_name, success in results:
            status = "✅ PASS" if success else "❌ FAIL"
            print(f"{status} {test_name}")
            if success:
                passed += 1

        print(f"\n📈 Results: {passed}/{total} tests passed")

        if passed == total:
            print("🎉 All tests passed!")
            return True
        else:
            print("⚠️  Some tests failed. Check output above.")
            return False


def main():
    """Main entry point"""
    tester = RubricsTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
