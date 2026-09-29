"""
================================================================================
Aviary Bulk Import Script
================================================================================

WHAT THIS SCRIPT DOES
----------------------
This script bulk-creates Resources and Media Files in an Aviary organization
via the Aviary REST API, driven by two CSV files exported from the Aviary
bulk-import template:

  1. RESOURCE CSV  (e.g. OPPL-Resources.csv)
     One row per Resource. For each row with a "Resource User Key", the
     script POSTs a new resource to /api/v1/resources, mapping these CSV
     columns into Aviary resource metadata:
         Description, Date, Agent, Coverage, Language, Identifier, Format,
         Type, Subject, Relation, Source, Publisher, Rights Statement,
         Keyword, Source Metadata URI, Preferred Citation,
         Location, Alt Date, Call Sign
     Metadata fields support Aviary's vocabulary-pair syntax so a single
     column can carry multiple entries:
         - "|" separates multiple values within one field
             e.g. Host;;Stan West|Guest;;Mamie Till Mobley
         - ";;" separates an optional "vocabulary" label from its value
             e.g. recorded;;1999-05-02  ->  vocabulary="recorded", value="1999-05-02"
     Plain-text columns (Location, Alt Date, Call Sign) go through the same
     mapping function, they just won't typically use the ";;"/"|" syntax.
     "Location" is expected in Aviary's "lat,long::zoom::place name" format,
     e.g. "41.8781,-87.6298::11::Chicago".

  2. MEDIA CSV  (e.g. OPPL-Media.csv)
     One row per Media File, linked back to its Resource via
     "Resource User Key". For each media row belonging to the resource just
     created, the script uploads the associated media (from a local file
     path, a remote URL, or an embed code) to /api/v1/media_files, and
     attaches media-level metadata mapped from these CSV columns:
         Publisher, Source, Coverage, Language, Format, Identifier,
         Relation, Subject, Rights, Description, Date, Type
     The "Display Name" column is used as the human-readable label shown in
     Aviary for the media file. If it's blank, the script falls back to the
     uploaded file's name.

  Optional sections (create_index, create_transcript, create_supplemental)
  extend the same pattern to Aviary Indexes, Transcripts, and Supplemental
  Files, each driven by its own CSV keyed on "Media User Key" /
  "Resource User Key". Each is independently optional: set its csv_path
  config variable (index_csv_path, transcript_csv_path,
  supplemental_csv_path) to enable it, or leave it as None to skip it
  entirely - the script runs fine with any combination enabled or skipped.

  3. LOG FILE
     Every run writes a log CSV (see `log_csv_path` in CONFIG) with one row
     per resource processed:
         Date, Resource User Key, Title, Media Files Imported,
         Indexes Imported, Transcripts Imported, Supplemental Files
         Imported, Success, Resource URL, Errors
     The log is written incrementally as each resource finishes (not just
     at the end), so partial progress is captured even if the script is
     interrupted or a later resource fails. "Success" reflects whether the
     resource itself was created without an API error; the counts reflect
     how many of that resource's media/index/transcript/supplemental rows
     were actually imported (a resource can succeed with 0 media if none
     matched, or partially succeed if some media rows failed).

     If an individual media file fails to upload (bad file path, network
     error, Aviary API error, etc.), that failure does NOT stop the script.
     The script logs the failure message in the "Errors" column for that
     resource's row (prefixed with "Media {Media User Key}: ...") and moves
     on to the next media row, then the next resource. Multiple errors for
     the same resource are separated by "; ". A resource-level failure -
     either the resource POST itself failing, or a malformed resource row
     (missing column, unexpected value, etc.) - is recorded the same way,
     prefixed with "Resource: ...", and does not stop the rest of the batch.

     RESUMING A RUN: the log file is no longer wiped at the start of each
     run. On startup, the script reads back any existing log and builds
     the set of Resource User Keys whose row has "Success" = True; those
     resources are skipped on this run rather than recreated. Resources
     that previously failed are NOT skipped - they're retried automatically,
     and (if they succeed this time) get a second, successful row appended
     to the same log. To force a completely fresh run instead of resuming,
     delete or rename the log CSV before running.

PERFORMANCE
-----------
The media/index/transcript/supplemental CSVs are each read from disk once,
up front, and grouped in memory by their matching key ("Resource User Key"
or "Media User Key"). Earlier versions of this script re-opened and
re-scanned these files for every resource (and, for index/transcript, for
every media item), which scales badly once you have hundreds of resources
and media rows. Grouping once up front makes each lookup an in-memory dict
lookup instead of a full file re-read.

USAGE
-----
1. Set your Aviary API token as an environment variable (don't hardcode it
   in the script):
     export AVIARY_TOKEN='your-api-token-here'

2. Update the CONFIG block below:
     - base_url        Your organization's Aviary URL, e.g. 'https://yourorg.aviaryplatform.com/'
     - collection_id    The numeric ID of the collection resources should be created in
     - folder_path      Local folder containing your CSVs and media files
     - resource_csv_path / media_csv_path   Paths to your two required CSVs
                        (relative to folder_path, or edit to an absolute path)
     - index_csv_path / transcript_csv_path / supplemental_csv_path
                        Optional. Set any of these to a path to enable that
                        import type; leave as None to skip it.

3. Make sure the CSVs match the Aviary bulk-import template column names
   listed above (extra/unused columns are fine and are ignored).

4. Install dependencies if needed:
     pip install requests validators

5. Run:
     python aviary_bulk_import.py

   The script will, for every resource row with a "Resource User Key":
     - POST the resource
     - find every media row whose "Resource User Key" matches, and POST
       each one (uploading the file/URL/embed and its metadata)
   Progress and any API errors are printed to the console as it runs, and
   a summary row is written to the log CSV for every resource (see LOG
   FILE above).

NOTES / CAVEATS
----------------
- This performs live POSTs to your Aviary organization. Test against a
  sandbox/test collection first.
- Re-running the script resumes rather than duplicates: resources already
  marked "Success" in the log are skipped (see RESUMING A RUN above).
  This is based on the log file, so don't delete/edit it between runs
  unless you intend to reprocess those resources.
- Authentication: confirm with Aviary support/docs whether your instance
  expects the token as a raw string or with a "Bearer " prefix in the
  Authorization header, and whether an "organization-id" header is also
  required for your organization - some Aviary instances need it. Add it
  to the `headers` dicts below if your requests come back unauthorized.
================================================================================
"""

import datetime
import requests
import os
import csv
import validators
import mimetypes
import re
import time
from urllib.parse import urlparse

# ==============================================================================
# CONFIG - update these for your organization / import job
# ==============================================================================
base_url = 'https://aviary.aviaryplatform.com/'
# Set your Aviary API token as an environment variable rather than hardcoding
# it here, e.g. in your terminal before running the script:
#   export AVIARY_TOKEN='your-api-token-here'
token = os.environ.get('AVIARY_TOKEN')
if not token:
    raise SystemExit(
        "AVIARY_TOKEN environment variable is not set. "
        "Run `export AVIARY_TOKEN='your-api-token-here'` before running this script."
    )
collection_id = 1
folder_path = "/Users/mycomputer/AviaryImportDirectory/"
resource_csv_path = folder_path + 'resources.csv'
media_csv_path = folder_path + 'media.csv'

# Optional CSVs - set any of these to a path to enable that import type,
# or leave as None to skip it. The script runs fine with any combination.
index_csv_path = None  # e.g. folder_path + 'indexes.csv'
transcript_csv_path = None  # e.g. folder_path + 'transcripts.csv'
supplemental_csv_path = None  # e.g. folder_path + 'supplemental.csv'
log_csv_path = folder_path + 'aviary_import_log.csv'
log_fieldnames = [
    'Date', 'Resource User Key', 'Title', 'Media Files Imported', 'Indexes Imported',
    'Transcripts Imported', 'Supplemental Files Imported', 'Success', 'Resource URL',
    'Errors',
]


def init_log():
    """
    Create the log file with a header row if it doesn't already exist.
    Unlike earlier versions, this does NOT overwrite an existing log -
    re-running the script appends to the same log rather than erasing the
    record of a previous run, which is what makes resuming possible (see
    load_completed_resource_keys()). To start completely fresh, delete or
    rename the log CSV before running.
    """
    if not os.path.exists(log_csv_path):
        with open(log_csv_path, 'w', newline='', encoding='utf-8') as log_file:
            writer = csv.DictWriter(log_file, fieldnames=log_fieldnames)
            writer.writeheader()


def load_completed_resource_keys():
    """
    Read the existing log CSV (if any) and return the set of Resource User
    Keys that already completed successfully in a previous run. Resources
    in this set are skipped by create_resources() so re-running the script
    after an interruption (or a partial failure) doesn't recreate resources
    that already succeeded. Resources that previously failed are NOT in
    this set, so they'll be retried automatically.
    """
    completed = set()
    if not os.path.exists(log_csv_path):
        return completed
    with open(log_csv_path, 'rt', newline='', encoding='utf-8') as log_file:
        reader = csv.DictReader(log_file)
        for row in reader:
            if (row.get('Success') or '').strip().lower() == 'true':
                key = (row.get('Resource User Key') or '').strip()
                if key:
                    completed.add(key)
    return completed


def write_log_row(row):
    """Append one resource's results to the log file immediately."""
    with open(log_csv_path, 'a', newline='', encoding='utf-8') as log_file:
        writer = csv.DictWriter(log_file, fieldnames=log_fieldnames)
        writer.writerow(row)


def load_grouped_csv(path, key_column):
    """
    Read a CSV once and group its rows by `key_column` (e.g. "Resource User
    Key" or "Media User Key"), so callers can look up matching rows from
    memory instead of re-opening and re-scanning the whole file for every
    resource or media item. Returns {} if `path` is falsy (used for the
    optional index/transcript/supplemental CSVs when they're disabled).

    Both column names and values are stripped of surrounding whitespace,
    matching the row-cleanup already applied elsewhere in the script.
    """
    grouped = {}
    if not path:
        return grouped
    with open(path, 'rt', encoding='utf-8-sig', errors='ignore') as f:
        reader = csv.DictReader(f)
        for row in reader:
            row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
            key = row.get(key_column, '')
            grouped.setdefault(key, []).append(row)
    return grouped


def process_resource(resource, keys, septater=";;", pair_separator="|", system_name=0):
    """
    Map one or more flat CSV columns into Aviary's metadata array format.

    Each column value may contain multiple entries separated by
    `pair_separator` ("|" by default), and each entry may optionally carry a
    "vocabulary" label separated from its value by `septater` (";;" by
    default), e.g. "Host;;Stan West|Guest;;Mamie Till Mobley". Columns with
    plain text and no separators (e.g. Alt Date, Call Sign) still work -
    they just come out as a single {'vocabulary': '', 'value': ...} entry.
    """
    data = {}
    for key in keys:
        pairs = resource[key].split(pair_separator)
        metadata = []
        for pair in pairs:
            split_text = pair.split(septater)
            if len(split_text) > 1:
                metadata.append({
                    'vocabulary': split_text[0].strip(),
                    'value': split_text[1].strip()
                })
            else:
                metadata.append({
                    'vocabulary': '',
                    'value': split_text[0].strip()
                })
        if system_name:
            data[key.lower().replace(' ', '_')] = metadata
        else:
            data[key] = metadata
    return data


def create_resources():
    init_log()

    # Resources that already succeeded in a previous run (read from the
    # existing log) are skipped so re-running the script after an
    # interruption doesn't recreate them. Previously-failed resources are
    # not in this set, so they're retried automatically.
    completed_resource_keys = load_completed_resource_keys()
    if completed_resource_keys:
        print(f"Resuming: {len(completed_resource_keys)} resource(s) already completed in a previous run will be skipped.")

    # Read the media/index/transcript/supplemental CSVs once, grouped by
    # their matching key, instead of re-scanning them for every resource /
    # media row. This matters a lot once you're dealing with hundreds of
    # resources and media rows.
    media_rows_by_resource = load_grouped_csv(media_csv_path, 'Resource User Key')
    index_rows_by_media = load_grouped_csv(index_csv_path, 'Media User Key')
    transcript_rows_by_media = load_grouped_csv(transcript_csv_path, 'Media User Key')
    supplemental_rows_by_resource = load_grouped_csv(supplemental_csv_path, 'Resource User Key')

    with open(resource_csv_path, 'rt', encoding='utf-8-sig', errors='ignore') as resource_csv_file:
        resource_csv_reader = csv.DictReader(resource_csv_file)

        url = base_url + "api/v1/resources"
        headers = {
            "Authorization": f"Bearer {token}",
        }
        for resource in resource_csv_reader:
            resource_user_key = (resource.get("Resource User Key") or "").strip()
            if resource_user_key == "":
                continue

            if resource_user_key in completed_resource_keys:
                print(f"Resource {resource_user_key} already completed - skipping")
                continue

            print(f"Resource {resource_user_key} Started")

            counts = {'media': 0, 'index': 0, 'transcript': 0, 'supplemental': 0, 'errors': []}
            success = False
            resource_url = ''
            title = resource.get("Title", "")

            # Wrap CSV field access + the resource POST together: a
            # malformed row (missing column, unexpected value, etc.) is
            # caught here and logged instead of crashing the whole batch.
            try:
                data = {
                    "resource_user_key": resource_user_key,
                    "collection_id": collection_id,
                    "title": title,
                    "access": "public" if resource["Public"] == "yes" else "restricted" if resource["Public"] == "no" else "private",
                    "is_featured": "true" if resource["Featured"] == "yes" else "false",
                    # "custom_unique_identifier": resource["Custom Unique Identifier"]
                }
                data["metadata"] = {}
                # Core descriptive metadata, plus Location / Alt Date / Call Sign
                data["metadata"] = data["metadata"] | process_resource(resource, [
                    'Description', 'Date', 'Agent', 'Coverage', 'Language', 'Identifier',
                    'Format', 'Type', 'Subject', 'Relation', 'Source', 'Publisher',
                    'Rights Statement', 'Keyword', 'Source Metadata URI',
                    'Location', 'Alt Date', 'Call Sign',
                ])
                data["metadata"] = data["metadata"] | process_resource(resource, ['Preferred Citation'], ',')

                response = requests.post(url, headers=headers, json=data)
                info = response.json()
            except Exception as e:
                print('error', str(e))
                info = {"error": str(e)}

            if isinstance(info, dict) and "error" in info:
                print('error', info["error"])
                counts['errors'].append(f"Resource: {info['error']}")
            else:
                try:
                    resource_id = info["data"]["update"]["id"]
                    resource_url = info["data"]["update"].get("url") or f"{base_url}collections/{collection_id}/collection_resources/{resource_id}"
                    success = True
                    counts = create_media(
                        resource_id, resource_user_key,
                        media_rows_by_resource, index_rows_by_media,
                        transcript_rows_by_media, supplemental_rows_by_resource,
                    )
                except (KeyError, TypeError, IndexError) as e:
                    # The response came back without an "error" key, but
                    # also didn't match the expected data > update > id
                    # shape. Log the raw response so the actual shape can
                    # be seen, rather than crashing the whole batch.
                    print('error - unexpected resource response shape:', e)
                    print('Raw response:', info)
                    counts['errors'].append(f"Resource: unexpected response shape ({e}); raw response: {info}")

            write_log_row({
                'Date': datetime.datetime.now().isoformat(timespec='seconds'),
                'Resource User Key': resource_user_key,
                'Title': title,
                'Media Files Imported': counts['media'],
                'Indexes Imported': counts['index'],
                'Transcripts Imported': counts['transcript'],
                'Supplemental Files Imported': counts['supplemental'],
                'Success': success,
                'Resource URL': resource_url,
                'Errors': '; '.join(counts.get('errors', [])),
            })

            print(f"Resource {resource_user_key} Ended")
            print(f"==============================================")
            print(f"")
    resource_csv_file.close()


# Nouman: multipart (chunked) upload settings. Files larger than
# MULTIPART_THRESHOLD are split into PART_SIZE chunks, and each chunk is PUT
# straight to Wasabi with its own presigned URL, so files over 5 GB work and
# memory use stays at about one chunk. Smaller files use a single presigned
# PUT. Aviary accepts part sizes from 5 MB to 5 GB and files up to 25 GB.
# Set MULTIPART_UPLOAD = False to always use the single-PUT upload (max 5 GB).
MULTIPART_UPLOAD = True
MULTIPART_THRESHOLD = 100 * 1024 * 1024
PART_SIZE = 100 * 1024 * 1024
PART_RETRIES = 3


def put_with_retries(url, file_path, label, offset=0, length=None):
    """Nouman: PUT bytes of file_path to a presigned URL, retrying on failure.

    Sends length bytes starting at offset, or streams the whole file from disk
    when length is None. Retried PART_RETRIES times with backoff. No
    Authorization header is sent: the URL is presigned, and sending the
    Aviary token to Wasabi would leak it.
    """
    for attempt in range(1, PART_RETRIES + 1):
        try:
            with open(file_path, 'rb') as fh:
                fh.seek(offset)
                body = fh if length is None else fh.read(length)
                resp = requests.put(url, data=body, timeout=(30, 3600))
            if 200 <= resp.status_code < 300:
                return
            error = f"HTTP {resp.status_code}: {resp.text[:300]}"
        except requests.exceptions.RequestException as e:
            error = str(e)
        if attempt == PART_RETRIES:
            raise RuntimeError(f"{label} upload failed: {error}")
        time.sleep(2 ** attempt)


def upload_parts(file_path, multipart_upload):
    """Nouman: PUT each chunk of the file to its presigned part URL.

    Part N is the bytes [(N-1) * part_size, N * part_size) of the file; the
    last part can be smaller. A failed part is retried by itself instead of
    restarting the whole file.
    """
    part_size = int(multipart_upload['part_size'])
    parts = sorted(multipart_upload['parts'], key=lambda p: int(p['part_number']))
    for part in parts:
        number = int(part['part_number'])
        put_with_retries(part['url'], file_path, f"part {number}", (number - 1) * part_size, part_size)
        print(f"part {number}/{len(parts)} uploaded")


def upload_to_presigned(file_path, url, headers, params):
    """Nouman: create the media file, upload the bytes to Wasabi, and complete.

    For files larger than MULTIPART_THRESHOLD (and MULTIPART_UPLOAD on) the
    create request also sends multipart=true, file_size and part_size. Aviary
    then returns multipart_upload (upload_id, part_size, parts_count, and one
    url per part) instead of presigned_url, and /complete is called with the
    upload_id so Aviary joins the parts. Smaller files, or a server that
    returns no multipart_upload (an Aviary release without multipart
    support), use a single PUT. Returns the create response; raises if any
    step fails (before, failures were ignored).
    """
    content_path = os.path.abspath(file_path)
    file_size = os.path.getsize(content_path)
    params = dict(params)
    if MULTIPART_UPLOAD and file_size > MULTIPART_THRESHOLD:
        params.update({'multipart': 'true', 'file_size': file_size, 'part_size': PART_SIZE})
    r = requests.post(url=url, files={"media_file": 'presigned'}, params=params, headers=headers)
    response = r.json()
    if response.get('errors') or response.get('error'):
        raise RuntimeError(f"Media create failed: {response.get('errors') or response.get('error')}")
    data = response['data']

    multipart_upload = data.get('multipart_upload')
    if multipart_upload:
        print(f"Uploading {os.path.basename(content_path)} in {multipart_upload['parts_count']} part(s)")
        upload_parts(content_path, multipart_upload)
        complete_params = {'upload_id': multipart_upload['upload_id'], 'parts_count': multipart_upload['parts_count']}
    else:
        # Single PUT (max 5 GB), streamed from disk rather than read fully
        # into memory.
        put_with_retries(data['presigned_url'], content_path, os.path.basename(content_path))
        complete_params = {}

    complete_url = f"{base_url}api/v1/media_files/{data['id']}/complete"
    complete = requests.get(complete_url, headers=headers, params=complete_params).json()
    if complete.get('errors'):
        raise RuntimeError(f"Media complete failed: {complete['errors']}")
    return r


def upload_from_path(file, url, headers, resource_id, access, display_name, filename, sort_order, is_360, thumbnail_path):

    params = {'collection_resource_id': resource_id,
              'access': access,
              'is_360': is_360,
              'media_file': 'presigned',
              'display_name': display_name,
              "thumbnail_path": thumbnail_path,
              'filename': filename,
              'sort_order': sort_order,
              }
    # Nouman: now uses the multipart presigned upload (see upload_to_presigned).
    r = upload_to_presigned(file, url, headers, params)
    return r.json()


def upload_from_link(file, url, headers, resource_id, access, display_name, filename, sort_order, is_360, thumbnail_path, metadata):
    params = {'collection_resource_id': resource_id,
              'access': access,
              'is_360': is_360,
              'display_name': display_name,
              'filename': filename,
              'sort_order': sort_order,
              "thumbnail_path": thumbnail_path,
              "media_file_link": file,
              "metadata": metadata,
              "media_file": {}
              }
    files = {}
    r = requests.post(url=url, files=files, json=params, headers=headers)
    return r.json()


def upload_from_embed(file, url, headers, resource_id, access, sort_order, is_360, source, target_domain, thumbnail_path, metadata):
    params = {'collection_resource_id': resource_id,
              'access': access,
              'is_360': is_360,
              'sort_order': sort_order,
              'target_domain': target_domain,
              "media_embed_code": file,
              "thumbnail_path": thumbnail_path,
              "media_embed_type": source,
              "metadata": metadata,
              "media_file": {}

              }
    files = {}
    r = requests.post(url=url, files=files, json=params, headers=headers)
    return r.json()


def media_meta_data_update(url, headers, metadata, media_response):
    data = {}
    data["metadata"] = metadata
    data["media_file"] = {}

    files = [

    ]
    headers = {
        "Authorization": f"Bearer {token}",
    }

    response = requests.request("PUT", url, headers=headers, json=data, files=files)
    return response.json()


def create_media(resource_id, resource_user_key, media_rows_by_resource,
                  index_rows_by_media=None, transcript_rows_by_media=None,
                  supplemental_rows_by_resource=None):
    """
    Upload every media row belonging to `resource_user_key` (looked up from
    the pre-grouped `media_rows_by_resource` dict built once in
    create_resources(), rather than re-reading the media CSV here), and
    return a counts dict used by create_resources() for the log file:
        {'media': int, 'index': int, 'transcript': int, 'supplemental': int,
         'errors': [str, ...]}
    A media row only counts as imported if its upload request came back
    without an "error" key. If a media row fails for any reason (network
    error, bad file path, Aviary API error, etc.), the failure is recorded
    in 'errors' and the loop moves on to the next media row rather than
    stopping the whole import.
    """
    counts = {'media': 0, 'index': 0, 'transcript': 0, 'supplemental': 0, 'errors': []}

    url = base_url + "api/v1/media_files"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    # Rows are already stripped/grouped by load_grouped_csv().
    for media in media_rows_by_resource.get(resource_user_key, []):
        media_key = media.get("Media User Key", "?")
        print(f"Media {resource_user_key} Started")
        try:
            # Media-level metadata mapped from the CSV
            metadata = process_resource(media, [
                'Publisher', 'Source', 'Coverage', 'Language', 'Format', 'Identifier',
                'Relation', 'Subject', 'Rights', 'Description', 'Date', 'Type',
            ], ";;", "|", 1)
            access = "true" if media["Public"] == "yes" else "false"
            sort_order = media["Sequence #"]
            is_3d = 'false' if media["360 Video"] == "no" else 'true'
            thumbnail_path = folder_path + media["Embed Source"]
            # Prefer the CSV's "Display Name" column; fall back to the
            # uploaded file's own name if it's blank.
            csv_display_name = media.get("Display Name", "").strip()
            if validators.url(media["URL"]):
                filename = os.path.basename(urlparse(media["URL"]).path)
                display_name = csv_display_name or filename
                media_response = upload_from_link(media["URL"], url, headers, resource_id, access, display_name, filename, sort_order, is_3d, thumbnail_path, metadata)
            elif media["Embed Code"]:
                if media["Embed Code"].startswith('<iframe'):
                    url_match = re.search(r'src="([^"]+)"', media["Embed Code"])
                    if url_match:
                        media["URL"] = url_match.group(1)
                else:
                    media["URL"] = media["Embed Code"]
                media_response = upload_from_embed(media["Embed Code"], url, headers, resource_id, access, sort_order, is_3d, media["Embed Source"].title(), media["Target Domain"], thumbnail_path, metadata)
            else:
                src = folder_path + media["Path"]
                filename = os.path.basename(src)
                display_name = csv_display_name or filename
                media_response = upload_from_path(src, url, headers, resource_id, access, display_name, filename, sort_order, is_3d, thumbnail_path)
                print(f"Media Metadata {resource_user_key} Started")
                metadata_url = f"{url}/{media_response['data']['id']}"
                media_meta_data_update(metadata_url, headers, metadata, media_response['data'])

            if isinstance(media_response, dict) and "error" in media_response:
                print('error', media_response["error"])
                counts['errors'].append(f"Media {media_key}: {media_response['error']}")
            else:
                counts['media'] += 1
                media_file_id = media_response["data"]["id"]
                media_user_key = media.get("Media User Key", "")

                if index_csv_path:
                    print(f"Index {resource_user_key} Started")
                    counts['index'] += create_index(resource_id, media_file_id, media_user_key, index_rows_by_media or {})
                if transcript_csv_path:
                    print(f"Transcript {resource_user_key} Started")
                    counts['transcript'] += create_transcript(resource_id, media_file_id, media_user_key, transcript_rows_by_media or {})
                if supplemental_csv_path:
                    print(f"Supplemental {resource_user_key} Started")
                    counts['supplemental'] += create_supplemental(resource_id, media_file_id, resource_user_key, supplemental_rows_by_resource or {})
        except Exception as e:
            print('error', str(e))
            counts['errors'].append(f"Media {media_key}: {e}")
            # Continue on to the next media row rather than
            # stopping the whole resource's import.
            continue

    return counts


def create_index(resource_id, media_id, media_user_key, index_rows_by_media):
    """Returns the number of index rows successfully imported for this media item."""
    if not index_csv_path:
        return 0
    count = 0
    url = base_url + "api/v1/indexes"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    for index in index_rows_by_media.get(media_user_key, []):
        data = {
            'language': index["Language"],
            'title': index["Title"],
            'is_public': "true" if index["Public"] == "yes" else "false",
            'resource_file_id': media_id,
            'description': index["Description"]
        }
        file_path = folder_path + index["Path"]
        file_name = os.path.basename(file_path)
        file_type = mimetypes.guess_type(file_path)[0]

        files = {
            'associated_file': (file_name, open(file_path, 'rb'), file_type)
        }
        response = requests.post(url, headers=headers, data=data, files=files)
        try:
            if "error" not in response.json():
                count += 1
        except ValueError:
            pass
    return count


def create_transcript(resource_id, media_id, media_user_key, transcript_rows_by_media):
    """Returns the number of transcript rows successfully imported for this media item."""
    if not transcript_csv_path:
        return 0
    count = 0
    url = base_url + "api/v1/transcripts"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    for transcript in transcript_rows_by_media.get(media_user_key, []):
        data = {
            'language': transcript["Language"],
            'title': transcript["Title"],
            'is_public': "true" if transcript["Public"] == "yes" else "false",
            'resource_file_id': media_id,
            'description': transcript["Description"],
            'is_caption': transcript["Captions"],
            'remove_title': '1' if transcript["Ignore Title"] == "yes" else "0",
        }
        file_path = folder_path + transcript["Path"]
        file_name = os.path.basename(file_path)
        file_type = mimetypes.guess_type(file_path)[0]
        files = {
            'associated_file': (file_name, open(file_path, 'rb'), file_type)
        }
        response = requests.post(url, headers=headers, data=data, files=files)
        try:
            if "error" not in response.json():
                count += 1
        except ValueError:
            pass
    return count


def create_supplemental(resource_id, media_id, resource_user_key, supplemental_rows_by_resource):
    """Returns the number of supplemental file rows successfully imported for this resource."""
    if not supplemental_csv_path:
        return 0
    count = 0
    url = base_url + "api/v1/supplemental_files"
    headers = {
        "Authorization": f"Bearer {token}",
    }

    for supplemental in supplemental_rows_by_resource.get(resource_user_key, []):
        data = {
            'title': supplemental["Title"],
            'access': 'yes' if supplemental["Public"] == "Yes" else 'no',
            'description': supplemental["Description"],
            'collection_resource_id': resource_id,
        }
        file_path = folder_path + supplemental["File Path"]
        file_name = os.path.basename(file_path)
        file_type = mimetypes.guess_type(file_path)[0]
        files = {
            'associated_file': (file_name, open(file_path, 'rb'), file_type)
        }
        response = requests.post(url, headers=headers, data=data, files=files)
        try:
            if "error" not in response.json():
                count += 1
        except ValueError:
            pass
    return count


def main():
    create_resources()


if __name__ == '__main__':
    main()
