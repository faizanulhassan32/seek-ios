from supabase import create_client, Client
import os
from typing import Dict, List, Optional

class SupabaseClient:
    def __init__(self):
        url = os.getenv('SUPABASE_URL')
        # Prefer Service Role Key for backend operations to bypass RLS
        key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')

        if not url or not key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY (or SUPABASE_SERVICE_ROLE_KEY) must be set in environment variables")

        self.client: Client = create_client(url, key)

    def create_person(self, person_data: Dict) -> Dict:
        """Create a new person record in the database"""
        response = self.client.table('persons').insert(person_data).execute()
        return response.data[0] if response.data else None

    def get_person(self, person_id: str) -> Optional[Dict]:
        """Retrieve a person by ID"""
        response = self.client.table('persons').select('*').eq('id', person_id).execute()
        return response.data[0] if response.data else None

    def search_persons_by_query(self, query: str) -> List[Dict]:
        """Search for persons by query string"""
        response = self.client.table('persons').select('*').ilike('query', f'%{query}%').execute()
        return response.data if response.data else []

    def get_person_by_query(self, normalized_query: str) -> Optional[Dict]:
        """Get person by exact normalized query match (case-insensitive)"""
        response = self.client.table('persons').select('*').ilike('query', normalized_query).execute()
        return response.data[0] if response.data else None

    def update_person(self, person_id: str, updates: Dict) -> Dict:
        """Update a person record"""
        response = self.client.table('persons').update(updates).eq('id', person_id).execute()
        return response.data[0] if response.data else None

    def increment_report_count(self, person_id: str) -> bool:
        """Increment the report count for a person"""
        # We use a stored procedure or just a get-update loop. 
        # For simplicity/speed without custom SQL functions, we'll do a get-update.
        # Ideally, use rpc() if a function exists, but we can't assume that.
        # Actually, we can assume the user will run SQL. 
        # But let's stick to simple python logic: fetch, increment, update.
        # Race conditions are possible but acceptable for this feature.
        try:
            person = self.get_person(person_id)
            if person:
                current_count = person.get('report_count', 0) or 0
                self.update_person(person_id, {'report_count': current_count + 1})
                return True
            return False
        except Exception as e:
            print(f"Error incrementing report count: {e}")
            return False

    def create_chat(self, chat_data: Dict) -> Dict:
        """Create a new chat record"""
        response = self.client.table('chats').insert(chat_data).execute()
        return response.data[0] if response.data else None

    def get_chat(self, chat_id: str) -> Optional[Dict]:
        """Retrieve a chat by ID"""
        response = self.client.table('chats').select('*').eq('id', chat_id).execute()
        return response.data[0] if response.data else None

    def get_chats_by_person(self, person_id: str) -> List[Dict]:
        """Get all chats for a specific person"""
        response = self.client.table('chats').select('*').eq('person_id', person_id).order('created_at', desc=True).execute()
        return response.data if response.data else []

    def update_chat(self, chat_id: str, messages: List[Dict]) -> Dict:
        """Update chat messages"""
        response = self.client.table('chats').update({'messages': messages}).eq('id', chat_id).execute()
        return response.data[0] if response.data else None

    # User Methods
    def get_user_by_apple_id(self, apple_id: str) -> Optional[Dict]:
        """Get user by Apple ID"""
        response = self.client.table('users').select('*').eq('apple_id', apple_id).execute()
        return response.data[0] if response.data else None

    def create_user(self, user_data: Dict) -> Dict:
        """Create a new user record"""
        response = self.client.table('users').insert(user_data).execute()
        return response.data[0] if response.data else None

    # Storage Methods
    def upload_file(self, bucket: str, path: str, file_data: bytes, content_type: str = "image/jpeg") -> Dict:
        """Upload a file to Supabase Storage"""
        try:
            response = self.client.storage.from_(bucket).upload(
                path=path,
                file=file_data,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            return response
        except Exception as e:
            # If file already exists (and upsert failed or wasn't used), or other error
            print(f"Error uploading file to Supabase: {e}")
            return None

    def get_public_url(self, bucket: str, path: str) -> str:
        """Get the public URL for a file in storage"""
        return self.client.storage.from_(bucket).get_public_url(path)

    def file_exists(self, bucket: str, path: str) -> bool:
        """Check if a file exists in storage"""
        try:
            # Try to list the file. If it returns items, it exists.
            # Note: 'list' takes a folder path. We can list the parent folder and check results.
            # A simpler way often used is to just try to get the public URL or metadata, 
            # but listing is more definitive if we want to avoid 404 checks on public URLs.
            # For simplicity/performance in this specific proxy case, we might just rely on 
            # the fact that we use a deterministic hash for the filename. 
            # If we want to be sure, we can try to list.
            
            # Optimization: We'll assume the caller might track this, or we just overwrite (upsert=True).
            # But to implement 'cache hit' logic without re-uploading, we need to check.
            
            # Supabase-py storage list method:
            folder = os.path.dirname(path)
            filename = os.path.basename(path)
            files = self.client.storage.from_(bucket).list(folder)
            
            for f in files:
                if f.get('name') == filename:
                    return True
            return False
        except Exception as e:
            print(f"Error checking file existence: {e}")
            return False

# Singleton instance
_supabase_client = None

def get_supabase_client() -> SupabaseClient:
    """Get or create the Supabase client singleton"""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = SupabaseClient()
    return _supabase_client
