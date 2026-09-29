######################################
# Steps to Run the Script
# 1 - Update base_url to your organization url in line # 18
# 2 - Update email to your user email in line # 21
# 3 - Update password for your email in line # 22
# 4 - Update resource_id for which you want to upload a media file in line # 76
# 5 - Update path of file which you want to upload a in line # 86
# 6 - Update params info according to your media file requirement from  line # 29 to line # 38
import datetime
from time import asctime
import requests
import os
import csv
import validators

import mimetypes
import threading
import math
import time

base_url = 'https://weareavp.aviaryplatform.com/'
token = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

def write_in_terminal(message):
    print(asctime() + ":Log - " + message)

# Nouman: multipart (chunked) upload settings. Local files are split into
# PART_SIZE chunks, and each chunk is PUT straight to Wasabi with its own
# presigned URL, so files over 5 GB work and memory use stays at about one
# chunk. Aviary accepts part sizes from 5 MB to 5 GB and files up to 25 GB.
# Set MULTIPART_UPLOAD = False to use the old single-PUT upload.
MULTIPART_UPLOAD = True
PART_SIZE = 100 * 1024 * 1024
PART_RETRIES = 3


def upload_parts(file_path, multipart_upload):
    """Nouman: PUT each chunk of the file to its presigned part URL.

    Part N is the bytes [(N-1) * part_size, N * part_size) of the file; the
    last part can be smaller. A failed part is retried by itself
    (PART_RETRIES times) instead of restarting the whole file. No
    Authorization header is sent: the part URLs are presigned, and sending
    the Aviary token to Wasabi would leak it.
    """
    part_size = int(multipart_upload['part_size'])
    parts = sorted(multipart_upload['parts'], key=lambda p: int(p['part_number']))
    with open(os.path.abspath(file_path), 'rb') as fh:
        for part in parts:
            number = int(part['part_number'])
            for attempt in range(1, PART_RETRIES + 1):
                fh.seek((number - 1) * part_size)
                try:
                    resp = requests.put(part['url'], data=fh.read(part_size), timeout=(30, 3600))
                    if 200 <= resp.status_code < 300:
                        break
                    error = f"HTTP {resp.status_code}: {resp.text[:300]}"
                except requests.exceptions.RequestException as e:
                    error = str(e)
                if attempt == PART_RETRIES:
                    raise RuntimeError(f"part {number} upload failed: {error}")
                time.sleep(2 ** attempt)
            write_in_terminal(f"part {number}/{len(parts)} uploaded")


def upload_to_presigned(file_path, url, headers, params):
    """Nouman: create the media file, upload the bytes to Wasabi, and complete.

    With MULTIPART_UPLOAD the create request also sends multipart=true,
    file_size and part_size. Aviary then returns multipart_upload (upload_id,
    part_size, parts_count, and one url per part) instead of presigned_url,
    and /complete is called with the upload_id so Aviary joins the parts. If
    the server returns no multipart_upload (an Aviary release without
    multipart support), the old single PUT is used. Returns the create
    response; raises if any step fails (before, failures were ignored).
    """
    content_path = os.path.abspath(file_path)
    params = dict(params)
    if MULTIPART_UPLOAD:
        params.update({'multipart': 'true', 'file_size': os.path.getsize(content_path), 'part_size': PART_SIZE})
    r = requests.post(url=url, files={"media_file": 'presigned'}, params=params, headers=headers)
    response = r.json()
    if response.get('errors') or response.get('error'):
        raise RuntimeError(f"Media create failed: {response.get('errors') or response.get('error')}")
    data = response['data']

    multipart_upload = data.get('multipart_upload')
    if multipart_upload:
        write_in_terminal(f"Uploading {os.path.basename(content_path)} in {multipart_upload['parts_count']} part(s)")
        upload_parts(content_path, multipart_upload)
        complete_params = {'upload_id': multipart_upload['upload_id'], 'parts_count': multipart_upload['parts_count']}
    else:
        # Old single PUT (max 5 GB). The file is streamed from disk, not read
        # fully into memory, and the Aviary token is not sent to Wasabi.
        with open(content_path, 'rb') as fh:
            requests.put(data['presigned_url'], data=fh).raise_for_status()
        complete_params = {}

    complete_url = f"{base_url}api/v1/media_files/{data['id']}/complete"
    complete = requests.get(complete_url, headers=headers, params=complete_params).json()
    if complete.get('errors'):
        raise RuntimeError(f"Media complete failed: {complete['errors']}")
    return r

def upload_from_id(media_staging_id, url, headers, resource_id, access, display_name, filename, sort_order, is_360):
    params = {'collection_resource_id': resource_id,
    'access': access,
    'is_360': 'false',
    'display_name': display_name,
    'filename': filename,
    'media_staging_id': media_staging_id,
    'sort_order': sort_order,
    'is_360': is_360,
    }
    r = requests.post(url=url, files=[],params=params, headers=headers)
    response = r.json()
    write_in_terminal(f"Response....{response}")
    return r

def upload_from_link(file, url, headers, resource_id, access, display_name, filename, sort_order, is_360):
    params = {'collection_resource_id': resource_id,
    'access': access,
    'is_360': 'false',
    'display_name': display_name,
    'filename': filename,
    'media_file_link': file,
    'sort_order': sort_order,
    'is_360': is_360,
    }
    files = {"media_file_link": file}
    r = requests.post(url=url, files=files,params=params, headers=headers)
    response = r.json()
    write_in_terminal(f"Response....{response}")
    return r


def upload(file, url, headers, resource_id, access, display_name, filename, sort_order, is_360):
    params = {'collection_resource_id': resource_id,
    'access': access,
    'is_360': 'false',
    'display_name': display_name,
    'filename': filename,
    'media_file': 'presigned',
    'sort_order': sort_order,
    'is_360': is_360.lower(),
    }
    # Nouman: now uses the multipart presigned upload (see upload_to_presigned).
    r = upload_to_presigned(file, url, headers, params)
    write_in_terminal(f"Response....{r}")
    return r



def deliver_to_aviary(src, resource_id, access, display_name, filename, sort_order, is_360, media_staging_id = ''):
    headers = {
        "Authorization": f"Bearer {token}",
    }
    print(f"Resource id --{resource_id}")
    url = f"{base_url}api/v1/media_files"
    if media_staging_id:
        del_response = upload_from_id(media_staging_id, url, headers, resource_id, access, display_name, filename, sort_order, is_360)
    elif validators.url(src):
        del_response = upload_from_link(src, url, headers, resource_id, access, display_name, filename, sort_order, is_360)
    else:
        del_response = upload(src, url, headers, resource_id, access, display_name, filename, sort_order, is_360)
    write_in_terminal(f"Final response... {del_response.json()}")

    return del_response


def main():
    csv_path = '/Users/weareavp/aviary-api-scripts/PythonTestingMedia.csv'
    csv_file = open(csv_path, 'rt', encoding='utf-8')
    csv_reader = csv.DictReader(csv_file)
    
    for row in csv_reader:
        resource_id = row["aviary ID"]
        src = row["Path"]
        url = row["URL"]
        sort_order = row["Sequence #"]
        is_360 = 'false'
        if row["Is 360"]:
            is_360 = row["Is 360"]

        display_name = row["Display Name"]
        filename = row["Filename"]
        access = row["Public"]
        media_staging_id = row["Media Staging ID"]
        if access == "yes":
            access = 'true'
        else:
            access = 'false'

        if resource_id.strip():
            start_time = datetime.datetime.now()
            write_in_terminal(f"Process started...{resource_id}")
            if  src.strip():
                response = deliver_to_aviary(src,resource_id,access,display_name,filename,sort_order, is_360)
            elif  url.strip():
                response = deliver_to_aviary(url,resource_id,access,display_name,filename,sort_order, is_360)
            elif media_staging_id:
                response = deliver_to_aviary('',resource_id,access,display_name,filename,sort_order, is_360, media_staging_id)

            write_in_terminal(f"Process finished...{resource_id}")
            end_time = datetime.datetime.now()
            print('Duration: {}'.format(end_time - start_time))
    csv_file.close()

if __name__ == '__main__':
    main()