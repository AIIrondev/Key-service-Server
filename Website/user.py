import os
from pymongo import MongoClient
import hashlib
from bson.objectid import ObjectId


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "Invario_Website")


def _get_users_collection():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
    db = client[MONGO_DB_NAME]
    return client, db["users"]


def check_password_strength(password):
    """
    Check if a password meets minimum security requirements.
    
    Args:
        password (str): Password to check
        
    Returns:
        bool: True if password is strong enough, False otherwise
    """
    if len(password) < 6:
        return False
    return True


def hashing(password):
    """
    Hash a password using SHA-512.
    
    Args:
        password (str): Password to hash
        
    Returns:
        str: Hexadecimal digest of the hashed password
    """
    return hashlib.sha512(password.encode()).hexdigest()


def check_nm_pwd(username, password):
    """
    Verify username and password combination.
    
    Args:
        username (str): Username to check
        password (str): Password to verify
        
    Returns:
        dict: User document if credentials are valid, None otherwise
    """
    client = None
    try:
        client, users = _get_users_collection()
        hashed_password = hashlib.sha512(password.encode()).hexdigest()
        return users.find_one({'Username': username, 'Password': hashed_password})
    finally:
        if client:
            client.close()


def add_user(username, password, name, last_name, email=""):
    """
    Add a new user to the database.
    
    Args:
        username (str): Username for the new user
        password (str): Password for the new user
        
    Returns:
        bool: True if user was added successfully, False if password was too weak
    """
    if not check_password_strength(password):
        return False

    client = None
    try:
        client, users = _get_users_collection()
        users.insert_one(
            {
                'Username': username,
                'Password': hashing(password),
                'Admin': False,
                'active_ausleihung': None,
                'name': name,
                'last_name': last_name,
                'email': (email or '').strip().lower(),
            }
        )
        return True
    finally:
        if client:
            client.close()


def make_admin(username):
    """
    Grant administrator privileges to a user.
    
    Args:
        username (str): Username of the user to promote
        
    Returns:
        bool: True if user was promoted successfully
    """
    client = None
    try:
        client, users = _get_users_collection()
        users.update_one({'Username': username}, {'$set': {'Admin': True}})
        return True
    finally:
        if client:
            client.close()

def remove_admin(username):
    """
    Remove administrator privileges from a user.
    
    Args:
        username (str): Username of the user to demote
        
    Returns:
        bool: True if user was demoted successfully
    """
    client = None
    try:
        client, users = _get_users_collection()
        users.update_one({'Username': username}, {'$set': {'Admin': False}})
        return True
    finally:
        if client:
            client.close()

def get_user(username):
    """
    Retrieve a specific user by username.
    
    Args:
        username (str): Username to search for
        
    Returns:
        dict: User document or None if not found
    """
    client = None
    try:
        client, users = _get_users_collection()
        return users.find_one({'Username': username})
    finally:
        if client:
            client.close()


def check_admin(username):
    """
    Check if a user has administrator privileges.
    
    Args:
        username (str): Username to check
        
    Returns:
        bool: True if user is an administrator, False otherwise
    """
    client = None
    try:
        client, users = _get_users_collection()
        user = users.find_one({'Username': username})
        return user and user.get('Admin', False)
    finally:
        if client:
            client.close()

def delete_user(username):
    """
    Delete a user from the database.
    Administrative function for removing user accounts.
    
    Args:
        username (str): Username of the account to delete
        
    Returns:
        bool: True if user was deleted successfully, False otherwise
    """
    client = None
    try:
        client, users = _get_users_collection()
        result = users.delete_one({'username': username})
        if result.deleted_count == 0:
            result = users.delete_one({'Username': username})
        return result.deleted_count > 0
    finally:
        if client:
            client.close()

def get_name(username):
    """
    Retrieve the name that is assosiated with the username.

    Returns:
        str: String of name
    """
    client = None
    try:
        client, users = _get_users_collection()
        user = users.find_one({'Username': username}) or {}
        return user.get("name")
    finally:
        if client:
            client.close()

def get_last_name(username):
    """
    Retrieve the last_name that is assosiated with the username.

    Returns:
        str: String of last_name
    """
    client = None
    try:
        client, users = _get_users_collection()
        user = users.find_one({'Username': username}) or {}
        return user.get("last_name")
    finally:
        if client:
            client.close()


def get_all_users():
    """
    Retrieve all users from the database.
    Administrative function for user management.
    
    Returns:
        list: List of all user documents
    """
    try:
        client, users = _get_users_collection()
        all_users = list(users.find())
        client.close()
        return all_users
    except Exception as e:
        return []

def update_password(username, new_password):
    """
    Update a user's password with a new one.
    
    Args:
        username (str): Username of the user
        new_password (str): New password to set
        
    Returns:
        bool: True if password was updated successfully, False otherwise
    """
    try:
        if not check_password_strength(new_password):
            return False

        client, users = _get_users_collection()
        
        # Hash the new password
        hashed_password = hashing(new_password)
        
        # Update the user's password
        result = users.update_one(
            {'Username': username}, 
            {'$set': {'Password': hashed_password}}
        )
        
        client.close()
        return result.modified_count > 0
    except Exception as e:
        print(f"Error updating password: {e}")
        return False
 
def update_user_name(username, name, last_name):
    """
    Update a user's name and last name.

    Args:
        username (str): Username of the user
        name (str): New first name
        last_name (str): New last name

    Returns:
        bool: True if updated successfully, False otherwise
    """
    try:
        client, users = _get_users_collection()
        
        result = users.update_one(
            {'Username': username}, 
            {'$set': {'name': name, 'last_name': last_name}}
        )
        
        client.close()
        return True
    except Exception as e:
        print(f"Error updating user name: {e}")
        return False