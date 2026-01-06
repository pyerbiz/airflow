# Airflow Connection Management Architecture

## Overview

Apache Airflow provides a sophisticated connection management system that allows it to manage connections for hundreds of different providers (databases, cloud services, APIs, etc.). This document explains how connections are saved, organized, and used throughout the codebase.

## Core Components

### 1. Connection Model (`airflow.models.connection.Connection`)

**Location:** `airflow-core/src/airflow/models/connection.py`

The `Connection` class is the core data model representing a connection in Airflow. It's a SQLAlchemy model that stores connection information in the metadata database.

#### Key Attributes:
- **`conn_id`** (str): Unique identifier for the connection (max 250 chars)
- **`conn_type`** (str): Type of connection (e.g., 'postgres', 'http', 's3')
- **`description`** (str): Human-readable description
- **`host`** (str): Hostname or endpoint
- **`login`** (str): Username/login credential
- **`password`** (str): Password (encrypted using Fernet)
- **`schema`** (str): Database schema or similar
- **`port`** (int): Port number
- **`extra`** (str): JSON-encoded additional parameters (encrypted)
- **`team_name`** (str): Optional team association for multi-tenant deployments
- **`is_encrypted`** (bool): Whether password is encrypted
- **`is_extra_encrypted`** (bool): Whether extra field is encrypted

#### Key Methods:

```python
# Get a connection from secrets backends
Connection.get_connection_from_secrets(conn_id: str) -> Connection

# Get the hook instance for this connection type
connection.get_hook() -> BaseHook

# Test if the connection works
connection.test_connection() -> (bool, str)

# Convert to/from various formats
connection.get_uri() -> str
connection.to_dict() -> dict
Connection.from_json(json_str) -> Connection
connection.as_json() -> str
```

#### Security Features:
- **Password Encryption**: Uses Fernet encryption (configured via `FERNET_KEY`)
- **Secret Masking**: Automatically masks passwords in logs
- **Extra Field Encryption**: Additional parameters can be encrypted
- **Key Rotation**: Supports rotating encryption keys

### 2. Secrets Backend Architecture

**Location:** `airflow-core/src/airflow/secrets/`

Airflow uses a pluggable secrets backend system to store and retrieve connections. Multiple backends can be configured in a priority chain.

#### Base Class: `BaseSecretsBackend`

All secrets backends inherit from `BaseSecretsBackend` and implement:

```python
def get_connection(self, conn_id: str, team_name: str | None = None) -> Connection | None:
    """Retrieve a connection by conn_id"""
    pass
```

#### Built-in Backends:

1. **MetastoreBackend** (`secrets/metastore.py`)
   - Stores connections in Airflow's metadata database
   - Default backend
   - Queries the `connection` table using SQLAlchemy
   - Supports team-based filtering for multi-tenant setups

2. **EnvironmentVariablesBackend** (`secrets/environment_variables.py`)
   - Reads connections from environment variables
   - Format: `AIRFLOW_CONN_{CONN_ID}=<connection_uri>`
   - Higher priority than metastore by default

3. **LocalFilesystemBackend** (`secrets/local_filesystem.py`)
   - Reads connections from JSON/YAML files
   - Useful for local development

#### External Backends (via Providers):
- AWS Secrets Manager
- Azure Key Vault
- Google Cloud Secret Manager
- HashiCorp Vault
- And many more...

#### Secret Resolution Flow:

```
1. Check SecretCache (if enabled)
2. Iterate through configured secrets backends in order:
   - Environment Variables
   - Custom backends (if configured)
   - Metastore (database)
3. Cache the result if found
4. Raise AirflowNotFoundException if not found
```

### 3. Providers Manager (`airflow.providers_manager.ProvidersManager`)

**Location:** `airflow-core/src/airflow/providers_manager.py`

The `ProvidersManager` is a singleton that discovers and manages all installed provider packages.

#### Key Responsibilities:

1. **Provider Discovery**: Scans for packages with `apache_airflow_provider` entry point
2. **Hook Registration**: Maps connection types to hook classes
3. **Connection Type Registration**: Associates connection types with providers
4. **UI Customization**: Manages connection form widgets and field behaviors

#### Important Data Structures:

```python
class ProvidersManager:
    # Maps connection_type -> HookClassProvider
    _hook_provider_dict: dict[str, HookClassProvider]
    
    # Lazy-loaded hooks (imported on demand)
    _hooks_lazy_dict: LazyDictWithCache[str, HookInfo]
    
    # Connection form customizations
    _connection_form_widgets: dict[str, ConnectionFormWidgetInfo]
    _field_behaviours: dict[str, dict]
```

#### Key Classes:

```python
@dataclass
class HookInfo:
    hook_class_name: str           # Full Python path to hook class
    connection_id_attribute_name: str  # Attribute name for conn_id
    package_name: str              # Provider package name
    hook_name: str                 # Display name
    connection_type: str           # Connection type identifier
    connection_testable: bool      # Whether test_connection is supported
```

#### Provider Discovery Process:

1. **Entry Point Loading**: 
   - Looks for `apache_airflow_provider` entry points
   - Each provider returns a dictionary matching `provider_info.schema.json`

2. **Hook Registration**:
   - Reads `connection-types` from `provider.yaml`
   - Maps connection type to hook class
   - Stores in `_hook_provider_dict`

3. **Lazy Loading**:
   - Hook classes are NOT imported during discovery
   - Only imported when first accessed via `Connection.get_hook()`

### 4. Hook Base Classes

**Location:** `airflow-core/src/airflow/hooks/base.py`

#### DiscoverableHook Protocol

Hooks that want to be automatically discovered by Airflow implement these class attributes:

```python
class PostgresHook(DbApiHook):
    conn_name_attr = "postgres_conn_id"  # Parameter name for connection ID
    default_conn_name = "postgres_default"  # Default conn_id to use
    conn_type = "postgres"  # Connection type identifier
    hook_name = "Postgres"  # Display name in UI
```

#### Optional Methods for UI Customization:

```python
@staticmethod
def get_connection_form_widgets() -> dict[str, Any]:
    """Return custom form widgets for extra connection fields"""
    return {
        "extra__postgres__sslmode": StringField("SSL Mode"),
        "extra__postgres__sslcert": StringField("SSL Certificate"),
    }

@staticmethod
def get_ui_field_behaviour() -> dict[str, Any]:
    """Customize connection form UI behavior"""
    return {
        "hidden_fields": ['port'],  # Hide certain fields
        "relabeling": {'login': 'Username'},  # Rename fields
        "placeholders": {
            'host': 'localhost',
            'login': 'postgres',
            'port': '5432',
        }
    }
```

### 5. Provider Structure

Each provider package follows a standard structure:

```
providers/{provider-name}/
├── provider.yaml          # Provider metadata and configuration
├── src/
│   └── airflow/
│       └── providers/
│           └── {provider}/
│               ├── hooks/         # Hook implementations
│               ├── operators/     # Operator implementations
│               ├── sensors/       # Sensor implementations
│               └── transfers/     # Transfer operators
└── tests/                 # Provider-specific tests
```

#### Example: `provider.yaml` for Postgres

```yaml
package-name: apache-airflow-providers-postgres
name: PostgreSQL

# Define connection types and their hooks
connection-types:
  - hook-class-name: airflow.providers.postgres.hooks.postgres.PostgresHook
    connection-type: postgres

# Reference to hook modules
hooks:
  - integration-name: PostgreSQL
    python-modules:
      - airflow.providers.postgres.hooks.postgres
```

## Connection Lifecycle

### 1. Connection Creation

Connections can be created through multiple methods:

#### Via UI:
- Navigate to Admin → Connections
- Click "+" to add new connection
- Fill in connection details
- Saved to metadata database via MetastoreBackend

#### Via CLI:
```bash
airflow connections add 'my_postgres' \
    --conn-type 'postgres' \
    --conn-host 'localhost' \
    --conn-login 'postgres' \
    --conn-password 'password' \
    --conn-port '5432'
```

#### Via Environment Variable:
```bash
export AIRFLOW_CONN_MY_POSTGRES='postgres://postgres:password@localhost:5432/mydb'
```

#### Programmatically:
```python
from airflow.models import Connection
from airflow.utils.session import create_session

conn = Connection(
    conn_id='my_postgres',
    conn_type='postgres',
    host='localhost',
    login='postgres',
    password='password',
    port=5432,
)

with create_session() as session:
    session.add(conn)
    session.commit()
```

### 2. Connection Storage

Connections are stored in the `connection` table in the Airflow metadata database:

**Database Schema:**
```sql
CREATE TABLE connection (
    id INTEGER PRIMARY KEY,
    conn_id VARCHAR(250) UNIQUE NOT NULL,
    conn_type VARCHAR(500) NOT NULL,
    description TEXT,
    host VARCHAR(500),
    schema VARCHAR(500),
    login TEXT,
    password TEXT,  -- Encrypted with Fernet
    port INTEGER,
    is_encrypted BOOLEAN DEFAULT FALSE,
    is_extra_encrypted BOOLEAN DEFAULT FALSE,
    team_name VARCHAR(50),
    extra TEXT  -- JSON-encoded, can be encrypted
);
```

### 3. Connection Retrieval

When code needs a connection:

```python
# In a Hook
class PostgresHook(DbApiHook):
    def __init__(self, postgres_conn_id='postgres_default'):
        self.postgres_conn_id = postgres_conn_id
        # Connection is retrieved lazily when needed
    
    def get_conn(self):
        conn = Connection.get_connection_from_secrets(self.postgres_conn_id)
        # Use connection parameters to create actual database connection
        return psycopg2.connect(
            host=conn.host,
            user=conn.login,
            password=conn.password,
            database=conn.schema,
            port=conn.port,
        )
```

**Retrieval Process:**

1. Call `Connection.get_connection_from_secrets(conn_id)`
2. Check `SecretCache` for cached URI
3. Iterate through secrets backends:
   - Environment variables
   - Custom backends (AWS Secrets Manager, etc.)
   - Metastore (database)
4. First backend that returns a connection wins
5. Cache the connection URI for future use
6. Return Connection object

### 4. Connection Usage via Hooks

```python
# In a DAG task
from airflow.providers.postgres.hooks.postgres import PostgresHook

def my_task():
    # Hook automatically retrieves connection
    hook = PostgresHook(postgres_conn_id='my_postgres')
    
    # Hook creates actual connection to database
    with hook.get_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM my_table")
            results = cursor.fetchall()
    
    return results
```

## Key Design Patterns

### 1. Lazy Loading

Providers and hooks are only loaded when actually needed:
- Provider metadata is loaded at startup
- Hook classes are imported only when `Connection.get_hook()` is called
- This allows Airflow to support 100+ providers without loading all dependencies

### 2. Plugin Architecture

The provider system uses Python entry points for discovery:
```python
# In provider's setup.py or pyproject.toml
entry_points={
    'apache_airflow_provider': [
        'provider_info=airflow.providers.postgres:get_provider_info'
    ]
}
```

### 3. Separation of Concerns

- **Connection Model**: Data storage and encryption
- **Secrets Backend**: Storage and retrieval mechanism
- **Providers Manager**: Discovery and registration
- **Hooks**: Usage and integration with external systems

### 4. Security by Default

- Passwords are encrypted automatically
- Secrets are masked in logs
- Support for external secret managers
- Team-based access control

## Advanced Features

### 1. Multi-Tenancy Support

Connections can be associated with teams:
```python
conn = Connection(
    conn_id='team_db',
    conn_type='postgres',
    team_name='team_a',
    ...
)
```

Tasks belonging to `team_a` can only access connections with `team_name='team_a'` or `team_name=None`.

### 2. Connection Testing

The `test_connection()` method allows testing connections:
```python
status, message = connection.test_connection()
if status:
    print(f"Connection successful: {message}")
else:
    print(f"Connection failed: {message}")
```

Hooks can implement a `test_connection()` method to provide custom testing logic.

### 3. Custom Connection Fields

Providers can define custom fields in the connection form:

```python
class MyCustomHook(BaseHook):
    @staticmethod
    def get_connection_form_widgets():
        from wtforms import StringField
        return {
            'extra__myservice__api_version': StringField('API Version'),
            'extra__myservice__timeout': IntegerField('Timeout'),
        }
```

These fields are stored in the `extra` JSON field with the prefix `extra__<conn_type>__`.

### 4. URI Format

Connections can be represented as URIs:
```
postgres://user:password@localhost:5432/mydb?sslmode=require
```

Format: `{conn_type}://[{login}[:{password}]@]{host}[:{port}][/{schema}][?{extra_params}]`

## Summary

Airflow's connection management system is built on several key principles:

1. **Centralized Storage**: All connections stored in metadata DB or external secret managers
2. **Type Safety**: Strong typing via connection types and provider registration  
3. **Security**: Encryption, masking, and external secret manager support
4. **Extensibility**: Plugin architecture allows unlimited provider types
5. **Lazy Loading**: Performance optimization through on-demand loading
6. **Testability**: Built-in connection testing capabilities

The system elegantly handles hundreds of different provider types while maintaining clean separation of concerns, security, and performance.
