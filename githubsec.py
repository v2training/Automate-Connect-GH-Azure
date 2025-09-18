import os
import requests
from cryptography.hazmat.primitives import serialization
from nacl import encoding, public
import jwt
import time


class GitHubSecretMagic:
    
    def __init__(self):

        #pull values from environment variables
        self.app_id = os.getenv('GITHUB_APP_ID')
        self.installation_id = os.getenv('GITHUB_APP_INSTALL_ID')       
        self.private_key_path = os.getenv('GITHUB_APP_PRIVATE_KEY_PATH')
        self.access_token = None
        self.token_expires_at = 0


    def _encrypt_secret(self, public_key, secret_value):        
        public_key_bytes = encoding.Base64Encoder.decode(public_key.encode())
        sealed_box = public.SealedBox(public.PublicKey(public_key_bytes))
        encrypted = sealed_box.encrypt(secret_value.encode())
        
        return encoding.Base64Encoder.encode(encrypted).decode()


    def get_headers(self):
        
        token = self.get_installation_token()
        return {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }


    def get_installation_token(self):

        try:       
            if self.access_token and time.time() < self.token_expires_at - 60:
                return self.access_token
        
            # Generate JWT
            with open(self.private_key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(key_file.read(), password=None)

        except Exception as e:
            raise Exception(f"Error loading private key: {str(e)}")


        payload = {
            'iat': int(time.time()) - 60,  # Issued 60 seconds in the past
            'exp': int(time.time()) + 600,  # Expires in 10 minutes
            'iss': self.app_id
        }
        
        jwt_token = jwt.encode(payload, private_key, algorithm='RS256')
        
        # Get installation access token
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        response = requests.post(
            f'https://api.github.com/app/installations/{self.installation_id}/access_tokens',
            headers=headers
        )
        
        if response.status_code != 201:
            raise Exception(f"Failed to get access token: {response.status_code} - {response.text}")
        
        token_data = response.json()
        self.access_token = token_data['token']
        
        # Tokens expire in 1 hour
        self.token_expires_at = time.time() + 3600
        
        return self.access_token


    def get_repository_public_key(self, owner, repo):
        # Get the repository's public key for encrypting secrets
        headers = self.get_headers()
        
        response = requests.get(
            f'https://api.github.com/repos/{owner}/{repo}/actions/secrets/public-key',
            headers=headers
        )
        
        if response.status_code != 200:
            raise Exception(f"Failed to get public key: {response.status_code} - {response.text}")
        
        return response.json()


    def get_existing_secrets(self, owner, repo):
        # Get list of existing secret names
        try:
            headers = self.get_headers()
            response = requests.get(
                f'https://api.github.com/repos/{owner}/{repo}/actions/secrets',
                headers=headers
            )
                
            if response.status_code == 200:
                secrets_data = response.json()
                return [secret['name'] for secret in secrets_data.get('secrets', [])]
            
            else:
                print(f"Error getting secrets list: {response.status_code}")
                return []
            
        except Exception as e:
            print(f"Error getting existing secrets: {str(e)}")
            return []


    def createrepoSecret(self, owner, repo, secret_name, secret_value):
                
        try:
            # Get repository public key
            pub_key_data = self.get_repository_public_key(owner, repo)
            
            # Encrypt the secret
            encrypted_value = self._encrypt_secret(pub_key_data['key'], secret_value)
            
            # Prepare secret data
            secret_data = {
                'encrypted_value': encrypted_value,
                'key_id': pub_key_data['key_id']
            }
            
            # Create/update the secret
            headers = self.get_headers()
            response = requests.put(
                f'https://api.github.com/repos/{owner}/{repo}/actions/secrets/{secret_name}',
                json=secret_data,
                headers=headers
            )
            
            if response.status_code in [201, 204]:
                action = "created" if response.status_code == 201 else "updated"
                print(f"Secret '{secret_name}' {action} successfully in {owner}/{repo}")
                return True
            
            else:
                raise Exception(f"Failed to create secret: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"Error creating secret '{secret_name}': {str(e)}")
            return False



    def list_repository_secrets(self, owner, repo):
        """List all secrets in a repository (names only, not values)"""
        headers = self.get_headers()
        
        response = requests.get(
            f'https://api.github.com/repos/{owner}/{repo}/actions/secrets',
            headers=headers
        )
        
        if response.status_code == 200:
            secrets_data = response.json()
            secrets = [secret['name'] for secret in secrets_data['secrets']]
            print(f"Secrets in {owner}/{repo}: {secrets}")
            return secrets
        
        else:
            raise Exception(f"Failed to list secrets: {response.status_code} - {response.text}")
    

    def check_repository_exists(self, owner, repo):                
        try:
            headers = self.get_headers()
            response = requests.get(
                f'https://api.github.com/repos/{owner}/{repo}',
                headers=headers
            )

            if response.status_code == 200:
                repo_data = response.json()
                return {
                    'exists': True,
                    'accessible': True,
                    'private': repo_data.get('private', False),
                    'message': f"Repository {owner}/{repo} exists and is accessible"
                }

            elif response.status_code == 404:
                return {
                    'exists': False,
                    'accessible': False,
                    'private': None,
                    'message': f"Repository {owner}/{repo} does not exist or is not accessible"
                }

            elif response.status_code == 403:
                return {
                    'exists': True,  # Likely exists but no access
                    'accessible': False,
                    'private': True,  # Probably private
                    'message': f"Repository {owner}/{repo} exists but access is forbidden"
                }

            else:
                return {
                    'exists': None,
                    'accessible': False,
                    'private': None,
                    'message': f"Unexpected response: {response.status_code} - {response.text}"
                }

        except Exception as e:
            return {
                'exists': None,
                'accessible': False,
                'private': None,
                'message': f"Error checking repository: {str(e)}"
            }