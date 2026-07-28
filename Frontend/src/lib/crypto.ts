import forge from 'node-forge';

let serverPublicKey: forge.pki.rsa.PublicKey | null = null;

export async function getServerPublicKey(): Promise<forge.pki.rsa.PublicKey> {
  if (serverPublicKey) return serverPublicKey;
  
  const res = await fetch('http://localhost:8000/api/auth/public-key');
  const json = await res.json();
  if (!json.success) throw new Error("Failed to fetch public key");
  
  serverPublicKey = forge.pki.publicKeyFromPem(json.data.public_key);
  return serverPublicKey;
}

export async function encryptPayload(payload: any): Promise<{rsa_encrypted_aes_key: string, aes_encrypted_payload: string}> {
  const publicKey = await getServerPublicKey();
  
  // 1. Generate AES-256 Key and IV
  const aesKeyBytes = forge.random.getBytesSync(32);
  const ivBytes = forge.random.getBytesSync(12);
  
  // 2. Encrypt Payload with AES-GCM
  const payloadStr = JSON.stringify(payload);
  const cipher = forge.cipher.createCipher('AES-GCM', aesKeyBytes);
  cipher.start({ iv: ivBytes });
  cipher.update(forge.util.createBuffer(payloadStr, 'utf8'));
  cipher.finish();
  
  const ciphertext = cipher.output.getBytes();
  const tag = cipher.mode.tag.getBytes();
  
  // Combine IV + Ciphertext + Tag
  const combinedPayload = ivBytes + ciphertext + tag;
  const aes_encrypted_payload = forge.util.encode64(combinedPayload);
  
  // 3. Encrypt AES Key with RSA Public Key (RSA-OAEP with SHA-256)
  // The backend expects the base64-encoded AES key to be encrypted.
  const b64AesKey = forge.util.encode64(aesKeyBytes);
  const encryptedAesKey = publicKey.encrypt(b64AesKey, 'RSA-OAEP', {
    md: forge.md.sha256.create()
  });
  const rsa_encrypted_aes_key = forge.util.encode64(encryptedAesKey);
  
  return {
    rsa_encrypted_aes_key,
    aes_encrypted_payload,
    raw_aes_key: aesKeyBytes // Keep this to decrypt the response!
  };
}

export async function generateEncryptionHeaders(): Promise<{ rsa_encrypted_aes_key: string, raw_aes_key: string }> {
  const publicKey = await getServerPublicKey();
  const aesKeyBytes = forge.random.getBytesSync(32);
  const b64AesKey = forge.util.encode64(aesKeyBytes);
  const encryptedAesKey = publicKey.encrypt(b64AesKey, 'RSA-OAEP', {
    md: forge.md.sha256.create()
  });
  return {
    rsa_encrypted_aes_key: forge.util.encode64(encryptedAesKey),
    raw_aes_key: aesKeyBytes
  };
}

export function decryptPayload(encryptedBase64: string, aesKeyBytes: string): any {
  const combinedBuffer = forge.util.decode64(encryptedBase64);
  const iv = combinedBuffer.substring(0, 12);
  const authTag = combinedBuffer.substring(combinedBuffer.length - 16);
  const ciphertext = combinedBuffer.substring(12, combinedBuffer.length - 16);
  
  const decipher = forge.cipher.createDecipher('AES-GCM', aesKeyBytes);
  decipher.start({ iv, tag: forge.util.createBuffer(authTag) });
  decipher.update(forge.util.createBuffer(ciphertext));
  const pass = decipher.finish();
  
  if (pass) {
    const jsonStr = decipher.output.toString('utf8');
    return JSON.parse(jsonStr);
  } else {
    throw new Error("Response decryption failed");
  }
}
