######################################
# Steps to Run the Script
# 1 - Update base_url to your organization url in line # 23
# 2 - Update token to your user token in line # 24
# 3 - Update collection_id for which you want to create a resources in line # 25
# 4 - Update folder_path of file which you have this file a in line # 26
# 5 - Update csv_path for each CSV file according to each file's location from  line # 27 to line # 31
import datetime
import requests
import os
import csv
import validators
import mimetypes
import threading
import math
import pdb
import urllib
import re
import time  # Add this import at the top of the file
import ipdb
from urllib.parse import urlparse  # Import urlparse

base_url = 'https://weareavp.aviaryplatform.com/'
token = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
collection_id = 39
folder_path = "/Users/weareavp/aviary-api-scripts/media_files_api_token/"
resource_csv_path = folder_path+'aviary-sample-bulk-import-package/Aviary-resource-csv-template.csv'
media_csv_path = folder_path+'aviary-sample-bulk-import-package/Aviary-media-csv-template.csv'
index_csv_path = folder_path+'aviary-sample-bulk-import-package/Aviary-index-csv-template.csv'
transcript_csv_path = folder_path+'aviary-sample-bulk-import-package/Aviary-transcript-csv-template.csv'
supplemental_csv_path = folder_path+'aviary-sample-bulk-import-package/Aviary-supplemental-csv-template.csv'

def process_resource(resource, keys, septater=";;", pair_separator= "|", system_name = 0):
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

def process_location(location_text):
    """
    Process location field with geolocation format.
    Format: GPS_COORDS::ZOOM::DESCRIPTION
    Multiple locations separated by |
    Example: 39.0119,-95.6789::15::Kansas Location|37.7749,-122.4194::13::San Francisco
    """
    if not location_text or location_text.strip() == '':
        return []
    
    locations = []
    location_pairs = location_text.split('|')
    
    for location_pair in location_pairs:
        parts = location_pair.split('::')
        if len(parts) >= 1:
            gps = parts[0].strip()
            zoom = parts[1].strip() if len(parts) > 1 else '17'
            description = parts[2].strip() if len(parts) > 2 else 'GPS Location'
            
            locations.append({
                'vocabulary': '',
                'value': {
                    'gps': gps,
                    'zoom': zoom,
                    'description': description
                }
            })
    
    return locations

def create_resources():
    with open(resource_csv_path, 'rt', encoding='utf-8-sig', errors='ignore') as resource_csv_file:
        resource_csv_reader = csv.DictReader(resource_csv_file)
        
        url = base_url+"api/v1/resources"
        headers = {
            "Authorization": f"Bearer {token}",
        }
        for resource in resource_csv_reader:
            
            if resource["Resource User Key"] != "":
                print(f"Resource {resource["Resource User Key"]} Started")
                data = {
                    "resource_user_key": resource["Resource User Key"],
                    "collection_id": collection_id,
                    "title": resource["Title"],
                    "access": "public" if resource["Public"] == "yes" else "restricted" if resource["Public"] == "no" else "private",
                    "is_featured": "true" if resource["Featured"] == "yes" else "false",
                    # "custom_unique_identifier": resource["Custom Unique Identifier"]
                }
                data["metadata"] = {}
                data["metadata"] = data["metadata"]|process_resource(resource,['Description','Date','Agent','Coverage','Language','Identifier','Format','Type','Subject','Relation','Source','Publisher','Rights Statement','Keyword','Source Metadata URI'])
                data["metadata"] = data["metadata"]|process_resource(resource,['Preferred Citation'],',')
                
                # Process Location field with geolocation format
                if resource.get("Location") and resource["Location"].strip():
                    data["metadata"]["Location"] = process_location(resource["Location"])
                
                response = requests.post(url, headers=headers, json=data)
                info = response.json()
                if "error" in info:
                    print('error',info["error"])
                else:
                    create_media(info["data"]["update"]["id"],resource["Resource User Key"])
                print(f"Resource {resource["Resource User Key"]} Ended")
                print(f"==============================================")
                print(f"")
    resource_csv_file.close()

def upload_from_path(file, url, headers, resource_id, access, display_name, filename, sort_order, is_360, thumbnail_path):
    
    params = {'collection_resource_id': resource_id,
    'access': access,
    'is_360': is_360,
    'media_file': 'presigned',
    'display_name': display_name if display_name else filename,
    "thumbnail_path": thumbnail_path,
    'filename': filename,
    'sort_order': sort_order,
    }
    files = {"media_file": 'presigned'}
    r = requests.post(url=url, files=files,params=params, headers=headers)
    response = r.json()
    presigned_url = response['data']['presigned_url']
    content_path = os.path.abspath(file)
    with open(content_path, 'rb') as file:
        file_data = file.read()
    headers['Content-Type'] = 'text/plain'
    requests.put(presigned_url, headers=headers, data=file_data)
    complete_url = f"{base_url}api/v1/media_files/{response['data']['id']}/complete"

    requests.get(complete_url, headers=headers, data={})
    return r.json()

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
    return r.json()
def upload_from_link(file, url, headers, resource_id, access, display_name, filename, sort_order, is_360, thumbnail_path, metadata):
    params = {'collection_resource_id': resource_id,
    'access': access,
    'is_360': is_360,
    'display_name': display_name if display_name else filename,
    'filename': filename,
    'sort_order': sort_order,
    "thumbnail_path": thumbnail_path,
    "media_file_link": file,
    "metadata": metadata,
    "media_file": {}
    }
    files = {}
    r = requests.post(url=url, files=files,json=params, headers=headers)
    return r.json()

def upload_from_embed(file, url, headers, resource_id, access, display_name, sort_order, is_360, source, target_domain, thumbnail_path, metadata):
    params = {'collection_resource_id': resource_id,
    'access': access,
    'is_360': is_360,
    'display_name': display_name if display_name else f"{source} Embed",
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
    data= {}
    data["metadata"] = metadata
    data["media_file"] = {}

    files=[

    ]
    headers = {
        "Authorization": f"Bearer {token}",
    }

    response = requests.request("PUT", url, headers=headers, json=data, files=files)
    return response.json()

def create_media(resource_id,resource_user_key):
    with open(media_csv_path, 'rt', encoding='utf-8-sig', errors='ignore') as media_csv_file:
        # Use DictReader to read the CSV content
        media_csv_reader = csv.DictReader(media_csv_file)

        url = base_url+"api/v1/media_files"
        headers = {
            "Authorization": f"Bearer {token}",
        }

        # Process each row
        for media in media_csv_reader:
            # Optionally clean values
            media = {k.strip(): v.strip() for k, v in media.items()}
            if media["Resource User Key"] == resource_user_key:
                print(f"Media {resource_user_key} Started")
                metadata = process_resource(media,['Publisher','Source','Coverage','Language','Format','Identifier','Relation','Subject','Rights','Description','Date','Type'], ";;", "|", 1)
                access = "true" if media["Public"] == "yes" else "false"
                sort_order = media["Sequence #"]
                is_3d  = 'false' if media["360 Video"] == "no" else 'true'
                thumbnail_path = folder_path+media["Embed Source"]
                media_staging_id = media["Media Staging ID"]
                # Get display name from CSV or use filename as fallback
                display_name = media.get("Display Name", "").strip()
                if media_staging_id:
                    media_response = upload_from_id(media_staging_id, url, headers, resource_id, access, display_name, '', sort_order, is_3d)
                elif validators.url(media["URL"]):
                    filename = os.path.basename(urlparse(media["URL"]).path)
                    if not display_name:
                        display_name = filename
                    media_response = upload_from_link(media["URL"], url, headers, resource_id, access, display_name, filename, sort_order, is_3d, thumbnail_path, metadata)
                elif media["Embed Code"]:
                    if media["Embed Code"].startswith('<iframe'):
                        url_match = re.search(r'src="([^"]+)"', media["Embed Code"])
                        if url_match:
                            media["URL"] = url_match.group(1)
                    else:
                        media["URL"] = media["Embed Code"]
                    media_response = upload_from_embed(media["Embed Code"], url, headers, resource_id, access, display_name, sort_order, is_3d, media["Embed Source"].title(), media["Target Domain"], thumbnail_path, metadata)
                else:
                    src = folder_path+media["Path"]
                    filename = os.path.basename(src)
                    if not display_name:
                        display_name = filename
                    media_response = upload_from_path(src, url, headers, resource_id, access, display_name, filename, sort_order, is_3d, thumbnail_path)
                    print(f"Media Metadata {resource_user_key} Started")
                    metadata_url = f"{url}/{media_response['data']['id']}"
                    media_meta_data_update(metadata_url, headers, metadata, media_response['data'])
                print(f"Index {resource_user_key} Started")
                create_index(resource_id,media_response["data"]["id"],media["Media User Key"])
                print(f"Transcript {resource_user_key} Started")
                create_transcript(resource_id, media_response["data"]["id"],media["Media User Key"])
                print(f"Supplemental {resource_user_key} Started")
                create_supplemental(resource_id, media_response["data"]["id"],resource_user_key)

def create_index(resource_id, media_id, media_user_key):
    with open(index_csv_path, 'rt', encoding='utf-8-sig', errors='ignore') as index_csv_file:
        # Use DictReader to read the CSV content
        index_csv_reader = csv.DictReader(index_csv_file)

        url = base_url+"api/v1/indexes"
        headers = {
            "Authorization": f"Bearer {token}",
        }

        # Process each row
        for index in index_csv_reader:
            # Optionally clean values
            index = {k.strip(): v.strip() for k, v in index.items()}
            if index["Media User Key"] == media_user_key:
                data = {
                    'language': index["Language"],
                    'title': index["Tile"],
                    'is_public': "true" if index["Public"] == "yes" else "false",
                    'resource_file_id': media_id,
                    'description': index["Description"]
                }
                file_path = folder_path + index["Path"]
                file_name = os.path.basename(file_path)
                file_type = mimetypes.guess_type(file_path)[0]
                
                files = {
                    'associated_file': (file_name,open(file_path,'rb'),file_type)
                }
                requests.post(url, headers=headers, data=data, files=files)


def create_transcript(resource_id, media_id, media_user_key):
    with open(transcript_csv_path, 'rt', encoding='utf-8-sig', errors='ignore') as transcript_csv_file:
        # Use DictReader to read the CSV content
        transcript_csv_reader = csv.DictReader(transcript_csv_file)

        url = base_url+"api/v1/transcripts"
        headers = {
            "Authorization": f"Bearer {token}",
        }

        # Process each row
        for transcript in transcript_csv_reader:
            # Optionally clean values
            transcript = {k.strip(): v.strip() for k, v in transcript.items()}
            if transcript["Media User Key"] == media_user_key:
                data = {
                    'language': transcript["Language"],
                    'title': transcript["Tile"],
                    'is_public': "true" if transcript["Public"] == "yes" else "false",
                    'resource_file_id': media_id,
                    'description': transcript["Description"],
                    'is_caption':  transcript["Captions"],
                    'remove_title': '1' if transcript["Ignore Title"] == "yes" else "0",
                }
                file_path = folder_path + transcript["Path"]
                file_name = os.path.basename(file_path)
                file_type = mimetypes.guess_type(file_path)[0]
                files = {
                    'associated_file': (file_name,open(file_path,'rb'),file_type)
                }
                response = requests.post(url, headers=headers, data=data, files=files)


def create_supplemental(resource_id, media_id, resource_user_key):
    with open(supplemental_csv_path, 'rt', encoding='utf-8-sig', errors='ignore') as supplemental_csv_file:
        # Use DictReader to read the CSV content
        supplemental_csv_reader = csv.DictReader(supplemental_csv_file)

        url = base_url+"api/v1/supplemental_files"
        headers = {
            "Authorization": f"Bearer {token}",
        }

        # Process each row
        for supplemental in supplemental_csv_reader:
            # Optionally clean values
            supplemental = {k.strip(): v.strip() for k, v in supplemental.items()}
            if supplemental["Resource User Key"] == resource_user_key:
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
                    'associated_file': (file_name,open(file_path,'rb'),file_type)
                }
                requests.post(url, headers=headers, data=data, files=files)


def main():
    create_resources()

if __name__ == '__main__':
    main()
