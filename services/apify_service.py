from apify_client import ApifyClient
import os
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from utils.logger import setup_logger

logger = setup_logger('apify_service')

class ApifyService:
    """Service for scraping social media and web data using Apify actors"""

    def __init__(self):
        api_key = os.getenv('APIFY_API_KEY')
        if not api_key:
            raise ValueError("APIFY_API_KEY must be set in environment variables")

        self.client = ApifyClient(api_key)

    def scrape_instagram(self, username: str) -> Dict:
        """
        Scrape Instagram profile using Apify

        Args:
            username: Instagram username to scrape

        Returns:
            Dictionary containing Instagram profile data
        """
        logger.info(f"Scraping Instagram for username: {username}")

        try:
            # Use Instagram Profile Scraper actor
            run_input = {
                "usernames": [username],
                "resultsLimit": 50
            }

            run = self.client.actor("apify/instagram-profile-scraper").call(run_input=run_input, timeout_secs=20)

            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)

            logger.info(f"Instagram scraping completed for {username}")

            return {
                'source': 'instagram',
                'username': username,
                'data': items[0] if items else {},
                'success': len(items) > 0
            }

        except Exception as e:
            logger.error(f"Error scraping Instagram: {str(e)}")
            return {
                'source': 'instagram',
                'username': username,
                'data': {},
                'error': str(e),
                'success': False
            }

    def scrape_twitter(self, username: str) -> Dict:
        """
        Scrape Twitter/X profile using Apify

        Args:
            username: Twitter username to scrape

        Returns:
            Dictionary containing Twitter profile data
        """
        logger.info(f"Scraping Twitter for username: {username}")

        try:
            # Use web.harvester/twitter-scraper
            run_input = {
                "twitterHandles": [username],
                "maxItems": 20
            }

            run = self.client.actor("web.harvester/twitter-scraper").call(run_input=run_input, timeout_secs=20)

            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)

            logger.info(f"Twitter scraping completed for {username}")

            return {
                'source': 'twitter',
                'username': username,
                'data': items,
                'success': len(items) > 0
            }

        except Exception as e:
            logger.error(f"Error scraping Twitter: {str(e)}")
            return {
                'source': 'twitter',
                'username': username,
                'data': [],
                'error': str(e),
                'success': False
            }

    def scrape_linkedin(self, profile_url: str) -> Dict:
        """
        Scrape LinkedIn profile using Apify

        Args:
            profile_url: LinkedIn profile URL

        Returns:
            Dictionary containing LinkedIn profile data
        """
        logger.info(f"Scraping LinkedIn profile: {profile_url}")

        try:
            # Use apimaestro/linkedin-profile-posts
            # Note: This actor might require cookies or specific input.
            # Assuming standard 'linkedinUrl' or 'profileUrl'.
            # Checking common inputs for this actor: usually 'linkedinUrl'
            run_input = {
                "linkedinUrl": profile_url,
                "maxPosts": 5 # Limit posts to save time/cost
            }

            run = self.client.actor("apimaestro/linkedin-profile-posts").call(run_input=run_input, timeout_secs=20)

            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)

            logger.info(f"LinkedIn scraping completed")

            return {
                'source': 'linkedin',
                'profile_url': profile_url,
                'data': items[0] if items else {},
                'success': len(items) > 0
            }

        except Exception as e:
            logger.error(f"Error scraping LinkedIn: {str(e)}")
            return {
                'source': 'linkedin',
                'profile_url': profile_url,
                'data': {},
                'error': str(e),
                'success': False
            }

    def scrape_tiktok(self, username: str) -> Dict:
        """Scrape TikTok profile using clockworks/tiktok-profile-scraper"""
        logger.info(f"Scraping TikTok for username: {username}")
        try:
            run_input = {"profiles": [username]}
            run = self.client.actor("clockworks/tiktok-profile-scraper").call(run_input=run_input, timeout_secs=20)
            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)
            return {'source': 'tiktok', 'username': username, 'data': items[0] if items else {}, 'success': len(items) > 0}
        except Exception as e:
            logger.error(f"Error scraping TikTok: {e}")
            return {'source': 'tiktok', 'username': username, 'error': str(e), 'success': False}

    def scrape_facebook(self, profile_url: str) -> Dict:
        """Scrape Facebook profile using lazyscraper/facebook-profile-scraper"""
        logger.info(f"Scraping Facebook profile: {profile_url}")
        try:
            run_input = {"startUrls": [{"url": profile_url}]}
            run = self.client.actor("lazyscraper/facebook-profile-scraper").call(run_input=run_input, timeout_secs=20)
            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)
            return {'source': 'facebook', 'profile_url': profile_url, 'data': items[0] if items else {}, 'success': len(items) > 0}
        except Exception as e:
            logger.error(f"Error scraping Facebook: {e}")
            return {'source': 'facebook', 'profile_url': profile_url, 'error': str(e), 'success': False}

    def scrape_youtube(self, channel_url: str) -> Dict:
        """Scrape YouTube channel using pratikdani/youtube-profile-scraper"""
        logger.info(f"Scraping YouTube channel: {channel_url}")
        try:
            run_input = {"startUrls": [{"url": channel_url}]}
            run = self.client.actor("pratikdani/youtube-profile-scraper").call(run_input=run_input, timeout_secs=20)
            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)
            return {'source': 'youtube', 'channel_url': channel_url, 'data': items[0] if items else {}, 'success': len(items) > 0}
        except Exception as e:
            logger.error(f"Error scraping YouTube: {e}")
            return {'source': 'youtube', 'channel_url': channel_url, 'error': str(e), 'success': False}

    def scrape_web_generic(self, urls: List[str]) -> Dict:
        """
        Scrape generic web pages using Apify

        Args:
            urls: List of URLs to scrape

        Returns:
            Dictionary containing scraped web data
        """
        logger.info(f"Scraping {len(urls)} web pages")

        try:
            # Use Web Scraper actor
            run_input = {
                "startUrls": [{"url": url} for url in urls],
                "pageFunction": """
                    async function pageFunction(context) {
                        const { request, log, skipLinks, $ } = context;
                        const title = $('title').text();
                        const text = $('body').text();
                        return {
                            url: request.url,
                            title: title,
                            text: text.substring(0, 5000)
                        };
                    }
                """
            }

            run = self.client.actor("apify/web-scraper").call(run_input=run_input, timeout_secs=30)

            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)

            logger.info(f"Web scraping completed for {len(urls)} pages")

            return {
                'source': 'web_scraper',
                'urls': urls,
                'data': items,
                'success': len(items) > 0
            }

        except Exception as e:
            logger.error(f"Error scraping web pages: {str(e)}")
            return {
                'source': 'web_scraper',
                'urls': urls,
                'data': [],
                'error': str(e),
                'success': False
            }

    def scrape_all_parallel(self, query: str, identifiers: Dict[str, str]) -> List[Dict]:
        """
        Scrape multiple platforms in parallel

        Args:
            query: Original search query
            identifiers: Dictionary mapping platforms to usernames/URLs
                        e.g., {'instagram': 'username', 'twitter': 'username', 'linkedin': 'url'}

        Returns:
            List of results from all scrapers
        """
        logger.info(f"Starting parallel scraping for query: {query}")

        results = []

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}

            if 'instagram' in identifiers and identifiers['instagram']:
                future = executor.submit(self.scrape_instagram, identifiers['instagram'])
                futures[future] = 'instagram'

            if 'twitter' in identifiers and identifiers['twitter']:
                future = executor.submit(self.scrape_twitter, identifiers['twitter'])
                futures[future] = 'twitter'

            if 'linkedin' in identifiers and identifiers['linkedin']:
                future = executor.submit(self.scrape_linkedin, identifiers['linkedin'])
                futures[future] = 'linkedin'

            if 'web_urls' in identifiers and identifiers['web_urls']:
                future = executor.submit(self.scrape_web_generic, identifiers['web_urls'])
                futures[future] = 'web'

            if 'tiktok' in identifiers and identifiers['tiktok']:
                future = executor.submit(self.scrape_tiktok, identifiers['tiktok'])
                futures[future] = 'tiktok'

            if 'facebook' in identifiers and identifiers['facebook']:
                future = executor.submit(self.scrape_facebook, identifiers['facebook'])
                futures[future] = 'facebook'

            if 'youtube' in identifiers and identifiers['youtube']:
                future = executor.submit(self.scrape_youtube, identifiers['youtube'])
                futures[future] = 'youtube'

            # Scrape Bumble and Tinder using generic web scraper if found
            if 'bumble' in identifiers and identifiers['bumble']:
                future = executor.submit(self.scrape_web_generic, [identifiers['bumble']])
                futures[future] = 'bumble'

            if 'tinder' in identifiers and identifiers['tinder']:
                future = executor.submit(self.scrape_web_generic, [identifiers['tinder']])
                futures[future] = 'tinder'

            for future in as_completed(futures):
                platform = futures[future]
                try:
                    # Set a hard timeout on the thread result as well
                    result = future.result(timeout=35)
                    results.append(result)
                    logger.info(f"Completed scraping {platform}")
                except Exception as e:
                    logger.error(f"Error in {platform} scraping (timeout or other): {str(e)}")
                    results.append({
                        'source': platform,
                        'error': f"Timeout or error: {str(e)}",
                        'success': False
                    })

        logger.info(f"Parallel scraping completed. {len(results)} results obtained")
        return results



    def find_social_links(self, name: str) -> Dict[str, str]:
        """
        Search for social media links using Apify Google Search Scraper
        Used as a fallback when OpenAI websearch fails to find profiles.
        """
        logger.info(f"Fallback: Searching for social media links for: {name}")

        try:
            # Construct queries for specific platforms
            queries = [
                f"site:instagram.com {name}",
                f"site:twitter.com {name}",
                f"site:linkedin.com/in/ {name}",
                f"site:facebook.com {name}",
                f"site:youtube.com {name}",
                f"site:tiktok.com {name}",
                f"site:bumble.com {name}",
                f"site:tinder.com {name}"
            ]

            run_input = {
                "queries": "\n".join(queries),
                "resultsPerPage": 1,
                "countryCode": "us",
                "maxPagesPerQuery": 1
            }

            # Note: The input format for apify/google-search-scraper might vary.
            # Checking documentation: usually "queries" is a string (one per line).

            run = self.client.actor("apify/google-search-scraper").call(run_input=run_input, timeout_secs=20)

            found_links = {}

            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                organic_results = item.get('organicResults', [])
                if not organic_results:
                    continue
                    
                first_result = organic_results[0]
                link = first_result.get('url')
                
                if 'instagram.com' in link:
                    parts = link.rstrip('/').split('/')
                    if len(parts) > 3:
                        found_links['instagram'] = parts[-1]
                elif 'twitter.com' in link or 'x.com' in link:
                    parts = link.rstrip('/').split('/')
                    if len(parts) > 3:
                        found_links['twitter'] = parts[-1]
                elif 'linkedin.com' in link:
                    found_links['linkedin'] = link
                elif 'facebook.com' in link:
                    found_links['facebook'] = link
                elif 'youtube.com' in link:
                    found_links['youtube'] = link
                elif 'tiktok.com' in link:
                    parts = link.rstrip('/').split('/')
                    if len(parts) > 3 and parts[-1].startswith('@'):
                        found_links['tiktok'] = parts[-1]
                    else:
                        found_links['tiktok'] = link
                elif 'bumble.com' in link:
                    found_links['bumble'] = link
                elif 'tinder.com' in link:
                    found_links['tinder'] = link
                    
            logger.info(f"Fallback search found: {found_links}")
            return found_links
            
        except Exception as e:
            logger.error(f"Error in fallback social search: {e}")
            return {}

    def scrape_osint(self, name: str, location: str = "") -> List[Dict]:
        """
        Scrape OSINT websites (TruePeopleSearch, PeekYou, FamilyTreeNow, IDCrawl)
        """
        logger.info(f"Starting OSINT scraping for: {name} in {location}")
        
        # Split name
        parts = name.strip().split()
        if len(parts) < 2:
            logger.warning("OSINT search requires at least first and last name")
            return []
            
        first = parts[0]
        last = parts[-1]
        
        # Construct URLs
        urls = []
        
        # 1. TruePeopleSearch
        # https://www.truepeoplesearch.com/results?name=John+Doe&citystatezip=New+York
        tps_loc = location.replace(" ", "+") if location else ""
        tps_url = f"https://www.truepeoplesearch.com/results?name={first}+{last}&citystatezip={tps_loc}"
        urls.append({"source": "truepeoplesearch", "url": tps_url})
        
        # 2. FamilyTreeNow
        # https://www.familytreenow.com/search/people/results?first=John&last=Doe&citystatezip=New+York
        ftn_url = f"https://www.familytreenow.com/search/people/results?first={first}&last={last}&citystatezip={tps_loc}"
        urls.append({"source": "familytreenow", "url": ftn_url})
        
        # 3. PeekYou
        # https://www.peekyou.com/john_doe/new_york
        py_loc = location.replace(" ", "_").replace(",", "").lower() if location else "us"
        py_url = f"https://www.peekyou.com/{first.lower()}_{last.lower()}/{py_loc}"
        urls.append({"source": "peekyou", "url": py_url})
        
        # 4. IDCrawl
        # https://www.idcrawl.com/john-doe
        idc_url = f"https://www.idcrawl.com/{first.lower()}-{last.lower()}"
        urls.append({"source": "idcrawl", "url": idc_url})
        
        results = []
        
        # Reuse Generic Web Scraper logic but in parallel for specific OSINT targets
        # We define a custom page function to extract broad data
        page_function_js = """
        async function pageFunction(context) {
            const { request, log, jQuery: $ } = context;
            const title = $('title').text();
            
            // Basic extraction (can be refined with specific selectors)
            const bodyText = $('body').text().replace(/\\s+/g, ' ').trim();
            
            // Extract potential relatives (heuristic)
            // Look for "Relatives:" or similar text patterns if possible, 
            // but for now we return text for backend LLM processing or simple regex.
            
            return {
                url: request.url,
                title: title,
                text_content: bodyText.substring(0, 10000) // Limit size
            };
        }
        """
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_to_source = {}
            for target in urls:
                # We simply use the generic web scraper actor but with our URLs
                run_input = {
                    "startUrls": [{"url": target['url']}],
                    "pageFunction": page_function_js
                }
                
                # We call the client directly here to allow parallel execution per source
                # instead of batching them all in one 'scrape_web_generic' call which might handle them purely sequentially in some actor configs(??)
                # Actually apify/web-scraper handles concurrency well. 
                # BUT, to keep error handling isolated per source, let's allow separate calls or just use scrape_web_generic?
                # Using scrape_web_generic is cleaner code-wise but it aggregates them.
                # Let's call them individually so we can tag the source easily.
                
                future = executor.submit(self._run_single_osint_scrape, target['source'], target['url'], page_function_js)
                future_to_source[future] = target['source']
                
            for future in as_completed(future_to_source):
                source = future_to_source[future]
                try:
                    data = future.result(timeout=40) # 40s timeout for OSINT
                    if data:
                        results.append(data)
                        logger.info(f"OSINT scrape success for {source}")
                except Exception as e:
                    logger.error(f"OSINT scrape failed for {source}: {e}")
                    
        return results

    def _run_single_osint_scrape(self, source: str, url: str, page_function: str) -> Optional[Dict]:
        """Helper to run a single OSINT scrape task"""
        try:
            run_input = {
                "startUrls": [{"url": url}],
                "pageFunction": page_function
            }
            # Use web-scraper
            run = self.client.actor("apify/web-scraper").call(run_input=run_input, timeout_secs=35)
            
            items = []
            for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
                items.append(item)
                
            if items:
                return {
                    "source": source,
                    "url": url,
                    "data": items[0]
                }
            return None
        except Exception as e:
            raise e

# Singleton instance
_apify_service = None

def get_apify_service() -> ApifyService:
    """Get or create the ApifyService singleton"""
    global _apify_service
    if _apify_service is None:
        _apify_service = ApifyService()
    return _apify_service
