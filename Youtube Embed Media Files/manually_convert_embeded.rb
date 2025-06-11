### Manually convert the Embeded Records to Aviary Resources Media File
require 'csv'    
file_path = '/Users/weareavp/aviary-api-scripts/YoutubeEmbedMediaFiles.csv'
csv_text = File.read(file_path)
csv = CSV.parse(csv_text, :headers => true)

bucket_name = 'aviaryplatform-local'
csv.each do |row|
    collection_resource_file = CollectionResourceFile.find_by(id: row[0].to_i)
    if collection_resource_file.present?
        resource = collection_resource_file.collection_resource
        file_name = row[1]
        file_name = collection_resource_file.id.to_s + '_' + file_name.gsub(/[^A-Za-z0-9 ]+/, '').strip.downcase.tr(' ', '_').delete('.')
        object_path = "embeded_files/"+file_name
        puts object_path
        expiry = 3600
        s3 = Aws::S3::Client.new(
            access_key_id: 'xxxxxxxxxxxxxxxxxxxxxxxx',
            secret_access_key: 'xxxxxxxxxxxxxxxxxxxxxxxxxxxx',
            region: 'xx-xxxx-x'
        )
        s3.head_object(bucket: bucket_name, key: object_path+'.mp4')

        url = Aws::S3::Object.new(key: object_path+'.mp4', bucket_name: bucket_name, client: s3)
                .presigned_url(:get, expires_in: expiry.ceil, response_content_disposition: 'attachment;',
                                        response_content_type: 'mp4')
        media = collection_resource_file
        media.update(resource_file: URI.open(url),embed_code: '', embed_type: '')
        puts row[0]+" completed"
    end
end
 