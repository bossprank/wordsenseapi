# MCP Server Setup Guide (GitHub, Brave Search, Context7)

This guide explains how to set up and run the MCP servers for GitHub, Brave Search, and Context7, based on the configuration observed for Cline.

## Prerequisites

*   **Node.js and npm/npx:** Ensure you have Node.js installed, which includes npm and npx. You can download it from [https://nodejs.org/](https://nodejs.org/).

## Server Setup Instructions

You will need to run each server in a separate terminal or manage them using a process manager. The primary method observed involves providing API keys directly as environment variables when launching the servers.

### 1. GitHub MCP Server

*   **Purpose:** Provides tools for interacting with GitHub repositories (creating issues, searching code, etc.).
*   **Command:**
    ```bash
    npx -y @modelcontextprotocol/server-github
    ```
*   **Required Environment Variable:**
    *   `GITHUB_PERSONAL_ACCESS_TOKEN`: Your GitHub Personal Access Token (PAT).
*   **Obtaining the Token:**
    *   Create a PAT from your GitHub Developer settings: [https://github.com/settings/tokens](https://github.com/settings/tokens)
    *   Ensure the token has the necessary scopes (e.g., `repo`, `read:user`, `gist`) depending on the tools you intend to use.
*   **Running the Server:**
    *   Replace `YOUR_GITHUB_PAT_HERE` with your actual token.
    *   **Method 1 (Direct Export):**
        ```bash
        export GITHUB_PERSONAL_ACCESS_TOKEN="YOUR_GITHUB_PAT_HERE"
        npx -y @modelcontextprotocol/server-github
        ```
    *   **Method 2 (Inline Variable):**
        ```bash
        GITHUB_PERSONAL_ACCESS_TOKEN="YOUR_GITHUB_PAT_HERE" npx -y @modelcontextprotocol/server-github
        ```
    *   **Method 3 (Using `.env` file):** Create a `.env` file in the directory where you run the command:
        ```dotenv
        GITHUB_PERSONAL_ACCESS_TOKEN="YOUR_GITHUB_PAT_HERE"
        ```
        Then use a tool like `dotenv-cli` (install with `npm install -g dotenv-cli`):
        ```bash
        dotenv npx -y @modelcontextprotocol/server-github
        ```

### 2. Brave Search MCP Server

*   **Purpose:** Provides tools for performing web and local searches using the Brave Search API.
*   **Command:**
    ```bash
    npx -y @modelcontextprotocol/server-brave-search
    ```
*   **Required Environment Variable:**
    *   `BRAVE_API_KEY`: Your Brave Search API Key.
*   **Obtaining the Key:**
    *   Sign up for the Brave Search API at [https://brave.com/search/api/](https://brave.com/search/api/) to get your key.
*   **Running the Server:**
    *   Replace `YOUR_BRAVE_API_KEY_HERE` with your actual key.
    *   **Method 1 (Direct Export):**
        ```bash
        export BRAVE_API_KEY="YOUR_BRAVE_API_KEY_HERE"
        npx -y @modelcontextprotocol/server-brave-search
        ```
    *   **Method 2 (Inline Variable):**
        ```bash
        BRAVE_API_KEY="YOUR_BRAVE_API_KEY_HERE" npx -y @modelcontextprotocol/server-brave-search
        ```
    *   **Method 3 (Using `.env` file):** Add to your `.env` file:
        ```dotenv
        BRAVE_API_KEY="YOUR_BRAVE_API_KEY_HERE"
        ```
        Then run with `dotenv`:
        ```bash
        dotenv npx -y @modelcontextprotocol/server-brave-search
        ```

### 3. Context7 (Upstash) MCP Server

*   **Purpose:** Provides tools for fetching documentation and resolving library IDs via Context7/Upstash.
*   **Command:**
    ```bash
    npx -y @upstash/context7-mcp@latest
    ```
*   **Required Environment Variable:**
    *   None explicitly required by the observed configuration for basic startup. However, specific tools *within* the server might require authentication (e.g., Upstash API keys) depending on usage. These might need to be set as general environment variables if required by the underlying `@upstash/context7-mcp` package. Consult its documentation if you encounter authentication issues.
*   **Running the Server:**
    ```bash
    npx -y @upstash/context7-mcp@latest
    ```

## Important Note on Configuration Methods

While analyzing the original workspace, a script (`scripts/start-brave-mcp.sh`) was found that attempted to fetch the `BRAVE_API_KEY` from Google Cloud Secret Manager as a fallback. However, the active configuration used by Cline involved setting the `BRAVE_API_KEY` and `GITHUB_PERSONAL_ACCESS_TOKEN` directly as environment variables (as detailed above).

This guide follows the direct environment variable method, as it's simpler and reflects the primary configuration observed. Using a secret manager is a valid alternative, especially in production environments, but requires additional setup (installing/configuring `gcloud`, granting permissions, etc.) not covered here.
