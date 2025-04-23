from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
import os
from getpass import getpass

def generate_key_pair():
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=4096,
        backend=default_backend()
    )

    # Generate public key
    public_key = private_key.public_key()

    # Get encryption password
    password = getpass("Enter password to encrypt private key: ").encode()

    # Serialize private key
    pem_private = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password)
    )

    # Serialize public key
    pem_public = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    )

    # Get OneDrive paths
    local_onedrive = os.environ.get('OneDrive', os.path.expanduser('~/OneDrive'))
    other_onedrive = input("Enter the path to the other person's OneDrive: ")

    # Define file paths
    private_key_path = os.path.join(local_onedrive, 'private_key.pem')
    public_key_path = os.path.join(other_onedrive, 'public_key.pem')

    try:
        # Save keys
        with open(private_key_path, 'wb') as f:
            f.write(pem_private)
        with open(public_key_path, 'wb') as f:
            f.write(pem_public)
        
        print(f"Private key saved to: {private_key_path}")
        print(f"Public key saved to: {public_key_path}")
        print("Keys generated and distributed successfully!")
    
    except Exception as e:
        print(f"Error saving keys: {str(e)}")
        print("Please verify the OneDrive paths and permissions.")

if __name__ == "__main__":
    generate_key_pair()