# Airflow Connection Management - Code Examples

This document provides practical code examples demonstrating how Airflow manages connections across different components.

## Example 1: Creating and Using a Connection

### Creating a Connection Programmatically

```python
from airflow.models import Connection
from airflow.utils.session import create_session

# Create a new connection
new_conn = Connection(
    conn_id='my_postgres_db',
    conn_type='postgres',
    description='Production PostgreSQL Database',
    host='db.example.com',
    login='airflow_user',
    password='secure_password',
    schema='production',
    port=5432,
    extra='{"sslmode": "require", "sslcert": "/path/to/cert.pem"}'
)

# Save to database
with create_session() as session:
    session.add(new_conn)
    session.commit()
```

### Retrieving and Using a Connection

```python
from airflow.models import Connection

# Method 1: Get connection from secrets
conn = Connection.get_connection_from_secrets('my_postgres_db')

print(f"Host: {conn.host}")
print(f"Port: {conn.port}")
print(f"User: {conn.login}")
print(f"Password: {conn.password}")  # Automatically decrypted
print(f"Extra: {conn.extra_dejson}")  # Parsed JSON

# Method 2: Get URI representation
uri = conn.get_uri()
print(f"URI: {uri}")
# Output: postgres://airflow_user:secure_password@db.example.com:5432/production?sslmode=require&sslcert=%2Fpath%2Fto%2Fcert.pem
```

## Example 2: Using Connections with Hooks

### Basic Hook Usage

```python
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook

@task
def query_database():
    # Hook automatically retrieves connection 'my_postgres_db'
    hook = PostgresHook(postgres_conn_id='my_postgres_db')
    
    # Execute a query
    records = hook.get_records("SELECT * FROM users WHERE active = true")
    
    return records

@task
def insert_data():
    hook = PostgresHook(postgres_conn_id='my_postgres_db')
    
    # Insert data
    hook.run(
        "INSERT INTO logs (timestamp, message) VALUES (%s, %s)",
        parameters=(datetime.now(), "Task completed")
    )
```

### Custom Hook Implementation

```python
from airflow.hooks.base_hook import BaseHook
import requests

class MyAPIHook(BaseHook):
    """Hook for interacting with a custom API."""
    
    conn_name_attr = 'api_conn_id'
    default_conn_name = 'my_api_default'
    conn_type = 'my_api'
    hook_name = 'My Custom API'
    
    def __init__(self, api_conn_id='my_api_default'):
        super().__init__()
        self.api_conn_id = api_conn_id
        self._conn = None
    
    def get_conn(self):
        """Return connection object."""
        if self._conn is None:
            # Get connection from Airflow
            conn = self.get_connection(self.api_conn_id)
            
            # Parse connection details
            base_url = f"{conn.host}:{conn.port}" if conn.port else conn.host
            
            # Parse extra params
            extra = conn.extra_dejson
            api_key = extra.get('api_key')
            
            # Create session with authentication
            session = requests.Session()
            session.headers.update({
                'Authorization': f'Bearer {api_key}',
                'Content-Type': 'application/json'
            })
            
            self._conn = {
                'session': session,
                'base_url': base_url
            }
        
        return self._conn
    
    def make_request(self, endpoint, method='GET', **kwargs):
        """Make an API request."""
        conn = self.get_conn()
        session = conn['session']
        base_url = conn['base_url']
        
        url = f"{base_url}/{endpoint}"
        response = session.request(method, url, **kwargs)
        response.raise_for_status()
        
        return response.json()
    
    def test_connection(self):
        """Test the API connection."""
        try:
            # Try to make a test request
            self.make_request('health')
            return True, "Connection successful"
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
    
    @staticmethod
    def get_ui_field_behaviour():
        """Customize the connection form UI."""
        return {
            "hidden_fields": ['schema', 'port'],
            "relabeling": {
                'host': 'API Base URL',
                'login': 'Username (optional)',
            },
            "placeholders": {
                'host': 'https://api.example.com',
                'extra': '{"api_key": "your-api-key"}',
            },
        }
```

## Example 3: Provider Configuration

### Provider YAML Configuration

```yaml
# providers/mycompany/provider.yaml
package-name: airflow-providers-mycompany
name: MyCompany Services
description: |
  Integration with MyCompany internal services

state: ready
versions:
  - 1.0.0

# Define connection types
connection-types:
  - hook-class-name: airflow.providers.mycompany.hooks.api.MyAPIHook
    connection-type: my_api

# Reference hook modules
hooks:
  - integration-name: MyCompany API
    python-modules:
      - airflow.providers.mycompany.hooks.api

# Optional: Custom configuration
config:
  mycompany:
    description: Configuration for MyCompany provider
    options:
      default_timeout:
        description: Default timeout for API calls
        type: integer
        default: 30
      retry_attempts:
        description: Number of retry attempts
        type: integer
        default: 3
```

### Provider Entry Point (pyproject.toml)

```toml
[project.entry-points."apache_airflow_provider"]
provider_info = "airflow.providers.mycompany:get_provider_info"
```

### Provider Info Function

```python
# airflow/providers/mycompany/__init__.py

def get_provider_info():
    return {
        "package-name": "airflow-providers-mycompany",
        "name": "MyCompany Services",
        "description": "Integration with MyCompany internal services",
        "connection-types": [
            {
                "hook-class-name": "airflow.providers.mycompany.hooks.api.MyAPIHook",
                "connection-type": "my_api",
            }
        ],
        "hooks": [
            {
                "integration-name": "MyCompany API",
                "python-modules": ["airflow.providers.mycompany.hooks.api"],
            }
        ],
        "versions": ["1.0.0"],
    }
```

## Example 4: Custom Secrets Backend

### Implementing a Custom Secrets Backend

```python
from airflow.secrets import BaseSecretsBackend
from airflow.models import Connection
import boto3

class AWSSecretsManagerBackend(BaseSecretsBackend):
    """
    Retrieves connections from AWS Secrets Manager.
    
    Configuration in airflow.cfg:
    [secrets]
    backend = airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
    backend_kwargs = {"connections_prefix": "airflow/connections"}
    """
    
    def __init__(self, connections_prefix='airflow/connections', **kwargs):
        super().__init__(**kwargs)
        self.connections_prefix = connections_prefix
        self.client = boto3.client('secretsmanager')
    
    def get_connection(self, conn_id, team_name=None):
        """
        Get connection from AWS Secrets Manager.
        
        Secret name format: {connections_prefix}/{conn_id}
        Secret value format: Connection URI or JSON
        """
        secret_name = f"{self.connections_prefix}/{conn_id}"
        
        try:
            response = self.client.get_secret_value(SecretId=secret_name)
            secret_value = response['SecretString']
            
            # Try to parse as URI first
            if '://' in secret_value:
                return Connection(conn_id=conn_id, uri=secret_value)
            
            # Otherwise parse as JSON
            import json
            conn_dict = json.loads(secret_value)
            return Connection(conn_id=conn_id, **conn_dict)
            
        except self.client.exceptions.ResourceNotFoundException:
            return None
        except Exception as e:
            self.log.error(f"Error retrieving secret {secret_name}: {e}")
            return None
```

### Configuring Multiple Secrets Backends

```python
# airflow.cfg
[secrets]
backend = airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend
backend_kwargs = {"connections_prefix": "airflow/connections", "region_name": "us-east-1"}

# Can also configure via Python in airflow_local_settings.py
from airflow.configuration import conf

conf.set('secrets', 'backend', 'airflow.providers.amazon.aws.secrets.secrets_manager.SecretsManagerBackend')
conf.set('secrets', 'backend_kwargs', '{"connections_prefix": "airflow/connections"}')
```

## Example 5: Connection Testing

### Testing a Connection

```python
from airflow.models import Connection

def test_postgres_connection():
    """Test a PostgreSQL connection."""
    conn = Connection.get_connection_from_secrets('my_postgres_db')
    
    # Test the connection
    success, message = conn.test_connection()
    
    if success:
        print(f"✓ Connection test passed: {message}")
    else:
        print(f"✗ Connection test failed: {message}")
    
    return success

# Usage in a task
@task
def validate_connections():
    results = {}
    for conn_id in ['postgres_prod', 'postgres_staging', 'api_endpoint']:
        try:
            conn = Connection.get_connection_from_secrets(conn_id)
            success, msg = conn.test_connection()
            results[conn_id] = {'status': 'success' if success else 'failed', 'message': msg}
        except Exception as e:
            results[conn_id] = {'status': 'error', 'message': str(e)}
    
    return results
```

## Example 6: Environment Variable Connections

### Setting Connection via Environment Variable

```bash
# URI format
export AIRFLOW_CONN_MY_POSTGRES='postgresql://user:pass@localhost:5432/mydb?sslmode=require'

# JSON format (base64 encoded for special characters)
export AIRFLOW_CONN_MY_API='{"conn_type":"http","host":"api.example.com","port":443,"extra":{"api_key":"secret123"}}'
```

### Accessing Environment-Based Connections

```python
import os
from airflow.models import Connection

# Set connection via environment variable
os.environ['AIRFLOW_CONN_TEST_DB'] = 'postgresql://user:pass@localhost:5432/testdb'

# Retrieve it (automatically discovered by EnvironmentVariablesBackend)
conn = Connection.get_connection_from_secrets('test_db')
print(f"Host: {conn.host}")  # localhost
print(f"Port: {conn.port}")  # 5432
```

## Example 7: ProvidersManager Usage

### Discovering Available Connection Types

```python
from airflow.providers_manager import ProvidersManager

# Get the singleton instance
pm = ProvidersManager()

# Initialize hooks discovery
pm.initialize_providers_hooks()

# List all available connection types
print("Available connection types:")
for conn_type, hook_info in pm.hooks.items():
    if hook_info:
        print(f"  - {conn_type}: {hook_info.hook_name}")
        print(f"    Hook class: {hook_info.hook_class_name}")
        print(f"    Provider: {hook_info.package_name}")
        print(f"    Testable: {hook_info.connection_testable}")

# Get specific hook info
postgres_info = pm.hooks.get('postgres')
if postgres_info:
    print(f"\nPostgreSQL Hook Info:")
    print(f"  Class: {postgres_info.hook_class_name}")
    print(f"  Connection ID attr: {postgres_info.connection_id_attribute_name}")
```

### Getting a Hook from a Connection

```python
from airflow.models import Connection

# Create or retrieve a connection
conn = Connection(
    conn_id='my_postgres',
    conn_type='postgres',
    host='localhost',
    login='user',
    password='pass'
)

# Get the appropriate hook for this connection type
hook = conn.get_hook()

# Now you can use the hook
print(f"Hook type: {type(hook).__name__}")
print(f"Hook connection ID: {hook.postgres_conn_id}")

# Use the hook
with hook.get_conn() as db_conn:
    # db_conn is now a psycopg2 connection object
    cursor = db_conn.cursor()
    cursor.execute("SELECT version()")
    print(cursor.fetchone())
```

## Example 8: Connection URI Manipulation

### Building and Parsing Connection URIs

```python
from airflow.models import Connection
from urllib.parse import quote

# Create connection from URI
uri = "postgres://user:p@ssw0rd@db.example.com:5432/mydb?sslmode=require"
conn = Connection(conn_id='my_conn', uri=uri)

print(f"Host: {conn.host}")
print(f"Login: {conn.login}")
print(f"Password: {conn.password}")
print(f"Extra: {conn.extra_dejson}")

# Build URI from connection object
conn2 = Connection(
    conn_id='another_conn',
    conn_type='postgres',
    host='localhost',
    login='admin',
    password='secret!@#',  # Special characters are URL-encoded
    schema='analytics',
    port=5432,
    extra='{"sslmode": "prefer"}'
)

uri2 = conn2.get_uri()
print(f"Generated URI: {uri2}")
# Output: postgres://admin:secret%21%40%23@localhost:5432/analytics?sslmode=prefer
```

## Example 9: Multi-Tenancy with Team-Based Connections

### Creating Team-Specific Connections

```python
from airflow.models import Connection
from airflow.utils.session import create_session

# Create connection for team_a
team_a_conn = Connection(
    conn_id='shared_db',
    conn_type='postgres',
    host='team-a-db.example.com',
    login='team_a_user',
    password='team_a_pass',
    team_name='team_a'
)

# Create connection for team_b
team_b_conn = Connection(
    conn_id='shared_db',
    conn_type='postgres',
    host='team-b-db.example.com',
    login='team_b_user',
    password='team_b_pass',
    team_name='team_b'
)

with create_session() as session:
    session.add(team_a_conn)
    session.add(team_b_conn)
    session.commit()
```

### Accessing Team-Based Connections

```python
from airflow.decorators import task

@task
def team_a_task():
    # This task belongs to team_a
    # Will only be able to access connections with team_name='team_a' or team_name=None
    conn = Connection.get_connection_from_secrets('shared_db', team_name='team_a')
    
    # This will return team-a-db.example.com
    print(f"Using host: {conn.host}")
```

## Example 10: Comprehensive DAG Example

### Complete Example with Connection Management

```python
from datetime import datetime
from airflow import DAG
from airflow.decorators import task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.http.hooks.http import HttpHook
from airflow.models import Connection

default_args = {
    'owner': 'airflow',
    'start_date': datetime(2024, 1, 1),
}

with DAG(
    'connection_management_example',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=False,
) as dag:

    @task
    def validate_connections():
        """Validate all required connections exist and work."""
        required_connections = ['postgres_prod', 'api_endpoint', 's3_bucket']
        results = {}
        
        for conn_id in required_connections:
            try:
                conn = Connection.get_connection_from_secrets(conn_id)
                success, message = conn.test_connection()
                results[conn_id] = success
            except Exception as e:
                results[conn_id] = False
                print(f"Error testing {conn_id}: {e}")
        
        return results

    @task
    def extract_data(validation_results):
        """Extract data from PostgreSQL."""
        if not validation_results.get('postgres_prod'):
            raise ValueError("PostgreSQL connection validation failed")
        
        hook = PostgresHook(postgres_conn_id='postgres_prod')
        
        sql = """
            SELECT id, name, created_at 
            FROM customers 
            WHERE created_at >= CURRENT_DATE
        """
        
        records = hook.get_records(sql)
        return records

    @task
    def transform_data(records):
        """Transform the extracted data."""
        transformed = []
        for record in records:
            transformed.append({
                'customer_id': record[0],
                'customer_name': record[1].upper(),
                'date': record[2].isoformat()
            })
        return transformed

    @task
    def send_to_api(data, validation_results):
        """Send transformed data to API."""
        if not validation_results.get('api_endpoint'):
            raise ValueError("API connection validation failed")
        
        hook = HttpHook(http_conn_id='api_endpoint', method='POST')
        
        # Get connection to access extra params
        conn = Connection.get_connection_from_secrets('api_endpoint')
        extra = conn.extra_dejson
        api_key = extra.get('api_key')
        
        response = hook.run(
            endpoint='/customers/bulk',
            json=data,
            headers={'Authorization': f'Bearer {api_key}'}
        )
        
        return response.status_code

    # Define task dependencies
    validation = validate_connections()
    extracted = extract_data(validation)
    transformed = transform_data(extracted)
    result = send_to_api(transformed, validation)
```

## Summary

These examples demonstrate:

1. **Creating connections** programmatically, via CLI, and via environment variables
2. **Using connections** through hooks in DAG tasks
3. **Implementing custom hooks** with connection support
4. **Configuring providers** with connection types
5. **Building custom secrets backends** for external secret management
6. **Testing connections** to validate configuration
7. **Managing multi-tenant** team-based connections
8. **Discovering connection types** via ProvidersManager

The connection management system provides a flexible, secure, and extensible way to manage credentials and configuration for hundreds of different services and APIs.
