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

# Files larger than MULTIPART_THRESHOLD are uploaded in PART_SIZE chunks (5 MB - 5 GB, max file 25 GB).
# Set MULTIPART_UPLOAD = False to always use a single PUT (max 5 GB).
MULTIPART_UPLOAD = True
MULTIPART_THRESHOLD = 100 * 1024 * 1024
PART_SIZE = 100 * 1024 * 1024
PART_RETRIES = 3


def put_with_retries(url, file_path, label, offset=0, length=None):
    # No Authorization header: the URL is presigned and the Aviary token must not be sent to Wasabi.
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
    part_size = int(multipart_upload['part_size'])
    parts = sorted(multipart_upload['parts'], key=lambda p: int(p['part_number']))
    for part in parts:
        number = int(part['part_number'])
        put_with_retries(part['url'], file_path, f"part {number}", (number - 1) * part_size, part_size)
        write_in_terminal(f"part {number}/{len(parts)} uploaded")


def upload_to_presigned(file_path, url, headers, params):
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
        write_in_terminal(f"Uploading {os.path.basename(content_path)} in {multipart_upload['parts_count']} part(s)")
        upload_parts(content_path, multipart_upload)
        complete_params = {'upload_id': multipart_upload['upload_id'], 'parts_count': multipart_upload['parts_count']}
    else:
        put_with_retries(data['presigned_url'], content_path, os.path.basename(content_path))
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