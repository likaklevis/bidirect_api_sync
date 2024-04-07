import base64
import hashlib
import secrets

APP = "APISYNC"  # API name


def generate_key(key_len=None):
    """
    Generates a random string key.
    :param key_len: Integer, length of key.
    """
    length = key_len or 32
    return secrets.token_hex(length)


def hash_key(key, salt=None, iterations=260000):
    """
    This function does a one-way hash of the 'key' parameter. Hash used: PBKDF2 SHA256 based on HMAC module.

    :param key: String to hash
    :param salt: String to salt
    :param iterations: Integer, number of iterations to hash (higher is more secure but less efficient)
    """
    if salt is None:  # if no salt, generate one
        salt = generate_key(16)
    assert salt and isinstance(salt, str) and "$" not in salt
    assert isinstance(key, str)
    api_key_hash = hashlib.pbkdf2_hmac("sha256", key.encode("utf-8"), salt.encode("utf-8"), iterations)
    hash_to_b64 = base64.b64encode(api_key_hash).decode("ascii").strip()
    return "{}${}${}${}".format(APP, iterations, salt, hash_to_b64)


def validate_key(key, key_hash):
    """
    Checks if the given key is valid, using the salt and iterations parameters from the hashed key.

    :param key: String to validate
    :param key_hash: Hash of the key to validate to.
    """
    if (key_hash or "").count("$") != 3:
        return False

    identifier, iterations, salt, b64_hash = key_hash.split("$", 3)
    iterations = int(iterations)
    assert identifier.startswith(APP)

    compare_hash = hash_key(key, salt=salt, iterations=iterations)
    return secrets.compare_digest(key_hash, compare_hash)
