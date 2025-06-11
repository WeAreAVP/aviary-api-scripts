### Manually Import XMLS
dir_path = "/Users/weareavp/aviary-api-scripts/xmls"
current_folder_path = Dir.entries(dir_path)
collection_id = 74
current_organization = Organization.find_by_url('weareavp')
current_user = User.find_by_email('raza@weareavp.com')
title = "Manually Import XMLS"

def open(url, _allow_redirections = '')
    res = url =~ URI::DEFAULT_PARSER.make_regexp
    if res.nil?
        File.open(url, allow_redirections: :all, ssl_verify_mode: OpenSSL::SSL::VERIFY_NONE)

    else
        URI.open(url, allow_redirections: :all, ssl_verify_mode: OpenSSL::SSL::VERIFY_NONE)
    end
end

def create_resource_and_description(resource, import, collection_id)
    return unless resource.present?
    is_public = resource[:access]
    is_featured = resource[:is_featured]
    value_custom_unique_identifier = begin
      resource[:custom_unique_identifier] = Aviary::ResourceManager.new.clean_uri(resource[:custom_unique_identifier])
    rescue StandardError => e
      report_error(import, "<strong>failing setting up custom_unique_identifier </strong> #{e}")
      as_config.logger.fatal "failing setting up custom_unique_identifier #{e}"
      ''
    end
    custom_unique_identifier = value_custom_unique_identifier.present? ? value_custom_unique_identifier : ''
    resource_file = CollectionResourceFile.find_by(id: resource[:resource_file][:link][:media_id])
    collection_resource = Collection.find(collection_id).collection_resources.where(title: resource[:title]).try(:first)
    unless collection_resource.present?
        collection_resource = import.collection.collection_resources.create!(
            title: resource[:title], access: is_public, is_featured: is_featured,
            custom_unique_identifier: custom_unique_identifier, external_resource_id: import.id
        )
        Aviary::ResourceManager.new.manage_resource_import(collection_resource, resource[:resource_fields])
        collection_resource = CollectionResource.find(collection_resource.id)
        collection_resource.reindex_collection_resource
        collection_resource
    end
    if collection_resource.collection_resource_files.count.zero? && resource_file.present?
        base_path = Rails.root.join('public').to_s
        file_path = Aviary::FileManager.new.create_file(
            base_path,
            resource_file.resource_file.url,
            resource_file.resource_file.expiring_url
        )
        media_file = collection_resource.collection_resource_files.create(resource_file: open(file_path), sort_order: (collection_resource.collection_resource_files.count+1), is_cc_on: resource_file.is_cc_on, is_3d: resource_file.is_3d,
            embed_code: '', embed_type: '', file_display_name: resource_file.file_display_name,
            resource_file_file_name: resource_file.resource_file_file_name, resource_file_content_type: resource_file.resource_file_content_type)
        collection_resource.reindex_collection_resource
        Aviary::FileManager.new.delete_file(file_path)
        binding.pry
    end
end

import = Import.create(organization_id: current_organization.id, collection_id: collection_id,
    import_type: 1, user_id: current_user.id, title: title,
    status: Import::StatusType::IN_PROGRESS)

current_folder_path.each do |file_xml|
    if file_xml != '.' && file_xml != '..'
        file_path =  "#{dir_path}/#{file_xml}"
        import.import_files.create(associated_file: File.open(file_path), file_type: ImportFile::FileType::XML,
                                 permission_object: {}.to_json)
        break
    end
end

aviary_hash = []
import.update(errors_list: nil)
import.errors_list = ''
ohms_file = Aviary::BulkImportManager::OHMSFile.new
ohms_files = import.import_files
ohms_files.each do |file|
    file_path = "#{dir_path}/#{file.associated_file_file_name}"
    doc = Nokogiri::XML(open(file_path))
    xml_hash = Hash.from_xml(doc.to_s)
    aviary_hash = {}
    aviary_hash[:errors] ||= []
    return aviary_hash unless ohms_file.check_root_and_record(xml_hash, import)

    

    record = xml_hash['ROOT']['record']
    aviary_hash[:title] = record['title']
    aviary_hash[:access] = ohms_file.file_access(file)

    ohms_file.check_title_and_access(aviary_hash, import)

    aviary_hash[:is_featured] = false
    aviary_hash[:resource_fields] = ohms_file.add_singular_fields(ohms_file.add_array_fields(record, import), record, import)

    xml_file = record['mediafile']
    if %w[other vimeo soundcloud youtube avalon aviary kaltura].include?(xml_file['host']&.downcase)
        aviary_hash = ohms_file.embed_code_mapping(aviary_hash, record, xml_file, import, file)
    end
    aviary_hash.delete(:errors)
    aviary_hash[:collection_resource_id] = ""
    aviary_hash[:resource_file][:link][:value] =  record['media_url']
    aviary_hash[:resource_file][:link][:media_id] =  429 #record['media_url'].split('/').last
    resources = [aviary_hash]

    resource_limit_flag = false
    resources.each_with_index do |resource, _index|
        if import.organization.resource_count >= import.organization.subscription.plan.max_resources
            report_error(import, '<strong>Resource cannot be synced. Organization resource limit reached. </strong> ' \
                                "could not sync resource #{resource[:title]}")

            resource_limit_flag = true
            next
        end
        collection_resource = create_resource_and_description(resource, import, collection_id)
    
    
    
        begin
            Aviary::ResourceManager.new.sync_single_resource_file(resource, import, collection_resource, true)
        rescue StandardError => e

            Rails.logger.error e
        end
    end

    import.save if import.errors_list.present? && resource_limit_flag

end 
