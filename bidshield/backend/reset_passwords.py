import hashlib, hmac, secrets, sqlite3

def hash_password(password, salt=None):
    if not salt:
        salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
    return salt + "$" + key.hex()

password = 'BidShield@123'

conn = sqlite3.connect('storage/bidshield.db')

for username in ['officer', 'admin', 'auditor', 'verifier']:
    new_hash = hash_password(password)
    conn.execute('UPDATE users SET hashed_password = ? WHERE username = ?', (new_hash, username))
    print('Updated', username)

conn.commit()

# Verify
rows = conn.execute('SELECT username, role, hashed_password FROM users').fetchall()
for r in rows:
    print(r[0], r[1], r[2][:20], '...')

conn.close()
print('Done - all passwords set to: BidShield123')
