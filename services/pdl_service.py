import os
import requests
from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger('pdl_service')

class PDLService:
    BASE_URL = "https://api.peopledatalabs.com/v5"

    def __init__(self):
        self.api_key = os.getenv('PDL_API_KEY')
        if not self.api_key:
            logger.warning("PDL_API_KEY not set in environment variables")

    def search_person(self, name: str, age: Optional[str] = None, location: Optional[str] = None, school: Optional[str] = None, company: Optional[str] = None, social: Optional[str] = None) -> List[Dict]:
        """
        Search for people using PDL Person Search API with SQL syntax.
        """
        if not self.api_key:
            return []
        
        url = f"{self.BASE_URL}/person/search"
        headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        # Build SQL Query
        # We use strict matching for now, or we could use LIKE for fuzziness if needed
        clauses = []
        if name:
            # Escape single quotes
            safe_name = name.replace("'", "''")
            clauses.append(f"full_name='{safe_name}'") 
        
        if location:
            safe_loc = location.replace("'", "''")
            clauses.append(f"location_name LIKE '%{safe_loc}%'")
            
        if company:
            safe_co = company.replace("'", "''")
            clauses.append(f"job_company_name LIKE '%{safe_co}%'")
            
        if school:
            safe_school = school.replace("'", "''")
            clauses.append(f"education_school_name LIKE '%{safe_school}%'")
            
        if social:
            # Clean social input (remove common prefixes if user typed them)
            clean_social = social.lower()
            for prefix in ["instagram:", "twitter:", "facebook:", "linkedin:", "github:", "https://", "http://", "www."]:
                clean_social = clean_social.replace(prefix, "").strip()
                
            safe_social = clean_social.replace("'", "''")
            # Search across common social URL fields
            # We use OR logic wrapped in parens
            social_clause = (
                f"(linkedin_url LIKE '%{safe_social}%' OR "
                f"twitter_url LIKE '%{safe_social}%' OR "
                f"facebook_url LIKE '%{safe_social}%' OR "
                f"github_url LIKE '%{safe_social}%')"
            )
            clauses.append(social_clause)
            
        if age and age.isdigit():
            # Estimate birth year. Current year 2025.
            current_year = 2025
            try:
                age_int = int(age)
                birth_year = current_year - age_int
                # Allow +/- 1 year range (3 years total)
                start = birth_year - 1
                end = birth_year + 1
                clauses.append(f"birth_year BETWEEN {start} AND {end}")
            except:
                pass
        
        if not clauses:
            return []
            
        sql = f"SELECT * FROM person WHERE {' AND '.join(clauses)}"
        logger.info(f"PDL SQL Query: {sql}")
        
        params = {
            'sql': sql,
            'size': 10,
            'pretty': True
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            if response.status_code == 200:
                data = response.json()
                return self._parse_candidates(data.get('data', []))
            
            # If 404/400, it might mean no query matched or syntax error
            logger.warning(f"PDL Search returned status {response.status_code}: {response.text}")
            return []
            
        except Exception as e:
            logger.error(f"Error calling PDL Search: {str(e)}")
            return []

    def enrich_person(self, params: Dict) -> Dict:
        """
        Enrich a person profile using PDL Enrichment API.
        params can include: {'profile': 'linkedin_url'}, {'email': '...'}, etc.
        """
        if not self.api_key:
            return {}
            
        url = f"{self.BASE_URL}/person/enrich"
        headers = {
            'X-Api-Key': self.api_key,
            'Content-Type': 'application/json'
        }
        
        try:
            # PDL Enrichment accepts params directly in query string
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                data = response.json()
                # Check match probability or status
                match_status = data.get('status', 200) # PDL returns 200 even for no match sometimes in body?
                # Actually checking 'status' field in response body
                if match_status == 200 and data.get('data'):
                    return data.get('data')
                    
            logger.warning(f"PDL Enrichment returned status {response.status_code}: {response.text}")
            return {}
            
        except Exception as e:
            logger.error(f"Error calling PDL Enrichment: {str(e)}")
            return {}

    def _parse_candidates(self, data: List[Dict]) -> List[Dict]:
        """Convert PDL schema to our internal Candidate schema"""
        candidates = []
        for p in data:
            try:
                # Name
                name = p.get('full_name') or p.get('name') or "Unknown"
                
                # Description: Title at Company • Location
                title = p.get('job_title') or ""
                company = p.get('job_company_name') or ""
                location = p.get('location_name') or ""
                
                desc_parts = []
                if title: 
                    if company:
                        desc_parts.append(f"{title} at {company}")
                    else:
                        desc_parts.append(title)
                elif company:
                     desc_parts.append(company)
                     
                if location:
                    desc_parts.append(location)
                    
                description = " • ".join(desc_parts)
                
                # Image: PDL sometimes is sparse on public images directly in 'data'
                # but let's check top level 'linkedin_url' or similar for future scraping
                # For candidate card, we need a URL. 
                # PDL usually doesn't return a direct 'image_url' field that is publicly accessible easily without enrichment?
                # Actually, check fields... 'facebook_url', 'twitter_url', 'linkedin_url'.
                # Sometimes they provide 'auth_id' logic. 
                # Let's check social profiles for image. 
                # For now, use None or a placeholder if not found.
                image_url = None
                
                candidates.append({
                    "id": p.get('id', name), # Prefer PDL ID
                    "name": name,
                    "description": description,
                    "imageUrl": image_url,
                    # Store extra identifiers for deep search/enrichment later
                    "pdl_id": p.get('id'),
                    "linkedin_url": p.get('linkedin_url'),
                    "twitter_url": p.get('twitter_url')
                })
            except Exception as e:
                logger.error(f"Error parsing PDL candidate: {e}")
                continue
                
        return candidates

# Singleton
_pdl_service = None

def get_pdl_service() -> PDLService:
    global _pdl_service
    if _pdl_service is None:
        _pdl_service = PDLService()
    return _pdl_service
