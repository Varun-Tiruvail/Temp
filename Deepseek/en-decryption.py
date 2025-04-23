from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import os

def encrypt_data():
    # Load recipient's public key
    other_onedrive = input("Enter path to recipient's OneDrive: ")
    public_key_path = os.path.join(other_onedrive, 'public_key.pem')
    
    with open(public_key_path, "rb") as key_file:
        public_key = serialization.load_pem_public_key(
            key_file.read(),
            backend=default_backend()
        )

    # Get data to encrypt
    message = input("Enter message to encrypt: ").encode('utf-8')

    # Encrypt the data
    ciphertext = public_key.encrypt(
        message,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    # Save encrypted data
    encrypted_path = os.path.join(os.getcwd(), 'encrypted_data.bin')
    with open(encrypted_path, 'wb') as f:
        f.write(ciphertext)
    
    print(f"Data encrypted and saved to: {encrypted_path}")

if __name__ == "__main__":
    encrypt_data()

#########################################################

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import os
from getpass import getpass

def decrypt_data():
    # Load private key
    local_onedrive = os.environ.get('OneDrive', os.path.expanduser('~/OneDrive'))
    private_key_path = os.path.join(local_onedrive, 'private_key.pem')
    
    password = getpass("Enter private key password: ").encode()
    
    with open(private_key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=password,
            backend=default_backend()
        )

    # Load encrypted data
    encrypted_path = os.path.join(os.getcwd(), 'encrypted_data.bin')
    with open(encrypted_path, 'rb') as f:
        ciphertext = f.read()

    # Decrypt the data
    plaintext = private_key.decrypt(
        ciphertext,
        padding.OAEP(
            mgf=padding.MGF1(algorithm=hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    print(f"\nDecrypted message: {plaintext.decode('utf-8')}")

if __name__ == "__main__":
    decrypt_data()