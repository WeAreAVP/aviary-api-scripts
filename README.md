# aviary-api-scripts

This repository contains a collection of scripts for interacting with the [Aviary Platform](https://aviaryplatform.com) via its public API. These scripts are designed to help external users import and export audiovisual assets and metadata to and from Aviary efficiently and securely.

## About Aviary

[Aviary](https://aviaryplatform.com) is a platform that allows libraries, archives, museums, and other cultural heritage organizations to manage, describe, and provide time-based access to their audiovisual materials. Aviary makes content discoverable through transcription, indexing, and search tools—all within a user-friendly, browser-based interface.

## Purpose of This Repository

This repository provides example and utility scripts that demonstrate how to:
- Import media files and metadata into Aviary collections
- Export metadata and asset information from Aviary
- Automate common workflows using the Aviary API

The scripts are written in Python and use the [Aviary RESTful API](https://www.aviaryplatform.com/api/v1/documentation).

## Getting Started

### Prerequisites

- Python 3.7+
- An Aviary account with API access
- Your organization’s Aviary base URL (e.g., `https://yourorganization.aviaryplatform.com`)
- An Aviary API key

### Configuration

Before running a script, you will typically need to update the following:
- `base_url`: Your organization’s Aviary instance URL
- `token`: Your Aviary API key
- Input/output paths or CSV file locations as needed

Each script includes inline comments to guide configuration.

## Example Scripts

- `Aviary Full Package Import` – Upload complete Aviary packages, including resources, media files, indexes, transcripts, and supplemental files to an existing collection. The process replicates the normal Aviary Package Import process available with the Aviary web user interface (without requiring the user to zip the package and upload it). [See more information about the Aviary Package Import here.](https://coda.aviaryplatform.com/bulk-importing-248)  
- `Media Files Import` – Upload media files to attach to existing resources.
- `Transcript Download` – Batch export and download all formats of transcripts for media files listed on a CSV.

📌 See individual script files for usage instructions.

## Documentation

You can explore the Aviary API documentation and try requests using the live demo at:  
🔗 [https://www.aviaryplatform.com/api/v1/documentation](https://www.aviaryplatform.com/api/v1/documentation)

## License

This repository is provided under the MIT License. See [LICENSE](./LICENSE) for details.

## Support

For issues related to Aviary accounts, configuration, or permissions, please contact [Aviary support](https://www.aviaryplatform.com/contact).
