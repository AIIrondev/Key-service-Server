from pymongo import MongoClient
import hashlib
from bson.objectid import ObjectId


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
    client = MongoClient('localhost', 27017)
    db = client['Invario_Website']
    users = db['users']
    hashed_password = hashlib.sha512(password.encode()).hexdigest()
    user = users.find_one({'Username': username, 'Password': hashed_password})
    client.close()
    return user


def add_user(username, password, name, last_name):
    """
    Add a new user to the database.
    
    Args:
        username (str): Username for the new user
        password (str): Password for the new user
        
    Returns:
        bool: True if user was added successfully, False if password was too weak
    """
    client = MongoClient('localhost', 27017)
    db = client['Invario_Website']
    users = db['users']
    if not check_password_strength(password):
        return False
    users.insert_one({'Username': username, 'Password': hashing(password), 'Admin': False, 'active_ausleihung': None, 'name': name, 'last_name': last_name})
    client.close()
    return True


def make_admin(username):
    """
    Grant administrator privileges to a user.
    
    Args:
        username (str): Username of the user to promote
        
    Returns:
        bool: True if user was promoted successfully
    """
    client = MongoClient('localhost', 27017)
    db = client['Invario_Website']
    users = db['users']
    users.update_one({'Username': username}, {'$set': {'Admin': True}})
    client.close()
    return True

def remove_admin(username):
    """
    Remove administrator privileges from a user.
    
    Args:
        username (str): Username of the user to demote
        
    Returns:
        bool: True if user was demoted successfully
    """
    client = MongoClient('localhost', 27017)
    db = client['Invario_Website']
    users = db['users']
    users.update_one({'Username': username}, {'$set': {'Admin': False}})
    client.close()
    return True

def get_user(username):
    """
    Retrieve a specific user by username.
    
    Args:
        username (str): Username to search for
        
    Returns:
        dict: User document or None if not found
    """
    client = MongoClient('localhost', 27017)
    db = client['Invario_Website']
    users = db['users']
    users_return = users.find_one({'Username': username})
    client.close()
    return users_return


def check_admin(username):
    """
    Check if a user has administrator privileges.
    
    Args:
        username (str): Username to check
        
    Returns:
        bool: True if user is an administrator, False otherwise
    """
    client = MongoClient('localhost', 27017)
    db = client['Invario_Website']
    users = db['users']
    user = users.find_one({'Username': username})
    client.close()
    return user and user.get('Admin', False)

def delete_user(username):
    """
    Delete a user from the database.
    Administrative function for removing user accounts.
    
    Args:
        username (str): Username of the account to delete
        
    Returns:
        bool: True if user was deleted successfully, False otherwise
    """
    client = MongoClient('localhost', 27017)
    db = client['Invario_Website']
    users = db['users']
    result = users.delete_one({'username': username})
    client.close()
    if result.deleted_count == 0:
        # Try with different field name
        client = MongoClient('localhost', 27017)
        db = client['Inventarsystem']
        users = db['users']
        result = users.delete_one({'Username': username})
        client.close()
    
    return result.deleted_count > 0

def get_name(username):
    """
    Retrieve the name that is assosiated with the username.

    Returns:
        str: String of name
    """
    client = MongoClient('localhost', 27017)
    db = client['Invario_Website']
    users = db['users']
    user = users.find_one({'Username': username})
    name = user.get("name")
    return name

def get_last_name(username):
    """
    Retrieve the last_name that is assosiated with the username.

    Returns:
        str: String of last_name
    """
    client = MongoClient('localhost', 27017)
    db = client['Invario_Website']
    users = db['users']
    user = users.find_one({'Username': username})
    name = user.get("last_name")
    return name


def get_all_users():
    """
    Retrieve all users from the database.
    Administrative function for user management.
    
    Returns:
        list: List of all user documents
    """
    try:
        client = MongoClient('localhost', 27017)
        db = client['Invario_Website']
        users = db['users']
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
            
        client = MongoClient('localhost', 27017)
        db = client['Invario_Website']
        users = db['users']
        
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
        client = MongoClient('localhost', 27017)
        db = client['Invario_Website']
        users = db['users']
        
        result = users.update_one(
            {'Username': username}, 
            {'$set': {'name': name, 'last_name': last_name}}
        )
        
        client.close()
        return True
    except Exception as e:
        print(f"Error updating user name: {e}")
        return False