from Crypto.Protocol.SecretSharing import SSS
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
import base64

def generate_master_key():
    # Generate RSA key pair
    key = RSA.generate(4096)
    public_key = key.publickey()
    return key, public_key

def split_private_key(master_private_key, num_shares=3):
    # Serialize private key
    pem = master_private_key.export_key()
    
    # Generate random AES key
    aes_key = get_random_bytes(32)  # 256-bit key
    
    # Encrypt private key with AES
    cipher_aes = AES.new(aes_key, AES.MODE_GCM)
    ciphertext, tag = cipher_aes.encrypt_and_digest(pem)
    nonce = cipher_aes.nonce
    
    # Split AES key using Shamir's (threshold=1, shares=3)
    shares = SSS.split(1, num_shares, aes_key)
    
    return {
        'encrypted_private': (ciphertext, nonce, tag),
        'shares': shares
    }

def encrypt_data(public_key, message):
    # Encrypt using RSA
    cipher_rsa = PKCS1_OAEP.new(public_key)
    ciphertext = cipher_rsa.encrypt(message)
    return ciphertext

def decrypt_with_share(share, encrypted_pkg):
    # Reconstruct AES key
    aes_key = SSS.combine([share])
    
    # Unpack encryption package
    ciphertext, nonce, tag = encrypted_pkg
    
    # Decrypt private key
    cipher_aes = AES.new(aes_key, AES.MODE_GCM, nonce=nonce)
    pem = cipher_aes.decrypt_and_verify(ciphertext, tag)
    
    # Load RSA key
    private_key = RSA.import_key(pem)
    
    return private_key

# Usage example
master_private, master_public = generate_master_key()
split_result = split_private_key(master_private)

# Encrypt data
message = b"Top secret government plans"
ciphertext = encrypt_data(master_public, message)

# Decrypt with first share
recovered_key = decrypt_with_share(
    split_result['shares'][0],
    split_result['encrypted_private']
)

# Decrypt message
cipher_rsa = PKCS1_OAEP.new(recovered_key)
plaintext = cipher_rsa.decrypt(ciphertext)

print("Decrypted:", plaintext.decode())