from flask import Blueprint, request, jsonify
import jwt
import requests
import os
from utils.logger import setup_logger

auth_bp = Blueprint('auth', __name__)
logger = setup_logger('auth_route')

APPLE_PUBLIC_KEYS_URL = "https://appleid.apple.com/auth/keys"

def get_apple_public_key(kid):
    """Fetch Apple's public key for the given key ID (kid)"""
    try:
        response = requests.get(APPLE_PUBLIC_KEYS_URL)
        keys = response.json().get('keys', [])
        for key in keys:
            if key['kid'] == kid:
                return key
        return None
    except Exception as e:
        logger.error(f"Error fetching Apple public keys: {e}")
        return None

@auth_bp.route('/auth/apple', methods=['POST'])
def apple_sign_in():
    """
    Handle Apple Sign In - create or retrieve user
    """
    try:
        from db.supabase_client import get_supabase_client
        
        data = request.get_json()
        apple_id = data.get('appleId')
        email = data.get('email')
        full_name = data.get('fullName')
        
        if not apple_id:
            return jsonify({'error': 'Missing appleId'}), 400
        
        db = get_supabase_client()
        
        # Check if user exists
        user = db.get_user_by_apple_id(apple_id)
        
        if user:
            logger.info(f"Existing user signed in: {apple_id}")
        else:
            # Create new user
            user_data = {
                'apple_id': apple_id,
                'email': email,
                'full_name': full_name
            }
            user = db.create_user(user_data)
            logger.info(f"New user created: {apple_id}")
        
        # Return user data with simple token (using user_id as token)
        return jsonify({
            'userId': user['id'],
            'appleId': user['apple_id'],
            'email': user.get('email'),
            'fullName': user.get('full_name'),
            'token': user['id']  # Simple token for now
        })
        
    except Exception as e:
        logger.error(f"Error in Apple sign in: {e}", exc_info=True)
        return jsonify({'error': 'Sign in failed'}), 500

@auth_bp.route('/auth/apple/verify', methods=['POST'])
def verify_apple_token():
    """
    Verify Apple Sign In identity token
    """
    try:
        data = request.get_json()
        identity_token = data.get('identityToken')
        
        if not identity_token:
            return jsonify({'error': 'Missing identityToken'}), 400

        # 1. Decode the header to get the Key ID (kid)
        header = jwt.get_unverified_header(identity_token)
        kid = header.get('kid')
        
        if not kid:
            return jsonify({'error': 'Invalid token header'}), 400

        # 2. Fetch the public key from Apple
        public_key_data = get_apple_public_key(kid)
        if not public_key_data:
            return jsonify({'error': 'Public key not found'}), 400

        # 3. Construct the public key object
        import json
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(public_key_data))

        # 4. Verify the token
        # Verify signature, issuer, and audience
        # Audience should be your app's bundle ID: com.sean.psearch
        decoded = jwt.decode(
            identity_token,
            public_key,
            algorithms=['RS256'],
            audience='com.sean.psearch',
            issuer='https://appleid.apple.com'
        )

        logger.info(f"Apple Sign In verified for user: {decoded.get('sub')}")
        
        return jsonify({
            'success': True,
            'userIdentifier': decoded.get('sub'),
            'email': decoded.get('email')
        })

    except jwt.ExpiredSignatureError:
        logger.warning("Apple identity token expired")
        return jsonify({'error': 'Token expired'}), 401
    except jwt.InvalidTokenError as e:
        logger.error(f"Invalid Apple token: {e}")
        return jsonify({'error': 'Invalid token'}), 401
    except Exception as e:
        logger.error(f"Error verifying Apple token: {e}", exc_info=True)
        return jsonify({'error': 'Verification failed'}), 500

@auth_bp.route('/auth/user/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """
    Delete user account
    """
    try:
        from db.supabase_client import get_supabase_client
        
        db = get_supabase_client()
        
        # Delete user from database
        response = db.client.table('users').delete().eq('id', user_id).execute()
        
        if response.data:
            logger.info(f"User deleted: {user_id}")
            return jsonify({'success': True, 'message': 'User deleted successfully'})
        else:
            return jsonify({'error': 'User not found'}), 404
        
    except Exception as e:
        logger.error(f"Error deleting user: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete user'}), 500
