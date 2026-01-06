# Airflow Connection Management - Class Relationships

This document describes the key classes and their relationships in Airflow's connection management system.

## Class Hierarchy and Relationships

### 1. Core Connection Classes

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Connection                                   │
│  (airflow.models.connection.Connection)                             │
├─────────────────────────────────────────────────────────────────────┤
│ Attributes:                                                          │
│  - id: int (primary key)                                            │
│  - conn_id: str (unique, max 250 chars)                             │
│  - conn_type: str (e.g., 'postgres', 'http')                       │
│  - description: str | None                                           │
│  - host: str | None                                                  │
│  - schema: str | None                                                │
│  - login: str | None                                                 │
│  - _password: str | None (encrypted)                                │
│  - port: int | None                                                  │
│  - is_encrypted: bool                                                │
│  - is_extra_encrypted: bool                                          │
│  - team_name: str | None                                             │
│  - _extra: str | None (JSON, encrypted)                             │
├─────────────────────────────────────────────────────────────────────┤
│ Methods:                                                             │
│  + get_connection_from_secrets(conn_id) -> Connection               │
│  + get_hook() -> BaseHook                                            │
│  + test_connection() -> (bool, str)                                  │
│  + get_uri() -> str                                                  │
│  + to_dict() -> dict                                                 │
│  + from_json(json_str) -> Connection                                 │
│  + as_json() -> str                                                  │
│  - _parse_from_uri(uri: str)                                        │
│  - _validate_extra(extra, conn_id)                                  │
└─────────────────────────────────────────────────────────────────────┘
         │
         │ inherits from
         ▼
    ┌─────────┐      ┌──────────────────┐
    │  Base   │      │  LoggingMixin    │
    │(SQLAlchemy)    │  (Airflow)       │
    └─────────┘      └──────────────────┘
```

### 2. Secrets Backend Architecture

```
                    ┌──────────────────────────────┐
                    │   BaseSecretsBackend         │
                    │  (Abstract Base Class)       │
                    ├──────────────────────────────┤
                    │ Methods:                     │
                    │  + get_connection()          │
                    │  + get_variable()            │
                    └──────────────────────────────┘
                               △
                               │ implements
          ┌────────────────────┼────────────────────┐
          │                    │                    │
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ MetastoreBackend│  │EnvironmentVars   │  │LocalFilesystem   │
│                 │  │ Backend          │  │Backend           │
├─────────────────┤  ├──────────────────┤  ├──────────────────┤
│ get_connection()│  │ get_connection() │  │ get_connection() │
│   - Queries DB  │  │   - Reads env    │  │   - Reads files  │
│   - Supports    │  │     vars         │  │                  │
│     teams       │  │   - Format:      │  │                  │
│                 │  │     AIRFLOW_CONN │  │                  │
└─────────────────┘  └──────────────────┘  └──────────────────┘

External Backends (via Providers):
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ AWSSecrets       │  │ AzureKeyVault    │  │ GCPSecretManager │
│ ManagerBackend   │  │ Backend          │  │ Backend          │
└──────────────────┘  └──────────────────┘  └──────────────────┘
```

### 3. Providers Manager and Hook System

```
┌────────────────────────────────────────────────────────────────────┐
│                     ProvidersManager                                │
│                     (Singleton)                                     │
├────────────────────────────────────────────────────────────────────┤
│ Attributes:                                                         │
│  - _provider_dict: dict[str, ProviderInfo]                         │
│  - _hook_provider_dict: dict[str, HookClassProvider]               │
│  - _hooks_lazy_dict: LazyDictWithCache[str, HookInfo]              │
│  - _connection_form_widgets: dict[str, ConnectionFormWidgetInfo]   │
│  - _field_behaviours: dict[str, dict]                              │
├────────────────────────────────────────────────────────────────────┤
│ Methods:                                                            │
│  + initialize_providers_list()                                      │
│  + initialize_providers_hooks()                                     │
│  - _discover_hooks()                                               │
│  - _import_hook()                                                  │
└────────────────────────────────────────────────────────────────────┘
         │
         │ discovers and registers
         ▼
┌────────────────────────────────────────────────────────────────────┐
│                         Provider Package                            │
│                    (Entry Point Discovery)                          │
├────────────────────────────────────────────────────────────────────┤
│  provider.yaml:                                                     │
│    - package-name                                                   │
│    - connection-types[]                                             │
│      - hook-class-name                                              │
│      - connection-type                                              │
│                                                                     │
│  Python entry point:                                                │
│    [apache_airflow_provider]                                        │
│    provider_info = pkg:get_provider_info                            │
└────────────────────────────────────────────────────────────────────┘
         │
         │ contains
         ▼
┌────────────────────────────────────────────────────────────────────┐
│                      Hook Implementation                            │
│                    (e.g., PostgresHook)                             │
├────────────────────────────────────────────────────────────────────┤
│ Class Attributes:                                                   │
│  - conn_name_attr: str                                              │
│  - default_conn_name: str                                           │
│  - conn_type: str                                                   │
│  - hook_name: str                                                   │
├────────────────────────────────────────────────────────────────────┤
│ Methods:                                                            │
│  + __init__(conn_id)                                                │
│  + get_conn() -> ActualConnection                                   │
│  + test_connection() -> (bool, str)                                 │
│  + get_connection_form_widgets() -> dict [static]                   │
│  + get_ui_field_behaviour() -> dict [static]                        │
└────────────────────────────────────────────────────────────────────┘
```

### 4. Hook Class Hierarchy

```
                    ┌──────────────────────┐
                    │   BaseHook           │
                    │  (SDK Protocol)      │
                    ├──────────────────────┤
                    │  + get_connection()  │
                    │  + get_connections() │
                    └──────────────────────┘
                               △
                               │ inherits
                ┌──────────────┴──────────────┐
                │                             │
      ┌──────────────────┐          ┌─────────────────┐
      │   DbApiHook      │          │   HttpHook      │
      │  (SQL databases) │          │  (REST APIs)    │
      ├──────────────────┤          ├─────────────────┤
      │ + get_conn()     │          │ + run()         │
      │ + get_records()  │          │ + check()       │
      │ + run()          │          └─────────────────┘
      │ + get_pandas_df()│
      └──────────────────┘
               △
               │ inherits
               │
    ┌──────────┴──────────┬──────────────────┐
    │                     │                  │
┌─────────┐      ┌─────────────┐    ┌──────────────┐
│Postgres │      │   MySql     │    │   Snowflake  │
│ Hook    │      │   Hook      │    │   Hook       │
└─────────┘      └─────────────┘    └──────────────┘
```

### 5. Data Structures

#### HookInfo (NamedTuple)

```
┌────────────────────────────────────────┐
│            HookInfo                    │
├────────────────────────────────────────┤
│ - hook_class_name: str                 │
│   (Full path: airflow.providers...)    │
│ - connection_id_attribute_name: str    │
│   (Parameter name for conn_id)         │
│ - package_name: str                    │
│   (Provider package name)              │
│ - hook_name: str                       │
│   (Display name)                       │
│ - connection_type: str                 │
│   (Connection type identifier)         │
│ - connection_testable: bool            │
│   (Supports test_connection)           │
└────────────────────────────────────────┘
```

#### HookClassProvider (NamedTuple)

```
┌────────────────────────────────────────┐
│        HookClassProvider               │
├────────────────────────────────────────┤
│ - hook_class_name: str                 │
│ - package_name: str                    │
└────────────────────────────────────────┘
```

#### ConnectionFormWidgetInfo (NamedTuple)

```
┌────────────────────────────────────────┐
│    ConnectionFormWidgetInfo            │
├────────────────────────────────────────┤
│ - hook_class_name: str                 │
│ - package_name: str                    │
│ - field: wtforms.Field                 │
│ - field_name: str                      │
│ - is_sensitive: bool                   │
└────────────────────────────────────────┘
```

### 6. Connection Retrieval Flow

```
┌─────────────┐
│   Task/DAG  │
│  (requests  │
│ connection) │
└──────┬──────┘
       │
       ▼
┌────────────────────────────────────┐
│ Connection.get_connection_from_    │
│ secrets(conn_id)                   │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│      SecretCache.get()             │
│   (Check if cached)                │
└────────────┬───────────────────────┘
             │ Cache miss
             ▼
┌────────────────────────────────────┐
│  Iterate Secrets Backends:         │
│                                    │
│  1. EnvironmentVariablesBackend    │
│     ├─ Check AIRFLOW_CONN_{ID}    │
│     └─ Return if found             │
│                                    │
│  2. Custom Backends (if configured)│
│     ├─ AWS Secrets Manager         │
│     ├─ Azure Key Vault             │
│     └─ Return if found             │
│                                    │
│  3. MetastoreBackend               │
│     ├─ Query database              │
│     ├─ Filter by team_name         │
│     └─ Return if found             │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│   Connection object found          │
│   - Decrypt password               │
│   - Decrypt extra                  │
│   - Mask secrets in logs           │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│  SecretCache.save()                │
│  (Cache for future use)            │
└────────────┬───────────────────────┘
             │
             ▼
┌────────────────────────────────────┐
│   Return Connection to caller      │
└────────────────────────────────────┘
```

### 7. Hook Instantiation Flow

```
┌─────────────────────────────┐
│  connection.get_hook()      │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  ProvidersManager.hooks[conn_type]  │
│  (Lookup hook by connection type)   │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Lazy load hook class               │
│  - Import hook module               │
│  - Get hook class                   │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Instantiate hook                   │
│  hook_class(                        │
│    {conn_id_attr}: self.conn_id,    │
│    **hook_params                    │
│  )                                  │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Hook instance ready                │
│  - hook.get_conn() available        │
│  - hook.test_connection() available │
└─────────────────────────────────────┘
```

### 8. Provider Discovery Flow

```
┌─────────────────────────────────────┐
│  Airflow starts                     │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  ProvidersManager.__init__()        │
│  (Singleton initialization)         │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Scan Python entry points:          │
│  entry_points("apache_airflow_      │
│               provider")            │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  For each provider found:           │
│  1. Load entry point                │
│  2. Get provider_info dict          │
│  3. Validate against schema         │
│  4. Store in _provider_dict         │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  initialize_providers_hooks()       │
│  (Lazy initialization on first use) │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  For each provider:                 │
│  1. Parse connection-types          │
│  2. Register in _hook_provider_dict │
│  3. Create lazy loader in           │
│     _hooks_lazy_dict                │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Providers ready                    │
│  - Hooks registered by conn_type    │
│  - Lazy loading configured          │
│  - UI customizations loaded         │
└─────────────────────────────────────┘
```

## Key Relationships

### Connection → Hook
- Connection stores `conn_type` (e.g., 'postgres')
- ProvidersManager maps `conn_type` → Hook class
- `connection.get_hook()` instantiates the appropriate hook

### Hook → Connection
- Hook has `conn_name_attr` (e.g., 'postgres_conn_id')
- Hook constructor accepts `conn_id` parameter
- Hook calls `BaseHook.get_connection(conn_id)` to retrieve connection

### ProvidersManager → Provider Packages
- ProvidersManager scans entry points
- Discovers all installed providers
- Registers connection types and hooks
- Lazy loads hook classes on demand

### Secrets Backend → Connection
- Multiple backends in priority chain
- Each backend can return Connection object
- First backend to return a connection wins
- Result is cached for performance

### Connection → Database
- SQLAlchemy model mapped to `connection` table
- MetastoreBackend queries this table
- Fernet encryption for sensitive fields
- Team-based filtering support

## Data Flow Summary

1. **Registration**: Providers register connection types via entry points
2. **Storage**: Connections stored in database, environment, or external secrets
3. **Retrieval**: Secrets backends chain to find connections
4. **Instantiation**: Hooks created from connection information
5. **Usage**: Tasks use hooks to interact with external systems

## Thread Safety and Caching

- **ProvidersManager**: Singleton, thread-safe initialization
- **SecretCache**: In-memory cache with expiration
- **LazyDictWithCache**: Deferred loading with memoization
- **Connection Pooling**: Managed by individual hooks (e.g., SQLAlchemy pools)

This architecture allows Airflow to support hundreds of providers while:
- Minimizing startup time (lazy loading)
- Maintaining security (encryption, masking)
- Ensuring flexibility (pluggable backends)
- Providing scalability (caching, pooling)
