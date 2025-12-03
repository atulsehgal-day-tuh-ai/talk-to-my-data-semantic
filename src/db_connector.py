import os
import snowflake.connector

def get_db_connection():
    """
    Establishes and returns a connection to Snowflake using 
    environment variables loaded by utils.config_loader.
    """
    try:
        # Fetch variables (fail loudly if missing to aid debugging)
        user = os.environ["SNOWFLAKE_USER"]
        password = os.environ["SNOWFLAKE_PASSWORD"]
        account = os.environ["SNOWFLAKE_ACCOUNT"]
        warehouse = os.environ["SNOWFLAKE_WAREHOUSE"]
        database = os.environ["SNOWFLAKE_DB"]
        schema = os.environ["SNOWFLAKE_SCHEMA"]
        role = os.environ.get("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
        authenticator = os.environ.get("SNOWFLAKE_AUTHENTICATOR", "snowflake")

        # Create connection
        conn = snowflake.connector.connect(
            user=user,
            password=password,
            account=account,
            warehouse=warehouse,
            database=database,
            schema=schema,
            role=role,
            authenticator=authenticator
        )
        return conn

    except KeyError as e:
        raise EnvironmentError(f"Missing required environment variable: {e}")
    except Exception as e:
        raise ConnectionError(f"Failed to connect to Snowflake: {e}")