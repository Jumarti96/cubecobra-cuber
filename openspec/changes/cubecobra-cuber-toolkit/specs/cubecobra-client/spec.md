## ADDED Requirements

### Requirement: Fetch public cube data from CubeCobra
The system SHALL download cube data from CubeCobra public endpoints without authentication. Fetch SHALL try formats in priority order: JSON → CSV → plaintext. On success, the system SHALL write `cubes/{short-id}/raw.csv` and `cubes/{short-id}/meta.json`.

#### Scenario: Successful fetch by short ID
- **WHEN** the user runs `python -m cuber fetch obc`
- **THEN** the system fetches `https://cubecobra.com/cube/download/csv/obc`, writes `cubes/obc/raw.csv` with all 19 columns, writes `cubes/obc/meta.json` with `{ short_id, cube_id, title, url, fetched_at }`, and prints a confirmation with card count

#### Scenario: Short ID not found
- **WHEN** the user provides a short ID that does not exist on CubeCobra
- **THEN** the system returns HTTP 404, prints a clear error message, and exits with a non-zero code without creating any files

### Requirement: Handle CubeCobra 403 responses
The system SHALL set a browser-like `User-Agent` header on all requests. If a 403 is still received, the system SHALL fall back to invoking `curl` with the same header as a subprocess.

#### Scenario: Default Python UA blocked
- **WHEN** CubeCobra returns HTTP 403 to the initial request
- **THEN** the system retries using `curl` with `User-Agent: Mozilla/5.0 (compatible; CubeCobraClient/1.0)` and succeeds if the response is 200

#### Scenario: Both attempts blocked
- **WHEN** both the httpx request and the curl fallback return 403
- **THEN** the system prints an actionable error message suggesting the cube may be private or the URL may have changed, and exits with a non-zero code

### Requirement: Store cube metadata
The system SHALL write `meta.json` alongside `raw.csv` containing the short ID, CubeCobra UUID, cube title, source URL, and ISO 8601 fetch timestamp.

#### Scenario: meta.json written on fetch
- **WHEN** fetch completes successfully
- **THEN** `cubes/{short-id}/meta.json` contains valid JSON with keys: `short_id`, `cube_id`, `title`, `url`, `fetched_at`

### Requirement: CSV column validation
The system SHALL validate that the downloaded CSV contains the expected 19 columns. If columns differ, the system SHALL warn and write a `schema_warning` field to `meta.json`.

#### Scenario: Unexpected CSV schema
- **WHEN** CubeCobra returns a CSV with different column headers than the expected 19
- **THEN** the system still saves the file, prints a warning listing the mismatched columns, and sets `meta.json.schema_warning` to `true`
