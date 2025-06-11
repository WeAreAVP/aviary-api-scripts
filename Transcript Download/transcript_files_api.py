######################################
# Steps to Run the Script
# 1 - Update base_url to your organization url in line # 15
# 3 - Update token for your api token in line # 16
# 4 - Update dir_path of file which you want to upload a transcript file in line # 17
# 5 - Update name of csv file which you want to upload a in line # 62

import datetime
from time import asctime
import os
import csv
import requests
import json

base_url = 'https://weareavp.aviaryplatform/'
token = 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
dir_path = '/Users/weareavp/aviary-api-scripts'

def create_folder_and_file(folder_path, file_path, content):

    try:
        # Create the folder if it doesn't exist
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            print(f"Folder created: {folder_path}")

        # Create or overwrite the file
        with open(file_path, 'w') as file:
            file.write(content)
        print(f"File created/overwritten: {file_path}")

    except Exception as e:
        print(f"An error occurred: {e}")

def deliver_to_aviary(resource_id):

    headers = {
        'Authorization': f'Bearer {token}'
    }
    print(f"Resource id --{resource_id}")
    url = f"{base_url}api/v1/resources/{resource_id}"
    r = requests.get(url=url, headers=headers)
    if r.status_code == 200:
        response = r.json()
        for transcripts_id in response["data"]["transcripts_id"]:
            url = f"{base_url}api/v1/transcripts/{transcripts_id}"
            t = requests.get(url=url, headers=headers)
            if t.status_code == 200:
                transcript = t.json()
                for format in transcript["data"]["export"]:
                    folder_path = dir_path+'/'+resource_id+'/'+str(transcript["data"]["id"])+'/'+format
                    file_path = os.path.join(folder_path, transcript["data"]["export"][format]["file_name"])
                    f = requests.get(url=transcript["data"]["export"][format]["file"], headers=headers)
                    if f.status_code == 200:
                        content = f.text
                        create_folder_and_file(folder_path, file_path, content)

    return response


def main():
    csv_path = dir_path+'/PythonTestingTranscript.csv'
    csv_file = open(csv_path, 'rt', encoding='utf-8')
    csv_reader = csv.DictReader(csv_file)
    
    for row in csv_reader:
        resource_id = row["Resources ID"]
        if resource_id.strip():
            deliver_to_aviary(resource_id)
    csv_file.close()

if __name__ == '__main__':
    main()