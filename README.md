```markdown
# Talk to My Data

## Project Overview
**Talk to My Data** is an LLM-driven framework that allows users to interact with Snowflake databases through natural language queries. By leveraging advanced large language models (LLM) and connecting seamlessly with Snowflake, this project facilitates intuitive database interactions, generating SQL queries on-the-fly and returning structured responses.

## Features
- **Dynamic Query Generation**: Automatically translates natural language into SQL queries, enabling user-friendly database interactions.
- **Snowflake Integration**: Establishes a robust connection with Snowflake for executing queries and retrieving results.
- **Environment Configuration**: Utilizes environment variables and configuration files for flexible deployment settings.
- **Utility Functions**: Contains supportive utilities for configuration management and query generation.

## Architecture Summary
The project consists of several components:

- **`src/main_app.py`**: The primary application file which orchestrates user input, query generation, and result retrieval.
- **`src/db_connector.py`**: Manages connections and interactions with the Snowflake database, facilitating seamless data retrieval and storage.
- **`src/llm_agent.py`**: Handles the integration with the large language model, converting user queries into SQL commands.
- **`utils/`**: Contains helper functions and scripts for various tasks such as loading configurations and generating data structures.
- **`configs/`**: Houses configuration files for application settings, including YAML and environment variable configurations.
- **`scripts/`**: A collection of scripts, including PowerShell scripts for running the application locally.
- **`.github/workflows`**: Contains workflow configurations for automated CI/CD processes.

## Folder Structure Explanation
The structure of the repository is as follows:

```
📁 Project Folder Structure
.
├── .gitignore                # Specifies intentionally untracked files to ignore
├── .vscode                   # Visual Studio Code configuration files
│   ├── settings.json         # VS Code workspace settings
│   └── tasks.json            # Task configurations for VS Code
├── README.md                 # Project documentation
├── bundle.yaml               # Configuration for environmental management
├── configs                   # Configuration files
│   └── settings.yaml         # YAML file for app configuration
├── folder_structure.txt       # Documentation of folder structure
├── requirements.txt          # Dependencies required for the project
├── sandbox                   # A scratch area for experimentation
│   ├── test_connection.py     # Test script to validate database connection
│   ├── test_db.py             # Tests interacting with the database
│   ├── test_langchain.py      # Tests related to LangChain integration
│   ├── test_sql.ipynb         # Jupyter notebook for SQL live testing
│   └── test_sql_generation.py  # Tests for SQL query generation
├── scripts                   # Local execution scripts
│   └── run_local.ps1         # PowerShell script to run the application locally
├── src                       # Source code for the application
│   ├── db_connector.py       # Database connection logic
│   ├── llm_agent.py          # LLM query handling
│   └── main_app.py           # Main application logic
└── utils                     # Utility functions
    ├── config_loader.py      # Loads configuration files
    ├── generate_tree.py      # Generates hierarchical data structures
    └── helper.py             # Contains miscellaneous helper functions
```

## Setup Instructions

### Prerequisites
- **Python Version**: This project requires Python 3.7 or later.

### Setting Up the Environment
1. **Create a Virtual Environment**:
    ```bash
    python -m venv venv
    ```

2. **Activate the Virtual Environment**:
   - On Windows:
     ```powershell
     .\venv\Scripts\Activate
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

3. **Install Dependencies**:
   Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**:
   Create a file named `dev.env` in the `configs` directory and set the following environment variables:
   ```env
   SNOWFLAKE_ACCOUNT=your_account
   SNOWFLAKE_USER=your_user
   SNOWFLAKE_PASSWORD=your_password
   SNOWFLAKE_ROLE=your_role
   SNOWFLAKE_DATABASE=your_db
   SNOWFLAKE_SCHEMA=public
   SNOWFLAKE_WAREHOUSE=your_wh
   OPENAI_API_KEY=your_api_key
   ```

### Running the Application
You can run the application using Python. Make sure your virtual environment is activated, and execute the following command:
```bash
python src/main_app.py
```
Alternatively, use the PowerShell script for local execution:
```powershell
.\scripts\run_local.ps1
```

## Description of `configs/`
- **`settings.yaml`**: This file contains application-specific configuration settings that guide the behavior of the application.
- **`dev.env` variables**: These are essential environment variables needed for connecting to Snowflake and the OpenAI API, ensuring secure credential handling.

## Description of `utils/`
- **`config_loader.py`**: A utility for loading configuration settings from the `settings.yaml` and environment variables to be used throughout the application.
- **`generate_tree.py`**: Generates hierarchical representations of data structures, facilitating easier navigation and querying.
- **`helper.py`**: Contains various helper functions to reduce code duplication and improve code organization.

## Description of `sandbox/`
The `sandbox` directory serves as a scratch area for experiments and testing new ideas. It contains scripts for testing database connections, language model interactions, and SQL generation. It is not intended for production tests.

## Example Usage
You may use the application to interact with your Snowflake database via natural language queries. Here’s an example:

1. Launch the application and input the query:
   ```
   "Show me the total sales by region for the last quarter."
   ```

2. The application will translate this query into SQL and execute it against your Snowflake database, returning structured results.

## Contribution Guidelines
Contributions are welcome! To contribute:
1. Fork the repository.
2. Create a new branch (`git checkout -b feature-branch`).
3. Make your changes and commit them (`git commit -m 'Add new feature'`).
4. Push to the branch (`git push origin feature-branch`).
5. Open a Pull Request.

## License
Please check the repository for license details. If none exists, please consider adding one.
```
