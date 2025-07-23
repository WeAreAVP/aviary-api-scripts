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

base_url = 'https://weareavp.aviaryplatform.com/'
token = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'

def write_in_terminal(message):
    print(asctime() + ":Log - " + message)

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
    files = {"media_file": 'presigned'}
    r = requests.post(url=url, files=files,params=params, headers=headers)
    response = r.json()
    presigned_url = response['data']['presigned_url']
    content_path = os.path.abspath(file)

    with open(content_path, 'rb') as file:
        file_data = file.read()
    headers['Content-Type'] = 'text/plain'
    response_presigned = requests.put(presigned_url, headers=headers, data=file_data)
    complete_url = f"{base_url}api/v1/media_files/{response['data']['id']}/complete"

    response_complete = requests.get(complete_url, headers=headers, data={})
    write_in_terminal(f"Response....{r}")
    return r



def deliver_to_aviary(src, resource_id, access, display_name, filename, sort_order, is_360):

    headers = {
        "Authorization": f"Bearer {token}",
    }
    print(f"Resource id --{resource_id}")
    url = f"{base_url}api/v1/media_files"
    if validators.url(src):
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

            write_in_terminal(f"Process finished...{resource_id}")
            end_time = datetime.datetime.now()
            print('Duration: {}'.format(end_time - start_time))
    csv_file.close()

if __name__ == '__main__':
    main()